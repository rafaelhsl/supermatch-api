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
import disjuntor  # noqa: E402

disjuntor.PAUSA_DA_SEGUNDA_RODADA = 0          # nenhum teste espera de verdade pela segunda rodada


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


def no_por_quilo(nome, preco, lista, multiplicador, unidade="kg", id_produto=500):
    no = no_graphql(id_produto, nome, [(1, preco)], unidade=unidade, categorias=("Hortifrúti", "Legumes"))
    no["unitMultiplier"] = multiplicador
    if lista is not None:
        no["offers"]["offers"][0]["listPrice"] = lista
    return no


def teste_atacadao_por_quilo_com_o_price_da_porcao():
    # desde 26/11/2026 o `price` de um item por quilo com multiplicador menor que 1 é o da porção mínima (150 g: R$ 2,68) e o `listPrice` é o do quilo (R$ 17,90).
    # O banco chegou a guardar "tomate R$ 2,68 o quilo" (dados reais de 26/11: Tomate Italiano Quilo, Cebola Roxa Quilo, Queijo Minas Padrão Porto Alegre...).
    f = c.preco_do_quilo_do_atacadao
    assert f(no_por_quilo("Tomate Italiano Quilo", 2.68, 17.9, 0.15), 2.68) == 17.9                    # vale o listPrice (2.68 / 0.15 daria 17.87)
    assert f(no_por_quilo("Cebola Roxa Quilo", 1.78, 11.9, 0.15), 1.78) == 11.9
    assert f(no_por_quilo("Queijo Minas Padrão Porto Alegre", 13.99, 34.99, 0.4), 13.99) == 34.99
    assert f(no_por_quilo("Alho a granel Quilo", 1.19, 11.9, 0.1), 1.19) == 11.9
    # a porção em promoção: o price fica abaixo de listPrice x multiplicador, e o quilo é o price / multiplicador
    assert f(no_por_quilo("Tomate em promoção", 2.0, 17.9, 0.15), 2.0) == 13.33
    # multiplicador 1 ou maior: o price já é o do quilo
    assert f(no_por_quilo("Melancia Baby Quilo", 5.99, 5.99, 1.5), 5.99) == 5.99
    assert f(no_por_quilo("Repolho Roxo Quilo", 4.99, 4.99, 1), 4.99) == 4.99
    assert f(no_por_quilo("Acém Porcionado", 39.9, 39.9, 1.2), 39.9) == 39.9
    # o comportamento antigo (até 24/11: price = quilo, mesmo com multiplicador < 1) continua certo se a loja voltar a ele, com ou sem promoção
    assert f(no_por_quilo("Tomate (como era)", 17.9, 17.9, 0.15), 17.9) == 17.9
    assert f(no_por_quilo("Tomate (como era, em promoção)", 14.9, 17.9, 0.15), 14.9) == 14.9
    # sem listPrice para conferir, ou sem multiplicador: o price, como sempre valeu
    assert f(no_por_quilo("Tomate sem listPrice", 2.68, None, 0.15), 2.68) == 2.68
    assert f(no_por_quilo("Tomate sem multiplicador", 17.9, 17.9, None), 17.9) == 17.9
    # o que não é por quilo não é mexido, nem com multiplicador menor que 1
    assert f(no_por_quilo("Arroz 5kg", 22.5, 40.0, 0.15, unidade="un"), 22.5) == 22.5
    # com faixas, vale o listPrice da faixa de 1 unidade
    com_faixas = no_graphql(501, "Queijo Minas com faixa", [(6, 11.0), (1, 13.99)], unidade="kg")
    com_faixas["unitMultiplier"] = 0.4
    for oferta in com_faixas["offers"]["offers"]:
        oferta["listPrice"] = 34.99 if oferta["minQuantity"] == 1 else 27.5
    assert f(com_faixas, 13.99) == 34.99


