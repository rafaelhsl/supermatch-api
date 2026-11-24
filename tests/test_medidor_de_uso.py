"""Testes da medição de uso SEM rastrear (medidor_de_uso.py, os pontos de contagem de api_supabase.py e docs/sql/uso_do_site.sql),
sem rede e sem banco. O que mais importa aqui: a contagem nunca atrasa nem derruba uma busca, e nada de pessoal passa por ela.

Rodar com:  python tests/test_medidor_de_uso.py   (precisa de fastapi, uvicorn, supabase e thefuzz, do requirements.txt)
"""
import contextlib
import io
import json
import os
import re
import sys
import threading
import time
import warnings
from collections import Counter
from pathlib import Path

os.environ.setdefault("SUPABASE_KEY", "chave-falsa-so-para-importar")      # a API cria o cliente ao importar
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sem_rede  # noqa: E402,F401  (tests/sem_rede.py: qualquer chamada de rede de verdade falha na hora)
import api_supabase as api  # noqa: E402
import busca  # noqa: E402
import medidor_de_uso as mu  # noqa: E402
import serie_de_precos as sp  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from sql_util import comandos, corpo, normalizado  # noqa: E402  (tests/sql_util.py)
from test_serie_de_precos import BancoDeSeries  # noqa: E402


class Gravador:
    """O `enviar` do medidor nos testes: guarda o que chegou (e pode falhar, demorar ou ficar travado de propósito).
    `chamadas` = os pedidos como chegaram [(evento, quantidade)]; `recebidos` = os eventos um a um (cada pedido vale `quantidade` ocorrências)."""

    def __init__(self, falhas=0, demora=0.0, travar=None, entrou=None):
        self.chamadas, self.recebidos, self.falhas, self.demora, self.travar, self.entrou = [], [], falhas, demora, travar, entrou
        self.trava = threading.Lock()

    def __call__(self, evento, quantidade):
        if self.entrou is not None:
            self.entrou.set()
        if self.travar is not None:
            self.travar.wait(5)
        if self.demora:
            time.sleep(self.demora)
        with self.trava:
            if self.falhas > 0:
                self.falhas -= 1
                raise RuntimeError("banco fora do ar")
            self.chamadas.append((evento, quantidade))
            self.recebidos.extend([evento] * quantidade)


def uma_de_cada_vez(medidor, *eventos):
    """Conta cada evento esperando o anterior sair (assim cada um vai num pedido só, sem juntar com o seguinte)."""
    for evento in eventos:
        medidor.contar(evento)
        assert medidor.esperar_esvaziar()


# ---------------------------------------------------------------- a lista fechada

def teste_a_lista_de_eventos_e_fechada():
    assert mu.EVENTOS == ("abertura", "busca", "busca_sem_resultado", "atualizacao_da_lista", "historico")
    assert mu.ORIGEM_DO_SITE == "site" and mu.ORIGEM_DA_LISTA == "lista"
    assert mu.INTERVALO_ENTRE_AVISOS == 600 and mu.CAPACIDADE_DA_FILA == 500           # os "10 minutos" e as "500 somas" que a documentação promete


# ---------------------------------------------------------------- o medidor

def teste_cada_ocorrencia_chega_ao_gravador():
    g = Gravador()
    m = mu.MedidorDeUso(g)
    for evento in mu.EVENTOS:
        m.contar(evento)
    m.contar("busca")
    assert m.esperar_esvaziar()
    assert Counter(g.recebidos) == Counter(list(mu.EVENTOS) + ["busca"])                  # (a ordem entre tipos não importa: só quantas vezes de cada)


def teste_o_que_chega_junto_sai_num_pedido_so_por_tipo_com_a_quantidade():
    solta, entrou = threading.Event(), threading.Event()
    g = Gravador(travar=solta, entrou=entrou)
    m = mu.MedidorDeUso(g)
    m.contar("busca")
    assert entrou.wait(3)                                                                 # o fio pegou a 1ª e está "enviando" (travado)
    for _ in range(10):
        m.contar("busca")
    for _ in range(3):
        m.contar("historico")
    for _ in range(5):
        m.contar("busca")
    solta.set()
    assert m.esperar_esvaziar()
    assert g.chamadas == [("busca", 1), ("busca", 15), ("historico", 3)], g.chamadas       # 18 ocorrências esperando viraram 2 pedidos, não 18


def teste_o_que_nao_e_da_lista_e_ignorado_sem_erro():
    g = Gravador()
    m = mu.MedidorDeUso(g)
    for ruim in ("", None, "Busca", "busca ", "cep", "30130010", "arroz", "MG", 7, ("busca",), ["busca"], {"busca"}, object()):
        m.contar(ruim)                                          # nunca levanta
    m.contar("busca")
    assert m.esperar_esvaziar() and g.chamadas == [("busca", 1)]


