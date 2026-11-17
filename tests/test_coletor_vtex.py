"""Testes do coletor por API (coletor_vtex.py), sem rede: as respostas das APIs são falsas.

Rodar com:  python tests/test_coletor_vtex.py
"""
import io
import json
import re
import sys
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletor_vtex as c  # noqa: E402


# ============================== apoio dos testes ==============================

class HttpFalso:
    """Responde por uma função (url, corpo) -> JSON e guarda as chamadas feitas."""

    def __init__(self, resposta):
        self.resposta, self.chamadas = resposta, []

    def get_json(self, url, cabecalhos=None):
        self.chamadas.append(("GET", url, None))
        return self.resposta(url, None)

    def post_json(self, url, corpo, cabecalhos=None):
        self.chamadas.append(("POST", url, corpo))
        return self.resposta(url, corpo)


def produto_vtex(id_produto, nome, preco, estoque=10, ean="7891000100103", marca="Marca", categorias=("/Mercearia/Grãos/Arroz/",), extra=None, item_id=None, unidade="un"):
    produto = {
        "productId": str(id_produto), "productName": nome, "brand": marca, "categories": list(categorias),
        "items": [{"itemId": str(item_id or id_produto + 1000), "ean": ean, "measurementUnit": unidade,
                   "sellers": [{"sellerId": "1", "commertialOffer": {"Price": preco, "ListPrice": preco, "AvailableQuantity": estoque}}]}],
    }
    produto.update(extra or {})
    return produto


def no_graphql(id_produto, nome, faixas, categorias=("Mercearia", "Grãos"), marca="Camil", unidade="un"):
    trilha = [{"name": n, "item": f"/{n.lower()}/", "position": i + 1} for i, n in enumerate(list(categorias) + [nome])]
    return {"id": str(id_produto + 1), "sku": str(id_produto + 1), "name": nome, "measurementUnit": unidade, "gtin": "11300984",
            "brand": {"brandName": marca}, "isVariantOf": {"productGroupID": str(id_produto)},
            "offers": {"offers": [{"price": p, "minQuantity": q} for q, p in faixas]},
            "breadcrumbList": {"itemListElement": trilha}}


# ============================== funções puras ==============================

def teste_ean_valido():
    assert c.ean_valido("7896006711155") == "7896006711155"
    assert c.ean_valido(" 7896006711155 ") == "7896006711155"
    assert c.ean_valido("78960067") == "78960067"                 # EAN-8
    assert c.ean_valido("8200") is None                           # código interno de marca própria
    assert c.ean_valido("0000000000000") is None                  # repetição óbvia
    assert c.ean_valido("789-6006711155") == "7896006711155"       # só dígitos contam
    assert c.ean_valido(None) is None and c.ean_valido("") is None


def teste_vendido_por_peso():
    assert c.vendido_por_peso("kg") and c.vendido_por_peso("KG") and c.vendido_por_peso("g")
    assert not c.vendido_por_peso("un") and not c.vendido_por_peso(None)
    assert c.vendido_por_peso("un", "Yes") and c.vendido_por_peso("un", "sim")
    assert not c.vendido_por_peso("un", "No")


def teste_categorias():
    assert c.caminho_da_categoria("/Mercearia/Grãos/Arroz/") == ["Mercearia", "Grãos", "Arroz"]
    assert c.folha_da_categoria(["/Mercearia/", "/Mercearia/Grãos/", "/Mercearia/Grãos/Arroz/"]) == "Mercearia > Grãos > Arroz"
    assert c.folha_da_categoria([]) == "" and c.folha_da_categoria(None) == ""


