"""Coletor por API pública (VTEX) para Apoio Entrega, Atacadão e Supernosso.

Em vez de abrir um navegador e ler a primeira página de cada busca (20 a 30 itens), pergunta direto à API que
os próprios sites usam. Isso traz até `teto` produtos por termo, com marca, categoria e código de barras (EAN).
O Super ABC não tem API aberta e continua pelo robô (Scraper_SuperABC.py).

De onde vem cada dado (sondado em 05/11/2026, ver docs/coletor_por_api.md):
- Supernosso: API de catálogo `/api/catalog_system/pub/products/search/`; só vale o que tem estoque.
- Apoio Entrega: a mesma API com `sc=15` (canal de Betim). O atacado é o campo "Quantidade para atacado" do
  produto mais o preço dessa quantidade na simulação de carrinho (`/api/checkout/pub/orderForms/simulation`).
- Atacadão: a API de catálogo devolve preço 0 para mais da metade dos produtos (não sabe qual loja) e não traz
  atacado. O que o site usa é o GraphQL `/api/graphql?operationName=ProductsQuery`, que aceita a loja de Betim
  (vendedor `atacadaobr167`) e devolve as faixas de preço (`minQuantity`). O EAN vem da API de catálogo, ligado
  pelo productId.

Só leitura: nada aqui escreve em banco. Rodar o relatório:  python coletor_vtex.py --termos arroz,feijão
"""
import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from busca import sem_acento

RAIZ = Path(__file__).resolve().parent
LISTA_PADRAO = RAIZ / "dados" / "lista_de_produtos.json"

MERCADOS = {
    "Apoio Entrega": {"base": "https://www.apoioentrega.com", "canal": "15", "uf": "MG"},
    "Atacadao": {"base": "https://www.atacadao.com.br", "vendedor": "atacadaobr167", "cep": "32607600", "uf": "BR"},
    "Supernosso": {"base": "https://www.supernossoemcasa.com.br", "uf": "MG"},
}

POR_PAGINA = 50          # a API de catálogo devolve no máximo 50 por chamada
MAX_PAGINAS = 6          # até 300 produtos brutos por termo e mercado (o teto de 100 vale depois do filtro)
EAN_VALIDOS = (8, 12, 13, 14)
STATUS_QUE_REPETE = (408, 425, 429, 500, 502, 503, 504)


class ErroDeColeta(Exception):
    """A API não respondeu como esperado, mesmo depois de repetir."""


# ============================== rede ==============================

class ClienteHttp:
    """GET/POST de JSON com repetição. Os sites às vezes respondem 500 ou 429 numa chamada e 200 na seguinte."""

    def __init__(self, pausa=0.2, tentativas=4, espera=2.0, timeout=40):
        self.pausa, self.tentativas, self.espera, self.timeout = pausa, tentativas, espera, timeout
        self.chamadas = 0

    def _enviar(self, url, corpo=None, cabecalhos=None):
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        cab = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        if dados is not None:
            cab["Content-Type"] = "application/json"
        cab.update(cabecalhos or {})
        ultimo = None
        for numero in range(1, self.tentativas + 1):
            time.sleep(self.pausa)
            self.chamadas += 1
            try:
                requisicao = urllib.request.Request(url, data=dados, headers=cab)
                with urllib.request.urlopen(requisicao, timeout=self.timeout) as resposta:
                    return json.loads(resposta.read().decode("utf-8"))
            except urllib.error.HTTPError as erro:
                ultimo = erro
                if erro.code not in STATUS_QUE_REPETE:
                    raise ErroDeColeta(f"HTTP {erro.code} em {url[:140]}") from erro
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as erro:
                ultimo = erro
            if numero < self.tentativas:
                time.sleep(self.espera * numero)
        raise ErroDeColeta(f"sem resposta depois de {self.tentativas} tentativas ({ultimo!r}) em {url[:140]}")

    def get_json(self, url, cabecalhos=None):
        return self._enviar(url, None, cabecalhos)

    def post_json(self, url, corpo, cabecalhos=None):
        return self._enviar(url, corpo, cabecalhos)


# ============================== utilidades ==============================