def teste_atacadao_baixa_o_item_por_quilo_com_o_preco_do_quilo():
    nos = [no_por_quilo("Tomate Italiano Quilo", 2.68, 17.9, 0.15, id_produto=700), no_por_quilo("Melancia Baby Quilo", 5.99, 5.99, 1.5, id_produto=800)]
    nos[0]["offers"]["offers"].append({"price": 2.0, "listPrice": 12.0, "minQuantity": 10})        # faixa de atacado: item por quilo não leva

    def resposta(url, corpo):
        if "graphql" in url:
            return {"data": {"search": {"products": {"pageInfo": {"totalCount": len(nos)}, "edges": [{"node": n} for n in nos]}}}}
        return []

    linhas = {l["nome"]: l for l in c.baixar_atacadao(HttpFalso(resposta), "tomate")}
    tomate = linhas["Tomate Italiano Quilo"]
    assert (tomate["preco_varejo"], tomate["preco_atacado"], tomate["quantidade_atacado"]) == (17.9, 17.9, 1)
    assert tomate["unidade"] == "kg" and tomate["multiplicador"] == 0.15 and tomate["peso_variavel"] is True
    melancia = linhas["Melancia Baby Quilo"]
    assert (melancia["preco_varejo"], melancia["multiplicador"]) == (5.99, 1.5)


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


def teste_cada_mercado_recebe_as_consultas_dele():
    termo = {"termo": "sal", "consultas": ["sal"], "consultas_super_abc": ["sal refinado", "sal grosso"]}
    assert c.consultas_do_termo(termo, "Super ABC") == ["sal refinado", "sal grosso"]            # a consulta própria do mercado
    assert c.consultas_do_termo(termo, "Supernosso") == ["sal"]                                    # os outros seguem a `consultas`
    assert c.consultas_do_termo({"termo": "arroz"}, "Super ABC") == ["arroz"]                      # sem nenhuma: o nome do termo
    assert c.consultas_do_termo({"termo": "x", "consultas": ["a"], "consultas_apoio_entrega": ["b"]}, "Apoio Entrega") == ["b"]   # espaço vira "_"
    assert c.consultas_do_termo({"termo": "x", "consultas": ["a"], "consultas_super_abc": []}, "Super ABC") == ["a"]               # vazio não vale

    pedidas = []

    def baixar(mercado):
        def baixador(http, consulta):
            pedidas.append((mercado, consulta))
            return []
        return baixador

    c.coletar(object(), ["Super ABC", "Supernosso"], [termo], 100, baixadores={"Super ABC": baixar("Super ABC"), "Supernosso": baixar("Supernosso")}, segunda_rodada=False)
    assert sorted(pedidas) == [("Super ABC", "sal grosso"), ("Super ABC", "sal refinado"), ("Supernosso", "sal")]


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


# ============================== hortifrúti (a lista própria, que a carga diária coleta junto com a de produtos) ==============================

def teste_peso_variavel_so_entra_no_termo_que_aceita():
    banana_kg = {"id_origem": "1", "nome": "Banana Prata Quilo", "categoria": "Hortifrúti > Frutas", "peso_variavel": True}
    normal = {"termo": "banana"}
    assert not c.passa_no_filtro(banana_kg, normal), "o termo comum continua descartando o produto vendido a peso"
    assert c.passa_no_filtro(banana_kg, {**normal, "aceita_peso_variavel": True})
    assert not c.passa_no_filtro(banana_kg, {**normal, "aceita_peso_variavel": False})
    # e aceitar o peso variável não afrouxa os outros filtros do termo
    assert not c.passa_no_filtro({**banana_kg, "nome": "Banana Frita Laminada"}, {"termo": "banana", "aceita_peso_variavel": True, "nome_exclui": ["frit"]})


def teste_unidade_normalizada():
    assert c.unidade_normalizada("kg") == "kg" and c.unidade_normalizada(" KG ") == "kg"
    assert all(c.unidade_normalizada(u) == "un" for u in ("un", "UN", "und", "unid", "unidade", "pc", "pç"))
    assert all(c.unidade_normalizada(u) is None for u in ("g", "l", "lt", "cx", "m", "", None))          # desconhecida: vazio


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
    # o robô do Super ABC não traz categoria (nem o campo peso_variavel): só o nome decide
    from casos_hortifruti import SUPER_ABC
    for termo, nomes in SUPER_ABC["entram"].items():
        for nome in nomes:
            assert c.passa_no_filtro({"nome": nome, "preco_varejo": 5.0}, por_termo[termo]), f"Super ABC, {termo}: deveria entrar: {nome}"
    for termo, nomes in SUPER_ABC["saem"].items():
        for nome in nomes:
            assert not c.passa_no_filtro({"nome": nome, "preco_varejo": 5.0}, por_termo[termo]), f"Super ABC, {termo}: deveria sair: {nome}"
    for termo, itens in ADAPTADOS.items():
        for nome, categoria in itens:
            assert not c.passa_no_filtro({"nome": nome, "categoria": categoria, "peso_variavel": True}, por_termo[termo]), f"{termo}: deveria sair: {nome} [{categoria}]"


