"""Testes do histórico de preços (historico.py), sem banco.

Rodar com:  python tests/test_historico.py

Duas formas de teste:
- um repositório em memória, que simula várias cargas em dias seguidos;
- um "Supabase falso" que entende o mesmo encadeamento de chamadas do cliente real (select/eq/is_/in_/upsert...),
  para provar que o RepositorioSupabase monta as consultas certas e que o resultado é o mesmo do repositório em memória.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import historico as h  # noqa: E402

D1 = date(2026, 11, 10)


def dia(n):
    return D1 + timedelta(days=n)


def prod(nome, varejo, atacado=None, qtd=1):
    return {"nome": nome, "preco_varejo": varejo, "preco_atacado": atacado if atacado is not None else varejo, "quantidade_atacado": qtd}


# ============================== repositório em memória ==============================

class RepositorioMemoria:
    def __init__(self):
        self.catalogo, self.precos, self.coletas = [], [], {}
        self.proximo = 1

    def carregar_catalogo(self, mercado):
        return {c["chave_origem"]: {"id": c["id"], "nome": c["nome"], "ativo": c["ativo"], "ultimo_dia": c["ultimo_dia"]} for c in self.catalogo if c["supermercado"] == mercado}

    def carregar_precos_abertos(self, mercado, praca):
        ids = {c["id"] for c in self.catalogo if c["supermercado"] == mercado}
        return {p["catalogo_id"]: dict(p) for p in self.precos if p["praca"] == praca and p["ate"] is None and p["catalogo_id"] in ids}

    def inserir_catalogo(self, mercado, itens, dia_):
        criados = {}
        for i in itens:
            self.catalogo.append({"id": self.proximo, "supermercado": mercado, "chave_origem": i["chave"], "nome": i["nome"], "ean": i.get("ean"),
                                  "marca": i.get("marca"), "categoria": i.get("categoria"), "primeiro_dia": dia_, "ultimo_dia": dia_, "ativo": True})
            criados[i["chave"]] = {"id": self.proximo, "nome": i["nome"], "ativo": True, "ultimo_dia": dia_}
            self.proximo += 1
        return criados

    def religar(self, pares):
        for i, chave, item in pares:
            for c in self.catalogo:
                if c["id"] == i:
                    c.update(chave_origem=chave, ean=item.get("ean"), marca=item.get("marca"), categoria=item.get("categoria"))

    def atualizar_visto(self, ids, dia_):
        for c in self.catalogo:
            if c["id"] in ids:
                c["ultimo_dia"], c["ativo"] = dia_, True

    def fechar_precos(self, ids, ate, praca):
        for p in self.precos:
            if p["catalogo_id"] in ids and p["praca"] == praca and p["ate"] is None:
                p["ate"] = ate

    def abrir_precos(self, pares, dia_, praca):
        for i, item in pares:
            assert not any(p["catalogo_id"] == i and p["praca"] == praca and p["ate"] is None for p in self.precos), "dois preços vigentes"
            self.precos.append({"catalogo_id": i, "praca": praca, "desde": dia_, "ate": None, "preco_varejo": item["preco_varejo"],
                                "preco_atacado": item["preco_atacado"], "quantidade_atacado": item["quantidade_atacado"]})

    def corrigir_precos(self, pares, dia_, praca):
        for i, item in pares:
            for p in self.precos:
                if p["catalogo_id"] == i and p["praca"] == praca and p["desde"] == dia_:
                    p.update(preco_varejo=item["preco_varejo"], preco_atacado=item["preco_atacado"], quantidade_atacado=item["quantidade_atacado"])

    def registrar_coleta(self, dia_, mercado, praca, status, itens, erro=None):
        chave = (dia_, mercado, praca)
        if status != "ok" and chave in self.coletas:
            return
        self.coletas[chave] = {"status": status, "itens": itens, "erro": erro}

    def ultimos_dias_ok(self, mercado, praca, quantos):
        return sorted((d for (d, m, p), v in self.coletas.items() if m == mercado and p == praca and v["status"] == "ok"), reverse=True)[:quantos]

    def inativar(self, inativos, praca):
        for i, ultimo in inativos:
            for c in self.catalogo:
                if c["id"] == i:
                    c["ativo"] = False
            for p in self.precos:
                if p["catalogo_id"] == i and p["praca"] == praca and p["ate"] is None:
                    p["ate"] = ultimo


def resumo_precos(repo, mercado="M"):
    """{nome: [(desde, ate, preço), ...]} em ordem de data."""
    nomes = {c["id"]: c["nome"] for c in repo.catalogo if c["supermercado"] == mercado}
    saida = {}
    for p in sorted(repo.precos, key=lambda p: (p["catalogo_id"], p["desde"])):
        if p["catalogo_id"] in nomes:
            saida.setdefault(nomes[p["catalogo_id"]], []).append((p["desde"], p["ate"], p["preco_varejo"]))
    return saida


# ============================== testes das funções puras ==============================

def teste_chave_e_itens():
    assert h.normalizar_nome("Arroz  Branco, CAMIL Tipo 1 – 5Kg!") == "arroz branco camil tipo 1 5kg"
    assert h.chave_origem("Café Pilão 500g") == h.chave_origem("cafe  pilao 500G")
    assert h.chave_origem("Café Pilão 500g") != h.chave_origem("Café Pilão 250g")
    itens, dup = h.preparar_itens([
        prod("Arroz A", 20.0, 18.0, 3), prod("arroz a", 19.5), prod("Sem preço", None), prod("Preço zero", 0), prod("", 5), {"nome": "Sem campo"},
        {"nome": "Atacado nulo", "preco_varejo": 7, "preco_atacado": None, "quantidade_atacado": None},
    ])
    assert dup == 1 and len(itens) == 2
    assert itens[h.chave_origem("Arroz A")]["preco_varejo"] == 19.5          # repetido: fica o mais barato
    nulo = itens[h.chave_origem("Atacado nulo")]
    assert nulo["preco_atacado"] is None and nulo["quantidade_atacado"] == 1


def teste_mesmo_preco():
    aberto = {"preco_varejo": 10.0, "preco_atacado": 9.0, "quantidade_atacado": 3}
    assert h.mesmo_preco(aberto, {"preco_varejo": 10.0, "preco_atacado": 9.0, "quantidade_atacado": 3})
    assert not h.mesmo_preco(aberto, {"preco_varejo": 10.01, "preco_atacado": 9.0, "quantidade_atacado": 3})
    assert not h.mesmo_preco(aberto, {"preco_varejo": 10.0, "preco_atacado": 8.5, "quantidade_atacado": 3})
    assert not h.mesmo_preco(aberto, {"preco_varejo": 10.0, "preco_atacado": 9.0, "quantidade_atacado": 6})
    assert not h.mesmo_preco(aberto, {"preco_varejo": 10.0, "preco_atacado": None, "quantidade_atacado": 3})
    assert h.mesmo_preco({"preco_varejo": 5, "preco_atacado": None, "quantidade_atacado": None}, {"preco_varejo": 5.0, "preco_atacado": None, "quantidade_atacado": 1})


def teste_escolher_inativos():
    catalogo = {
        "a": {"id": 1, "ativo": True, "ultimo_dia": dia(0)},     # visto no 1º dia das 3 cargas: fica
        "b": {"id": 2, "ativo": True, "ultimo_dia": dia(-1)},    # sumiu das 3 cargas: sai
        "c": {"id": 3, "ativo": False, "ultimo_dia": dia(-9)},   # já estava fora
        "d": {"id": 4, "ativo": True, "ultimo_dia": dia(2)},
    }
    assert h.escolher_inativos(catalogo, [dia(2), dia(1), dia(0)]) == [(2, dia(-1))]
    assert h.escolher_inativos(catalogo, [dia(2), dia(1)]) == []                      # ainda não há 3 cargas completas
    assert h.escolher_inativos(catalogo, [dia(5), dia(3), dia(2)]) == [(1, dia(0)), (2, dia(-1))]   # cargas com lacuna: conta cargas, não dias


# ============================== simulação de vários dias ==============================

def teste_varios_dias():
    repo = RepositorioMemoria()
    # dia 0: tudo novo
    r = h.registrar_mercado(repo, "M", [prod("Arroz", 20.0), prod("Feijão", 8.0), prod("Café", 15.0, 14.0, 2)], dia(0))
    assert (r.itens, r.novos, r.mudaram, r.reabertos, r.inativados) == (3, 3, 0, 0, 0)
    assert len(repo.precos) == 3 and all(p["ate"] is None for p in repo.precos)

    # dia 1: arroz sobe, feijão igual, café some, leite novo
    r = h.registrar_mercado(repo, "M", [prod("Arroz", 22.0), prod("Feijão", 8.0), prod("Leite", 5.0)], dia(1))
    assert (r.itens, r.novos, r.mudaram, r.reabertos, r.inativados) == (3, 1, 1, 0, 0)
    p = resumo_precos(repo)
    assert p["Arroz"] == [(dia(0), dia(0), 20.0), (dia(1), None, 22.0)]
    assert p["Feijão"] == [(dia(0), None, 8.0)]                 # sem mudança: continua um intervalo só, aberto desde o dia 0
    assert p["Leite"] == [(dia(1), None, 5.0)]
    assert p["Café"] == [(dia(0), None, 15.0)]                  # sumiu uma vez: ainda não é dado como saído

    # repetir a carga do mesmo dia não muda nada
    antes = (len(repo.catalogo), [dict(x) for x in repo.precos])
    h.registrar_mercado(repo, "M", [prod("Arroz", 22.0), prod("Feijão", 8.0), prod("Leite", 5.0)], dia(1))
    assert (len(repo.catalogo), repo.precos) == antes

    # repetir no mesmo dia com outro preço corrige o intervalo de hoje (sem criar intervalo de 0 dia)
    r = h.registrar_mercado(repo, "M", [prod("Arroz", 21.5), prod("Feijão", 8.0), prod("Leite", 5.0)], dia(1))
    assert r.mudaram == 1
    assert resumo_precos(repo)["Arroz"] == [(dia(0), dia(0), 20.0), (dia(1), None, 21.5)]

    # dia 2: café continua fora (2ª carga sem ele); leite cai
    h.registrar_mercado(repo, "M", [prod("Arroz", 21.5), prod("Feijão", 8.0), prod("Leite", 4.5)], dia(2))
    assert next(c for c in repo.catalogo if c["nome"] == "Café")["ativo"] is True

    # dia 3: 3ª carga sem o café -> sai, e o preço dele fecha no último dia em que foi visto
    r = h.registrar_mercado(repo, "M", [prod("Arroz", 21.5), prod("Feijão", 8.0), prod("Leite", 4.5)], dia(3))
    assert r.inativados == 1
    cafe = next(c for c in repo.catalogo if c["nome"] == "Café")
    assert cafe["ativo"] is False and resumo_precos(repo)["Café"] == [(dia(0), dia(0), 15.0)]

    # dia 5 (dia 4 sem coleta: lacuna): o café volta com o preço antigo -> novo intervalo, o buraco fica no histórico
    r = h.registrar_mercado(repo, "M", [prod("Arroz", 21.5), prod("Feijão", 8.0), prod("Leite", 4.5), prod("Café", 15.0, 14.0, 2)], dia(5))
    assert (r.novos, r.reabertos) == (0, 1)
    assert resumo_precos(repo)["Café"] == [(dia(0), dia(0), 15.0), (dia(5), None, 15.0)]
    assert next(c for c in repo.catalogo if c["nome"] == "Café")["ativo"] is True

    # nunca dois preços vigentes para o mesmo produto, e todo intervalo tem ate >= desde
    abertos = [p["catalogo_id"] for p in repo.precos if p["ate"] is None]
    assert len(abertos) == len(set(abertos))
    assert all(p["ate"] is None or p["ate"] >= p["desde"] for p in repo.precos)


def teste_mercados_separados_e_falhas():
    repo = RepositorioMemoria()
    h.registrar_mercado(repo, "M1", [prod("Arroz", 20.0)], dia(0))
    h.registrar_mercado(repo, "M2", [prod("Arroz", 21.0)], dia(0))
    assert len(repo.catalogo) == 2                                   # mesmo nome em mercados diferentes são produtos diferentes
    assert resumo_precos(repo, "M1")["Arroz"][0][2] == 20.0 and resumo_precos(repo, "M2")["Arroz"][0][2] == 21.0

    # falha não vira ausência: 5 dias de falha, o produto continua ativo
    for n in range(1, 6):
        h.registrar_falha(repo, "M1", "robô caiu", dia(n))
    h.registrar_mercado(repo, "M1", [prod("Arroz", 20.0)], dia(6))
    assert next(c for c in repo.catalogo if c["supermercado"] == "M1")["ativo"] is True
    assert repo.coletas[(dia(3), "M1", "betim")]["status"] == "falhou"

    # falha depois de uma coleta ok do mesmo dia não a sobrescreve
    h.registrar_falha(repo, "M1", "carga repetida falhou", dia(6))
    assert repo.coletas[(dia(6), "M1", "betim")]["status"] == "ok"

    # coleta vazia não pode virar "todo mundo saiu"
    try:
        h.registrar_mercado(repo, "M1", [prod("Sem preço", None)], dia(7))
    except ValueError:
        pass
    else:
        raise AssertionError("coleta sem itens válidos deveria ser recusada")


# ============================== o Supabase falso ==============================

class ConsultaFalsa:
    """Entende o encadeamento do cliente `supabase` que o RepositorioSupabase usa, sobre tabelas em memória."""

    def __init__(self, banco, tabela):
        self.banco, self.tabela = banco, tabela
        self.op, self.dados, self.filtros, self.faixa, self.ordem, self.limite = "select", None, [], None, None, None
        self.opcoes = {}

    def select(self, colunas):
        self.op, self.colunas = "select", colunas
        return self

    def insert(self, dados):
        self.op, self.dados = "insert", dados
        return self

    def update(self, dados):
        self.op, self.dados = "update", dados
        return self

    def upsert(self, dados, on_conflict=None, ignore_duplicates=False):
        self.op, self.dados, self.opcoes = "upsert", dados, {"on_conflict": on_conflict, "ignore": ignore_duplicates}
        return self

    def eq(self, coluna, valor):
        self.filtros.append(("eq", coluna, valor))
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self.filtros.append(("is_null", coluna, None))
        return self

    def in_(self, coluna, valores):
        self.filtros.append(("in", coluna, set(valores)))
        return self

    def order(self, coluna, desc=False):
        self.ordem = (coluna, desc)
        return self

    def range(self, inicio, fim):
        self.faixa = (inicio, fim)
        return self

    def limit(self, n):
        self.limite = n
        return self

    # --- execução ---
    def _valor(self, linha, coluna):
        if "." in coluna:                       # filtro em tabela embutida: catalogo.supermercado
            tabela, campo = coluna.split(".")
            return linha[tabela][campo]
        return linha[coluna]

    def _casa(self, linha):
        for tipo, coluna, valor in self.filtros:
            v = self._valor(linha, coluna)
            if (tipo == "eq" and v != valor) or (tipo == "is_null" and v is not None) or (tipo == "in" and v not in valor):
                return False
        return True

    def execute(self):
        linhas = self.banco.tabelas[self.tabela]
        if self.op == "select":
            candidatas = linhas
            if "catalogo!inner" in self.colunas:         # junta o catálogo, como o PostgREST faz
                catalogo = {c["id"]: c for c in self.banco.tabelas["catalogo"]}
                candidatas = [{**l, "catalogo": {"supermercado": catalogo[l["catalogo_id"]]["supermercado"]}} for l in linhas]
            achadas = [dict(l) for l in candidatas if self._casa(l)]
            if self.ordem:
                achadas.sort(key=lambda l: l[self.ordem[0]], reverse=self.ordem[1])
            if self.faixa:
                achadas = achadas[self.faixa[0]:self.faixa[1] + 1]
            if self.limite is not None:
                achadas = achadas[:self.limite]
            return Resposta(achadas)
        if self.op == "insert":
            novas = []
            for d in (self.dados if isinstance(self.dados, list) else [self.dados]):
                nova = {**PADROES[self.tabela], **d}
                if self.tabela == "catalogo":
                    nova["id"] = self.banco.proximo_id
                    self.banco.proximo_id += 1
                linhas.append(nova)
                novas.append(dict(nova))
            return Resposta(novas)
        if self.op == "update":
            alvo = [l for l in linhas if self._casa(l)]
            for l in alvo:
                l.update(self.dados)
            return Resposta([dict(l) for l in alvo])
        if self.op == "upsert":
            chaves = self.opcoes["on_conflict"].split(",")
            for d in (self.dados if isinstance(self.dados, list) else [self.dados]):
                existente = next((l for l in linhas if all(str(l[c]) == str(d[c]) for c in chaves)), None)
                if existente is None:
                    linhas.append({**PADROES[self.tabela], **d})
                elif not self.opcoes["ignore"]:
                    existente.update(d)
            return Resposta([])
        raise AssertionError(self.op)


class Resposta:
    def __init__(self, data):
        self.data = data


# colunas que o banco preenche sozinho quando a gravação não as envia
PADROES = {"catalogo": {"ean": None, "marca": None, "categoria": None}, "precos": {"ate": None, "disponivel": True}, "coletas": {"erro": None, "itens": None}}


class SupabaseFalso:
    def __init__(self):
        self.tabelas = {"catalogo": [], "precos": [], "coletas": []}
        self.proximo_id = 1

    def table(self, nome):
        return ConsultaFalsa(self, nome)


def teste_supabase_falso_igual_a_memoria():
    """O RepositorioSupabase, sobre um banco falso, produz o mesmo histórico que o repositório em memória."""
    memoria, falso = RepositorioMemoria(), SupabaseFalso()
    banco = h.RepositorioSupabase(falso)
    cargas = [
        (0, [prod("Arroz", 20.0), prod("Feijão", 8.0), prod("Café", 15.0, 14.0, 2)]),
        (1, [prod("Arroz", 22.0), prod("Feijão", 8.0), prod("Leite", 5.0)]),
        (1, [prod("Arroz", 21.5), prod("Feijão", 8.0), prod("Leite", 5.0)]),     # repetida no mesmo dia com outro preço
        (2, [prod("Arroz", 21.5), prod("Feijão", 8.0), prod("Leite", 4.5)]),
        (3, [prod("Arroz", 21.5), prod("Feijão", 8.0), prod("Leite", 4.5)]),     # o café sai
        (5, [prod("Arroz", 21.5), prod("Feijão", 8.0), prod("Leite", 4.5), prod("Café", 15.0, 14.0, 2)]),
    ]
    for n, produtos in cargas:
        a = h.registrar_mercado(memoria, "M", produtos, dia(n))
        b = h.registrar_mercado(banco, "M", produtos, dia(n))
        assert a == b, (n, a, b)
    h.registrar_falha(memoria, "M", "caiu", dia(6))
    h.registrar_falha(banco, "M", "caiu", dia(6))

    # mesmo catálogo, mesmos intervalos, mesmas coletas
    def visto(repo_catalogo):
        return sorted((c["nome"], str(c["primeiro_dia"]), str(c["ultimo_dia"]), c["ativo"]) for c in repo_catalogo)
    assert visto(memoria.catalogo) == visto(falso.tabelas["catalogo"])
    nomes = {c["id"]: c["nome"] for c in falso.tabelas["catalogo"]}

    def intervalos(precos, nomes_):
        return sorted((nomes_[p["catalogo_id"]], str(p["desde"]), str(p["ate"]) if p["ate"] else None, p["preco_varejo"], p["preco_atacado"], p["quantidade_atacado"]) for p in precos)
    nomes_mem = {c["id"]: c["nome"] for c in memoria.catalogo}
    assert intervalos(memoria.precos, nomes_mem) == intervalos(falso.tabelas["precos"], nomes)
    assert sorted((str(l["dia"]), l["status"], l["itens"]) for l in falso.tabelas["coletas"]) == sorted((str(d), v["status"], v["itens"]) for (d, _, _), v in memoria.coletas.items())
    # as datas chegam ao banco como texto ISO, o formato que o Supabase espera
    assert all(isinstance(c["ultimo_dia"], str) for c in falso.tabelas["catalogo"])


def teste_lotes():
    """Mais produtos que o tamanho do lote e mais de 1000 linhas: nada se perde na paginação."""
    falso = SupabaseFalso()
    banco = h.RepositorioSupabase(falso)
    produtos = [prod(f"Produto {i:05d}", 1 + i / 100) for i in range(2500)]
    r = h.registrar_mercado(banco, "M", produtos, dia(0))
    assert r.itens == 2500 and r.novos == 2500
    assert len(falso.tabelas["catalogo"]) == 2500 and len(falso.tabelas["precos"]) == 2500
    # no dia seguinte, 100 preços sobem; a leitura paginada (1000 por vez) tem de enxergar todos os 2500 intervalos abertos
    segundo = [prod(f"Produto {i:05d}", (1 + i / 100) * (1.1 if i % 25 == 0 else 1)) for i in range(2500)]
    r = h.registrar_mercado(banco, "M", segundo, dia(1))
    assert r.novos == 0 and r.mudaram == 100
    assert len([p for p in falso.tabelas["precos"] if p["ate"] is None]) == 2500
    assert len(falso.tabelas["precos"]) == 2600


def prodv(nome, varejo, id_origem, ean="7896006711155", atacado=None, qtd=1, marca="Marca", categoria="Mercearia > Grãos"):
    """Produto como o coletor por API entrega: com id do mercado, EAN, marca e categoria."""
    return {"nome": nome, "preco_varejo": varejo, "preco_atacado": atacado if atacado is not None else varejo, "quantidade_atacado": qtd,
            "id_origem": id_origem, "ean": ean, "marca": marca, "categoria": categoria}


def teste_id_do_mercado_religa_o_produto_e_mantem_o_historico():
    for repo in (RepositorioMemoria(), h.RepositorioSupabase(SupabaseFalso())):
        mercado = "M"
        # dia 0: o histórico antigo guardava pelo nome (robô)
        h.registrar_mercado(repo, mercado, [prod("Arroz Camil 5kg", 24.9, 23.9, 6), prod("Feijão Preto 1kg", 8.0)], dia(0))
        # dia 1: o coletor por API traz os mesmos produtos com id, EAN e marca; um preço mudou e há um produto novo
        r = h.registrar_mercado(repo, mercado, [prodv("Arroz Camil 5kg", 24.9, "13743:13744", atacado=23.9, qtd=6),
                                                prodv("Feijão Preto 1kg", 8.5, "14000:14001", ean="7896006744115"),
                                                prodv("Sal 1kg", 3.0, "15000:15001", ean="7891000000017")], dia(1))
        assert r.religados == 2 and r.novos == 1 and r.mudaram == 1, r
        catalogo = repo.carregar_catalogo(mercado)
        assert sorted(catalogo) == ["v:13743:13744", "v:14000:14001", "v:15000:15001"], sorted(catalogo)    # nenhum "n:" sobrou, nenhum produto duplicado
        # o histórico de preços continua: o arroz não ganhou intervalo novo (preço igual), o feijão fechou ontem e abriu hoje
        if isinstance(repo, RepositorioMemoria):
            precos = resumo_precos(repo, mercado)
            assert precos["Arroz Camil 5kg"] == [(dia(0), None, 24.9)], precos
            assert precos["Feijão Preto 1kg"] == [(dia(0), dia(0), 8.0), (dia(1), None, 8.5)], precos
            arroz = next(c for c in repo.catalogo if c["nome"] == "Arroz Camil 5kg")
        else:
            arroz = next(c for c in repo.banco.tabelas["catalogo"] if c["nome"] == "Arroz Camil 5kg")
        assert arroz["ean"] == "7896006711155" and arroz["marca"] == "Marca" and arroz["categoria"] == "Mercearia > Grãos"
        # dia 2: a API caiu e só o robô de reserva traz o arroz (sem id): continua sendo o mesmo produto
        r = h.registrar_mercado(repo, mercado, [prod("Arroz Camil 5kg", 24.9, 23.9, 6)], dia(2), status="parcial")
        assert r.novos == 0 and r.religados == 0 and r.status == "parcial", r
        assert sorted(repo.carregar_catalogo(mercado)) == ["v:13743:13744", "v:14000:14001", "v:15000:15001"]


def teste_coleta_parcial_nao_da_produto_como_saido():
    memoria, falso = RepositorioMemoria(), SupabaseFalso()
    banco = h.RepositorioSupabase(falso)
    completa = [prodv("Arroz", 20.0, "1:1"), prodv("Feijão", 8.0, "2:2"), prodv("Café", 15.0, "3:3")]
    sem_cafe = completa[:2]
    cargas = [(0, completa, "ok"), (1, completa, "ok"), (2, sem_cafe, "parcial"), (3, sem_cafe, "parcial"), (4, sem_cafe, "parcial"), (5, sem_cafe, "parcial")]
    for n, produtos, status in cargas:
        a = h.registrar_mercado(memoria, "M", produtos, dia(n), status=status)
        b = h.registrar_mercado(banco, "M", produtos, dia(n), status=status)
        assert a == b and a.inativados == 0, (n, a, b)                    # 4 dias parciais seguidos sem o café: ele não "saiu"
    assert all(c["ativo"] for c in memoria.catalogo)
    assert [v["status"] for _, v in sorted(memoria.coletas.items())] == ["ok", "ok", "parcial", "parcial", "parcial", "parcial"]
    # dias parciais não contam como "cargas completas": é preciso 3 cargas ok seguidas sem o café para ele sair
    for n in (6, 7):
        assert h.registrar_mercado(memoria, "M", sem_cafe, dia(n)).inativados == 0
    assert h.registrar_mercado(memoria, "M", sem_cafe, dia(8)).inativados == 1
    # um dia parcial nunca sobrescreve o "ok" do mesmo dia
    h.registrar_mercado(memoria, "M", sem_cafe, dia(8), status="parcial")
    assert memoria.coletas[(dia(8), "M", "betim")]["status"] == "ok"


def teste_status_invalido_e_recusado():
    try:
        h.registrar_mercado(RepositorioMemoria(), "M", [prod("Arroz", 20.0)], dia(0), status="falhou")
    except ValueError:
        return
    raise AssertionError("status desconhecido deveria ser recusado")


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
