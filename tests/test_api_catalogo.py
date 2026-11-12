"""Testes do catálogo em memória da API (api_supabase.py), sem rede e sem banco.

Rodar com:  python tests/test_api_catalogo.py   (precisa de fastapi, uvicorn, supabase e thefuzz, do requirements.txt)
"""
import contextlib
import io
import os
import re
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("SUPABASE_KEY", "chave-falsa-so-para-importar")      # a API cria o cliente ao importar
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api_supabase as api  # noqa: E402


class Resposta:
    def __init__(self, data):
        self.data = data


class ConsultaFalsa:
    def __init__(self, linhas, chamadas):
        self.linhas, self.chamadas, self.inicio, self.fim = linhas, chamadas, 0, 999

    def select(self, colunas):
        self.chamadas.append(("select", colunas))
        return self

    def in_(self, coluna, valores):
        self.chamadas.append(("in", coluna, tuple(valores)))
        return self

    def order(self, coluna):
        return self

    def range(self, inicio, fim):
        self.inicio, self.fim = inicio, fim
        self.chamadas.append(("range", inicio, fim))
        return self

    def execute(self):
        return Resposta(self.linhas[self.inicio:self.fim + 1])


class BancoFalso:
    def __init__(self, n):
        self.linhas = [{"id": i, "nome": f"Produto {i}", "supermercado": "Apoio Entrega", "termo": "arroz"} for i in range(n)]
        self.chamadas = []

    def table(self, nome):
        assert nome == "produtos"
        return ConsultaFalsa(self.linhas, self.chamadas)


VALIDADE_PADRAO = api.CATALOGO_VALIDADE_SEGUNDOS


def limpar():
    api._catalogos.clear()
    api._travas.clear()
    api.CATALOGO_VALIDADE_SEGUNDOS = VALIDADE_PADRAO


class Contador:
    """Troca baixar_catalogo por uma versão que conta as chamadas e devolve 'versão N'."""

    def __init__(self, espera=None, falha_a_partir=None):
        self.chamadas, self.espera, self.falha_a_partir, self.trava = 0, espera, falha_a_partir, threading.Lock()

    def __call__(self, uf):
        with self.trava:
            self.chamadas += 1
            numero = self.chamadas
        if self.espera is not None and numero > 1:
            self.espera.wait(5)                                  # a 1ª carga é imediata; as seguintes esperam o teste soltar
        if self.falha_a_partir and numero >= self.falha_a_partir:
            raise RuntimeError("banco fora do ar")
        return f"versão {numero}"


def esperar(condicao, segundos=3):
    limite = time.time() + segundos
    while time.time() < limite:
        if condicao():
            return True
        time.sleep(0.01)
    return False


# ============================== o download ==============================

def teste_baixar_catalogo_pagina_e_pede_so_as_colunas_usadas():
    anterior = api.supabase
    api.supabase = BancoFalso(2300)
    try:
        catalogo = api.baixar_catalogo("MG")
        chamadas = api.supabase.chamadas
    finally:
        api.supabase = anterior
    assert len(catalogo) == 2300
    assert [c[1:] for c in chamadas if c[0] == "range"] == [(0, 999), (1000, 1999), (2000, 2999)]      # lê tudo, 1000 por vez
    assert {c[1] for c in chamadas if c[0] == "select"} == {api.COLUNAS_DO_CATALOGO}
    assert "texto_original" not in api.COLUNAS_DO_CATALOGO
    for coluna in ("id", "supermercado", "nome", "preco_varejo", "preco_atacado", "quantidade_atacado", "atualizado_em", "ean", "termo"):
        assert coluna in api.COLUNAS_DO_CATALOGO.split(","), coluna                                    # o site e a busca precisam delas
    assert ("in", "uf_cobertura", ("MG", "BR")) in chamadas


def capturar(funcao):
    """O que `funcao` imprime no log (inclusive de threads em segundo plano que terminarem antes de ela devolver)."""
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        funcao()
    return saida.getvalue()


def teste_log_diz_o_motivo_e_a_duracao_de_cada_carga():
    def devagar(uf):
        time.sleep(0.4)
        return "x" * 8244
    api.baixar_catalogo = devagar
    try:
        limpar()
        log = capturar(lambda: api.carregar_catalogo("MG"))
        assert re.search(r"Catálogo de MG\+BR carregado do banco em 0\.[4-5] s: 8244 produtos", log), log                  # mede o download
        assert "primeira busca, sem catálogo na memória" in log, log

        api.CATALOGO_VALIDADE_SEGUNDOS = 0.05
        time.sleep(0.1)
        log = capturar(lambda: (api.carregar_catalogo("MG"), time.sleep(0.7)))                                           # vencido: a carga roda por trás
        assert "busca com catálogo vencido; o catálogo anterior tinha 0 min" in log, log                                  # diz de quem e a idade do anterior
        assert re.search(r"carregado do banco em 0\.[4-5] s", log), log
    finally:
        limpar()


