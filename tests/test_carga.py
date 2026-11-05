"""Testes da carga diária (alimentar_banco.py), sem rede, sem navegador e sem banco.

Rodar com:  python tests/test_carga.py   (precisa das bibliotecas do requirements.txt)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import alimentar_banco as ab  # noqa: E402
import coletor_vtex as c  # noqa: E402
from robos_comum import FalhaNoRobo  # noqa: E402


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
        if self.banco.erro_ao_inserir and self.op == "insert":
            raise RuntimeError("insert caiu")
        self.banco.chamadas.append((self.tabela, self.op, self.dados if self.op == "insert" else None, self.filtros))
        return Resposta()


class BancoFalso:
    def __init__(self, tem_colunas_novas=True, erro_ao_inserir=False):
        self.chamadas, self.tem_colunas_novas, self.erro_ao_inserir = [], tem_colunas_novas, erro_ao_inserir

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
        coleta = asyncio.run(ab.coletar_por_robo("Super ABC", ab.alvos_da_lista(termos), paralelo=2))
    finally:
        ab.ROBOS = anterior
    assert maximo[0] <= 2 and len(chamadas) == 5                                    # nunca mais de 2 navegadores juntos
    assert coleta.termos_total == 5 and coleta.termos_falhos == ["feijão"] and "busca não realizada" in coleta.motivos[0]
    nomes = [p["nome"] for p in coleta.produtos]
    assert "Shampoo com Óleo de Argan" not in nomes and "Óleo de Soja Liza 900ml" in nomes     # o filtro do termo vale para o robô
    assert nomes.count("Produto repetido") == 1                                     # repetido entre termos entra uma vez
    assert all(p["supermercado"] == "Super ABC" and p["uf_cobertura"] == "MG" and p["termo"] for p in coleta.produtos)


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
