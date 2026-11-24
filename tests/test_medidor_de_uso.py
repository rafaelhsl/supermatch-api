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
from pathlib import Path

os.environ.setdefault("SUPABASE_KEY", "chave-falsa-so-para-importar")      # a API cria o cliente ao importar
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import api_supabase as api  # noqa: E402
import busca  # noqa: E402
import medidor_de_uso as mu  # noqa: E402
import serie_de_precos as sp  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from test_serie_de_precos import BancoDeSeries  # noqa: E402


class Gravador:
    """O `enviar` do medidor nos testes: guarda o que chegou (e pode falhar ou demorar de propósito)."""

    def __init__(self, falhas=0, demora=0.0, travar=None):
        self.recebidos, self.falhas, self.demora, self.travar, self.trava = [], falhas, demora, travar, threading.Lock()

    def __call__(self, evento):
        if self.travar is not None:
            self.travar.wait(5)
        if self.demora:
            time.sleep(self.demora)
        with self.trava:
            if self.falhas > 0:
                self.falhas -= 1
                raise RuntimeError("banco fora do ar")
            self.recebidos.append(evento)


# ---------------------------------------------------------------- a lista fechada

def teste_a_lista_de_eventos_e_fechada():
    assert mu.EVENTOS == ("abertura", "busca", "busca_sem_resultado", "atualizacao_da_lista", "historico")
    assert mu.ORIGEM_DO_SITE == "site" and mu.ORIGEM_DA_LISTA == "lista"


# ---------------------------------------------------------------- o medidor

def teste_cada_ocorrencia_chega_ao_gravador_na_ordem():
    g = Gravador()
    m = mu.MedidorDeUso(g)
    for evento in mu.EVENTOS:
        m.contar(evento)
    m.contar("busca")
    assert m.esperar_esvaziar()
    assert g.recebidos == list(mu.EVENTOS) + ["busca"]


def teste_o_que_nao_e_da_lista_e_ignorado_sem_erro():
    g = Gravador()
    m = mu.MedidorDeUso(g)
    for ruim in ("", None, "Busca", "busca ", "cep", "30130010", "arroz", "MG", 7, ("busca",), ["busca"], {"busca"}, object()):
        m.contar(ruim)                                          # nunca levanta
    m.contar("busca")
    assert m.esperar_esvaziar() and g.recebidos == ["busca"]


def teste_contar_engole_qualquer_falha_interna():
    m = mu.MedidorDeUso(Gravador())

    def sem_fio():
        raise RuntimeError("não deu para criar o fio")
    m._garantir_fio = sem_fio
    m.contar("busca")                                           # não levanta: a busca do usuário não pode quebrar por causa da medição
    assert m._fila.qsize() == 0


def teste_contar_nao_espera_o_gravador():
    g = Gravador(demora=0.25)
    m = mu.MedidorDeUso(g)
    inicio = time.perf_counter()
    for _ in range(20):
        m.contar("busca")
    gasto = time.perf_counter() - inicio
    assert gasto < 0.1, f"contar 20 vezes levou {gasto:.3f}s: está esperando o gravador"
    assert m.esperar_esvaziar(limite=10) and len(g.recebidos) == 20


def teste_um_so_fio_de_envio_por_medidor_e_ele_nao_trava_o_encerramento():
    antes = sum(1 for t in threading.enumerate() if t.name == "medidor-de-uso")
    m = mu.MedidorDeUso(Gravador())
    for _ in range(50):
        m.contar("busca")
    assert m.esperar_esvaziar()
    fios = [t for t in threading.enumerate() if t.name == "medidor-de-uso"]
    assert len(fios) == antes + 1 and all(t.daemon for t in fios)            # daemon: não impede o servidor de desligar


