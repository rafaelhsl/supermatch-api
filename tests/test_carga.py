"""Testes da carga diária (alimentar_banco.py), sem rede, sem navegador e sem banco.

Rodar com:  python tests/test_carga.py   (precisa das bibliotecas do requirements.txt)
"""
import asyncio
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import alimentar_banco as ab  # noqa: E402
import coletor_vtex as c  # noqa: E402
import disjuntor  # noqa: E402
from robos_comum import FalhaNoRobo  # noqa: E402

disjuntor.PAUSA_DA_SEGUNDA_RODADA = 0          # nenhum teste espera de verdade pela segunda rodada


# ============================== um banco falso que só anota o que lhe pedem ==============================

class ErroDeColuna(Exception):
    code = "42703"


class Resposta:
    data = []


class ConsultaFalsa:
    def __init__(self, banco, tabela):
        self.banco, self.tabela, self.op, self.dados, self.filtros = banco, tabela, None, None, []

    def insert(self, linhas):
        self.op, self.dados = "insert", linhas
        return self

    def delete(self):
        self.op = "delete"
        return self

    def select(self, colunas):
        self.op, self.dados = "select", colunas
        return self

    def limit(self, n):
        return self

    def eq(self, coluna, valor):
        self.filtros.append(("eq", coluna, valor))
        return self

    def lt(self, coluna, valor):
        self.filtros.append(("lt", coluna, valor))
        return self

    def or_(self, filtro):
        self.filtros.append(("or", filtro))
        return self

    def execute(self):
        if self.op == "select" and "ean" in self.dados and not self.banco.tem_colunas_novas:
            raise ErroDeColuna("column produtos.ean does not exist")
        if self.op == "select" and "unidade" in self.dados and not self.banco.tem_unidade:
            raise ErroDeColuna("column produtos.unidade does not exist")
        if self.banco.erro_ao_inserir and self.op == "insert":
            raise RuntimeError("insert caiu")
        self.banco.chamadas.append((self.tabela, self.op, self.dados if self.op == "insert" else None, self.filtros))
        return Resposta()


class BancoFalso:
    def __init__(self, tem_colunas_novas=True, erro_ao_inserir=False, tem_unidade=None):
        self.chamadas, self.tem_colunas_novas, self.erro_ao_inserir = [], tem_colunas_novas, erro_ao_inserir
        self.tem_unidade = tem_colunas_novas if tem_unidade is None else tem_unidade       # um banco sem as colunas novas também não tem `unidade`

    def table(self, nome):
        return ConsultaFalsa(self, nome)

    def inserts(self):
        return [ch for ch in self.chamadas if ch[1] == "insert"]

    def deletes(self):
        return [ch for ch in self.chamadas if ch[1] == "delete"]


def linha_api(mercado, i, termo="arroz"):
    return {"supermercado": mercado, "id_origem": f"{i}:{i + 1}", "nome": f"Produto {i}", "marca": "Marca", "ean": f"78960067{i:05d}",
            "categoria": "Mercearia > Grãos", "preco_varejo": 10.0 + i, "preco_atacado": 9.0 + i, "quantidade_atacado": 6,
            "uf_cobertura": "MG", "termo": termo, "peso_variavel": False}


# ============================== regras de status ==============================

def teste_avaliar_coleta():
    assert ab.avaliar_coleta([], 100, []) == "falhou"                              # nada veio
    assert ab.avaliar_coleta([1], 100, []) == "ok"
    assert ab.avaliar_coleta([1], 100, ["a"] * 10) == "parcial"                    # 10% dos termos
    assert ab.avaliar_coleta([1], 100, ["a"] * 11) == "falhou"
    assert ab.avaliar_coleta([1], 11, ["a"]) == "parcial"
    assert ab.avaliar_coleta([1], 11, ["a", "b"]) == "falhou"
    assert ab.avaliar_coleta([1], 5, ["a"]) == "parcial"                           # sempre se tolera pelo menos 1
    assert ab.avaliar_coleta([1], 100, ["a"], tolerancia=0) == "falhou"            # modo antigo: tudo ou nada
    assert ab.avaliar_coleta([1], 100, [], tolerancia=0) == "ok"


# ============================== linhas e gravação ==============================