def teste_a_carga_diaria_coleta_a_lista_de_produtos_e_a_de_hortifruti_numa_coleta_so():
    """A gravação apaga os produtos antigos do mercado: uma carga que usasse SÓ a lista de hortifrúti (28 termos) apagaria os outros ~2.000
    produtos de cada mercado, e uma que usasse só a de produtos apagaria o hortifrúti. Por isso as duas vão juntas, por um caminho só."""
    teto, padrao = c.carregar_lista()
    assert not [t["termo"] for t in padrao if t.get("aceita_peso_variavel") or t.get("grupo") == "Hortifrúti"], "a lista de produtos não tem hortifrúti"
    assert c.LISTA_PADRAO.name == "lista_de_produtos.json" and c.LISTA_HORTIFRUTI.name == "lista_hortifruti.json"
    _, hortifruti = c.carregar_lista(c.LISTA_HORTIFRUTI)
    assert hortifruti and all(t.get("aceita_peso_variavel") and t.get("grupo") == "Hortifrúti" for t in hortifruti)
    assert not {t["termo"] for t in hortifruti} & {t["termo"] for t in padrao}

    teto_da_carga, termos = c.carregar_lista_da_carga()
    assert teto_da_carga == teto == 100 and len(termos) == len(padrao) + len(hortifruti) == 128
    assert [t["termo"] for t in termos] == [t["termo"] for t in padrao] + [t["termo"] for t in hortifruti]       # a de produtos primeiro: o repetido fica com ela

    # a carga lê a lista pelo caminho único; nada mais lê um arquivo de lista (o robô e a API usam o que a carga lhes entrega)
    carga = (c.RAIZ / "alimentar_banco.py").read_text(encoding="utf-8")
    assert "carregar_lista_da_carga()" in carga and "carregar_lista(" not in carga and "LISTA_HORTIFRUTI" not in carga and "LISTA_PADRAO" not in carga
    assert "lista_hortifruti" not in (c.RAIZ / "api_supabase.py").read_text(encoding="utf-8")


# ============================== carnes e queijos a peso (a lista própria, ainda FORA da carga diária) ==============================

# Os tipos do plano que já têm termo na lista de 100 (o item embalado): ao ligar na carga, esses termos passam a aceitar peso variável (docs/carnes_e_frios.md).
TERMOS_DE_CARNE_QUE_JA_ESTAO_NA_LISTA_DE_100 = {"frango congelado", "peito de frango", "carne moída", "linguiça", "bacon", "presunto", "queijo mussarela", "queijo prato"}