def teste_fila_cheia_descarta_a_sobra_sem_erro_e_sem_esperar():
    solta = threading.Event()
    g = Gravador(travar=solta)
    m = mu.MedidorDeUso(g, capacidade=3)
    inicio = time.perf_counter()
    for _ in range(12):
        m.contar("busca")
    assert time.perf_counter() - inicio < 0.2                                # o gravador está travado e mesmo assim contar não espera
    assert m.descartados >= 12 - 3 - 1, m.descartados                        # cabem 3 na fila + 1 que o fio já pegou
    solta.set()
    assert m.esperar_esvaziar()
    assert len(g.recebidos) + m.descartados == 12                            # nada some sem ser contado como descarte


def teste_falha_do_banco_nao_derruba_o_fio_e_so_avisa_uma_vez_por_intervalo():
    avisos, relogio = [], [1000.0]
    g = Gravador(falhas=2)
    m = mu.MedidorDeUso(g, agora=lambda: relogio[0], avisar=avisos.append)
    m.contar("busca")
    m.contar("busca")
    m.contar("historico")
    assert m.esperar_esvaziar()
    assert g.recebidos == ["historico"]                                      # as duas primeiras falharam; o fio seguiu vivo e entregou a terceira
    assert len(avisos) == 1 and "RuntimeError" in avisos[0] and "a busca segue normal" in avisos[0]
    g.falhas = 1
    relogio[0] += mu.INTERVALO_ENTRE_AVISOS - 1
    m.contar("busca")
    assert m.esperar_esvaziar() and len(avisos) == 1                         # ainda dentro do intervalo: sem aviso novo
    g.falhas = 1
    relogio[0] += 2
    m.contar("busca")
    assert m.esperar_esvaziar() and len(avisos) == 2                         # passou o intervalo: avisa de novo
    g.falhas = 1
    relogio[0] += 5
    m.contar("busca")
    assert m.esperar_esvaziar() and len(avisos) == 2                         # e o intervalo recomeça a contar a partir deste aviso


def teste_aviso_que_falha_tambem_nao_derruba_o_fio():
    def avisar_quebrado(_):
        raise OSError("sem saída")
    g = Gravador(falhas=1)
    m = mu.MedidorDeUso(g, avisar=avisar_quebrado)
    m.contar("busca")
    m.contar("historico")
    assert m.esperar_esvaziar() and g.recebidos == ["historico"]


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
                    raise RuntimeError("Could not find the function public.registrar_uso(p_evento) in the schema cache")
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


def so_os_eventos(banco):
    return [p["p_evento"] for _, p in banco.contagens]


def teste_o_medidor_da_api_tem_fila_limitada():
    assert isinstance(api._medidor, mu.MedidorDeUso) and api._medidor._fila.maxsize == mu.CAPACIDADE_DA_FILA > 0      # sem limite, um banco travado encheria a memória do servidor


def teste_busca_conta_uma_busca():
    banco = BancoDeUso()
    r = com_banco(banco, lambda: buscar("32607600", "arroz"))
    assert r["status"] == "sucesso" and r["carrinho_comparativo"]
    assert so_os_eventos(banco) == ["busca"]
    assert all(nome == "registrar_uso" for nome, _ in banco.contagens)


def teste_busca_sem_nenhum_produto_conta_a_busca_e_tambem_a_sem_resultado():
    banco = BancoDeUso()
    r = com_banco(banco, lambda: buscar("32607600", "picanha"))
    assert r["carrinho_comparativo"] == [] and r["ocultos"] == 0
    assert so_os_eventos(banco) == ["busca", "busca_sem_resultado"]


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
    assert so_os_eventos(banco) == ["busca"]


def teste_a_atualizacao_automatica_da_lista_nao_e_contada_como_busca():
    banco = BancoDeUso()

    def varias():
        buscar("32607600", "arroz", origem="lista")                       # o site renovando os preços da lista de compras
        buscar("32607600", "picanha", origem="lista")                     # (mesmo sem resultado: não é busca de ninguém)
        buscar("32607600", "arroz")                                       # uma pessoa buscando
    com_banco(banco, varias)
    assert so_os_eventos(banco) == ["atualizacao_da_lista", "atualizacao_da_lista", "busca"]


