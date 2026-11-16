"""Testes do selo "caiu X% em 7 dias" (quedas.py e a parte dele em api_supabase.py), sem rede e sem banco de verdade.

Rodar com:  python tests/test_quedas.py   (precisa de fastapi, uvicorn, supabase e thefuzz, do requirements.txt)
"""
import contextlib
import io
import os
import re
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("SUPABASE_KEY", "chave-falsa-so-para-importar")      # a API cria o cliente ao importar
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import api_supabase as api  # noqa: E402
import busca  # noqa: E402
import quedas  # noqa: E402
from historico import chave_origem  # noqa: E402

CARGA_DE_HOJE = "2026-11-16T10:44:50.134498+00:00"          # 07:44 de 16/11 em Brasília
DIA_DE_ANTES = date(2026, 11, 9)                             # 7 dias antes de 16/11


# ============================== um banco falso que se comporta como o PostgREST ==============================

class Resposta:
    def __init__(self, data):
        self.data = data


class ConsultaFalsa:
    """select/eq/lte/gte/in_/order/range/execute sobre uma lista de linhas. Como no SQL, comparar com vazio (None) nunca casa."""

    def __init__(self, banco, tabela):
        self.banco, self.tabela, self.filtros, self.ordem, self.inicio, self.fim = banco, tabela, [], [], 0, 10 ** 9

    def select(self, colunas):
        self.banco.chamadas.append(("select", self.tabela, colunas))
        return self

    def eq(self, coluna, valor):
        self.filtros.append(lambda l: l.get(coluna) == valor)
        self.banco.chamadas.append(("eq", self.tabela, coluna, valor))
        return self

    def lte(self, coluna, valor):
        self.filtros.append(lambda l: l.get(coluna) is not None and str(l[coluna]) <= valor)
        self.banco.chamadas.append(("lte", self.tabela, coluna, valor))
        return self

    def gte(self, coluna, valor):
        self.filtros.append(lambda l: l.get(coluna) is not None and str(l[coluna]) >= valor)
        self.banco.chamadas.append(("gte", self.tabela, coluna, valor))
        return self

    def in_(self, coluna, valores):
        self.filtros.append(lambda l: l.get(coluna) in valores)
        return self

    def order(self, coluna):
        self.ordem.append(coluna)
        return self

    def range(self, inicio, fim):
        self.inicio, self.fim = inicio, fim
        self.banco.chamadas.append(("range", self.tabela, inicio, fim))
        return self

    def execute(self):
        if self.tabela == "precos" and self.banco.falha_no_historico:
            raise RuntimeError("o histórico está fora do ar")
        linhas = [l for l in self.banco.tabelas[self.tabela] if all(f(l) for f in self.filtros)]
        for coluna in reversed(self.ordem):
            linhas.sort(key=lambda l: l[coluna])
        return Resposta(linhas[self.inicio:self.fim + 1])


class BancoFalso:
    def __init__(self, produtos=(), precos=(), falha_no_historico=False):
        self.tabelas = {"produtos": list(produtos), "precos": list(precos)}
        self.falha_no_historico, self.chamadas = falha_no_historico, []

    def table(self, nome):
        return ConsultaFalsa(self, nome)

    def consultas_ao_historico(self):
        return [c for c in self.chamadas if c[0] == "select" and c[1] == "precos"]


def capturar(funcao):
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        resultado = funcao()
    return resultado, saida.getvalue()


# ============================== os dados do cenário ==============================
# Cada produto tem a linha do catálogo do dia (`produtos`) e o histórico dele (`precos`), como o banco guardaria.

def intervalo(catalogo_id, mercado, chave, desde, ate, varejo, praca="betim"):
    return {"catalogo_id": catalogo_id, "praca": praca, "desde": desde, "ate": ate, "preco_varejo": varejo,
            "catalogo": {"supermercado": mercado, "chave_origem": chave}}