def ean_valido(texto):
    """Só dígitos, com 8, 12, 13 ou 14 posições e sem repetição óbvia. Códigos internos (ex.: '8200') são descartados."""
    digitos = re.sub(r"\D", "", str(texto or ""))
    if len(digitos) not in EAN_VALIDOS or len(set(digitos)) <= 2:
        return None
    return digitos


def numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def vendido_por_peso(unidade_de_medida, marca_de_peso_variavel=""):
    """Produto de peso variável (queijo fatiado, carne moída, hortifruti): o preço é por kg, fica para a Fase 2."""
    return str(unidade_de_medida or "").strip().lower() in ("kg", "g") or str(marca_de_peso_variavel or "").strip().lower() in ("yes", "sim", "true")


def caminho_da_categoria(texto):
    """'/Mercearia/Grãos/Arroz/' -> ['Mercearia', 'Grãos', 'Arroz']."""
    return [parte.strip() for parte in str(texto or "").split("/") if parte.strip()]


def folha_da_categoria(categorias):
    """A categoria mais específica (mais níveis) entre as que o produto declara, como 'Mercearia > Grãos > Arroz'."""
    caminhos = [caminho_da_categoria(c) for c in categorias or []]
    caminhos = [c for c in caminhos if c]
    return " > ".join(max(caminhos, key=len)) if caminhos else ""


def paginar_ids(ids, tamanho=POR_PAGINA):
    ids = list(ids)
    for i in range(0, len(ids), tamanho):
        yield ids[i:i + tamanho]


# ============================== API de catálogo (Apoio, Supernosso e EAN do Atacadão) ==============================

def produtos_do_catalogo(http, base, consulta, extra="", max_paginas=MAX_PAGINAS, ordem=None):
    """Produtos da busca por texto (do mais relevante para o menos; `ordem` pede outra, como OrderByTopSaleDESC), em páginas de 50."""
    for pagina in range(max_paginas):
        de = pagina * POR_PAGINA
        url = (f"{base}/api/catalog_system/pub/products/search/?ft={urllib.parse.quote(consulta)}"
               f"&_from={de}&_to={de + POR_PAGINA - 1}{'&O=' + ordem if ordem else ''}{extra}")
        lote = http.get_json(url)
        yield from lote
        if len(lote) < POR_PAGINA:
            return


def ofertas_do_produto(produto):
    """Um (item, oferta) por SKU com estoque e preço. Produto sem estoque na região não entra."""
    for item in produto.get("items", []):
        for vendedor in item.get("sellers", []):
            oferta = vendedor.get("commertialOffer") or {}
            if numero(oferta.get("Price")) > 0 and numero(oferta.get("AvailableQuantity")) > 0:
                yield item, vendedor, oferta
                break


def nome_do_item(produto, item):
    if len(produto.get("items", [])) <= 1:
        return produto.get("productName", "").strip()
    return (item.get("nameComplete") or f"{produto.get('productName', '')} {item.get('name', '')}").strip()


def linha_do_catalogo(mercado, produto, item, oferta, termo):
    return {
        "supermercado": mercado,
        "id_origem": f"{produto.get('productId')}:{item.get('itemId')}",
        "nome": nome_do_item(produto, item),
        "marca": (produto.get("brand") or "").strip() or None,
        "ean": ean_valido(item.get("ean")),
        "categoria": folha_da_categoria(produto.get("categories")),
        "preco_varejo": round(numero(oferta.get("Price")), 2),
        "preco_atacado": round(numero(oferta.get("Price")), 2),
        "quantidade_atacado": 1,
        "uf_cobertura": MERCADOS[mercado]["uf"],
        "termo": termo,
        "peso_variavel": vendido_por_peso(item.get("measurementUnit"), (produto.get("Peso variável") or [""])[0]),
    }


def baixar_supernosso(http, consulta):
    base = MERCADOS["Supernosso"]["base"]
    return [linha_do_catalogo("Supernosso", p, item, oferta, consulta)
            for p in produtos_do_catalogo(http, base, consulta)
            for item, _, oferta in ofertas_do_produto(p)]