def teste_so_origem_lista_exata_vira_atualizacao_da_lista():
    banco = BancoDeUso()
    com_banco(banco, lambda: [buscar("32607600", "arroz", origem=o) for o in ("", "Lista", "lista ", "site", "outra", "LISTA")])
    assert so_os_eventos(banco) == ["busca"] * 6                           # qualquer outro valor é uma busca comum


def teste_comparar_recebe_origem_pelo_endereco():
    rota = next(r for r in api.app.routes if getattr(r, "path", "") == "/comparar")
    assert [p.alias for p in rota.dependant.query_params] == ["cep", "item", "todos", "origem"] and not rota.dependant.body_params and not rota.dependant.header_params


def teste_nada_de_pessoal_chega_a_contagem():
    """O CEP (inteiro ou parte), o estado, o termo, o produto e o IP não aparecem em NENHUMA chamada de contagem; só uma chave, de uma lista fechada."""
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
    assert so_os_eventos(banco) == ["busca", "busca_sem_resultado", "atualizacao_da_lista", "historico", "abertura"]
    for nome, parametros in banco.contagens:
        assert nome == "registrar_uso" and set(parametros) == {"p_evento"} and parametros["p_evento"] in mu.EVENTOS, parametros
    despejo = json.dumps(banco.contagens, ensure_ascii=False).lower()
    for proibido in ("30130", "arroz", "segredo", "vov", "picanha", "joão", "atacadao", "v:100", "127.0.0.1", "mg", "sp"):
        assert proibido not in despejo, f"{proibido!r} vazou para a contagem: {despejo}"


def teste_historico_conta_quando_responde_e_tambem_quando_vem_do_cache():
    banco = BancoDeUso()
    com_banco(banco, lambda: (api.historico_de_precos("Atacadao|v:100:1"), api.historico_de_precos("Atacadao|v:100:1")))
    assert so_os_eventos(banco) == ["historico", "historico"]
    assert banco.consultas.count("catalogo") == 1                              # a 2ª veio do cache e mesmo assim foi contada: contamos o pedido do usuário


def teste_historico_com_pedido_ruim_ou_banco_fora_nao_conta():
    banco = BancoDeUso()

    def pedidos():
        for ruim in ("", "lixo", "Atacadao|v:1;2"):
            try:
                api.historico_de_precos(ruim)
            except HTTPException as erro:
                assert erro.status_code == 400
        banco.falha = True
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                api.historico_de_precos("Atacadao|v:100:1")
        except HTTPException as erro:
            assert erro.status_code == 503
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
    assert so_os_eventos(banco) == ["abertura"]                                # os monitores que chamam /saude de 5 em 5 minutos não inflam o uso: só "origem=site", exato


def teste_saude_recebe_origem_pelo_endereco_e_nada_mais():
    rota = next(r for r in api.app.routes if getattr(r, "path", "") == "/saude")
    assert [p.alias for p in rota.dependant.query_params] == ["origem"] and not rota.dependant.body_params and not rota.dependant.header_params
    assert set(rota.methods) == {"GET", "HEAD"}


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


def teste_contagem_lenta_nao_atrasa_a_resposta():
    banco = BancoDeUso(demora_na_contagem=0.6)
    medidas = []

    def uma():
        inicio = time.perf_counter()
        buscar("30130010", "arroz")
        medidas.append(time.perf_counter() - inicio)
    com_banco(banco, uma)
    assert medidas[0] < 0.3, f"a busca esperou a contagem: {medidas[0]:.3f}s"
    assert so_os_eventos(banco) == ["busca"]                                     # e a contagem acabou chegando


def teste_o_gravador_da_api_manda_so_o_evento_para_a_funcao_do_banco():
    banco = BancoDeUso()
    anterior = api.supabase
    api.supabase = banco
    try:
        api._gravar_uso("busca")
    finally:
        api.supabase = anterior
    assert banco.contagens == [("registrar_uso", {"p_evento": "busca"})]