def produto(id_, mercado, nome, varejo, id_origem=None, ean=None):
    ean = ean or f"7890000000{id_:03d}"                                      # um código de barras por produto: cada um fica no seu grupo
    return {"id": id_, "supermercado": mercado, "nome": nome, "preco_varejo": varejo, "id_origem": id_origem, "ean": ean,
            "termo": "margarina", "uf_cobertura": "MG", "atualizado_em": CARGA_DE_HOJE}


NOME_ABC = "Margarina Qualy Cremosa 500g"

PRODUTOS = [
    produto(1, "Supernosso", "Margarina Becel 500g", 7.99, id_origem="11:1"),        # 14,99 -> 7,99: caiu 47%
    produto(2, "Atacadão", "Margarina Delícia 500g", 4.99, id_origem="22:1"),        # não mudou desde 04/11
    produto(3, "Apoio Entrega", "Margarina Doriana 500g", 8.50, id_origem="33:1"),   # 10,00 -> 9,00 -> 8,50: caiu 15% (conta o preço de 09/11)
    produto(4, "Super ABC", NOME_ABC, 19.50),                                         # sem id do mercado: histórico por nome; 20,00 -> 19,50 = 2,5%: pouco
    produto(5, "Supernosso", "Margarina Claybom 500g", 6.00, id_origem="55:1"),      # subiu
    produto(6, "Atacadão", "Margarina Primor 500g", 10.00, id_origem="66:1"),        # 10 -> 8 -> 10: voltou ao mesmo preço
    produto(7, "Apoio Entrega", "Margarina Vigor 500g", 3.00, id_origem="77:1"),     # produto novo (14/11): nada de 7 dias atrás
    produto(8, "Supernosso", "Margarina Aurora 500g", 9.50, id_origem="88:1"),       # 10,00 -> 9,50: caiu 5% (no limite)
    produto(9, "Atacadão", "Margarina Soya 500g", 9.51, id_origem="99:1"),           # 10,00 -> 9,51: caiu 4,9% (abaixo do limite)
]

PRECOS = [
    intervalo(1, "Supernosso", "v:11:1", "2026-11-04", "2026-11-11", 14.99), intervalo(1, "Supernosso", "v:11:1", "2026-11-12", None, 7.99),
    intervalo(2, "Atacadão", "v:22:1", "2026-11-04", None, 4.99),
    intervalo(3, "Apoio Entrega", "v:33:1", "2026-11-04", "2026-11-10", 10.00), intervalo(3, "Apoio Entrega", "v:33:1", "2026-11-11", "2026-11-14", 9.00),
    intervalo(3, "Apoio Entrega", "v:33:1", "2026-11-15", None, 8.50),
    intervalo(4, "Super ABC", chave_origem(NOME_ABC), "2026-11-04", "2026-11-13", 20.00), intervalo(4, "Super ABC", chave_origem(NOME_ABC), "2026-11-14", None, 19.50),
    intervalo(5, "Supernosso", "v:55:1", "2026-11-04", "2026-11-12", 5.00), intervalo(5, "Supernosso", "v:55:1", "2026-11-13", None, 6.00),
    intervalo(6, "Atacadão", "v:66:1", "2026-11-04", "2026-11-10", 10.00), intervalo(6, "Atacadão", "v:66:1", "2026-11-11", "2026-11-13", 8.00),
    intervalo(6, "Atacadão", "v:66:1", "2026-11-14", None, 10.00),
    intervalo(7, "Apoio Entrega", "v:77:1", "2026-11-14", None, 3.00),
    intervalo(8, "Supernosso", "v:88:1", "2026-11-04", "2026-11-14", 10.00), intervalo(8, "Supernosso", "v:88:1", "2026-11-15", None, 9.50),
    intervalo(9, "Atacadão", "v:99:1", "2026-11-04", "2026-11-14", 10.00), intervalo(9, "Atacadão", "v:99:1", "2026-11-15", None, 9.51),
    # outra praça (não é a da coleta): não pode entrar na conta
    intervalo(1, "Supernosso", "v:11:1", "2026-11-04", "2026-11-11", 99.00, praca="outra"),
]