def teste_faixas_do_atacadao():
    assert c.preco_e_atacado_do_no(no_graphql(1, "Óleo Liza", [(1, 7.89), (6, 7.59)])) == (7.89, 7.59, 6)
    assert c.preco_e_atacado_do_no(no_graphql(1, "Óleo Liza", [(6, 7.59), (1, 7.89)])) == (7.89, 7.59, 6)     # fora de ordem
    assert c.preco_e_atacado_do_no(no_graphql(1, "Arroz", [(1, 22.5)])) == (22.5, 22.5, 1)                     # sem atacado
    assert c.preco_e_atacado_do_no(no_graphql(1, "Estranho", [(1, 5.0), (3, 5.5)])) == (5.0, 5.0, 1)          # faixa mais cara não vale
    assert c.preco_e_atacado_do_no(no_graphql(1, "Duas", [(1, 10.0), (5, 9.0), (10, 8.0)])) == (10.0, 9.0, 5) # fica a primeira faixa
    assert c.preco_e_atacado_do_no(no_graphql(1, "Sem preço", [(1, 0)])) is None


def teste_selecionar():
    def linha(i, nome, categoria="Mercearia > Grãos > Arroz", peso=False):
        return {"id_origem": str(i), "nome": nome, "categoria": categoria, "peso_variavel": peso}

    linhas = [linha(1, "Arroz Camil 5kg"), linha(1, "Arroz Camil 5kg"), linha(3, "Biscoito de Arroz", "Mercearia > Biscoitos"),
              linha(4, "Arroz Tio João 1kg"), linha(5, "Arroz a Granel", peso=True), linha(6, "Arroz Para Risoto", "Mercearia > Arroz Para Risoto"),
              linha(7, "Arroz Xyz 2kg"), linha(8, "Arroz Parboilizado 1kg")]
    termo = {"termo": "arroz", "categorias": ["> arroz$", "> graos$"], "nome_exclui": ["biscoito"]}
    escolhidas = c.selecionar(linhas, termo, 100)
    assert [l["id_origem"] for l in escolhidas] == ["1", "4", "7", "8"], [l["id_origem"] for l in escolhidas]    # repetido, biscoito e peso variável fora; "Arroz Para Risoto" não termina em arroz
    assert [l["id_origem"] for l in c.selecionar(linhas, termo, 2)] == ["1", "4"]                              # teto
    assert len(c.selecionar(linhas, {"termo": "qualquer"}, 100)) == 6                                         # sem regra: só tira repetido e peso variável
    so_nome = {"termo": "arroz", "nome_inclui": ["tio joao", "parboilizado"]}
    assert [l["id_origem"] for l in c.selecionar(linhas, so_nome, 100)] == ["4", "8"]                         # acento e caixa não atrapalham


# ============================== catálogo: Supernosso e paginação ==============================

def teste_supernosso_paginacao_e_estoque():
    paginas = {0: [produto_vtex(i, f"Produto {i}", 5.0 + i, estoque=0 if i % 10 == 0 else 5) for i in range(50)],
               50: [produto_vtex(i, f"Produto {i}", 5.0 + i) for i in range(50, 70)]}

    def resposta(url, corpo):
        return paginas[int(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["_from"][0])]

    http = HttpFalso(resposta)
    linhas = c.baixar_supernosso(http, "arroz")
    assert len(http.chamadas) == 2                              # a 2ª página veio com menos de 50: acabou
    assert len(linhas) == 70 - 5                                # 5 sem estoque (0, 10, 20, 30, 40)
    assert "&O=" not in http.chamadas[0][1]                     # ordem padrão (relevância)
    assert linhas[0]["supermercado"] == "Supernosso" and linhas[0]["uf_cobertura"] == "MG" and linhas[0]["quantidade_atacado"] == 1
    assert linhas[0]["marca"] == "Marca" and linhas[0]["ean"] == "7891000100103" and linhas[0]["categoria"] == "Mercearia > Grãos > Arroz"


def teste_produto_com_varios_skus_vira_varias_linhas():
    produto = produto_vtex(1, "Detergente Ypê", 2.5)
    produto["items"].append(dict(produto["items"][0], itemId="2001", nameComplete="Detergente Ypê Maçã 500ml", ean="7896098900123"))
    http = HttpFalso(lambda url, corpo: [produto])
    linhas = c.baixar_supernosso(http, "detergente")
    assert [l["id_origem"] for l in linhas] == ["1:1001", "1:2001"]
    assert linhas[1]["nome"] == "Detergente Ypê Maçã 500ml" and linhas[1]["ean"] == "7896098900123"


# ============================== Apoio: atacado pela simulação ==============================