def teste_log_diz_quem_acordou_o_catalogo_e_se_a_carga_falhou():
    contador = Contador()
    api.baixar_catalogo = contador
    try:
        limpar()
        log = capturar(lambda: (api.saude(), esperar(lambda: "MG" in api._catalogos)))
        assert "chamada a /saude, sem catálogo na memória" in log, log

        limpar()
        log = capturar(lambda: (api.aquecer_catalogo("MG", contexto="servidor iniciando"), esperar(lambda: "MG" in api._catalogos)))
        assert "servidor iniciando, sem catálogo na memória" in log, log

        limpar()
        api.baixar_catalogo = Contador(falha_a_partir=1)
        log = capturar(lambda: (api.aquecer_catalogo("MG"), time.sleep(0.3)))
        assert "a carga falhou após" in log and "banco fora do ar" in log and "aquecimento, sem catálogo na memória" in log, log     # a causa e o motivo no log
        assert "Sigo com o catálogo anterior de MG" in log, log
        assert not api._trava_da_uf("MG").locked() and "MG" not in api._catalogos
    finally:
        limpar()


def teste_baixar_catalogo_calcula_a_chave_de_equivalencia_de_cada_produto():
    banco = BancoFalso(0)
    banco.linhas = [
        {"id": 1, "nome": "Leite UHT Integral Itambé Caixa com Tampa 1l", "supermercado": "Supernosso", "termo": "leite"},
        {"id": 2, "nome": "Leite Longa Vida Porto Alegre Integral 1L", "supermercado": "Super ABC", "termo": "leite"},
        {"id": 3, "nome": "Leite UHT Desnatado Itambé Caixa com Tampa 1l", "supermercado": "Supernosso", "termo": "leite"},
        {"id": 4, "nome": "Sabonete Dove Original 90g", "supermercado": "Supernosso", "termo": "sabonete"},
    ]
    anterior = api.supabase
    api.supabase = banco
    try:
        catalogo = api.baixar_catalogo("MG")
    finally:
        api.supabase = anterior
    por_id = {e.produto["id"]: e.produto for e in catalogo}
    assert por_id[1]["chave_equivalencia"] == por_id[2]["chave_equivalencia"]                          # marcas e embalagens diferentes, mesmo produto
    assert por_id[1]["chave_equivalencia"] != por_id[3]["chave_equivalencia"]                          # integral não é desnatado
    assert por_id[1]["rotulo_equivalencia"] == "Leite integral, 1 L"
    assert "chave_equivalencia" not in por_id[4] and "rotulo_equivalencia" not in por_id[4]            # fora de qualquer família: sem chave


# ============================== o cache ==============================

def teste_primeira_busca_baixa_e_as_seguintes_usam_o_cache():
    contador = Contador()
    api.baixar_catalogo = contador
    try:
        limpar()
        assert api.carregar_catalogo("MG") == "versão 1" and api.carregar_catalogo("MG") == "versão 1"
        assert contador.chamadas == 1
        assert api.carregar_catalogo("BR") == "versão 2"                                               # cada UF tem o seu
    finally:
        limpar()


def teste_catalogo_vencido_responde_na_hora_e_atualiza_em_segundo_plano():
    solta = threading.Event()
    contador = Contador(espera=solta)
    api.baixar_catalogo = contador
    try:
        limpar()
        api.CATALOGO_VALIDADE_SEGUNDOS = 0.05
        assert api.carregar_catalogo("MG") == "versão 1"
        time.sleep(0.1)                                                                                # venceu
        inicio = time.time()
        assert api.carregar_catalogo("MG") == "versão 1"                                               # responde com o antigo, sem esperar a recarga
        assert time.time() - inicio < 0.5
        assert esperar(lambda: contador.chamadas == 2)                                                 # a atualização começou por trás...
        assert api.carregar_catalogo("MG") == "versão 1"                                               # ...e ainda não terminou
        solta.set()
        assert esperar(lambda: api._catalogos["MG"][1] == "versão 2")                                  # terminou: a próxima busca já vê o novo
        api.CATALOGO_VALIDADE_SEGUNDOS = VALIDADE_PADRAO
        assert api.carregar_catalogo("MG") == "versão 2" and contador.chamadas == 2
    finally:
        solta.set()
        limpar()