def banco_do_cenario(**kw):
    return BancoFalso([dict(p) for p in PRODUTOS], [dict(p) for p in PRECOS], **kw)


def com_catalogo_novo():
    api._quedas = quedas.QuedasDoHistorico()


# ============================== as regras ==============================

def teste_dia_dos_dados_e_o_de_brasilia():
    um = lambda momento: [{"atualizado_em": momento}]
    assert quedas.dia_dos_dados(um("2026-11-16T10:44:50.134498+00:00")) == date(2026, 11, 16)
    assert quedas.dia_dos_dados(um("2026-11-16T02:59:59+00:00")) == date(2026, 11, 15)          # ainda é a noite de 15/11 em Brasília
    assert quedas.dia_dos_dados(um("2026-11-16T03:00:00Z")) == date(2026, 11, 16)
    assert quedas.dia_dos_dados(um("2026-11-16T04:00:00")) == date(2026, 11, 16)               # sem fuso vale como UTC
    misturado = [{"atualizado_em": "2026-11-15T10:00:00+00:00"}, {"atualizado_em": None}, {}, {"atualizado_em": "lixo"}, {"atualizado_em": "2026-11-16T10:00:00+00:00"}]
    assert quedas.dia_dos_dados(misturado) == date(2026, 11, 16)                                # vale a carga mais nova; o que não dá para ler é ignorado
    assert quedas.dia_dos_dados([{}]) is None and quedas.dia_dos_dados([]) is None


def teste_marcar_quedas_regras():
    antes = {("Supernosso", "v:1:1"): 14.99, ("Super ABC", chave_origem("Arroz Camil 5kg")): 20.0, ("Atacadão", "v:2:2"): 10.0, ("Apoio Entrega", "v:3:3"): 10.0,
             ("Apoio Entrega", "v:4:4"): 20.0, ("Apoio Entrega", "v:5:5"): 20.0, ("Apoio Entrega", "v:6:6"): 0.0}
    p = lambda mercado, nome, varejo, id_origem=None: {"supermercado": mercado, "nome": nome, "preco_varejo": varejo, "id_origem": id_origem}
    produtos = [
        p("Supernosso", "Becel", 7.99, "1:1"),                  # 46,7% -> 47
        p("Super ABC", "Arroz Camil 5kg", 15.0),                # chave pelo nome: -25%
        p("Atacadão", "Subiu", 11.0, "2:2"),
        p("Apoio Entrega", "Igual", 10.0, "3:3"),
        p("Apoio Entrega", "Cinco por cento", 19.0, "4:4"),     # exatamente 5%: entra
        p("Apoio Entrega", "Quase", 19.02, "5:5"),              # 4,9%: não
        p("Apoio Entrega", "Sem base", 1.0, "6:6"),             # preço de antes zerado: ignora
        p("Apoio Entrega", "Sem histórico", 1.0, "7:7"),
        {"supermercado": "Apoio Entrega", "nome": "Sem preço", "preco_varejo": None, "id_origem": "1:1"},
        {"nome": "Sem mercado", "preco_varejo": 1.0},
    ]
    n = quedas.marcar_quedas(produtos, antes)
    marcados = {x["nome"]: x.get("queda_preco") for x in produtos}
    assert n == 3, marcados
    assert marcados["Becel"] == {"preco_antes": 14.99, "percentual": 47, "dias": 7}
    assert marcados["Arroz Camil 5kg"] == {"preco_antes": 20.0, "percentual": 25, "dias": 7}
    assert marcados["Cinco por cento"]["percentual"] == 5
    for nome in ("Subiu", "Igual", "Quase", "Sem base", "Sem histórico", "Sem preço", "Sem mercado"):
        assert marcados.get(nome) is None, nome