def teste_lista_de_carnes_e_frios_do_repositorio():
    from casos_carnes import CASOS, SUPER_ABC
    teto, termos = c.carregar_lista(c.RAIZ / "dados" / "lista_carnes_e_frios.json")
    nomes = [t["termo"] for t in termos]
    assert teto == 100 and len(nomes) == len(set(nomes)) == 10 and set(CASOS) == set(nomes) == set(SUPER_ABC["entram"]) == set(SUPER_ABC["saem"]), (len(nomes), set(CASOS) ^ set(nomes))
    for t in termos:
        assert t["grupo"] in ("Carnes", "Frios e queijos") and t["aceita_peso_variavel"] is True and t["nome_inclui"] and t["consultas"] and t["categorias"], t["termo"]
        for chave in ("categorias", "categorias_proibidas", "nome_exclui", "nome_inclui"):
            for padrao in t.get(chave, []):
                re.compile(padrao)
    por_termo = {t["termo"]: t for t in termos}
    for termo, caso in CASOS.items():
        assert caso["entram"], f"{termo}: precisa de ao menos um caso que entra"
        for nome, categoria in caso["entram"]:
            assert c.passa_no_filtro({"nome": nome, "categoria": categoria, "peso_variavel": True}, por_termo[termo]), f"{termo}: deveria entrar: {nome} [{categoria}]"
            assert c.passa_no_filtro({"nome": nome, "categoria": categoria, "peso_variavel": False}, por_termo[termo]), f"{termo}: o embalado também entra: {nome}"
        for nome, categoria in caso["saem"]:
            assert not c.passa_no_filtro({"nome": nome, "categoria": categoria, "peso_variavel": True}, por_termo[termo]), f"{termo}: deveria sair: {nome} [{categoria}]"
    # o Super ABC não traz categoria (nem o campo peso_variavel): só o nome decide
    for termo, nomes_do_abc in SUPER_ABC["entram"].items():
        for nome in nomes_do_abc:
            assert c.passa_no_filtro({"nome": nome, "preco_varejo": 5.0}, por_termo[termo]), f"Super ABC, {termo}: deveria entrar: {nome}"
    for termo, nomes_do_abc in SUPER_ABC["saem"].items():
        for nome in nomes_do_abc:
            assert not c.passa_no_filtro({"nome": nome, "preco_varejo": 5.0}, por_termo[termo]), f"Super ABC, {termo}: deveria sair: {nome}"
    # a mesma peça de porco e a carne de sol não são o corte bovino, e a peça premium e a congelada entram (a faixa é da chave de equivalência, não da lista)
    assert not c.passa_no_filtro({"nome": "Picanha Suína Embalagem 400g", "categoria": "Açougue > Carne Suína", "peso_variavel": True}, por_termo["picanha"])
    assert c.passa_no_filtro({"nome": "Picanha Angus Cong 1Kg", "categoria": "Aves, Carnes e Peixes > Carne Bovina", "peso_variavel": True}, por_termo["picanha"])
    assert c.passa_no_filtro({"nome": "Contra Filé Bovino Carapreta Congelado 1Kg", "categoria": "Aves, Carnes e Peixes > Carne Bovina", "peso_variavel": True}, por_termo["contra filé"])


def teste_a_lista_de_carnes_e_frios_ainda_nao_entra_na_carga():
    """Nada de carne a peso entra na carga antes do OK do dono (e da equivalência por corte, forma, estado, tempero e faixa): a lista existe, mas ninguém a lê."""
    _, carnes = c.carregar_lista(c.RAIZ / "dados" / "lista_carnes_e_frios.json")
    _, da_carga = c.carregar_lista_da_carga()
    assert len(da_carga) == 128 and not {t["termo"] for t in carnes} & {t["termo"] for t in da_carga}      # nenhum termo dela está na carga...
    assert not {t["termo"] for t in carnes} & {t["termo"] for t in c.carregar_lista()[1]}                  # ...e nenhum repete um da lista de 100 (poderia entrar sem erro)
    leitores = [p.name for p in c.RAIZ.glob("*.py") if "lista_carnes_e_frios" in p.read_text(encoding="utf-8")]
    assert leitores == [], f"alguém lê a lista de carnes antes da hora: {leitores}"
    ja_existem = {t["termo"] for t in c.carregar_lista()[1]}
    assert TERMOS_DE_CARNE_QUE_JA_ESTAO_NA_LISTA_DE_100 <= ja_existem, TERMOS_DE_CARNE_QUE_JA_ESTAO_NA_LISTA_DE_100 - ja_existem


def teste_listas_com_termo_repetido_ou_teto_diferente_nao_sobem_para_a_carga():
    import tempfile
    padrao = {"teto_por_termo": 100, "termos": [{"termo": "tomate"}, {"termo": "arroz"}]}
    hortifruti = {"teto_por_termo": 100, "termos": [{"termo": "Tomaté"}]}                    # o mesmo termo, só mudam o acento e a caixa
    with tempfile.TemporaryDirectory() as pasta:
        a, b = Path(pasta) / "a.json", Path(pasta) / "b.json"
        a.write_text(json.dumps(padrao), encoding="utf-8")
        b.write_text(json.dumps(hortifruti), encoding="utf-8")
        with mock.patch.object(c, "LISTA_PADRAO", a), mock.patch.object(c, "LISTA_HORTIFRUTI", b):
            try:
                c.carregar_lista_da_carga()
            except ValueError as erro:
                assert "repetidos" in str(erro)
            else:
                raise AssertionError("termo repetido entre as listas devia ser recusado")
            hortifruti.update(termos=[{"termo": "banana"}], teto_por_termo=50)
            b.write_text(json.dumps(hortifruti), encoding="utf-8")
            try:
                c.carregar_lista_da_carga()
            except ValueError as erro:
                assert "teto" in str(erro)
            else:
                raise AssertionError("teto diferente entre as listas devia ser recusado")