def teste_contar_engole_qualquer_falha_interna():
    m = mu.MedidorDeUso(Gravador())

    def sem_fio():
        raise RuntimeError("não deu para criar o fio")
    m._garantir_fio = sem_fio
    m.contar("busca")                                           # não levanta: a busca do usuário não pode quebrar por causa da medição
    assert m._fila.qsize() == 1                                 # a contagem ficou esperando (nada se perde): a próxima tentativa sobe o fio


def teste_fio_que_nao_subiu_ou_morreu_e_recriado():
    g = Gravador()
    original = threading.Thread.start
    chamadas = []

    def falha_so_a_primeira_vez(self):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("can't start new thread")
        return original(self)
    threading.Thread.start = falha_so_a_primeira_vez
    try:
        m = mu.MedidorDeUso(g)
        m.contar("busca")                                       # o fio não sobe: não levanta, e a contagem espera na fila
        assert m._fio is None and m._fila.qsize() == 1 and g.recebidos == []
        m.contar("historico")                                   # a próxima tentativa sobe o fio e as duas saem
        assert m.esperar_esvaziar() and Counter(g.recebidos) == Counter(["busca", "historico"])
        primeiro = m._fio
        primeiro_morreu = threading.Event()

        def morre(_evento, _quantidade):
            primeiro_morreu.set()
            raise SystemExit                                    # (BaseException: o fio morre de verdade, o `except Exception` não pega)
        m._enviar = morre
        m.contar("busca")
        assert primeiro_morreu.wait(3)
        primeiro.join(3)
        assert not primeiro.is_alive()
        m._enviar = g
        m.contar("historico")                                   # com o fio morto, a contagem seguinte cria outro
        assert m.esperar_esvaziar(limite=3) and g.recebidos[-1] == "historico" and m._fio is not primeiro and m._fio.is_alive()
    finally:
        threading.Thread.start = original


def teste_sem_envio_o_medidor_esta_desligado_e_nao_faz_nada():
    m = mu.MedidorDeUso()
    for evento in mu.EVENTOS:
        m.contar(evento)
    assert m._fio is None and m._fila.qsize() == 0 and m.descartados == 0       # nem fio, nem fila: desligado não custa nada


def teste_ligar_comeca_a_enviar_e_desligar_para_depois_de_mandar_o_que_esta_na_fila():
    g = Gravador(demora=0.05)
    m = mu.MedidorDeUso()
    m.contar("busca")                                                           # desligado: ignorado
    m.ligar(g)
    for _ in range(5):
        m.contar("busca")
    m.desligar(esperar=3)                                                       # dá tempo de a fila sair antes de desligar
    assert len(g.recebidos) == 5 and m._enviar is None
    m.contar("busca")                                                           # desligado de novo: ignorado
    time.sleep(0.05)
    assert len(g.recebidos) == 5
    m.ligar(g)                                                                  # e pode ligar de novo
    m.contar("historico")
    assert m.esperar_esvaziar() and g.recebidos[-1] == "historico"


def teste_desligar_sem_esperar_descarta_o_que_ainda_estava_na_fila_sem_erro():
    solta, entrou = threading.Event(), threading.Event()
    g = Gravador(travar=solta, entrou=entrou)
    avisos = []
    m = mu.MedidorDeUso(g, avisar=avisos.append)
    m.contar("busca")
    assert entrou.wait(3)                                                       # o fio está "enviando" a 1ª (travado)
    for _ in range(4):
        m.contar("busca")
    m.desligar()                                                                # não espera nada
    solta.set()
    assert m.esperar_esvaziar()                                                 # o fio termina a que estava em andamento e descarta o resto, sem erro
    assert g.recebidos == ["busca"] and avisos == []                            # (descartar por estar desligado não é falha: nada no log)


def teste_fila_cheia_avisa_no_log_uma_vez_por_intervalo():
    avisos, relogio = [], [500.0]
    solta, entrou = threading.Event(), threading.Event()
    g = Gravador(travar=solta, entrou=entrou)
    m = mu.MedidorDeUso(g, capacidade=2, agora=lambda: relogio[0], avisar=avisos.append)
    m.contar("busca")
    assert entrou.wait(3)                                                       # o fio está ocupado (travado) com a 1ª: o resto vai se acumulando
    for _ in range(30):
        m.contar("busca")
    assert len(avisos) == 1 and "descartadas" in avisos[0] and "A busca segue normal" in avisos[0], avisos
    relogio[0] += mu.INTERVALO_ENTRE_AVISOS + 1
    m.contar("busca")
    assert len(avisos) == 2                                                     # passou o intervalo: avisa de novo
    solta.set()
    assert m.esperar_esvaziar()