def teste_para_o_banco():
    linha = ab.para_o_banco(linha_api("Supernosso", 1))
    assert set(linha) == set(ab.COLUNAS_BASE) | set(ab.COLUNAS_NOVAS)
    assert "peso_variavel" not in linha and linha["texto_original"] is None
    assert linha["id_origem"] == "1:2" and linha["termo"] == "arroz" and linha["ean"] == "7896006700001"
    antiga = ab.para_o_banco(linha_api("Supernosso", 1), com_colunas_novas=False)
    assert set(antiga) == set(ab.COLUNAS_BASE)                                      # sem as colunas novas do SQL
    robo = ab.para_o_banco({"supermercado": "Super ABC", "nome": "Arroz", "preco_varejo": 5.0, "preco_atacado": None, "quantidade_atacado": None, "uf_cobertura": "MG"})
    assert robo["preco_atacado"] == 5.0 and robo["quantidade_atacado"] == 1         # colunas NOT NULL
    assert robo["ean"] is None and robo["termo"] is None


def teste_filtro_termos_mantidos():
    assert ab.filtro_termos_mantidos(["arroz", "molho de tomate"]) == 'termo.is.null,termo.not.in.("arroz","molho de tomate")'
    assert ab.filtro_termos_mantidos(['a"b']) == 'termo.is.null,termo.not.in.("ab")'


def teste_gravar_mercado():
    produtos = [linha_api("Supernosso", i) for i in range(450)]
    banco = BancoFalso()
    ab.gravar_mercado(banco, "Supernosso", produtos, "2026-11-05T12:00:00+00:00")
    assert [len(ch[2]) for ch in banco.inserts()] == [200, 200, 50]
    assert banco.chamadas[-1][1] == "delete"                                        # só apaga depois de gravar tudo
    assert banco.deletes()[0][3] == [("eq", "supermercado", "Supernosso"), ("lt", "atualizado_em", "2026-11-05T12:00:00+00:00")]

    banco = BancoFalso()                                                            # termos que falharam: as linhas antigas deles ficam
    ab.gravar_mercado(banco, "Supernosso", produtos[:3], "agora", termos_mantidos=["arroz", "sal"])
    assert banco.deletes()[0][3][-1] == ("or", 'termo.is.null,termo.not.in.("arroz","sal")')

    banco = BancoFalso()                                                            # sem as colunas novas: nada de termo
    ab.gravar_mercado(banco, "Supernosso", produtos[:3], "agora", com_colunas_novas=False, termos_mantidos=["arroz"])
    assert set(banco.inserts()[0][2][0]) == set(ab.COLUNAS_BASE)
    assert all(f[0] != "or" for f in banco.deletes()[0][3])


def teste_colunas_novas_existem():
    assert ab.colunas_novas_existem(BancoFalso(tem_colunas_novas=True)) is True
    assert ab.colunas_novas_existem(BancoFalso(tem_colunas_novas=False)) is False

    class BancoQuebrado:
        def table(self, nome):
            raise ConnectionError("sem rede")

    try:
        ab.colunas_novas_existem(BancoQuebrado())
    except ConnectionError:
        return
    raise AssertionError("erro de rede não pode virar 'coluna não existe'")


def teste_unidade_so_chega_ao_banco_normalizada():
    base = linha_api("Supernosso", 1)
    for bruto, esperado in (("kg", "kg"), ("KG", "kg"), (" un ", "un"), ("und", "un"), ("g", None), ("l", None), ("cx", None), ("", None), (None, None)):
        assert ab.para_o_banco({**base, "unidade": bruto}, com_unidade=True)["unidade"] == esperado, bruto            # uma unidade desconhecida vira vazio
    assert "unidade" not in ab.para_o_banco({**base, "unidade": "kg"})                                                   # sem pedir, a coluna não é enviada (banco sem o SQL)
    assert ab.para_o_banco(base, com_unidade=True)["unidade"] is None                                                    # robô do Super ABC: sem unidade
    assert set(ab.para_o_banco(base, com_unidade=True)) == set(ab.COLUNAS_BASE) | set(ab.COLUNAS_NOVAS) | {"unidade"}
    assert ab.COLUNAS_DA_UNIDADE == ("unidade",) and "unidade" not in ab.COLUNAS_NOVAS                                    # detectada à parte das cinco colunas