def baixar_apoio(http, consulta):
    config = MERCADOS["Apoio Entrega"]
    brutos = []
    for p in produtos_do_catalogo(http, config["base"], consulta, extra=f"&sc={config['canal']}"):
        for item, vendedor, oferta in ofertas_do_produto(p):
            linha = linha_do_catalogo("Apoio Entrega", p, item, oferta, consulta)
            try:
                minimo = int(float(str((p.get("Quantidade para atacado") or [""])[0]).replace(",", ".")))
            except ValueError:
                minimo = 0
            brutos.append((linha, item, vendedor, minimo))
    _preencher_atacado_do_apoio(http, config, brutos)
    return [linha for linha, _, _, _ in brutos]


def _preencher_atacado_do_apoio(http, config, brutos):
    """Pergunta à simulação de carrinho o preço de cada produto na quantidade de atacado (vários por chamada)."""
    com_atacado = [b for b in brutos if b[3] > 1]
    for lote in paginar_ids(com_atacado, 40):
        corpo = {"items": [{"id": item["itemId"], "quantity": minimo, "seller": vendedor["sellerId"]} for _, item, vendedor, minimo in lote],
                 "country": "BRA", "postalCode": "32607600"}
        resposta = http.post_json(f"{config['base']}/api/checkout/pub/orderForms/simulation?sc={config['canal']}", corpo)
        precos = {}
        for retorno in resposta.get("items", []):
            if retorno.get("availability") == "available" and numero(retorno.get("sellingPrice")) > 0:
                precos[str(retorno.get("id"))] = round(numero(retorno["sellingPrice"]) / 100, 2)
        for linha, item, _, minimo in lote:
            preco = precos.get(str(item["itemId"]))
            if preco and preco < linha["preco_varejo"]:
                linha["preco_atacado"], linha["quantidade_atacado"] = preco, minimo


# ============================== Atacadão (GraphQL do site + EAN do catálogo) ==============================

def regiao_do_atacadao(vendedor):
    return base64.b64encode(f"SW#{vendedor}".encode("utf-8")).decode("ascii")


def _graphql_com_repeticao(http, url, base, tentativas=3, espera=2.0):
    """O GraphQL do site às vezes devolve 'errors' (ex.: "Cannot read properties of undefined (reading 'price')") numa
    chamada e responde bem na seguinte, com a mesma busca. Por isso repete antes de desistir do termo."""
    ultimo = None
    for numero_da_tentativa in range(1, tentativas + 1):
        resposta = http.get_json(url, {"Referer": base + "/"})
        if not resposta.get("errors"):
            return resposta
        ultimo = str(resposta["errors"])[:200]
        if numero_da_tentativa < tentativas:
            time.sleep(espera * numero_da_tentativa)
    raise ErroDeColeta(f"GraphQL do Atacadão devolveu erro {tentativas} vezes: {ultimo}")


def nos_do_graphql_atacadao(http, consulta, vendedor, por_pagina=50, max_paginas=MAX_PAGINAS, ordem="score_desc"):
    base = MERCADOS["Atacadao"]["base"]
    regiao = regiao_do_atacadao(vendedor)
    canal = json.dumps({"salesChannel": "1", "seller": vendedor, "regionId": regiao}, separators=(",", ":"))
    recebidos = 0
    for _ in range(max_paginas):
        variaveis = {"first": por_pagina, "after": str(recebidos), "sort": ordem, "term": consulta,
                     "selectedFacets": [{"key": "region-id", "value": regiao}, {"key": "channel", "value": canal},
                                        {"key": "locale", "value": "pt-BR"}]}
        url = f"{base}/api/graphql?operationName=ProductsQuery&variables={urllib.parse.quote(json.dumps(variaveis, separators=(',', ':')))}"
        resposta = _graphql_com_repeticao(http, url, base)
        produtos = (((resposta.get("data") or {}).get("search") or {}).get("products")) or {}
        arestas = produtos.get("edges") or []
        for aresta in arestas:
            yield aresta["node"]
        recebidos += len(arestas)
        if not arestas or recebidos >= numero((produtos.get("pageInfo") or {}).get("totalCount")):
            return