def teste_contar_nao_espera_o_gravador():
    g = Gravador(demora=0.25)
    m = mu.MedidorDeUso(g)
    inicio = time.perf_counter()
    for _ in range(20):
        m.contar("busca")
    gasto = time.perf_counter() - inicio
    assert gasto < 0.1, f"contar 20 vezes levou {gasto:.3f}s: está esperando o gravador"
    assert m.esperar_esvaziar(limite=10) and len(g.recebidos) == 20 and len(g.chamadas) <= 3     # (e as 20 viraram poucos pedidos)


def teste_um_so_fio_de_envio_por_medidor_e_ele_nao_trava_o_encerramento():
    antes = sum(1 for t in threading.enumerate() if t.name == "medidor-de-uso")
    m = mu.MedidorDeUso(Gravador())
    for _ in range(50):
        m.contar("busca")
    assert m.esperar_esvaziar()
    fios = [t for t in threading.enumerate() if t.name == "medidor-de-uso"]
    assert len(fios) == antes + 1 and all(t.daemon for t in fios)            # daemon: não impede o servidor de desligar


def teste_fila_cheia_descarta_a_sobra_sem_erro_e_sem_esperar():
    solta, entrou = threading.Event(), threading.Event()
    g = Gravador(travar=solta, entrou=entrou)
    m = mu.MedidorDeUso(g, capacidade=3, avisar=lambda _: None)
    m.contar("busca")
    assert entrou.wait(3)                                                    # o fio pegou a 1ª e está travado enviando
    inicio = time.perf_counter()
    for _ in range(12):
        m.contar("busca")
    assert time.perf_counter() - inicio < 0.2                                # o gravador está travado e mesmo assim contar não espera
    assert m.descartados == 12 - 3, m.descartados                            # cabem 3 na fila; as outras 9 se perdem (e são contadas como perdidas)
    solta.set()
    assert m.esperar_esvaziar()
    assert len(g.recebidos) + m.descartados == 13                            # nada some sem ser contado como descarte


def teste_falha_do_banco_nao_derruba_o_fio_e_so_avisa_uma_vez_por_intervalo():
    avisos, relogio = [], [1000.0]
    g = Gravador(falhas=2)
    m = mu.MedidorDeUso(g, agora=lambda: relogio[0], avisar=avisos.append)
    uma_de_cada_vez(m, "busca", "busca", "historico")
    assert g.recebidos == ["historico"]                                      # as duas primeiras falharam; o fio seguiu vivo e entregou a terceira
    assert len(avisos) == 1 and "RuntimeError" in avisos[0] and "a busca segue normal" in avisos[0]
    g.falhas = 1
    relogio[0] += mu.INTERVALO_ENTRE_AVISOS - 1
    uma_de_cada_vez(m, "busca")
    assert len(avisos) == 1                                                  # ainda dentro do intervalo: sem aviso novo
    g.falhas = 1
    relogio[0] += 2
    uma_de_cada_vez(m, "busca")
    assert len(avisos) == 2                                                  # passou o intervalo: avisa de novo
    g.falhas = 1
    relogio[0] += 5
    uma_de_cada_vez(m, "busca")
    assert len(avisos) == 2                                                  # e o intervalo recomeça a contar a partir deste aviso


def teste_um_tipo_que_falha_no_lote_nao_impede_os_outros():
    solta, entrou = threading.Event(), threading.Event()
    g = Gravador(travar=solta, entrou=entrou)
    m = mu.MedidorDeUso(g, avisar=lambda _: None)
    m.contar("busca")
    assert entrou.wait(3)
    m.contar("abertura")
    m.contar("historico")
    g.falhas = 1                                                             # (a 1ª chamada depois da travada falha: a "busca" que já estava em andamento)
    solta.set()
    assert m.esperar_esvaziar()
    assert Counter(g.recebidos) == Counter(["abertura", "historico"])        # os outros tipos do lote seguinte saem normalmente


def teste_com_os_padroes_o_aviso_vai_para_a_tela_uma_vez_e_o_relogio_e_o_de_verdade():
    saida = io.StringIO()
    m = mu.MedidorDeUso(Gravador(falhas=3))                                   # sem injetar nada: avisar=print, agora=time.monotonic
    assert m._agora is time.monotonic and m._avisar is print
    with contextlib.redirect_stdout(saida):
        uma_de_cada_vez(m, "busca", "busca", "busca")
    assert saida.getvalue().count("Medição de uso indisponível (a busca segue normal): RuntimeError") == 1, saida.getvalue()


def teste_o_aviso_corta_a_mensagem_do_erro_em_200_caracteres():
    avisos = []

    def quebra(_evento, _quantidade):
        raise RuntimeError("x" * 500)
    m = mu.MedidorDeUso(quebra, avisar=avisos.append)
    uma_de_cada_vez(m, "busca")
    assert avisos == ["⚠️ Medição de uso indisponível (a busca segue normal): RuntimeError: " + "x" * 200]