def teste_varias_buscas_ao_mesmo_tempo_baixam_uma_vez_so():
    contador = Contador()

    def lento(uf):
        time.sleep(0.2)
        return contador(uf)

    api.baixar_catalogo = lento
    try:
        limpar()
        resultados = []
        linhas = [threading.Thread(target=lambda: resultados.append(api.carregar_catalogo("MG"))) for _ in range(8)]
        for t in linhas:
            t.start()
        for t in linhas:
            t.join()
        assert contador.chamadas == 1 and resultados == ["versão 1"] * 8
    finally:
        limpar()


def teste_vencido_com_varias_buscas_dispara_uma_atualizacao_so():
    solta = threading.Event()
    contador = Contador(espera=solta)
    api.baixar_catalogo = contador
    try:
        limpar()
        api.CATALOGO_VALIDADE_SEGUNDOS = 0.05
        api.carregar_catalogo("MG")
        time.sleep(0.1)
        for _ in range(20):
            api.carregar_catalogo("MG")
        assert esperar(lambda: contador.chamadas == 2)
        time.sleep(0.1)
        assert contador.chamadas == 2                                                                  # 20 buscas, 1 atualização
    finally:
        solta.set()
        limpar()


def teste_falha_na_atualizacao_mantem_o_catalogo_anterior():
    contador = Contador(falha_a_partir=2)
    api.baixar_catalogo = contador
    try:
        limpar()
        api.CATALOGO_VALIDADE_SEGUNDOS = 0.05
        assert api.carregar_catalogo("MG") == "versão 1"
        time.sleep(0.1)
        assert api.carregar_catalogo("MG") == "versão 1"                                               # a atualização por trás vai falhar
        assert esperar(lambda: contador.chamadas >= 2)
        time.sleep(0.1)
        assert api.carregar_catalogo("MG") == "versão 1"                                               # segue com o anterior, sem erro para a pessoa
        assert not api._trava_da_uf("MG").locked()                                                     # e a trava foi liberada para tentar de novo
    finally:
        limpar()


def teste_primeira_carga_com_falha_levanta_erro():
    api.baixar_catalogo = Contador(falha_a_partir=1)
    try:
        limpar()
        try:
            api.carregar_catalogo("MG")
        except RuntimeError:
            assert not api._trava_da_uf("MG").locked() and "MG" not in api._catalogos
            return
        raise AssertionError("sem catálogo nenhum, a falha tem de aparecer")
    finally:
        limpar()


# ============================== a resposta de /comparar ==============================

def teste_resposta_traz_os_campos_dos_ocultos_e_aceita_todos():
    import busca
    produtos = [{"id": i, "nome": f"Arroz Marca {i}", "termo": "arroz", "supermercado": "Apoio Entrega", "preco_varejo": 5.0 + i, "ean": f"789000000000{i}"} for i in range(3)]
    produtos += [{"id": 9, "nome": "Condicionador com Arroz Preto", "termo": "condicionador", "supermercado": "Supernosso", "preco_varejo": 20.0, "ean": "7891"}]
    anteriores = (api.carregar_catalogo, api.obter_uf_pelo_cep)
    api.carregar_catalogo = lambda uf: busca.indexar(produtos)
    api.obter_uf_pelo_cep = lambda cep: "MG"
    try:
        r = api.buscar_e_comparar(cep="32607600", item="arroz")
        assert r["ocultos"] == 1 and r["ocultos_so_citam"] == 1 and r["ocultos_pelo_limite"] == 0
        assert r["so_citam_por_mercado"] == {"Supernosso": 1} and len(r["carrinho_comparativo"]) == 3
        t = api.buscar_e_comparar(cep="32607600", item="arroz", todos=True)
        assert t["ocultos"] == 0 and t["ocultos_so_citam"] == 0 and t["so_citam_por_mercado"] == {"Supernosso": 1}
        opcoes = [o for g in t["carrinho_comparativo"] for o in g["opcoes_de_compra"]]
        assert len(opcoes) == 4 and [o.get("so_cita") for o in opcoes].count(True) == 1     # o site sabe quais opções só citam
    finally:
        api.carregar_catalogo, api.obter_uf_pelo_cep = anteriores


