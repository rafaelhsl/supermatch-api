"""Busca de produtos no catálogo: ignora acentos e maiúsculas e exige todas as palavras digitadas."""
import unicodedata

# Palavras que não ajudam a achar o produto e atrapalham quando o nome não as traz
# ("óleo de soja" deve achar também "Óleo Soja Liza").
PALAVRAS_DE_LIGACAO = {"de", "da", "do", "das", "dos", "e", "com", "para", "em"}


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
    """Calcula uma vez o nome sem acento de cada produto: [(nome_sem_acento, produto), ...]."""
    return [(sem_acento(produto["nome"]), produto) for produto in produtos]


def filtrar(catalogo_indexado, item):
    """Produtos cujo nome contém todas as palavras de `item`, em qualquer ordem."""
    palavras = palavras_da_busca(item)
    if not palavras:
        return []
    return [produto for nome, produto in catalogo_indexado if all(p in nome for p in palavras)]