def teste_coluna_unidade_existe():
    assert ab.coluna_unidade_existe(BancoFalso()) is True
    assert ab.coluna_unidade_existe(BancoFalso(tem_unidade=False)) is False
    assert ab.colunas_novas_existem(BancoFalso(tem_unidade=False)) is True              # uma não depende da outra

    class BancoQuebrado:
        def table(self, nome):
            raise ConnectionError("sem rede")

    try:
        ab.coluna_unidade_existe(BancoQuebrado())
    except ConnectionError:
        return
    raise AssertionError("erro de rede não pode virar 'coluna não existe'")


# ============================== coleta pelo robô e pela API ==============================

def teste_coletar_por_robo():
    ativos, maximo, chamadas = [0], [0], []

    async def super_abc(texto):
        chamadas.append(texto)
        ativos[0] += 1
        maximo[0] = max(maximo[0], ativos[0])
        await asyncio.sleep(0.01)
        ativos[0] -= 1
        if texto == "feijão":
            raise FalhaNoRobo("Super ABC", "busca não realizada")
        if texto == "papinha":
            return []                                                              # o site não vende: não é falha
        if texto == "óleo":
            return [{"nome": "Óleo de Soja Liza 900ml", "preco_varejo": 7.0}, {"nome": "Shampoo com Óleo de Argan", "preco_varejo": 20.0}]
        return [{"nome": f"{texto.title()} Camil 1kg", "preco_varejo": 5.0}, {"nome": "Produto repetido", "preco_varejo": 1.0}]

    termos = [{"termo": "arroz", "nome_inclui": [], "nome_exclui": []}, {"termo": "feijão"}, {"termo": "papinha"},
              {"termo": "óleo", "nome_inclui": ["^oleo\\b"]}, {"termo": "sal"}]
    anterior = ab.ROBOS
    ab.ROBOS = {"Super ABC": super_abc}
    try:
        coleta = asyncio.run(ab.coletar_por_robo("Super ABC", ab.alvos_da_lista(termos), paralelo=2, segunda_rodada=False))
    finally:
        ab.ROBOS = anterior
    assert maximo[0] <= 2 and len(chamadas) == 5                                    # nunca mais de 2 navegadores juntos
    assert coleta.termos_total == 5 and coleta.termos_falhos == ["feijão"] and "busca não realizada" in coleta.motivos[0]
    nomes = [p["nome"] for p in coleta.produtos]
    assert "Shampoo com Óleo de Argan" not in nomes and "Óleo de Soja Liza 900ml" in nomes     # o filtro do termo vale para o robô
    assert nomes.count("Produto repetido") == 1                                     # repetido entre termos entra uma vez
    assert all(p["supermercado"] == "Super ABC" and p["uf_cobertura"] == "MG" and p["termo"] for p in coleta.produtos)


def teste_termo_com_mais_de_uma_busca_conta_uma_vez():
    termos = [{"termo": "sal", "consultas_robo": ["sal refinado", "sal grosso"]}, {"termo": "arroz"}]
    assert ab.alvos_da_lista(termos) == [("sal", "sal refinado", termos[0]), ("sal", "sal grosso", termos[0]), ("arroz", "arroz", termos[1])]

    async def robo(texto):
        if texto.startswith("sal"):
            raise FalhaNoRobo("Super ABC", f"caiu em {texto}")
        return [{"nome": f"{texto} x", "preco_varejo": 1.0}]

    anterior = ab.ROBOS
    ab.ROBOS = {"Super ABC": robo}
    try:
        coleta = asyncio.run(ab.coletar_por_robo("Super ABC", ab.alvos_da_lista(termos)))
    finally:
        ab.ROBOS = anterior
    assert coleta.termos_total == 2 and coleta.termos_falhos == ["sal"]            # o termo falha uma vez, mesmo com duas buscas caídas
    assert len(coleta.motivos) == 2 and len(coleta.produtos) == 1


def teste_coletar_por_robo_modo_antigo_nao_filtra_nem_marca_termo():
    async def robo(texto):
        return [{"nome": f"{texto} qualquer", "preco_varejo": 3.0}]

    anterior = ab.ROBOS
    ab.ROBOS = {"Atacadao": robo}
    try:
        coleta = asyncio.run(ab.coletar_por_robo("Atacadao", [("Arroz", "Arroz", None)], tolerancia=0))
    finally:
        ab.ROBOS = anterior
    assert coleta.produtos[0]["termo"] is None and coleta.tolerancia == 0