def teste_a_linha_de_comando_usa_a_lista_da_carga_e_aceita_uma_so():
    vistos = []

    def coletar_falso(http, mercados, termos, teto, ao_terminar=None, **resto):
        vistos.append([t["termo"] for t in termos])
        return {m: {} for m in mercados}, []

    with mock.patch.object(c, "coletar", coletar_falso), mock.patch("sys.stdout", io.StringIO()), mock.patch.object(c.sys.stdout, "reconfigure", create=True):
        c.principal(["--termos", "arroz,tomate,banana", "--mercados", "Supernosso"])                                    # sem --lista: a lista da carga (as duas)
        c.principal(["--termos", "arroz,tomate,banana", "--mercados", "Supernosso", "--lista", str(c.LISTA_HORTIFRUTI)])    # com --lista: só aquela
        c.principal(["--termos", "arroz,tomate,banana", "--mercados", "Supernosso", "--lista", str(c.LISTA_PADRAO)])
    assert vistos == [["arroz", "banana", "tomate"], ["banana", "tomate"], ["arroz"]]


def teste_item_por_quilo_nao_leva_faixa_de_atacado():
    por_quilo = {"unidade": "kg", "preco_varejo": 4.99, "preco_atacado": 3.99, "quantidade_atacado": 6}
    assert c.sem_atacado_se_por_quilo(por_quilo) == {"unidade": "kg", "preco_varejo": 4.99, "preco_atacado": 4.99, "quantidade_atacado": 1}
    pacote = {"unidade": "un", "preco_varejo": 7.99, "preco_atacado": 6.99, "quantidade_atacado": 4}
    assert c.sem_atacado_se_por_quilo(dict(pacote)) == pacote                           # o atacado do pacote continua valendo
    sem_unidade = {"unidade": None, "preco_varejo": 7.99, "preco_atacado": 6.99, "quantidade_atacado": 4}
    assert c.sem_atacado_se_por_quilo(dict(sem_unidade)) == sem_unidade
    sem_faixa = {"unidade": "kg", "preco_varejo": 4.99, "preco_atacado": 4.99, "quantidade_atacado": 1}
    assert c.sem_atacado_se_por_quilo(dict(sem_faixa)) == sem_faixa


def teste_a_coleta_tira_o_atacado_do_item_por_quilo_e_deixa_o_do_pacote():
    termo = {"termo": "cebola", "aceita_peso_variavel": True, "nome_inclui": ["^cebola\\b"]}

    def baixar(http, consulta):
        return [{"id_origem": "1", "nome": "Cebola Quilo", "categoria": "", "unidade": "kg", "peso_variavel": True, "preco_varejo": 6.99, "preco_atacado": 5.5, "quantidade_atacado": 5},
                {"id_origem": "2", "nome": "Cebola 19kg", "categoria": "", "unidade": "un", "peso_variavel": False, "preco_varejo": 170.8, "preco_atacado": 160.0, "quantidade_atacado": 2}]

    resultado, erros = c.coletar(None, ["Atacadao"], [termo], 100, baixadores={"Atacadao": baixar})
    kilo, saco = resultado["Atacadao"]["cebola"]
    assert not erros and (kilo["preco_atacado"], kilo["quantidade_atacado"]) == (6.99, 1) and (saco["preco_atacado"], saco["quantidade_atacado"]) == (160.0, 2)


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


# ============================== o disjuntor e a segunda rodada ==============================

def termos_de(n):
    return [{"termo": f"termo{i:03d}"} for i in range(n)]


def linhas_de(consulta):
    return [{"id_origem": consulta, "nome": consulta, "categoria": "", "peso_variavel": False}]