def teste_so_os_valores_combinados_valem():
    assert quedas.JANELA_DIAS == 7 and quedas.LIMITE_QUEDA_PCT == 5.0
    carga = (RAIZ / "alimentar_banco.py").read_text(encoding="utf-8")
    praca_da_carga = re.search(r'^PRACA_BASE = "(\w+)"', carga, re.M).group(1)
    assert quedas.PRACA == praca_da_carga, "o selo e a carga precisam falar da mesma praça do histórico"


# ============================== a leitura do histórico ==============================

def teste_ler_precos_de_antes_traz_so_quem_mudou_depois():
    banco = banco_do_cenario()
    antes = quedas.ler_precos_de_antes(banco, DIA_DE_ANTES)
    assert antes == {
        ("Supernosso", "v:11:1"): 14.99,                                  # o preço de 09/11, não o de hoje
        ("Apoio Entrega", "v:33:1"): 10.00,                               # mudou duas vezes: vale o de 09/11
        ("Super ABC", chave_origem(NOME_ABC)): 20.00,
        ("Supernosso", "v:55:1"): 5.00,
        ("Atacadão", "v:66:1"): 10.00,
        ("Supernosso", "v:88:1"): 10.00,
        ("Atacadão", "v:99:1"): 10.00,
    }, antes
    # fora: o que não mudou (intervalo ainda aberto), o produto novo (não existia em 09/11) e o que é de outra praça
    assert ("Atacadão", "v:22:1") not in antes and ("Apoio Entrega", "v:77:1") not in antes
    consulta = [c for c in banco.chamadas if c[1] == "precos"]
    assert ("eq", "precos", "praca", "betim") in consulta
    assert ("lte", "precos", "desde", "2026-11-09") in consulta and ("gte", "precos", "ate", "2026-11-09") in consulta
    colunas = [c[2] for c in consulta if c[0] == "select"][0]
    assert "catalogo(supermercado,chave_origem)" in colunas and "preco_varejo" in colunas


def teste_ler_precos_de_antes_le_todas_as_paginas():
    linhas = [intervalo(i, "Apoio Entrega", f"v:{i}:1", "2026-11-01", "2026-11-12", 5.0) for i in range(1, 2301)]
    banco = BancoFalso(precos=linhas)
    antes = quedas.ler_precos_de_antes(banco, DIA_DE_ANTES)
    assert len(antes) == 2300
    assert [c[2:] for c in banco.chamadas if c[0] == "range"] == [(0, 999), (1000, 1999), (2000, 2999)]


def teste_historico_estranho_nao_derruba_a_leitura():
    banco = BancoFalso(precos=[
        {"catalogo_id": 1, "praca": "betim", "desde": "2026-11-01", "ate": "2026-11-12", "preco_varejo": 5.0, "catalogo": None},
        {"catalogo_id": 2, "praca": "betim", "desde": "2026-11-01", "ate": "2026-11-12", "preco_varejo": None, "catalogo": {"supermercado": "A", "chave_origem": "v:2"}},
        {"catalogo_id": 3, "praca": "betim", "desde": "2026-11-01", "ate": "2026-11-12", "preco_varejo": "7.50", "catalogo": {"supermercado": "A", "chave_origem": "v:3"}},
    ])
    assert quedas.ler_precos_de_antes(banco, DIA_DE_ANTES) == {("A", "v:3"): 7.5}                # texto numérico do banco vira número


# ============================== o catálogo da API ==============================

def com_banco(banco, funcao):
    anterior = api.supabase
    api.supabase = banco
    try:
        return funcao()
    finally:
        api.supabase = anterior


def por_id(catalogo):
    return {e.produto["id"]: e.produto for e in catalogo}


