"""Busca de produtos no catálogo: ignora acentos e maiúsculas e exige todas as palavras digitadas.

Com o catálogo grande (cerca de 8 mil produtos), só "o nome contém a palavra" traz ruído: "arroz" acha condicionador com
arroz preto e "óleo" acha xampu com óleo de argan. Por isso os resultados têm duas faixas:

- **principais**: o produto é daquilo que foi digitado. O `termo` da lista de produtos (a coluna `termo`, ex.: `arroz`) tem as
  palavras digitadas, ou o nome do produto **começa** por elas ("Arroz Branco Camil…");
- **só citam**: a palavra aparece no meio do nome ("Condicionador … Arroz Preto").

Havendo ao menos `MINIMO_DE_PRINCIPAIS` principais, só eles voltam e o resto é contado como oculto. Com poucos principais
(a pessoa digitou uma marca, como "ninho", ou um produto que a lista não tem), voltam todos, para a busca nunca ficar vazia.
"""
import re
import unicodedata
from collections import Counter, namedtuple

# Palavras que não ajudam a achar o produto e atrapalham quando o nome não as traz
# ("óleo de soja" deve achar também "Óleo Soja Liza").
PALAVRAS_DE_LIGACAO = {"de", "da", "do", "das", "dos", "e", "com", "para", "em"}
MINIMO_DE_PRINCIPAIS = 3
LIMITE_DE_RESULTADOS = 400        # a busca de "a" casava 6,6 mil produtos e o agrupamento levava 24 s
TAMANHO_MINIMO_PARA_PREFIXO = 4   # "arro" acha "arroz"; "sal" não acha "salsicha"

Entrada = namedtuple("Entrada", "nome palavras_do_nome palavras_do_termo produto")
# produtos: o que volta; so_citam_por_mercado: {mercado: quantos} dos que só citam a palavra (escondidos ou não);
# ocultos_so_citam: quantos desses ficaram escondidos; ocultos_pelo_limite: quantos passaram do teto de resultados.
Busca = namedtuple("Busca", "produtos so_citam_por_mercado ocultos_so_citam ocultos_pelo_limite")


def sem_acento(texto):
    """Minúsculas e sem acentos: 'Óleo' vira 'oleo'."""
    decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def palavras_da_busca(item):
    palavras = [p.strip(".,;:!?()-") for p in sem_acento(item).split()]
    palavras = [p for p in palavras if p]
    uteis = [p for p in palavras if p not in PALAVRAS_DE_LIGACAO]
    return uteis or palavras


def indexar(produtos):
    """Calcula uma vez o nome e o termo de cada produto, sem acento: [Entrada, ...]."""
    return [Entrada(nome, re.findall(r"[a-z0-9]+", nome), re.findall(r"[a-z0-9]+", sem_acento(produto.get("termo") or "")), produto)
            for produto in produtos for nome in [sem_acento(produto["nome"])]]


def _e_a_palavra(digitada, palavra):
    """A palavra digitada é essa palavra (ou, se for longa, o começo dela)."""
    return palavra == digitada or (len(digitada) >= TAMANHO_MINIMO_PARA_PREFIXO and palavra.startswith(digitada))


def _e_principal(palavras, entrada):
    # 1) o termo da lista tem todas as palavras digitadas ("arroz" -> termo "arroz"; "leite" -> "leite em pó")
    if entrada.palavras_do_termo and all(any(_e_a_palavra(p, w) for w in entrada.palavras_do_termo) for p in palavras):
        return True
    # 2) o nome começa pela primeira palavra digitada e traz as outras ("arroz integral" -> "Arroz Integral Tio João")
    return bool(entrada.palavras_do_nome) and _e_a_palavra(palavras[0], entrada.palavras_do_nome[0]) \
        and all(p in entrada.nome for p in palavras[1:])


def buscar_detalhado(catalogo_indexado, item, minimo_de_principais=MINIMO_DE_PRINCIPAIS, limite=LIMITE_DE_RESULTADOS, incluir_so_citam=False):
    """Os produtos da busca, principais primeiro, e o que ficou de fora (veja `Busca`).

    Os que só citam a palavra voltam quando há menos de `minimo_de_principais` principais, ou quando `incluir_so_citam` pede
    (o botão "Mostrar também" do site). Voltam como cópias marcadas com `so_cita: True`; o catálogo em memória não é alterado.
    """
    palavras = palavras_da_busca(item)
    if not palavras:
        return Busca([], {}, 0, 0)
    achados = [(e.produto, _e_principal(palavras, e)) for e in catalogo_indexado if all(p in e.nome for p in palavras)]
    principais = [produto for produto, principal in achados if principal]
    so_citam = [produto for produto, principal in achados if not principal]
    mostrar_so_citam = incluir_so_citam or len(principais) < minimo_de_principais
    produtos = principais + ([{**produto, "so_cita": True} for produto in so_citam] if mostrar_so_citam else [])
    pelo_limite = max(0, len(produtos) - limite)     # busca de uma letra ou de palavra comum: o agrupamento ficaria lento e ninguém lê 6 mil linhas
    return Busca(produtos[:limite], dict(Counter(p["supermercado"] for p in so_citam)), 0 if mostrar_so_citam else len(so_citam), pelo_limite)


def buscar(catalogo_indexado, item, minimo_de_principais=MINIMO_DE_PRINCIPAIS, limite=LIMITE_DE_RESULTADOS):
    """(produtos, ocultos): os produtos da busca, principais primeiro, e quantos ficaram de fora (só citam a palavra, ou passaram do limite)."""
    busca = buscar_detalhado(catalogo_indexado, item, minimo_de_principais, limite)
    return busca.produtos, busca.ocultos_so_citam + busca.ocultos_pelo_limite


def filtrar(catalogo_indexado, item):
    """Só os produtos de `buscar`."""
    return buscar(catalogo_indexado, item)[0]