def teste_coletas_pela_api():
    def baixar_apoio(http, consulta):
        return [linha_api("Apoio Entrega", 1, consulta), linha_api("Apoio Entrega", 2, consulta)]

    def baixar_supernosso(http, consulta):
        if consulta == "feijão":
            raise c.ErroDeColeta("HTTP 503")
        return [linha_api("Supernosso", 1, consulta)]

    termos = [{"termo": "arroz"}, {"termo": "feijão"}, {"termo": "sal"}]
    coletas = ab.coletas_pela_api(["Apoio Entrega", "Supernosso"], termos, 100, http=object(),
                                  baixadores={"Apoio Entrega": baixar_apoio, "Supernosso": baixar_supernosso})
    apoio, supernosso = coletas["Apoio Entrega"], coletas["Supernosso"]
    assert len(apoio.produtos) == 2 and apoio.termos_falhos == [] and apoio.termos_total == 3     # o mesmo produto em 3 termos entra uma vez
    assert supernosso.termos_falhos == ["feijão"] and "HTTP 503" in supernosso.motivos[0] and len(supernosso.produtos) == 1


# ============================== o disjuntor e a segunda rodada ==============================

def alvos_de(n):
    termos = [{"termo": f"termo{i:03d}"} for i in range(n)]
    return ab.alvos_da_lista(termos)


def com_robo(robo, **opcoes):
    """Roda coletar_por_robo com um robô falso no lugar do Super ABC."""
    anterior = ab.ROBOS
    ab.ROBOS = {"Super ABC": robo}
    try:
        return asyncio.run(ab.coletar_por_robo("Super ABC", **opcoes))
    finally:
        ab.ROBOS = anterior


def teste_robo_fora_do_ar_nao_gasta_a_lista_inteira():
    chamadas = []

    async def robo(texto):
        chamadas.append(texto)
        raise FalhaNoRobo("Super ABC", "não consegui abrir a lista de unidades (Locator.click: Timeout 15000ms exceeded)")

    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        coleta = com_robo(robo, alvos=alvos_de(100), paralelo=1, segunda_rodada=False)
    assert len(chamadas) == 6                                       # e não 100 (no incidente de 18/11: 45 minutos perdidos)
    assert coleta.termos_total == 100 and len(coleta.termos_falhos) == 100 and coleta.produtos == []
    assert "Timeout 15000ms" in coleta.motivos[0] and not disjuntor.foi_pulado(coleta.motivos[0].split(": ", 1)[1])   # a primeira falha é a real
    assert sum(1 for m in coleta.motivos if "não tentado" in m) == 94
    assert saida.getvalue().count("⛔ Super ABC '") == 6 and "94 busca(s) não tentado" in saida.getvalue()   # o log não ganha 94 linhas iguais
    assert ab.avaliar_coleta(coleta.produtos, coleta.termos_total, coleta.termos_falhos, coleta.tolerancia) == "falhou"


def teste_com_varios_navegadores_o_disjuntor_ainda_poupa_a_lista():
    chamadas = []

    async def robo(texto):
        chamadas.append(texto)
        await asyncio.sleep(0.01)
        raise FalhaNoRobo("Super ABC", "caiu")

    with contextlib.redirect_stdout(io.StringIO()):
        com_robo(robo, alvos=alvos_de(100), paralelo=3, segunda_rodada=False)
    assert 6 <= len(chamadas) <= 8                                  # os que já estavam em andamento terminam; nenhum novo começa


def teste_robo_com_acerto_no_meio_nao_abre_o_disjuntor():
    async def robo(texto):
        if int(texto[-3:]) % 6 != 5:
            raise FalhaNoRobo("Super ABC", "caiu")
        return [{"nome": f"{texto} Camil 1kg", "preco_varejo": 5.0}]

    with contextlib.redirect_stdout(io.StringIO()):
        coleta = com_robo(robo, alvos=alvos_de(60), paralelo=1, segunda_rodada=False)
    assert len(coleta.termos_falhos) == 50 and len(coleta.produtos) == 10 and not any("não tentado" in m for m in coleta.motivos)