def teste_aviso_que_falha_tambem_nao_derruba_o_fio():
    def avisar_quebrado(_):
        raise OSError("sem saída")
    g = Gravador(falhas=1)
    m = mu.MedidorDeUso(g, avisar=avisar_quebrado)
    uma_de_cada_vez(m, "busca", "historico")
    assert g.recebidos == ["historico"]


# ---------------------------------------------------------------- na API

class BancoDeUso(BancoDeSeries):
    """O Supabase de mentira: as séries do /historico (BancoDeSeries) e a chamada `rpc` da contagem, que guarda o que a API mandou."""

    def __init__(self, falha_na_contagem=False, demora_na_contagem=0.0):
        super().__init__()
        self.contagens, self.falha_na_contagem, self.demora_na_contagem = [], falha_na_contagem, demora_na_contagem

    def rpc(self, nome, parametros):
        banco = self

        class Chamada:
            def execute(self):
                if banco.demora_na_contagem:
                    time.sleep(banco.demora_na_contagem)
                if banco.falha_na_contagem:
                    raise RuntimeError("Could not find the function public.registrar_uso(p_evento, p_qtd) in the schema cache")
                banco.contagens.append((nome, dict(parametros)))
        return Chamada()


def com_banco(banco, funcao, avisos=None):
    """Roda `funcao` com a API ligada ao banco de mentira e um medidor novo (que usa a própria _gravar_uso da API); espera a fila esvaziar."""
    anteriores = (api.supabase, api._series, api._medidor, api.carregar_catalogo, api.obter_uf_pelo_cep, api.buscar_detalhado)
    api.supabase, api._series = banco, sp.CacheDeSeries()
    api._medidor = mu.MedidorDeUso(api._gravar_uso, avisar=(avisos.append if avisos is not None else (lambda _: None)))
    try:
        resultado = funcao()
        assert api._medidor.esperar_esvaziar()
        return resultado
    finally:
        api.supabase, api._series, api._medidor, api.carregar_catalogo, api.obter_uf_pelo_cep, api.buscar_detalhado = anteriores


def catalogo_de(*nomes):
    return busca.indexar([{"id": i, "nome": n, "termo": "arroz", "supermercado": "Apoio Entrega", "preco_varejo": 5.0 + i, "ean": f"78900000000{i}"} for i, n in enumerate(nomes)])


def buscar(cep, item, uf="MG", catalogo=None, **extra):
    api.carregar_catalogo = lambda _uf: catalogo if catalogo is not None else catalogo_de("Arroz Tipo 1 5kg", "Arroz Integral 1kg")
    api.obter_uf_pelo_cep = lambda _cep: uf
    with contextlib.redirect_stdout(io.StringIO()):
        return api.buscar_e_comparar(cep=cep, item=item, **extra)


def totais(banco):
    """O que a API mandou ao banco, somado por evento (a ordem e o agrupamento em pedidos não importam: só quantas vezes de cada)."""
    soma = Counter()
    for _, p in banco.contagens:
        soma[p["p_evento"]] += p["p_qtd"]
    return dict(soma)


def teste_o_medidor_da_api_nasce_desligado_e_os_handlers_nao_falam_com_o_banco_por_causa_dele():
    """Os testes antigos chamam os handlers direto, sem trocar o medidor: nada pode sair para a rede (o host de produção está fixo em api_supabase.py)."""
    import httpx
    assert api._medidor._enviar is None
    chamadas = []
    original, banco = httpx.Client.send, api.supabase
    httpx.Client.send = lambda self, requisicao, **kwargs: chamadas.append(str(requisicao.url)) or httpx.Response(204, request=requisicao)
    anteriores = (api.carregar_catalogo, api.obter_uf_pelo_cep, api.aquecer_catalogo)
    try:
        buscar("30130010", "arroz")
        buscar("30130010", "picanha", origem="lista")
        api.aquecer_catalogo = lambda *a, **k: None
        api.saude(origem="site")
        time.sleep(0.2)
    finally:
        httpx.Client.send, api.supabase = original, banco
        api.carregar_catalogo, api.obter_uf_pelo_cep, api.aquecer_catalogo = anteriores
    assert chamadas == [] and api._medidor._fio is None and api._medidor._fila.qsize() == 0, chamadas


def teste_o_servidor_liga_o_medidor_ao_subir_e_desliga_ao_cair():
    import asyncio
    anterior = api.aquecer_catalogo
    api.aquecer_catalogo = lambda *a, **k: None
    visto = {}

    async def rodar():
        async with api.ciclo_de_vida(api.app):
            visto["dentro"] = api._medidor._enviar
        visto["fora"] = api._medidor._enviar
    try:
        asyncio.run(rodar())
        assert visto["dentro"] is api._gravar_uso and visto["fora"] is None
        try:                                                                    # mesmo se o servidor cair por um erro, a medição desliga
            async def com_erro():
                async with api.ciclo_de_vida(api.app):
                    raise RuntimeError("o servidor caiu")
            asyncio.run(com_erro())
        except RuntimeError:
            pass
        assert api._medidor._enviar is None
    finally:
        api.aquecer_catalogo = anterior