def teste_resposta_leva_as_chaves_de_equivalencia_e_as_familias():
    import busca
    from equivalencia import com_equivalencia
    produtos = com_equivalencia([
        {"id": 1, "nome": "Sal Refinado Cisne Tradicional Pacote 1 Kg", "termo": "sal", "supermercado": "Apoio Entrega", "preco_varejo": 3.0},
        {"id": 2, "nome": "Sal Refinado Globo Tradicional 1kg", "termo": "sal", "supermercado": "Atacadão", "preco_varejo": 2.5},
        {"id": 3, "nome": "Sal Grosso Cisne 1kg", "termo": "sal", "supermercado": "Atacadão", "preco_varejo": 2.9},
    ])
    anteriores = (api.carregar_catalogo, api.obter_uf_pelo_cep)
    api.carregar_catalogo = lambda uf: busca.indexar(produtos)
    api.obter_uf_pelo_cep = lambda cep: "MG"
    try:
        r = api.buscar_e_comparar(cep="32607600", item="sal")
        assert "sal" in r["equivalencia_familias"] and "arroz" in r["equivalencia_familias"]            # o site lista as famílias na mensagem
        assert len(r["equivalencia_familias"]) == len(set(r["equivalencia_familias"]))
        opcoes = {o["id"]: o for g in r["carrinho_comparativo"] for o in g["opcoes_de_compra"]}
        assert opcoes[1]["chave_equivalencia"] == opcoes[2]["chave_equivalencia"] != opcoes[3]["chave_equivalencia"]
        assert opcoes[1]["rotulo_equivalencia"].startswith("Sal")
    finally:
        api.carregar_catalogo, api.obter_uf_pelo_cep = anteriores


# ============================== aquecimento ==============================

def teste_aquecer_catalogo_carrega_por_tras_e_so_quando_precisa():
    contador = Contador()
    api.baixar_catalogo = contador
    try:
        limpar()
        api.aquecer_catalogo("MG")
        assert esperar(lambda: "MG" in api._catalogos) and contador.chamadas == 1
        api.aquecer_catalogo("MG")                                                                     # já está fresco: nada a fazer
        time.sleep(0.1)
        assert contador.chamadas == 1
        assert api.saude() == {"status": "ok"}                                                         # /saude responde na hora e não baixa de novo
        time.sleep(0.1)
        assert contador.chamadas == 1
    finally:
        limpar()


def teste_saude_de_5_em_5_minutos_nao_recarrega_o_catalogo():
    """Um monitor externo chama /saude para o Render não dormir. Isso não pode baixar o catálogo do Supabase a cada vencimento."""
    contador = Contador()
    api.baixar_catalogo = contador
    try:
        limpar()
        api.CATALOGO_VALIDADE_SEGUNDOS = 0.05
        assert api.carregar_catalogo("MG") == "versão 1"
        time.sleep(0.1)                                                                                # o catálogo venceu
        for _ in range(20):
            assert api.saude() == {"status": "ok"}
        time.sleep(0.2)
        assert contador.chamadas == 1                                                                  # 20 chamadas de /saude, nenhum download
        api.carregar_catalogo("MG")                                                                    # uma busca de verdade é quem recarrega o vencido
        assert esperar(lambda: contador.chamadas == 2)
    finally:
        limpar()


def teste_saude_aceita_get_e_head_e_o_catalogo_vale_pelo_menos_1_hora():
    rota = next(r for r in api.app.routes if getattr(r, "path", None) == "/saude")
    assert {"GET", "HEAD"} <= set(rota.methods)                                                        # monitores gratuitos costumam mandar HEAD
    assert VALIDADE_PADRAO >= 3600                                                                     # 3,5 MB por recarga: a cota do Supabase não aguenta menos


def teste_saude_sem_catalogo_acorda_o_carregamento_sem_esperar():
    solta = threading.Event()

    def lento(uf):
        solta.wait(5)
        return "versão 1"

    api.baixar_catalogo = lento
    try:
        limpar()
        inicio = time.time()
        assert api.saude() == {"status": "ok"}
        assert time.time() - inicio < 0.5                                                              # não espera o download
        solta.set()
        assert esperar(lambda: "MG" in api._catalogos)
    finally:
        solta.set()
        limpar()


def teste_o_servidor_aquece_o_catalogo_ao_iniciar():
    import asyncio
    contador = Contador()
    api.baixar_catalogo = contador
    assert api.app.router.lifespan_context is not None
    try:
        limpar()

        async def iniciar():
            async with api.app.router.lifespan_context(api.app):                                       # é o que o servidor faz ao ligar
                assert await asyncio.get_running_loop().run_in_executor(None, esperar, lambda: "MG" in api._catalogos)

        asyncio.run(iniciar())
        assert contador.chamadas == 1
    finally:
        limpar()


if __name__ == "__main__":
    original = api.baixar_catalogo
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        api.baixar_catalogo = original
        t()
    api.baixar_catalogo = original
    print(f"ok: {len(testes)} testes passaram")