def preco_e_atacado_do_no(no):
    """(varejo, atacado, quantidade). Varejo = faixa de 1 unidade; atacado = a primeira faixa acima de 1, se for mais barata."""
    faixas = sorted(((int(numero(o.get("minQuantity")) or 1), numero(o.get("price"))) for o in (no.get("offers") or {}).get("offers") or []
                     if numero(o.get("price")) > 0), key=lambda f: f[0])
    if not faixas:
        return None
    varejo = faixas[0][1]
    for minimo, preco in faixas[1:]:
        if minimo > 1 and preco < varejo:
            return round(varejo, 2), round(preco, 2), minimo
    return round(varejo, 2), round(varejo, 2), 1


def eans_do_atacadao(http, ids_de_produto):
    """productId -> EAN, buscando até 50 produtos por chamada no catálogo."""
    base = MERCADOS["Atacadao"]["base"]
    eans = {}
    for lote in paginar_ids(sorted(set(ids_de_produto))):
        url = f"{base}/api/catalog_system/pub/products/search/?" + "&".join(f"fq=productId:{i}" for i in lote)
        for produto in http.get_json(url):
            for item in produto.get("items", []):
                ean = ean_valido(item.get("ean"))
                if ean:
                    eans[str(produto.get("productId"))] = ean
                    break
    return eans


def baixar_atacadao(http, consulta):
    vendedor = MERCADOS["Atacadao"]["vendedor"]
    linhas, ids = [], []
    for no in nos_do_graphql_atacadao(http, consulta, vendedor):
        precos = preco_e_atacado_do_no(no)
        if not precos:
            continue
        varejo, atacado, minimo = precos
        produto_id = str((no.get("isVariantOf") or {}).get("productGroupID") or no.get("id"))
        trilha = [str(n.get("name", "")).strip() for n in ((no.get("breadcrumbList") or {}).get("itemListElement") or [])]
        # o último nível da trilha é o próprio produto; a categoria é o que vem antes
        categoria = " > ".join(t for t in trilha[:-1] if t)
        linhas.append({
            "supermercado": "Atacadao", "id_origem": f"{produto_id}:{no.get('sku')}", "nome": str(no.get("name", "")).strip(),
            "marca": ((no.get("brand") or {}).get("brandName") or "").strip() or None, "ean": None, "categoria": categoria,
            "preco_varejo": varejo, "preco_atacado": atacado, "quantidade_atacado": minimo,
            "uf_cobertura": MERCADOS["Atacadao"]["uf"], "termo": consulta, "peso_variavel": vendido_por_peso(no.get("measurementUnit")),
        })
        ids.append(produto_id)
    eans = eans_do_atacadao(http, ids) if ids else {}
    for linha in linhas:
        linha["ean"] = eans.get(linha["id_origem"].split(":")[0])
    return linhas


BAIXADORES = {"Apoio Entrega": baixar_apoio, "Atacadao": baixar_atacadao, "Supernosso": baixar_supernosso}


# ============================== lista de produtos e seleção ==============================

def carregar_lista(caminho=LISTA_PADRAO):
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return dados["teto_por_termo"], dados["termos"]


def _casa(padroes, texto):
    return any(re.search(p, texto) for p in padroes or [])


def passa_no_filtro(linha, termo):
    """Aplica as regras do termo: categoria esperada, nomes proibidos e peso variável.

    Todas as expressões são regulares aplicadas a textos em minúsculas e sem acento.
    `categorias`: ao menos uma precisa casar com o caminho da categoria do produto, como "mercearia > graos > arroz".
    `categorias_proibidas`: se alguma casar com o caminho, o produto sai (xampu que cita "óleo", gelatina capilar...).
    `nome_inclui`: ao menos uma precisa casar com o nome. `nome_exclui`: se alguma casar com o nome, o produto sai.
    """
    if linha.get("peso_variavel"):
        return False
    nome = sem_acento(linha["nome"])
    if _casa(termo.get("nome_exclui"), nome):
        return False
    if termo.get("nome_inclui") and not _casa(termo["nome_inclui"], nome):
        return False
    caminho = " > ".join(sem_acento(p) for p in linha["categoria"].split(" > "))
    if _casa(termo.get("categorias_proibidas"), caminho):
        return False
    if termo.get("categorias"):
        return _casa(termo["categorias"], caminho)
    return True