def teste_o_medidor_do_modulo_grava_pela_funcao_do_banco_depois_que_o_servidor_o_liga():
    import asyncio
    banco = BancoDeUso()
    anteriores = (api.aquecer_catalogo, api.supabase)
    api.aquecer_catalogo = lambda *a, **k: None
    api.supabase = banco

    async def rodar():
        async with api.ciclo_de_vida(api.app):
            api._medidor.contar("busca")                                        # o objeto de verdade do módulo, ligado pelo servidor
            assert api._medidor.esperar_esvaziar()
    try:
        asyncio.run(rodar())
    finally:
        api.aquecer_catalogo, api.supabase = anteriores
    assert banco.contagens == [("registrar_uso", {"p_evento": "busca", "p_qtd": 1})]


def teste_o_servidor_da_um_instante_para_a_fila_sair_ao_desligar():
    import asyncio
    g = Gravador(demora=0.3)                                                    # (cada envio demora: o que está na fila só sai se o desligamento esperar)
    anteriores = (api.aquecer_catalogo, api._gravar_uso)
    api.aquecer_catalogo = lambda *a, **k: None
    api._gravar_uso = g

    async def rodar():
        async with api.ciclo_de_vida(api.app):
            for _ in range(3):
                api._medidor.contar("busca")
    try:
        asyncio.run(rodar())
        assert len(g.recebidos) == 3, g.recebidos                               # as 3 saíram antes de o servidor terminar de desligar
    finally:
        api.aquecer_catalogo, api._gravar_uso = anteriores


def teste_o_medidor_da_api_tem_fila_limitada():
    assert isinstance(api._medidor, mu.MedidorDeUso) and api._medidor._fila.maxsize == mu.CAPACIDADE_DA_FILA > 0      # sem limite, um banco travado encheria a memória do servidor


def teste_busca_conta_uma_busca():
    banco = BancoDeUso()
    r = com_banco(banco, lambda: buscar("32607600", "arroz"))
    assert r["status"] == "sucesso" and r["carrinho_comparativo"]
    assert totais(banco) == {"busca": 1}
    assert all(nome == "registrar_uso" for nome, _ in banco.contagens)


def teste_busca_sem_nenhum_produto_conta_a_busca_e_tambem_a_sem_resultado():
    banco = BancoDeUso()
    r = com_banco(banco, lambda: buscar("32607600", "picanha"))
    assert r["carrinho_comparativo"] == [] and r["ocultos"] == 0
    assert totais(banco) == {"busca": 1, "busca_sem_resultado": 1}


def teste_busca_com_resultados_ocultos_e_nenhum_visivel_nao_e_sem_resultado():
    """Hoje o catálogo nunca esconde TODOS os produtos, mas se a regra da busca mudar o site passa a oferecer "mostrar os escondidos": isso não é busca sem resultado."""
    produtos = [{"id": 9, "nome": "Condicionador com Arroz Preto", "termo": "condicionador", "supermercado": "Supernosso", "preco_varejo": 20.0, "ean": "7891"}]
    banco = BancoDeUso()

    class SoOcultos:
        produtos = []
        ocultos_so_citam = 2
        ocultos_pelo_limite = 0
        so_citam_por_mercado = {"Supernosso": 2}

    def uma():
        api.buscar_detalhado = lambda catalogo, item, incluir_so_citam=False: SoOcultos()
        return buscar("32607600", "arroz", catalogo=busca.indexar(produtos))
    r = com_banco(banco, uma)
    assert r["ocultos"] == 2 and r["carrinho_comparativo"] == []
    assert totais(banco) == {"busca": 1}


def teste_mostrar_tambem_e_buscar_de_novo_contam_como_busca():
    banco = BancoDeUso()
    com_banco(banco, lambda: (buscar("32607600", "arroz", todos=True), buscar("32607600", "arroz")))
    assert totais(banco) == {"busca": 2}


def teste_a_atualizacao_automatica_da_lista_nao_e_contada_como_busca():
    banco = BancoDeUso()

    def varias():
        buscar("32607600", "arroz", origem="lista")                       # o site renovando os preços da lista de compras
        buscar("32607600", "picanha", origem="lista")                     # (mesmo sem resultado: não é busca de ninguém)
        buscar("32607600", "arroz")                                       # uma pessoa buscando
    com_banco(banco, varias)
    assert totais(banco) == {"atualizacao_da_lista": 2, "busca": 1}


