"""Testes da série de preços para o gráfico do site (serie_de_precos.py e o endpoint /historico de api_supabase.py), sem rede e sem banco.

Rodar com:  python tests/test_serie_de_precos.py   (precisa de fastapi, uvicorn, supabase e thefuzz, do requirements.txt)
"""
import contextlib
import io
import os
import sys
from pathlib import Path

os.environ.setdefault("SUPABASE_KEY", "chave-falsa-so-para-importar")      # a API cria o cliente ao importar
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import api_supabase as api  # noqa: E402
import serie_de_precos as sp  # noqa: E402
from fastapi import HTTPException  # noqa: E402


class Resposta:
    def __init__(self, data):
        self.data = data


class ConsultaFalsa:
    """Só o que serie_de_precos usa: select, eq, in_, order (várias) e execute."""

    def __init__(self, banco, tabela):
        self.banco, self.tabela, self.filtros, self.ordem = banco, tabela, [], []

    def select(self, colunas):
        return self

    def eq(self, coluna, valor):
        self.filtros.append(lambda l: l.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        valores = list(valores)
        self.filtros.append(lambda l: l.get(coluna) in valores)
        return self

    def order(self, coluna):
        self.ordem.append(coluna)
        return self

    def execute(self):
        self.banco.consultas.append(self.tabela)
        if self.banco.falha:
            raise RuntimeError("banco fora do ar")
        linhas = [dict(l) for l in self.banco.tabelas[self.tabela] if all(f(l) for f in self.filtros)]
        for coluna in reversed(self.ordem):
            linhas.sort(key=lambda l: l[coluna])
        return Resposta(linhas)


class BancoDeSeries:
    def __init__(self):
        self.tabelas = {
            "catalogo": [
                {"id": 1, "supermercado": "Atacadao", "chave_origem": "v:100:1"},
                {"id": 2, "supermercado": "Supernosso", "chave_origem": "v:100:1"},         # a mesma chave em outro mercado é outro produto
                {"id": 3, "supermercado": "Super ABC", "chave_origem": "n:0123456789abcdef0123"},
                {"id": 4, "supermercado": "Atacadao", "chave_origem": "v:200:2"},           # sem nenhum preço
            ],
            "precos": [
                {"catalogo_id": 1, "praca": "betim", "desde": "2026-11-12", "ate": None, "preco_varejo": 22.5},
                {"catalogo_id": 1, "praca": "betim", "desde": "2026-11-04", "ate": "2026-11-11", "preco_varejo": 24.99},     # fora de ordem de propósito
                {"catalogo_id": 1, "praca": "outra", "desde": "2026-11-04", "ate": None, "preco_varejo": 1.0},               # outra praça: não entra
                {"catalogo_id": 2, "praca": "betim", "desde": "2026-11-04", "ate": None, "preco_varejo": 24.99},
                {"catalogo_id": 3, "praca": "betim", "desde": "2026-11-06", "ate": "2026-11-09", "preco_varejo": 7.999},
                {"catalogo_id": 3, "praca": "betim", "desde": "2026-11-15", "ate": None, "preco_varejo": 8.5},                 # com buraco entre os dois
            ],
        }
        self.consultas, self.falha = [], False

    def table(self, nome):
        return ConsultaFalsa(self, nome)


# ---------------------------------------------------------------- o pedido

def teste_interpretar_aceita_o_pedido_certo():
    assert sp.interpretar("Atacadao|v:100:1") == [("Atacadao", "v:100:1")]
    assert sp.interpretar(" Atacadao|v:100:1 , Super ABC|n:0123456789abcdef0123 ") == [("Atacadao", "v:100:1"), ("Super ABC", "n:0123456789abcdef0123")]
    assert sp.interpretar("Atacadao|v:1:2,Atacadao|v:1:2,Supernosso|v:1:2") == [("Atacadao", "v:1:2"), ("Supernosso", "v:1:2")]      # repetido sai; a ordem fica
    assert sp.interpretar(",".join(f"Atacadao|v:{i}:1" for i in range(sp.MAXIMO_DE_PRODUTOS))) and True


def teste_interpretar_recusa_o_que_nao_e_chave():
    ruins = ["", "   ", None, "Atacadao", "Atacadao|", "|v:1:2", "Outro Mercado|v:1:2", "atacadao|v:1:2",                     # sem mercado, mercado desconhecido, caixa errada
             "Atacadao|1:2", "Atacadao|x:1:2", "Atacadao|v:", "Atacadao|v:1 2", "Atacadao|v:1;drop table precos", "Atacadao|v:1'2",
             "Atacadao|v:" + "1" * 101, "Atacadao|v:1:2|extra", "Atacadao|v:1/2", "Atacadao|v:1\n2"]
    for texto in ruins:
        try:
            sp.interpretar(texto)
        except sp.PedidoInvalido:
            continue
        raise AssertionError(f"devia recusar: {texto!r}")
    for vazio in ("", "   ", None):
        try:
            sp.interpretar(vazio)
        except sp.PedidoInvalido as erro:
            assert "informe os produtos" in str(erro), erro                          # o pedido vazio tem a sua mensagem, não a de "mal formado"
    try:
        sp.interpretar(",".join(f"Atacadao|v:{i}:1" for i in range(sp.MAXIMO_DE_PRODUTOS + 1)))
    except sp.PedidoInvalido as erro:
        assert "no máximo" in str(erro)
    else:
        raise AssertionError("mais de 8 produtos devia ser recusado")


# ---------------------------------------------------------------- a leitura

def teste_ler_series_traz_os_intervalos_em_ordem_e_so_da_praca_da_coleta():
    banco = BancoDeSeries()
    s = sp.ler_series(banco, [("Atacadao", "v:100:1"), ("Supernosso", "v:100:1"), ("Super ABC", "n:0123456789abcdef0123")])
    assert s[("Atacadao", "v:100:1")] == [{"desde": "2026-11-04", "ate": "2026-11-11", "preco": 24.99}, {"desde": "2026-11-12", "ate": None, "preco": 22.5}]
    assert s[("Supernosso", "v:100:1")] == [{"desde": "2026-11-04", "ate": None, "preco": 24.99}]                       # o id do Atacadão não vaza para o Supernosso
    assert s[("Super ABC", "n:0123456789abcdef0123")] == [{"desde": "2026-11-06", "ate": "2026-11-09", "preco": 8.0}, {"desde": "2026-11-15", "ate": None, "preco": 8.5}]
    assert all(i["preco"] != 1.0 for lista in s.values() for i in lista)                                                  # a praça "outra" ficou de fora


def teste_produto_sem_historico_ou_desconhecido_volta_com_lista_vazia():
    s = sp.ler_series(BancoDeSeries(), [("Atacadao", "v:200:2"), ("Atacadao", "v:999:9"), ("Apoio Entrega", "v:100:1")])
    assert s == {("Atacadao", "v:200:2"): [], ("Atacadao", "v:999:9"): [], ("Apoio Entrega", "v:100:1"): []}


def teste_duas_consultas_por_mercado_no_maximo():
    banco = BancoDeSeries()
    sp.ler_series(banco, [("Atacadao", "v:100:1"), ("Atacadao", "v:200:2"), ("Supernosso", "v:100:1")])
    assert banco.consultas.count("catalogo") == 2 and banco.consultas.count("precos") == 2        # um catálogo e um preços por mercado, não por produto


# ---------------------------------------------------------------- o cache

def teste_o_cache_nao_repete_a_consulta_ate_vencer():
    banco, agora = BancoDeSeries(), [1000.0]
    cache = sp.CacheDeSeries(validade=60, relogio=lambda: agora[0])
    pares = [("Atacadao", "v:100:1")]
    cache.obter(banco, pares)
    n = len(banco.consultas)
    cache.obter(banco, pares)
    agora[0] += 59
    cache.obter(banco, pares)
    assert len(banco.consultas) == n                                           # dentro da validade: nada de banco
    agora[0] += 2
    cache.obter(banco, pares)
    assert len(banco.consultas) > n                                            # venceu: consulta de novo


def teste_o_cache_so_busca_o_que_falta():
    banco = BancoDeSeries()
    cache = sp.CacheDeSeries()
    cache.obter(banco, [("Atacadao", "v:100:1")])
    banco.consultas.clear()
    s = cache.obter(banco, [("Atacadao", "v:100:1"), ("Supernosso", "v:100:1")])
    assert len(s[("Atacadao", "v:100:1")]) == 2 and len(s[("Supernosso", "v:100:1")]) == 1
    assert banco.consultas == ["catalogo", "precos"]                           # só o Supernosso, que não estava


def teste_banco_fora_do_ar_nao_guarda_nada_pela_metade():
    banco = BancoDeSeries()
    cache = sp.CacheDeSeries()
    banco.falha = True
    try:
        cache.obter(banco, [("Atacadao", "v:100:1")])
    except RuntimeError:
        pass
    else:
        raise AssertionError("o erro do banco tem de subir")
    banco.falha = False
    assert len(cache.obter(banco, [("Atacadao", "v:100:1")])[("Atacadao", "v:100:1")]) == 2     # e a próxima tentativa funciona


def teste_o_cache_tem_limite():
    cache = sp.CacheDeSeries(limite=3)
    banco = BancoDeSeries()
    for i in range(10):
        cache.obter(banco, [("Atacadao", f"v:{i}:1")])
    assert len(cache._guardado) == 3


# ---------------------------------------------------------------- o endpoint

def com_banco(banco, funcao):
    anterior, anterior_cache = api.supabase, api._series
    api.supabase, api._series = banco, sp.CacheDeSeries()
    try:
        return funcao()
    finally:
        api.supabase, api._series = anterior, anterior_cache


def teste_endpoint_devolve_hoje_e_os_produtos_na_ordem_pedida():
    r = com_banco(BancoDeSeries(), lambda: api.historico_de_precos("Supernosso|v:100:1,Atacadao|v:100:1"))
    assert len(r["hoje"]) == 10 and r["hoje"][4] == "-"                                                  # AAAA-MM-DD
    assert [(p["mercado"], p["chave"]) for p in r["produtos"]] == [("Supernosso", "v:100:1"), ("Atacadao", "v:100:1")]
    assert r["produtos"][1]["intervalos"][0] == {"desde": "2026-11-04", "ate": "2026-11-11", "preco": 24.99}


def teste_endpoint_recusa_pedido_ruim_com_400_e_nao_toca_no_banco():
    banco = BancoDeSeries()
    for ruim in ("", "lixo", "Atacadao|v:1;2", ",".join(f"Atacadao|v:{i}:1" for i in range(20))):
        try:
            com_banco(banco, lambda: api.historico_de_precos(ruim))
        except HTTPException as erro:
            assert erro.status_code == 400, ruim
        else:
            raise AssertionError(f"devia dar 400: {ruim!r}")
    assert banco.consultas == []


def teste_endpoint_com_banco_fora_do_ar_da_503_sem_vazar_o_erro():
    banco = BancoDeSeries()
    banco.falha = True
    saida = io.StringIO()
    try:
        with contextlib.redirect_stdout(saida):
            com_banco(banco, lambda: api.historico_de_precos("Atacadao|v:100:1"))
    except HTTPException as erro:
        assert erro.status_code == 503 and "indisponível" in erro.detail and "banco fora do ar" not in erro.detail
    else:
        raise AssertionError("devia dar 503")
    assert "Histórico de preços indisponível" in saida.getvalue()                      # o motivo vai para o log, não para quem pediu


def teste_o_catalogo_leva_a_chave_do_historico_em_cada_produto():
    from test_api_catalogo import BancoFalso, limpar
    from historico import chave_do_produto
    banco = BancoFalso(3)
    banco.linhas = [{"id": 1, "nome": "Banana Prata Quilo", "supermercado": "Atacadao", "id_origem": "100:1", "termo": "banana"},
                    {"id": 2, "nome": "Cebola Roxa 400 G", "supermercado": "Super ABC", "id_origem": None, "termo": "cebola"},
                    {"id": 3, "nome": "Arroz Camil 5kg", "supermercado": "Supernosso", "id_origem": "300:3", "termo": "arroz"}]
    anterior = api.supabase
    api.supabase = banco
    try:
        catalogo = api.baixar_catalogo("MG")
    finally:
        api.supabase = anterior
        limpar()
    chaves = {e.produto["id"]: e.produto["chave_historico"] for e in catalogo}
    assert chaves == {1: "v:100:1", 2: chave_do_produto({"nome": "Cebola Roxa 400 G"}), 3: "v:300:3"}
    assert chaves[2].startswith("n:") and len(chaves[2]) == 22                          # o Super ABC, sem id do mercado, vai pelo nome


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