def teste_apoio_atacado_pela_simulacao():
    produtos = [
        produto_vtex(1, "Arroz A 5kg", 24.99, extra={"Quantidade para atacado": ["6"]}),
        produto_vtex(2, "Arroz B 1kg", 5.29, extra={"Quantidade para atacado": ["5"]}),      # simulação sem desconto
        produto_vtex(3, "Arroz C 2kg", 9.99),                                                   # sem campo de atacado
        produto_vtex(4, "Arroz D 1kg", 7.0, estoque=0, extra={"Quantidade para atacado": ["3"]}),
        produto_vtex(5, "Arroz E 1kg", 8.99, extra={"Quantidade para atacado": ["abc"]}),    # campo inválido
        produto_vtex(6, "Arroz F kg", 12.0, unidade="kg"),                                      # vendido por peso
    ]

    def resposta(url, corpo):
        if "simulation" in url:
            preco = {"1001": 2449, "1002": 529}
            return {"items": [{"id": i["id"], "sellingPrice": preco[i["id"]], "availability": "available"} for i in corpo["items"]]}
        return produtos

    http = HttpFalso(resposta)
    linhas = {l["id_origem"].split(":")[0]: l for l in c.baixar_apoio(http, "arroz")}
    assert "4" not in linhas                                                                  # sem estoque
    assert (linhas["1"]["preco_varejo"], linhas["1"]["preco_atacado"], linhas["1"]["quantidade_atacado"]) == (24.99, 24.49, 6)
    assert (linhas["2"]["preco_atacado"], linhas["2"]["quantidade_atacado"]) == (5.29, 1)    # sem desconto: fica o varejo
    assert linhas["3"]["quantidade_atacado"] == 1 and linhas["5"]["quantidade_atacado"] == 1
    assert linhas["6"]["peso_variavel"] is True
    simulacoes = [ch for ch in http.chamadas if ch[0] == "POST"]
    assert len(simulacoes) == 1 and "sc=15" in simulacoes[0][1]                              # uma chamada para todos
    assert [(i["id"], i["quantity"]) for i in simulacoes[0][2]["items"]] == [("1001", 6), ("1002", 5)]
    assert all("sc=15" in ch[1] for ch in http.chamadas if ch[0] == "GET")


# ============================== Atacadão: GraphQL + EAN ==============================

def teste_atacadao_graphql_e_ean():
    nos = [no_graphql(13743, "Arroz Branco Camil Tipo 1 5kg", [(1, 22.5)]),
           no_graphql(14662, "Arroz Prato Fino Agulhinha 5kg", [(1, 31.9), (6, 30.9)], marca="Prato Fino"),
           no_graphql(99, "Item sem preço", [(1, 0)]),
           no_graphql(77, "Queijo a peso", [(1, 40.0)], unidade="kg")]

    def resposta(url, corpo):
        if "graphql" in url:
            variaveis = json.loads(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["variables"][0])
            assert variaveis["term"] == "arroz" and variaveis["after"] == "0"
            canal = json.loads(next(f["value"] for f in variaveis["selectedFacets"] if f["key"] == "channel"))
            assert canal["seller"] == "atacadaobr167"
            return {"data": {"search": {"products": {"pageInfo": {"totalCount": len(nos)}, "edges": [{"node": n} for n in nos]}}}}
        ids = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["fq"]
        return [{"productId": i.split(":")[1], "items": [{"ean": {"13743": "7896006711155", "14662": "7896290300011"}.get(i.split(":")[1], "")}]} for i in ids]

    http = HttpFalso(resposta)
    linhas = {l["nome"]: l for l in c.baixar_atacadao(http, "arroz")}
    assert "Item sem preço" not in linhas                                                     # sem preço na loja de Betim
    camil = linhas["Arroz Branco Camil Tipo 1 5kg"]
    assert (camil["preco_varejo"], camil["preco_atacado"], camil["quantidade_atacado"]) == (22.5, 22.5, 1)
    assert camil["ean"] == "7896006711155" and camil["marca"] == "Camil" and camil["categoria"] == "Mercearia > Grãos"
    assert camil["id_origem"] == "13743:13744"
    prato = linhas["Arroz Prato Fino Agulhinha 5kg"]
    assert (prato["preco_atacado"], prato["quantidade_atacado"], prato["ean"]) == (30.9, 6, "7896290300011")
    assert linhas["Queijo a peso"]["peso_variavel"] is True and linhas["Queijo a peso"]["ean"] is None
    assert len([ch for ch in http.chamadas if "graphql" in ch[1]]) == 1                       # totalCount alcançado: não pede mais páginas