def teste_mercado_fora_do_ar_para_depois_de_seis_falhas_seguidas():
    chamadas = {"Atacadao": [], "Supernosso": []}

    def fora_do_ar(http, consulta):
        chamadas["Atacadao"].append(consulta)
        raise c.ErroDeColeta(f"HTTP 403 em https://www.atacadao.com.br/api/graphql?q={consulta}")

    def saudavel(http, consulta):
        chamadas["Supernosso"].append(consulta)
        return linhas_de(consulta)

    termos = termos_de(100)
    resultado, erros = c.coletar(None, ["Atacadao", "Supernosso"], termos, 100, baixadores={"Atacadao": fora_do_ar, "Supernosso": saudavel}, segunda_rodada=False)
    assert len(chamadas["Atacadao"]) == 6                          # parou na sexta falha seguida, em vez de perguntar os 100
    assert len(chamadas["Supernosso"]) == 100 and len(resultado["Supernosso"]) == 100       # o outro mercado nem percebe
    atacadao = [e for e in erros if e[0] == "Atacadao"]
    assert [e[1] for e in atacadao] == [t["termo"] for t in termos]                          # todos os termos aparecem como falha, na ordem da lista
    assert all("HTTP 403" in e[2] and not disjuntor.foi_pulado(e[2]) for e in atacadao[:6])
    assert all(disjuntor.foi_pulado(e[2]) and "6 vezes seguidas" in e[2] and "HTTP 403" in e[2] for e in atacadao[6:])
    assert resultado["Atacadao"] == {}


def teste_um_acerto_no_meio_impede_o_disjuntor():
    chamadas = []

    def baixar(http, consulta):
        chamadas.append(consulta)
        if int(consulta[-3:]) % 6 != 5:                           # cinco falhas, um acerto, cinco falhas...
            raise c.ErroDeColeta("caiu")
        return linhas_de(consulta)

    resultado, erros = c.coletar(None, ["Apoio Entrega"], termos_de(60), 100, baixadores={"Apoio Entrega": baixar}, segunda_rodada=False)
    assert len(chamadas) == 60 and len(resultado["Apoio Entrega"]) == 10 and len(erros) == 50
    assert not any(disjuntor.foi_pulado(e[2]) for e in erros)


def teste_limite_de_falhas_vem_do_chamador_e_zero_desliga():
    def sempre_cai(http, consulta):
        raise c.ErroDeColeta("caiu")

    for limite, esperado in ((2, 2), (0, 30)):
        chamadas = []

        def baixar(http, consulta, chamadas=chamadas):
            chamadas.append(consulta)
            return sempre_cai(http, consulta)

        c.coletar(None, ["Apoio Entrega"], termos_de(30), 100, baixadores={"Apoio Entrega": baixar}, limite_de_falhas=limite, segunda_rodada=False)
        assert len(chamadas) == esperado, (limite, len(chamadas))


def teste_segunda_rodada_recupera_uma_falha_passageira():
    vezes, pausas, vistos = {}, [], []

    def baixar(http, consulta):
        vezes[consulta] = vezes.get(consulta, 0) + 1
        if consulta == "termo002" and vezes[consulta] == 1:
            raise c.ErroDeColeta("HTTP 503 passageiro")
        return linhas_de(consulta)

    termos = termos_de(5)
    resultado, erros = c.coletar(None, ["Supernosso"], termos, 100, lambda m, t, brutas, esc: vistos.append(t["termo"]),
                                 baixadores={"Supernosso": baixar}, pausa=45, dormir=pausas.append)
    assert erros == [] and vezes["termo002"] == 2 and all(vezes[t["termo"]] == (2 if t["termo"] == "termo002" else 1) for t in termos)
    assert pausas == [45]                                           # esperou antes de tentar de novo
    assert list(resultado["Supernosso"]) == [t["termo"] for t in termos]      # a ordem da lista, mesmo com o termo recuperado no fim
    assert sorted(vistos) == [t["termo"] for t in termos] and vistos.count("termo002") == 1   # o aviso de "termo pronto" vale uma vez por termo


def teste_sem_falha_nao_ha_segunda_rodada_nem_pausa():
    pausas = []
    resultado, erros = c.coletar(None, ["Supernosso"], termos_de(5), 100, baixadores={"Supernosso": lambda h, q: linhas_de(q)}, dormir=pausas.append)
    assert erros == [] and pausas == [] and len(resultado["Supernosso"]) == 5