def teste_so_origem_lista_exata_vira_atualizacao_da_lista():
    banco = BancoDeUso()
    com_banco(banco, lambda: [buscar("32607600", "arroz", origem=o) for o in ("", "Lista", "lista ", "site", "outra", "LISTA")])
    assert totais(banco) == {"busca": 6}                                   # qualquer outro valor é uma busca comum


def esquema_openapi():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                         # (o FastAPI avisa de "Duplicate Operation ID" em /saude, que atende GET e HEAD; é de antes e não importa aqui)
        return api.app.openapi()


def parametros_da_rota(caminho, metodo="get"):
    """Os parâmetros que a API anuncia para a rota, pelo OpenAPI (a API pública do FastAPI): [(nome, onde)]."""
    return [(p["name"], p["in"]) for p in esquema_openapi()["paths"][caminho][metodo].get("parameters", [])]


def teste_comparar_recebe_origem_pelo_endereco():
    assert parametros_da_rota("/comparar") == [("cep", "query"), ("item", "query"), ("todos", "query"), ("origem", "query")]


def teste_nada_de_pessoal_chega_a_contagem():
    """O CEP (inteiro ou parte), o estado, o termo, o produto e o IP não aparecem em NENHUMA chamada de contagem; só o nome do evento e quantas vezes."""
    banco = BancoDeUso()

    def tudo():
        buscar("30130010", "arroz segredo da vovó", uf="MG")
        buscar("30130-010", "picanha do joão", uf="SP", origem="lista")
        api.historico_de_precos("Atacadao|v:100:1")
        anterior = api.aquecer_catalogo
        api.aquecer_catalogo = lambda *a, **k: None
        try:
            api.saude(origem="site")
        finally:
            api.aquecer_catalogo = anterior
    com_banco(banco, tudo)
    assert totais(banco) == {"busca": 1, "busca_sem_resultado": 1, "atualizacao_da_lista": 1, "historico": 1, "abertura": 1}
    for nome, parametros in banco.contagens:
        assert nome == "registrar_uso" and set(parametros) == {"p_evento", "p_qtd"} and parametros["p_evento"] in mu.EVENTOS, parametros
        assert type(parametros["p_qtd"]) is int and 1 <= parametros["p_qtd"] <= mu.CAPACIDADE_DA_FILA, parametros
    despejo = json.dumps(banco.contagens, ensure_ascii=False).lower()
    for proibido in ("30130", "arroz", "segredo", "vov", "picanha", "joão", "atacadao", "v:100", "127.0.0.1", "mg", "sp"):
        assert proibido not in despejo, f"{proibido!r} vazou para a contagem: {despejo}"


def teste_historico_conta_quando_responde_e_tambem_quando_vem_do_cache():
    banco = BancoDeUso()
    com_banco(banco, lambda: (api.historico_de_precos("Atacadao|v:100:1"), api.historico_de_precos("Atacadao|v:100:1")))
    assert totais(banco) == {"historico": 2}
    assert banco.consultas.count("catalogo") == 1                              # a 2ª veio do cache e mesmo assim foi contada: contamos o pedido do usuário


def teste_historico_conta_um_por_pedido_mesmo_com_varias_chaves():
    """O site manda todas as chaves do produto (uma por mercado) num pedido só: é UMA consulta ao histórico."""
    banco = BancoDeUso()
    com_banco(banco, lambda: api.historico_de_precos("Supernosso|v:100:1,Atacadao|v:100:1"))
    assert totais(banco) == {"historico": 1}


def teste_historico_com_pedido_ruim_ou_banco_fora_nao_conta():
    banco = BancoDeUso()

    def pedidos():
        for ruim in ("", "lixo", "Atacadao|v:1;2"):
            try:
                api.historico_de_precos(ruim)
            except HTTPException as erro:
                assert erro.status_code == 400
            else:
                raise AssertionError(f"devia dar 400: {ruim!r}")
        banco.falha = True
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                api.historico_de_precos("Atacadao|v:100:1")
        except HTTPException as erro:
            assert erro.status_code == 503
        else:
            raise AssertionError("devia dar 503")
    com_banco(banco, pedidos)
    assert banco.contagens == []


def teste_saude_so_conta_a_abertura_quando_vem_do_site():
    banco = BancoDeUso()
    anterior = api.aquecer_catalogo
    api.aquecer_catalogo = lambda *a, **k: None
    try:
        com_banco(banco, lambda: (api.saude(), api.saude(origem=""), api.saude(origem="monitor"), api.saude(origem="Site"), api.saude(origem="site "), api.saude(origem="site")))
    finally:
        api.aquecer_catalogo = anterior
    assert totais(banco) == {"abertura": 1}                                    # os monitores que chamam /saude de 5 em 5 minutos não inflam o uso: só "origem=site", exato


def teste_saude_recebe_origem_pelo_endereco_e_nada_mais():
    assert set(esquema_openapi()["paths"]["/saude"]) == {"get", "head"}
    for metodo in ("get", "head"):
        assert parametros_da_rota("/saude", metodo) == [("origem", "query")]