def teste_segunda_rodada_do_robo_recupera_o_que_falhou():
    vezes, pausas = {}, []

    async def robo(texto):
        vezes[texto] = vezes.get(texto, 0) + 1
        if texto in ("termo001", "termo003") and vezes[texto] == 1:
            raise FalhaNoRobo("Super ABC", "busca não realizada")
        return [{"nome": f"{texto} Camil 1kg", "preco_varejo": 5.0}]

    async def dormir(segundos):
        pausas.append(segundos)

    with contextlib.redirect_stdout(io.StringIO()):
        coleta = com_robo(robo, alvos=alvos_de(5), paralelo=2, pausa=30, dormir=dormir)
    assert coleta.termos_falhos == [] and coleta.motivos == [] and len(coleta.produtos) == 5      # a carga fica "ok", não "parcial"
    assert pausas == [30] and vezes["termo001"] == 2 and vezes["termo000"] == 1
    assert ab.avaliar_coleta(coleta.produtos, coleta.termos_total, coleta.termos_falhos, coleta.tolerancia) == "ok"


def teste_busca_que_falha_nas_duas_rodadas_continua_falha():
    vezes = {}

    async def robo(texto):
        vezes[texto] = vezes.get(texto, 0) + 1
        if texto == "termo002":
            raise FalhaNoRobo("Super ABC", "busca não realizada")
        return [{"nome": f"{texto} Camil 1kg", "preco_varejo": 5.0}]

    with contextlib.redirect_stdout(io.StringIO()):
        coleta = com_robo(robo, alvos=alvos_de(5), paralelo=2, pausa=0)
    assert vezes["termo002"] == 2 and coleta.termos_falhos == ["termo002"] and len(coleta.produtos) == 4      # tenta duas vezes, não três
    assert len(coleta.motivos) == 1 and "busca não realizada" in coleta.motivos[0]
    assert ab.avaliar_coleta(coleta.produtos, coleta.termos_total, coleta.termos_falhos, coleta.tolerancia) == "parcial"


def teste_sem_falha_o_robo_nao_espera_nada():
    pausas = []

    async def robo(texto):
        return [{"nome": f"{texto} Camil 1kg", "preco_varejo": 5.0}]

    async def dormir(segundos):
        pausas.append(segundos)

    with contextlib.redirect_stdout(io.StringIO()):
        coleta = com_robo(robo, alvos=alvos_de(4), paralelo=2, dormir=dormir)
    assert pausas == [] and coleta.termos_falhos == [] and len(coleta.produtos) == 4


def teste_robo_que_volta_na_segunda_rodada_completa_a_coleta():
    chamadas = []

    async def robo(texto):
        chamadas.append(texto)
        if len(chamadas) <= 6:                                      # o site some por um momento, depois volta
            raise FalhaNoRobo("Super ABC", "caiu")
        return [{"nome": f"{texto} Camil 1kg", "preco_varejo": 5.0}]

    with contextlib.redirect_stdout(io.StringIO()):
        coleta = com_robo(robo, alvos=alvos_de(100), paralelo=1, pausa=0)
    assert coleta.termos_falhos == [] and len(coleta.produtos) == 100 and len(chamadas) == 106
    assert ab.avaliar_coleta(coleta.produtos, coleta.termos_total, coleta.termos_falhos, coleta.tolerancia) == "ok"


def teste_robo_que_continua_fora_do_ar_gasta_so_duas_rodadas_curtas():
    chamadas = []

    async def robo(texto):
        chamadas.append(texto)
        raise FalhaNoRobo("Super ABC", "caiu")

    with contextlib.redirect_stdout(io.StringIO()):
        coleta = com_robo(robo, alvos=alvos_de(100), paralelo=1, pausa=0)
    assert len(chamadas) == 12 and len(coleta.termos_falhos) == 100 and coleta.produtos == []


def teste_erro_inesperado_do_robo_tambem_conta_para_o_disjuntor():
    chamadas = []

    async def robo(texto):
        chamadas.append(texto)
        raise ValueError("estourou")

    with contextlib.redirect_stdout(io.StringIO()):
        coleta = com_robo(robo, alvos=alvos_de(50), paralelo=1, segunda_rodada=False)
    assert len(chamadas) == 6 and "erro inesperado" in coleta.motivos[0]