def teste_segunda_rodada_desligada_nao_repete_nem_espera():
    chamadas, pausas = [], []

    def baixar(http, consulta):
        chamadas.append(consulta)
        raise c.ErroDeColeta("caiu")

    _, erros = c.coletar(None, ["Supernosso"], termos_de(3), 100, baixadores={"Supernosso": baixar}, segunda_rodada=False, dormir=pausas.append)
    assert len(chamadas) == 3 and pausas == [] and len(erros) == 3


def teste_a_pausa_padrao_e_lida_na_hora():
    pausas = []

    def uma_falha(http, consulta):
        raise c.ErroDeColeta("caiu")

    anterior = disjuntor.PAUSA_DA_SEGUNDA_RODADA
    disjuntor.PAUSA_DA_SEGUNDA_RODADA = 7
    try:
        c.coletar(None, ["Supernosso"], termos_de(1), 100, baixadores={"Supernosso": uma_falha}, dormir=pausas.append)
    finally:
        disjuntor.PAUSA_DA_SEGUNDA_RODADA = anterior
    assert pausas == [7]
    c.coletar(None, ["Supernosso"], termos_de(1), 100, baixadores={"Supernosso": uma_falha}, dormir=pausas.append)
    assert pausas == [7, 0]                                         # (nos testes a constante vale 0, veja o início do arquivo)


def teste_mercado_que_volta_na_segunda_rodada_completa_a_coleta():
    chamadas = []

    def baixar(http, consulta):
        chamadas.append(consulta)
        if len(chamadas) <= 6:                                      # fora do ar nas seis primeiras perguntas, depois volta
            raise c.ErroDeColeta("HTTP 403")
        return linhas_de(consulta)

    termos = termos_de(100)
    resultado, erros = c.coletar(None, ["Atacadao"], termos, 100, baixadores={"Atacadao": baixar}, pausa=0, dormir=lambda s: None)
    assert erros == [] and len(resultado["Atacadao"]) == 100        # inclusive os 94 que o disjuntor pulou na primeira rodada
    assert len(chamadas) == 6 + 100                                 # 6 que falharam + a segunda rodada inteira
    assert list(resultado["Atacadao"]) == [t["termo"] for t in termos]


def teste_mercado_que_continua_fora_do_ar_desiste_na_segunda_rodada():
    chamadas = []

    def baixar(http, consulta):
        chamadas.append(consulta)
        raise c.ErroDeColeta("HTTP 403")

    termos = termos_de(100)
    resultado, erros = c.coletar(None, ["Atacadao"], termos, 100, baixadores={"Atacadao": baixar}, dormir=lambda s: None)
    assert len(chamadas) == 12                                      # 6 na primeira rodada, 6 na segunda: nunca os 200
    assert resultado["Atacadao"] == {} and len(erros) == 100
    assert sum(1 for e in erros if not disjuntor.foi_pulado(e[2])) == 6
    assert [e[1] for e in erros][:6] == [t["termo"] for t in termos][:6]          # o primeiro erro é uma falha de verdade, não um "não tentado"


def teste_relatorio_da_linha_de_comando_resume_os_termos_pulados():
    def baixar(http, consulta):
        raise c.ErroDeColeta("HTTP 403")

    lista = Path(__file__).resolve().parent / "_lista_do_disjuntor.json"
    lista.write_text(json.dumps({"teto_por_termo": 100, "termos": termos_de(40)}), encoding="utf-8")
    saida = io.StringIO()
    try:
        with mock.patch.dict(c.BAIXADORES, {"Apoio Entrega": baixar}), mock.patch("sys.stdout", saida), mock.patch.object(c.sys.stdout, "reconfigure", create=True):
            codigo = c.principal(["--mercados", "Apoio Entrega", "--lista", str(lista)])
    finally:
        lista.unlink()
    texto = saida.getvalue()
    assert codigo == 1 and texto.count("ERRO Apoio Entrega /") == 6          # as seis falhas de verdade, uma a uma
    assert "ERRO Apoio Entrega (34 termos)" in texto and "6 vezes seguidas" in texto  # e os 34 que não foram tentados, numa linha só


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_")]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