def teste_banco_sem_a_funcao_de_contagem_nao_atrapalha_a_busca_e_so_avisa_uma_vez():
    banco = BancoDeUso(falha_na_contagem=True)
    avisos = []

    def varias():
        return [buscar("30130010", "arroz segredo") for _ in range(5)]
    respostas = com_banco(banco, varias, avisos)
    assert all(r["status"] == "sucesso" for r in respostas)
    assert banco.contagens == []
    assert len(avisos) == 1 and "Medição de uso indisponível" in avisos[0] and "registrar_uso" in avisos[0]
    assert "30130" not in avisos[0] and "segredo" not in avisos[0]               # o aviso não carrega nada do pedido


def teste_contagem_lenta_nao_atrasa_nenhuma_resposta():
    """O banco leva 1,5 s para cada soma; busca, abertura do site e histórico respondem na hora (o limite de 1 s tem folga para uma máquina carregada)."""
    banco = BancoDeUso(demora_na_contagem=1.5)
    medidas = {}
    anterior = api.aquecer_catalogo
    api.aquecer_catalogo = lambda *a, **k: None

    def cada(nome, funcao):
        inicio = time.perf_counter()
        funcao()
        medidas[nome] = time.perf_counter() - inicio

    def todas():
        cada("busca", lambda: buscar("30130010", "arroz"))
        cada("abertura", lambda: api.saude(origem="site"))
        cada("historico", lambda: api.historico_de_precos("Atacadao|v:100:1"))
    try:
        com_banco(banco, todas)
    finally:
        api.aquecer_catalogo = anterior
    assert all(t < 1.0 for t in medidas.values()), f"alguma resposta esperou a contagem: {medidas}"
    assert totais(banco) == {"busca": 1, "abertura": 1, "historico": 1}           # e as contagens acabaram chegando


def teste_o_gravador_da_api_manda_so_o_evento_e_a_quantidade_para_a_funcao_do_banco():
    banco = BancoDeUso()
    anterior = api.supabase
    api.supabase = banco
    try:
        api._gravar_uso("busca", 3)
    finally:
        api.supabase = anterior
    assert banco.contagens == [("registrar_uso", {"p_evento": "busca", "p_qtd": 3})]


def teste_o_pedido_http_que_sai_para_o_banco_leva_so_o_evento_e_a_quantidade():
    """Com o cliente de verdade do Supabase (só a rede é de mentira): o que sai pela rede em cada contagem é um POST a /rpc/registrar_uso com
    {"p_evento", "p_qtd"} e nada mais no corpo."""
    import httpx
    from supabase import create_client
    pedidos = []

    def enviar_de_mentira(self, requisicao, **kwargs):
        pedidos.append((requisicao.method, requisicao.url.path, requisicao.url.query.decode(), requisicao.content.decode()))
        return httpx.Response(204, request=requisicao)

    originais = (httpx.Client.send, api.supabase, api._medidor, api.carregar_catalogo, api.obter_uf_pelo_cep, api.aquecer_catalogo)
    httpx.Client.send = enviar_de_mentira
    api.supabase = create_client("https://exemplo.invalid", "chave-falsa-" + "x" * 40)
    api._medidor = mu.MedidorDeUso(api._gravar_uso, avisar=lambda _: None)
    api.aquecer_catalogo = lambda *a, **k: None
    try:
        buscar("30130010", "arroz segredo da vovó", uf="MG")
        api.saude(origem="site")
        assert api._medidor.esperar_esvaziar(limite=30)          # (o 1º uso do cliente de verdade pode demorar numa máquina carregada)
    finally:
        httpx.Client.send, api.supabase, api._medidor, api.carregar_catalogo, api.obter_uf_pelo_cep, api.aquecer_catalogo = originais
    assert [(m, p, q) for m, p, q, _ in pedidos] == [("POST", "/rest/v1/rpc/registrar_uso", "")] * 3, pedidos
    assert sorted((json.loads(c) for *_, c in pedidos), key=lambda x: x["p_evento"]) == [
        {"p_evento": "abertura", "p_qtd": 1}, {"p_evento": "busca", "p_qtd": 1}, {"p_evento": "busca_sem_resultado", "p_qtd": 1}]
    despejo = json.dumps(pedidos, ensure_ascii=False).lower()
    for proibido in ("30130", "arroz", "segredo", "vov", "mg"):
        assert proibido not in despejo, proibido


# ---------------------------------------------------------------- o SQL combina com o Python

def sql_do_uso():
    return (RAIZ / "docs" / "sql" / "uso_do_site.sql").read_text(encoding="utf-8")


def sql_sem_comentarios():
    return "\n".join(re.sub(r"--.*$", "", linha) for linha in sql_do_uso().splitlines())