def teste_ean_do_atacadao_divide_o_lote_e_segue_sem_ean():
    ids = [str(1000 + i) for i in range(8)]
    chamadas = []

    def resposta(url, corpo):
        pedidos = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["fq"]
        chamadas.append(len(pedidos))
        if len(pedidos) > 4 or "productId:1003" in pedidos:      # lote grande falha; o id 1003 falha sempre
            raise c.ErroDeColeta("HTTP 500")
        return [{"productId": p.split(":")[1], "items": [{"ean": "78910001001" + p[-2:]}]} for p in pedidos]

    http = HttpFalso(resposta)
    http.avisos = []
    eans = c.eans_do_atacadao(http, ids)
    # lote de 8 falha -> 4+4; o primeiro (com 1003) falha -> 2+2; o par (1002, 1003) falha de novo e desiste: só esses dois ficam sem EAN
    assert sorted(eans) == ["1000", "1001", "1004", "1005", "1006", "1007"], sorted(eans)
    assert http.avisos == [http.avisos[0]] and "2 produto(s) ficaram sem EAN" in http.avisos[0]
    assert chamadas[0] == 8                                                         # primeiro tenta o lote inteiro


def teste_ean_do_atacadao_sem_erro_nao_avisa():
    http = HttpFalso(lambda url, corpo: [{"productId": "1", "items": [{"ean": "7896006711155"}]}])
    http.avisos = []
    assert c.eans_do_atacadao(http, ["1"]) == {"1": "7896006711155"} and http.avisos == []


def teste_atacadao_pagina_ate_o_total():
    todos = [no_graphql(1000 + i, f"Produto {i}", [(1, 3.0)]) for i in range(120)]

    def resposta(url, corpo):
        if "graphql" in url:
            variaveis = json.loads(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["variables"][0])
            de = int(variaveis["after"])
            return {"data": {"search": {"products": {"pageInfo": {"totalCount": 120}, "edges": [{"node": n} for n in todos[de:de + variaveis["first"]]]}}}}
        return []

    http = HttpFalso(resposta)
    nos = list(c.nos_do_graphql_atacadao(http, "x", "atacadaobr167"))
    assert len(nos) == 120 and len(http.chamadas) == 3                                        # 50 + 50 + 20


def teste_graphql_com_erro_levanta_depois_de_repetir():
    http = HttpFalso(lambda url, corpo: {"errors": [{"message": "boom"}]})
    with mock.patch("time.sleep"):
        try:
            list(c.nos_do_graphql_atacadao(http, "x", "atacadaobr167"))
        except c.ErroDeColeta as erro:
            assert "boom" in str(erro) and "3 vezes" in str(erro)
        else:
            raise AssertionError("devia levantar ErroDeColeta")
    assert len(http.chamadas) == 3


def teste_graphql_erro_passageiro_se_recupera():
    respostas = [{"errors": [{"message": "Cannot read properties of undefined (reading 'price')"}]},
                 {"data": {"search": {"products": {"pageInfo": {"totalCount": 1}, "edges": [{"node": no_graphql(1, "Papinha", [(1, 3.0)])}]}}}}]
    http = HttpFalso(lambda url, corpo: respostas.pop(0))
    with mock.patch("time.sleep"):
        nos = list(c.nos_do_graphql_atacadao(http, "papa", "atacadaobr167"))
    assert len(nos) == 1 and len(http.chamadas) == 2


# ============================== rede e orquestração ==============================