def teste_o_pedido_http_que_sai_para_o_banco_leva_so_o_evento():
    """Com o cliente de verdade do Supabase (só a rede é de mentira): o que sai pela rede em cada contagem é um POST a /rpc/registrar_uso com
    {"p_evento"} e nada mais. É o que o provedor do banco enxerga."""
    import httpx
    from supabase import create_client
    pedidos = []

    def enviar_de_mentira(self, requisicao, **kwargs):
        pedidos.append((requisicao.method, requisicao.url.path, requisicao.url.query.decode(), requisicao.content.decode()))
        return httpx.Response(204, request=requisicao)

    originais = (httpx.Client.send, api.supabase, api._medidor, api.carregar_catalogo, api.obter_uf_pelo_cep, api.aquecer_catalogo)
    httpx.Client.send = enviar_de_mentira
    api.supabase = create_client("https://exemplo.supabase.co", "chave-falsa-" + "x" * 40)
    api._medidor = mu.MedidorDeUso(api._gravar_uso, avisar=lambda _: None)
    api.aquecer_catalogo = lambda *a, **k: None
    try:
        buscar("30130010", "arroz segredo da vovó", uf="MG")
        api.saude(origem="site")
        assert api._medidor.esperar_esvaziar()
    finally:
        httpx.Client.send, api.supabase, api._medidor, api.carregar_catalogo, api.obter_uf_pelo_cep, api.aquecer_catalogo = originais
    assert [(m, p, q) for m, p, q, _ in pedidos] == [("POST", "/rest/v1/rpc/registrar_uso", "")] * 3, pedidos
    assert [json.loads(c) for *_, c in pedidos] == [{"p_evento": "busca"}, {"p_evento": "busca_sem_resultado"}, {"p_evento": "abertura"}]
    despejo = json.dumps(pedidos, ensure_ascii=False).lower()
    for proibido in ("30130", "arroz", "segredo", "vov", "mg"):
        assert proibido not in despejo, proibido


# ---------------------------------------------------------------- o SQL combina com o Python

def sql_do_uso():
    return (RAIZ / "docs" / "sql" / "uso_do_site.sql").read_text(encoding="utf-8")


def sql_sem_comentarios():
    return "\n".join(re.sub(r"--.*$", "", linha) for linha in sql_do_uso().splitlines())


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
    assert re.findall(r"'([a-z_]+)'", lista.group(1)) == list(mu.EVENTOS)           # a mesma lista, na mesma ordem: o banco recusa o que o Python não conta


def teste_sql_so_a_chave_secreta_acessa_a_tabela_e_a_funcao():
    sql = " ".join(sql_sem_comentarios().lower().split())
    assert "alter table uso_diario enable row level security" in sql
    assert "create policy" not in sql                                                # RLS ligado e nenhuma política: a chave pública não lê nem escreve
    assert "revoke all on uso_diario from anon, authenticated" in sql
    assert "create or replace function registrar_uso(p_evento text)" in sql
    assert "revoke all on function registrar_uso(text) from public, anon, authenticated" in sql
    assert "grant execute on function registrar_uso(text) to service_role" in sql
    assert not re.search(r"grant [^;]*\b(anon|authenticated|public)\b", sql), "nada pode ser liberado para a chave pública"
    assert "security definer" not in sql                                             # roda com os direitos de quem chama (a chave secreta), não com os de dono
    assert "returns void language sql set search_path = public as $$" in sql         # o esquema de busca fixo (o painel de segurança do Supabase avisa quando falta)


def teste_sql_a_soma_e_atomica_e_nao_guarda_horario():
    sql = " ".join(sql_sem_comentarios().lower().split())
    assert "on conflict (dia, evento) do update set total = uso_diario.total + 1" in sql
    assert "(now() at time zone 'america/sao_paulo')::date" in sql                  # só o dia (de Brasília), nunca a hora
    assert not re.search(r"\b(timestamp|timestamptz|now\(\)(?! at time zone))", sql.split("create or replace function")[0]), "a tabela não pode ter coluna de horário"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