def selecionar(linhas, termo, teto):
    """Mantém a ordem (mais vendidos primeiro), tira repetidos e corta no teto."""
    vistos, escolhidas = set(), []
    for linha in linhas:
        if linha["id_origem"] in vistos or not passa_no_filtro(linha, termo):
            continue
        vistos.add(linha["id_origem"])
        escolhidas.append(linha)
        if len(escolhidas) >= teto:
            break
    return escolhidas


def _coletar_mercado(http, mercado, termos, teto, ao_terminar_termo, baixadores):
    por_termo, erros = {}, []
    for termo in termos:
        try:
            brutas = []
            for consulta in termo.get("consultas") or [termo["termo"]]:
                brutas += baixadores[mercado](http, consulta)
            escolhidas = selecionar(brutas, termo, teto)
        except ErroDeColeta as erro:
            erros.append((mercado, termo["termo"], str(erro)))
            continue
        for linha in escolhidas:
            linha["termo"] = termo["termo"]
        por_termo[termo["termo"]] = escolhidas
        if ao_terminar_termo:
            ao_terminar_termo(mercado, termo, len(brutas), escolhidas)
    return por_termo, erros


def coletar(http, mercados, termos, teto, ao_terminar_termo=None, baixadores=None):
    """({mercado: {termo: [linhas]}}, [erros]). Cada mercado roda em sua própria linha de execução (são sites diferentes).

    Uma falha em um termo vira erro daquele (mercado, termo); os demais termos continuam.
    """
    baixadores = baixadores or BAIXADORES
    with ThreadPoolExecutor(max_workers=max(1, len(mercados))) as pool:
        futuros = {m: pool.submit(_coletar_mercado, http, m, termos, teto, ao_terminar_termo, baixadores) for m in mercados}
        feitos = {m: futuros[m].result() for m in mercados}
    return {m: feitos[m][0] for m in mercados}, [erro for m in mercados for erro in feitos[m][1]]


def resumo_de_termo(linhas):
    com_atacado = sum(1 for l in linhas if l["quantidade_atacado"] > 1)
    com_ean = sum(1 for l in linhas if l["ean"])
    return f"{len(linhas):>3} itens, {com_ean:>3} c/EAN, {com_atacado:>3} c/atacado"


# ============================== linha de comando ==============================

def principal(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Relatório do coletor por API (só leitura, não grava em banco).")
    parser.add_argument("--termos", help="só estes termos da lista, separados por vírgula (padrão: todos)")
    parser.add_argument("--mercados", help="só estes mercados, separados por vírgula (padrão: os três)")
    parser.add_argument("--lista", default=str(LISTA_PADRAO))
    parser.add_argument("--saida", help="grava as linhas coletadas neste arquivo JSON")
    args = parser.parse_args(argv)

    teto, termos = carregar_lista(args.lista)
    if args.termos:
        pedidos = {sem_acento(t.strip()) for t in args.termos.split(",")}
        termos = [t for t in termos if sem_acento(t["termo"]) in pedidos]
    mercados = [m.strip() for m in args.mercados.split(",")] if args.mercados else list(MERCADOS)
    desconhecidos = [m for m in mercados if m not in MERCADOS]
    if desconhecidos:
        parser.error(f"mercado desconhecido: {desconhecidos}; opções: {list(MERCADOS)}")

    http = ClienteHttp()
    inicio = time.time()

    def ao_terminar(mercado, termo, brutas, escolhidas):
        print(f"{termo['termo']:<24} {mercado:<14} {brutas:>4} brutos -> {resumo_de_termo(escolhidas)}", flush=True)

    resultado, erros = coletar(http, mercados, termos, teto, ao_terminar)
    total = sum(len(l) for por_termo in resultado.values() for l in por_termo.values())
    print(f"\n{total} linhas em {time.time() - inicio:.0f}s, {http.chamadas} chamadas, {len(erros)} erro(s)")
    for mercado, termo, erro in erros:
        print(f"  ERRO {mercado} / {termo}: {erro}")
    if args.saida:
        Path(args.saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(principal())