COMANDOS_DO_SQL = [
    "create table if not exists uso_diario ( dia date not null, evento text not null check (evento in ('abertura', 'busca', 'busca_sem_resultado', 'atualizacao_da_lista', 'historico')), "
    "total bigint not null default 0 check (total >= 0), primary key (dia, evento) )",
    "alter table uso_diario enable row level security",
    "revoke all on uso_diario from anon, authenticated",
    "grant select, insert, update on uso_diario to service_role",
    "create or replace function registrar_uso(p_evento text, p_qtd bigint default 1) returns void language sql set search_path = public as $$ "
    "insert into uso_diario (dia, evento, total) select (now() at time zone 'america/sao_paulo')::date, p_evento, p_qtd where p_qtd between 1 and 1000000 "
    "on conflict (dia, evento) do update set total = uso_diario.total + excluded.total; $$",
    "revoke all on function registrar_uso(text, bigint) from public, anon, authenticated",
    "grant execute on function registrar_uso(text, bigint) to service_role",
    "notify pgrst, 'reload schema'",
]


def teste_sql_o_script_tem_exatamente_estes_comandos_e_nada_mais():
    """Script de segurança colado à mão em produção: qualquer mudança (outra coluna, outra tabela, um `alter table`, um `do $$`...) reprova aqui até
    alguém atualizar esta lista de propósito, junto com o aviso do site e os documentos."""
    assert [normalizado(c) for c in comandos(sql_do_uso())] == COMANDOS_DO_SQL


def teste_sql_o_corpo_da_funcao_so_acrescenta_na_tabela_da_medicao():
    miolo = normalizado(corpo(next(c for c in comandos(sql_do_uso()) if c.lower().startswith("create or replace function"))))
    assert miolo == COMANDOS_DO_SQL[4].split(" as $$ ")[1].removesuffix(" $$").strip(), miolo


def teste_sql_a_tabela_so_tem_dia_evento_e_total():
    sql = " ".join(sql_sem_comentarios().lower().split())
    corpo = re.search(r"create table if not exists uso_diario \((.*?)\); alter table", sql)
    assert corpo, "não achei o create table uso_diario"
    colunas = [c.strip().split()[0] for c in re.split(r",\s*(?![^()]*\))", corpo.group(1)) if c.strip() and not c.strip().startswith("primary key")]
    assert colunas == ["dia", "evento", "total"], colunas                          # nenhuma coluna para CEP, estado, termo, IP, horário ou pessoa
    assert "primary key (dia, evento)" in corpo.group(1)


def teste_sql_aceita_exatamente_os_eventos_do_python():
    sql = " ".join(sql_sem_comentarios().lower().split())
    lista = re.search(r"check \(evento in \((.*?)\)\)", sql)
    assert lista, "não achei a restrição check (evento in (...))"
    assert re.findall(r"'([^']+)'", lista.group(1)) == list(mu.EVENTOS)             # a mesma lista, na mesma ordem: o banco recusa o que o Python não conta


def teste_sql_so_a_chave_secreta_acessa_a_tabela_e_a_funcao():
    sql = " ".join(sql_sem_comentarios().lower().split())
    assert "alter table uso_diario enable row level security" in sql
    assert "create policy" not in sql                                                # RLS ligado e nenhuma política: a chave pública não lê nem escreve
    assert "revoke all on uso_diario from anon, authenticated" in sql
    assert "grant select, insert, update on uso_diario to service_role" in sql        # explícito: o Supabase está deixando de dar permissão automática em tabela nova
    assert "create or replace function registrar_uso(p_evento text, p_qtd bigint default 1)" in sql
    assert "revoke all on function registrar_uso(text, bigint) from public, anon, authenticated" in sql
    assert "grant execute on function registrar_uso(text, bigint) to service_role" in sql
    assert not re.search(r"grant [^;]*\b(anon|authenticated|public)\b", sql), "nada pode ser liberado para a chave pública"
    assert "security definer" not in sql                                             # roda com os direitos de quem chama (a chave secreta), não com os de dono
    assert "returns void language sql set search_path = public as $$" in sql         # o esquema de busca fixo (o painel de segurança do Supabase avisa quando falta)


def teste_sql_a_soma_e_atomica_limitada_e_nao_guarda_horario():
    sql = " ".join(sql_sem_comentarios().lower().split())
    assert "on conflict (dia, evento) do update set total = uso_diario.total + excluded.total" in sql
    assert "where p_qtd between 1 and 1000000 on conflict" in sql                    # quantidade absurda (ou negativa) é ignorada
    assert "(now() at time zone 'america/sao_paulo')::date" in sql                  # só o dia (de Brasília), nunca a hora
    assert not re.search(r"\b(timestamp|timestamptz|now\(\)(?! at time zone))", sql.split("create or replace function")[0]), "a tabela não pode ter coluna de horário"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