def teste_catalogo_leva_o_selo_nos_produtos_que_cairam():
    com_catalogo_novo()
    banco = banco_do_cenario()
    catalogo, log = capturar(lambda: com_banco(banco, lambda: api.baixar_catalogo("MG")))
    p = por_id(catalogo)
    assert p[1]["queda_preco"] == {"preco_antes": 14.99, "percentual": 47, "dias": 7}
    assert p[3]["queda_preco"] == {"preco_antes": 10.0, "percentual": 15, "dias": 7}
    assert p[8]["queda_preco"]["percentual"] == 5
    for id_ in (2, 4, 5, 6, 7, 9):
        assert "queda_preco" not in p[id_], id_                  # parado, queda pequena, subida, voltou ao mesmo preço, produto novo, abaixo do limite
    assert "3 de 9 produtos com queda de 5% ou mais em 7 dias" in log, log
    assert "7 produtos com preço diferente do de 09/11 (dados de 16/11)" in log, log


def teste_o_historico_so_e_lido_uma_vez_por_dia_de_carga():
    com_catalogo_novo()
    banco = banco_do_cenario()
    com_banco(banco, lambda: capturar(lambda: api.baixar_catalogo("MG")))
    leituras = len(banco.consultas_ao_historico())
    assert leituras == 1
    for _ in range(3):                                           # o catálogo recarrega de hora em hora, no mesmo dia de dados
        catalogo, _log = capturar(lambda: com_banco(banco, lambda: api.baixar_catalogo("MG")))
        assert "queda_preco" in por_id(catalogo)[1]              # e continua com os selos
    assert len(banco.consultas_ao_historico()) == leituras, "recarregar o catálogo no mesmo dia não pode reler o histórico"
    # dia novo de dados: lê de novo, agora para o dia 10/11
    for linha in banco.tabelas["produtos"]:
        linha["atualizado_em"] = "2026-11-17T10:44:50+00:00"
    com_banco(banco, lambda: capturar(lambda: api.baixar_catalogo("MG")))
    assert len(banco.consultas_ao_historico()) == leituras + 1
    assert ("lte", "precos", "desde", "2026-11-10") in banco.chamadas


def teste_historico_fora_do_ar_nao_derruba_o_catalogo_e_a_proxima_carga_tenta_de_novo():
    com_catalogo_novo()
    banco = banco_do_cenario(falha_no_historico=True)
    catalogo, log = capturar(lambda: com_banco(banco, lambda: api.baixar_catalogo("MG")))
    assert len(catalogo) == 9 and not any("queda_preco" in e.produto for e in catalogo)
    assert "histórico indisponível" in log and "o histórico está fora do ar" in log, log
    banco.falha_no_historico = False
    catalogo, _log = capturar(lambda: com_banco(banco, lambda: api.baixar_catalogo("MG")))
    assert por_id(catalogo)[1]["queda_preco"]["percentual"] == 47          # voltou: não ficou "preso" na falha
    assert len(banco.consultas_ao_historico()) == 2


def teste_catalogo_sem_data_nao_consulta_o_historico():
    com_catalogo_novo()
    banco = BancoFalso([{"id": 1, "supermercado": "A", "nome": "X", "preco_varejo": 1.0, "uf_cobertura": "MG"}])
    catalogo, _log = capturar(lambda: com_banco(banco, lambda: api.baixar_catalogo("MG")))
    assert len(catalogo) == 1 and banco.consultas_ao_historico() == []


def teste_a_resposta_de_comparar_leva_o_selo_na_opcao():
    com_catalogo_novo()
    catalogo, _log = capturar(lambda: com_banco(banco_do_cenario(), lambda: api.baixar_catalogo("MG")))
    anteriores = (api.carregar_catalogo, api.obter_uf_pelo_cep)
    api.carregar_catalogo = lambda uf: catalogo
    api.obter_uf_pelo_cep = lambda cep: "MG"
    try:
        r = api.buscar_e_comparar(cep="32607600", item="margarina")
    finally:
        api.carregar_catalogo, api.obter_uf_pelo_cep = anteriores
    opcoes = {o["id"]: o for g in r["carrinho_comparativo"] for o in g["opcoes_de_compra"]}
    assert opcoes[1]["queda_preco"] == {"preco_antes": 14.99, "percentual": 47, "dias": 7}
    assert "queda_preco" not in opcoes[2] and len(opcoes) == 9


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