def teste_coletas_pela_api_com_mercado_fora_do_ar():
    def baixar_atacadao(http, consulta):
        raise c.ErroDeColeta(f"HTTP 403 em https://www.atacadao.com.br/api/graphql?termo={consulta}")

    def baixar_apoio(http, consulta):
        return [linha_api("Apoio Entrega", 1, consulta)]

    termos = [{"termo": f"termo{i:03d}"} for i in range(100)]
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        coletas = ab.coletas_pela_api(["Apoio Entrega", "Atacadao"], termos, 100, http=object(),
                                      baixadores={"Apoio Entrega": baixar_apoio, "Atacadao": baixar_atacadao})
    atacadao = coletas["Atacadao"]
    assert atacadao.termos_total == 100 and len(atacadao.termos_falhos) == 100 and atacadao.produtos == []
    assert "HTTP 403" in atacadao.motivos[0] and "não tentado" not in atacadao.motivos[0]
    assert saida.getvalue().count("⛔ Atacadao 'termo") == 6 and "⛔ Atacadao: 94 termo(s) não tentado" in saida.getvalue()
    assert coletas["Apoio Entrega"].termos_falhos == [] and len(coletas["Apoio Entrega"].produtos) == 1     # o outro mercado segue
    assert ab.avaliar_coleta(atacadao.produtos, atacadao.termos_total, atacadao.termos_falhos, atacadao.tolerancia) == "falhou"


def teste_o_limite_de_falhas_do_robo_vem_do_chamador():
    for limite, esperado in ((2, 2), (0, 20)):                      # 0 desliga o disjuntor
        chamadas = []

        async def robo(texto, chamadas=chamadas):
            chamadas.append(texto)
            raise FalhaNoRobo("Super ABC", "caiu")

        with contextlib.redirect_stdout(io.StringIO()):
            com_robo(robo, alvos=alvos_de(20), paralelo=1, limite_de_falhas=limite, segunda_rodada=False)
        assert len(chamadas) == esperado, (limite, len(chamadas))


def teste_coletas_pela_api_repassa_as_opcoes_da_coleta():
    chamadas, pausas = [], []

    def baixar(http, consulta):
        chamadas.append(consulta)
        raise c.ErroDeColeta("caiu")

    termos = [{"termo": f"termo{i}"} for i in range(10)]
    with contextlib.redirect_stdout(io.StringIO()):
        ab.coletas_pela_api(["Atacadao"], termos, 100, http=object(), baixadores={"Atacadao": baixar}, limite_de_falhas=2, segunda_rodada=False)
        assert len(chamadas) == 2                                   # o limite e o "sem segunda rodada" chegaram ao coletor
        ab.coletas_pela_api(["Atacadao"], termos, 100, http=object(), baixadores={"Atacadao": baixar}, limite_de_falhas=2, pausa=33, dormir=pausas.append)
    assert len(chamadas) == 2 + 4 and pausas == [33]


# ============================== a gravação de ponta a ponta ==============================

def com_historico_falso(funcao):
    """Troca anotar_historico por um que só anota as chamadas."""
    def teste():
        anteriores = ab.anotar_historico
        chamadas = []
        ab.anotar_historico = lambda banco, mercado, dia, produtos=None, falha=None, status="ok": chamadas.append((mercado, status if falha is None else "falha", falha))
        try:
            funcao(chamadas)
        finally:
            ab.anotar_historico = anteriores
    teste.__name__ = funcao.__name__
    return teste


def coleta_de(mercado, n_produtos, termos_total, falhos=(), tolerancia=0.10):
    return ab.Coleta(mercado, [linha_api(mercado, i) for i in range(n_produtos)], termos_total, list(falhos),
                     [f"'{t}': caiu" for t in falhos], tolerancia)


@com_historico_falso
def teste_gravar_coletas_ok_parcial_e_falha(historico):
    banco = BancoFalso()
    coletas = {"Apoio Entrega": coleta_de("Apoio Entrega", 5, 100),
               "Atacadao": coleta_de("Atacadao", 5, 100, falhos=["arroz", "sal"]),                    # parcial
               "Supernosso": coleta_de("Supernosso", 5, 100, falhos=[f"t{i}" for i in range(11)]),     # falhas demais
               "Super ABC": coleta_de("Super ABC", 0, 100)}                                            # nada veio
    situacoes = ab.gravar_coletas(banco, coletas, "inicio", None)
    assert situacoes == {"Apoio Entrega": "atualizado", "Atacadao": "parcial", "Supernosso": "falhou", "Super ABC": "falhou"}
    assert [coleta.status for coleta in coletas.values()] == ["ok", "parcial", "falhou", "falhou"]
    assert len(banco.inserts()) == 2                                                                   # só Apoio e Atacadão gravaram
    apagar = {ch[3][0][2]: ch[3] for ch in banco.deletes()}
    assert all(f[0] != "or" for f in apagar["Apoio Entrega"])
    assert apagar["Atacadao"][-1] == ("or", 'termo.is.null,termo.not.in.("arroz","sal")')              # mantém as linhas antigas dos termos que falharam
    assert historico == [("Apoio Entrega", "ok", None), ("Atacadao", "parcial", None), ("Supernosso", "falha", "'t0': caiu"),
                         ("Super ABC", "falha", "nenhum produto coletado")]