class RespostaFalsa(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def erro_http(codigo):
    return urllib.error.HTTPError("http://x", codigo, "erro", {}, io.BytesIO(b""))


def teste_http_repete_em_erro_passageiro():
    cliente = c.ClienteHttp(pausa=0, tentativas=4, espera=0)
    respostas = [erro_http(500), erro_http(429), RespostaFalsa(b'{"ok": true}')]

    def abrir(requisicao, timeout=0):
        item = respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    with mock.patch("urllib.request.urlopen", abrir):
        assert cliente.get_json("http://x/a") == {"ok": True}
    assert cliente.chamadas == 3


def teste_http_nao_repete_erro_definitivo_e_desiste():
    cliente = c.ClienteHttp(pausa=0, tentativas=3, espera=0)
    with mock.patch("urllib.request.urlopen", mock.Mock(side_effect=erro_http(404))) as abrir:
        try:
            cliente.get_json("http://x/a")
        except c.ErroDeColeta as erro:
            assert "404" in str(erro)
        else:
            raise AssertionError("404 devia levantar")
        assert abrir.call_count == 1
    with mock.patch("urllib.request.urlopen", mock.Mock(side_effect=erro_http(503))) as abrir:
        try:
            cliente.get_json("http://x/a")
        except c.ErroDeColeta as erro:
            assert "3 tentativas" in str(erro)
        else:
            raise AssertionError("503 repetido devia desistir")
        assert abrir.call_count == 3


def teste_coletar_continua_depois_de_um_erro():
    def baixar_ok(http, consulta):
        return [{"id_origem": consulta, "nome": consulta, "categoria": "", "peso_variavel": False}]

    def baixar_ruim(http, consulta):
        if consulta == "feijão":
            raise c.ErroDeColeta("caiu")
        return baixar_ok(http, consulta)

    termos = [{"termo": "arroz"}, {"termo": "feijão"}, {"termo": "sal", "consultas": ["sal refinado", "sal grosso"]}]
    vistos = []
    resultado, erros = c.coletar(None, ["Apoio Entrega", "Supernosso"], termos, 100, lambda m, t, brutas, esc: vistos.append((m, t["termo"])),
                                 baixadores={"Apoio Entrega": baixar_ruim, "Supernosso": baixar_ok})
    assert erros == [("Apoio Entrega", "feijão", "caiu")]
    assert sorted(resultado["Apoio Entrega"]) == ["arroz", "sal"] and sorted(resultado["Supernosso"]) == ["arroz", "feijão", "sal"]
    assert [l["nome"] for l in resultado["Supernosso"]["sal"]] == ["sal refinado", "sal grosso"]  # cada consulta vai à API e os resultados se juntam
    assert resultado["Supernosso"]["sal"][0]["termo"] == "sal"                                     # a linha guarda o termo da lista, não a consulta
    assert len(vistos) == 5


def teste_lista_de_produtos_do_repositorio():
    teto, termos = c.carregar_lista()
    assert teto == 100
    nomes = [t["termo"] for t in termos]
    assert len(nomes) == len(set(nomes)) == 100, len(nomes)
    for t in termos:
        assert t.get("grupo") and t.get("nome_inclui") and t.get("consultas"), t["termo"]
        for chave in ("categorias", "categorias_proibidas", "nome_exclui", "nome_inclui"):
            for padrao in t.get(chave, []):
                re.compile(padrao)                                                              # expressão válida
    # os termos de alimento não deixam passar produto de higiene, e o filtro de nome barra o ruído conhecido
    oleo = next(t for t in termos if t["termo"] == "óleo")
    assert c.passa_no_filtro({"nome": "Óleo de Soja Liza 900ml", "categoria": "Mercearia > Óleos", "peso_variavel": False}, oleo)
    assert not c.passa_no_filtro({"nome": "Óleo Capilar Hidratante", "categoria": "Cuidado com os Cabelos", "peso_variavel": False}, oleo)
    assert not c.passa_no_filtro({"nome": "Shampoo com Óleo de Argan", "categoria": "Mercearia > Óleos", "peso_variavel": False}, oleo)
    racao = next(t for t in termos if t["termo"] == "ração para cães")
    assert not c.passa_no_filtro({"nome": "Coloração Permanente Imédia", "categoria": "Beleza", "peso_variavel": False}, racao)
    gatos = next(t for t in termos if t["termo"] == "ração para gatos")
    for nome, cao, gato in (("Ração Dog Chow Cães Adultos 1kg", True, False), ("Ração Friskies Gatos Adultos 1kg", False, True), ("Ração Dog Abc Carne 13kg", True, False),
                            ("Ração Quatree Gourmet Adulto Gatos", False, True), ("Ração Filhote Sabor Frango", False, False)):
        linha = {"nome": nome, "categoria": "", "peso_variavel": False}
        assert c.passa_no_filtro(linha, racao) is cao and c.passa_no_filtro(linha, gatos) is gato, nome


# ============================== hortifrúti (etapa 1: só a coleta, fora da carga diária) ==============================

def teste_peso_variavel_so_entra_no_termo_que_aceita():
    banana_kg = {"id_origem": "1", "nome": "Banana Prata Quilo", "categoria": "Hortifrúti > Frutas", "peso_variavel": True}
    normal = {"termo": "banana"}
    assert not c.passa_no_filtro(banana_kg, normal), "o termo comum continua descartando o produto vendido a peso"
    assert c.passa_no_filtro(banana_kg, {**normal, "aceita_peso_variavel": True})
    assert not c.passa_no_filtro(banana_kg, {**normal, "aceita_peso_variavel": False})
    # e aceitar o peso variável não afrouxa os outros filtros do termo
    assert not c.passa_no_filtro({**banana_kg, "nome": "Banana Frita Laminada"}, {"termo": "banana", "aceita_peso_variavel": True, "nome_exclui": ["frit"]})


def teste_linha_traz_a_unidade_e_o_multiplicador():
    # Supernosso/Apoio (API de catálogo): "kg" = o preço é por quilo; o multiplicador é de quanto em quanto se compra
    produto = produto_vtex(1, "Tomate Italiano Supernosso 500g", 18.99, categorias=("/Hortifrúti/Legumes/",), unidade="kg")
    produto["items"][0]["unitMultiplier"] = 0.5
    linha = c.baixar_supernosso(HttpFalso(lambda url, corpo: [produto]), "tomate")[0]
    assert linha["unidade"] == "kg" and linha["multiplicador"] == 0.5 and linha["peso_variavel"] is True and linha["preco_varejo"] == 18.99
    pacote = produto_vtex(2, "Cebola Orgânico do Chico 400g", 7.99, categorias=("/Hortifrúti/Legumes/",), unidade="un")
    linha = c.baixar_supernosso(HttpFalso(lambda url, corpo: [pacote]), "cebola")[0]
    assert linha["unidade"] == "un" and linha["multiplicador"] is None and linha["peso_variavel"] is False       # preço do pacote, não por quilo
    assert c.linha_do_catalogo("Supernosso", {"productId": "9", "productName": "X"}, {"itemId": "1"}, {"Price": 1}, "x")["unidade"] is None     # sem a informação: vazio
    # Atacadão (GraphQL): o nó traz o mesmo par
    no = no_graphql(5, "Banana Prata Quilo", [(1, 3.79)], categorias=("Hortifrúti", "Frutas"), unidade="kg")
    no["unitMultiplier"] = 0.15
    linhas = c.baixar_atacadao(HttpFalso(lambda url, corpo: {"data": {"search": {"products": {"edges": [{"node": no}], "pageInfo": {"totalCount": 1}}}}} if "graphql" in url else []), "banana")
    assert linhas[0]["unidade"] == "kg" and linhas[0]["multiplicador"] == 0.15 and linhas[0]["peso_variavel"] is True


def teste_lista_de_hortifruti_do_repositorio():
    from casos_hortifruti import ADAPTADOS, CASOS
    teto, termos = c.carregar_lista(c.RAIZ / "dados" / "lista_hortifruti.json")
    nomes = [t["termo"] for t in termos]
    assert teto == 100 and len(nomes) == len(set(nomes)) == 28 and set(CASOS) == set(nomes), (len(nomes), set(CASOS) ^ set(nomes))
    for t in termos:
        assert t["grupo"] == "Hortifrúti" and t["aceita_peso_variavel"] is True and t["nome_inclui"] and t["consultas"] and t["categorias"], t["termo"]
        for chave in ("categorias", "categorias_proibidas", "nome_exclui", "nome_inclui"):
            for padrao in t.get(chave, []):
                re.compile(padrao)
    por_termo = {t["termo"]: t for t in termos}
    for termo, caso in CASOS.items():
        assert caso["entram"], f"{termo}: precisa de ao menos um caso que entra"
        for nome, categoria in caso["entram"]:
            assert c.passa_no_filtro({"nome": nome, "categoria": categoria, "peso_variavel": True}, por_termo[termo]), f"{termo}: deveria entrar: {nome} [{categoria}]"
        for nome, categoria in caso["saem"]:
            assert not c.passa_no_filtro({"nome": nome, "categoria": categoria, "peso_variavel": True}, por_termo[termo]), f"{termo}: deveria sair: {nome} [{categoria}]"
    for termo, itens in ADAPTADOS.items():
        for nome, categoria in itens:
            assert not c.passa_no_filtro({"nome": nome, "categoria": categoria, "peso_variavel": True}, por_termo[termo]), f"{termo}: deveria sair: {nome} [{categoria}]"


def teste_a_carga_diaria_nao_le_a_lista_de_hortifruti():
    """Hortifrúti vende a peso (o preço é por quilo) e o site ainda não sabe mostrar isso: gravar esses produtos agora faria o site exibir
    "Tomate Italiano 500g: R$ 18,99" quando o preço é de 1 kg. Por isso a lista fica à parte e a carga não a lê (docs/hortifruti.md)."""
    teto, padrao = c.carregar_lista()
    assert not [t["termo"] for t in padrao if t.get("aceita_peso_variavel") or t.get("grupo") == "Hortifrúti"], "a lista da carga diária não pode ter hortifrúti"
    assert c.LISTA_PADRAO.name == "lista_de_produtos.json"
    for arquivo in ("alimentar_banco.py", "api_supabase.py"):
        assert "lista_hortifruti" not in (c.RAIZ / arquivo).read_text(encoding="utf-8"), f"{arquivo} não pode ler a lista de hortifrúti ainda"
    # e a lista de hortifrúti não carrega termos do dia a dia (uma carga com ela apagaria os outros produtos do mercado)
    _, hortifruti = c.carregar_lista(c.RAIZ / "dados" / "lista_hortifruti.json")
    assert not {t["termo"] for t in hortifruti} & {t["termo"] for t in padrao}


def teste_coletar_hortifruti_mantem_o_fresco_e_conta_os_itens_por_quilo():
    termo = {"termo": "tomate", "aceita_peso_variavel": True, "nome_inclui": ["^tomate\\b"], "nome_exclui": ["seco|pelado"], "categorias": ["^hortifruti"], "categorias_proibidas": []}

    def baixar(http, consulta):
        def l(i, nome, categoria, unidade, peso):
            return {"id_origem": str(i), "nome": nome, "categoria": categoria, "unidade": unidade, "multiplicador": 0.5 if unidade == "kg" else None, "peso_variavel": peso,
                    "ean": None, "quantidade_atacado": 1}
        return [l(1, "Tomate Italiano Quilo", "Hortifrúti > Legumes", "kg", True), l(2, "Tomate Grape Mini Bandeja 300g", "Hortifrúti > Legumes", "un", False),
                l(3, "Tomate Seco Speciale 100g", "Hortifrúti > Legumes", "un", False), l(4, "Tomate Pelado Italiano 400g", "Mercearia > Molhos", "un", False)]

    resultado, erros = c.coletar(c.ClienteHttp(), ["Supernosso"], [termo], 100, baixadores={"Supernosso": baixar})
    linhas = resultado["Supernosso"]["tomate"]
    assert not erros and [l["nome"] for l in linhas] == ["Tomate Italiano Quilo", "Tomate Grape Mini Bandeja 300g"]
    assert "1 por kg" in c.resumo_de_termo(linhas) and "por kg" not in c.resumo_de_termo([dict(linhas[1], ean=None, quantidade_atacado=1)])


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_")]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