@com_historico_falso
def teste_gravar_coletas_sem_colunas_novas(historico):
    banco = BancoFalso(tem_colunas_novas=False)
    coletas = {"Apoio Entrega": coleta_de("Apoio Entrega", 5, 100), "Atacadao": coleta_de("Atacadao", 5, 100, falhos=["arroz"])}
    situacoes = ab.gravar_coletas(banco, coletas, "inicio", None)
    assert situacoes == {"Apoio Entrega": "atualizado", "Atacadao": "falhou"}                          # parcial exige as colunas: senão apagaria os termos que falharam
    assert "colunas novas" in coletas["Atacadao"].motivos[-1]
    assert set(banco.inserts()[0][2][0]) == set(ab.COLUNAS_BASE) and len(banco.inserts()) == 1


@com_historico_falso
def teste_gravar_coletas_grava_a_unidade_quando_a_coluna_existe(historico):
    coleta = coleta_de("Supernosso", 3, 100)
    coleta.produtos[0]["unidade"], coleta.produtos[1]["unidade"] = "kg", "un"          # o terceiro vem sem unidade (como o robô)
    banco = BancoFalso()
    assert ab.gravar_coletas(banco, {"Supernosso": coleta}, "inicio", None) == {"Supernosso": "atualizado"}
    assert [l["unidade"] for l in banco.inserts()[0][2]] == ["kg", "un", None]


@com_historico_falso
def teste_gravar_coletas_sem_a_coluna_unidade_segue_gravando_o_resto(historico):
    import contextlib
    import io
    banco = BancoFalso(tem_colunas_novas=True, tem_unidade=False)
    coletas = {"Apoio Entrega": coleta_de("Apoio Entrega", 3, 100), "Atacadao": coleta_de("Atacadao", 3, 100, falhos=["arroz"])}
    for c in coletas.values():
        c.produtos[0]["unidade"] = "kg"
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        situacoes = ab.gravar_coletas(banco, coletas, "inicio", None)
    assert situacoes == {"Apoio Entrega": "atualizado", "Atacadao": "parcial"}         # a falta da coluna não derruba nem a coleta parcial
    for insercao in banco.inserts():
        assert all("unidade" not in linha and set(linha) == set(ab.COLUNAS_BASE) | set(ab.COLUNAS_NOVAS) for linha in insercao[2])
    assert "docs/sql/coluna_unidade.sql" in saida.getvalue() and saida.getvalue().count("::notice") == 1


@com_historico_falso
def teste_gravar_coletas_sem_gravar_e_erro_ao_gravar(historico):
    coletas = {"Apoio Entrega": coleta_de("Apoio Entrega", 5, 100), "Atacadao": coleta_de("Atacadao", 5, 100, falhos=["arroz"])}
    assert ab.gravar_coletas(None, coletas, "inicio", None) == {"Apoio Entrega": "nao_gravado", "Atacadao": "nao_gravado"}
    assert [c.status for c in coletas.values()] == ["ok", "parcial"] and historico == []                # teste sem gravar não toca no histórico

    banco = BancoFalso(erro_ao_inserir=True)
    coletas = {"Apoio Entrega": coleta_de("Apoio Entrega", 5, 100)}
    assert ab.gravar_coletas(banco, coletas, "inicio", None) == {"Apoio Entrega": "falhou"}
    assert "erro ao gravar no banco" in coletas["Apoio Entrega"].motivos[0] and banco.deletes() == []  # falhou no insert: nada foi apagado
    assert historico == [("Apoio Entrega", "falha", coletas["Apoio Entrega"].motivos[0])]


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
