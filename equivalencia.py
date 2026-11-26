"""Produto equivalente: o mesmo tipo de produto no mesmo tamanho, de qualquer marca.

Cada família abaixo diz o que DIFERENCIA um produto do outro (arroz parboilizado não é arroz branco; leite desnatado não é
leite integral; vinagre de maçã não é vinagre de álcool) e o que não importa (marca, embalagem, "pacote", "caixa com tampa").
O tamanho (g, kg, ml, L) sempre conta. O resultado é uma chave: produtos com a mesma chave são equivalentes.

Na dúvida, não junta: o produto que não cabe em nenhuma regra fica sem chave e só aparece no modo "exato". Errar por juntar
de menos é seguro; juntar o que não é equivalente engana a pessoa.

As 11 primeiras famílias (arroz a papel higiênico) são a tradução fiel das que viviam em site/index.html; o teste
tests/test_equivalencia.py as confere com os casos do teste em JavaScript da época (tests/casos_equivalencia_legado.json); o motor do site foi removido. As demais são declaradas pela função
`declarar`, com as dimensões que diferenciam o produto. Veja docs/equivalencia.md.
"""
import re
from dataclasses import dataclass
from typing import Callable, Optional

from busca import sem_acento


@dataclass(frozen=True)
class Equivalencia:
    chave: str
    rotulo: str


@dataclass
class _Analise:
    partes: list
    m: Optional[tuple]          # (massa?, valor em g ou ml) ou None
    rotulo: str


@dataclass(frozen=True)
class Familia:
    id: str
    titulo: str                 # como aparece na lista "vale para arroz, feijão, ..."
    casa: Callable[[str], bool]
    analisar: Callable[..., Optional[_Analise]]
    usa_unidade: bool = False   # True: `analisar(t, unidade)`; a unidade ("kg" = o preço é por quilo) vem do banco, não do nome


def normalizar(nome) -> str:
    """'Café 3 Corações Tradicional - Vácuo 500g' -> 'cafe 3 coracoes tradicional vacuo 500g' (só letras, números e + , .)."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+,. ]", " ", sem_acento(str(nome)))).strip()


def escolher(t, regras, padrao):
    """O valor da primeira regra (regex, valor) que casa com o texto; `padrao` se nenhuma casar."""
    for padrao_re, valor in regras:
        if re.search(padrao_re, t):
            return valor
    return padrao


def medida(t, tipo="qualquer", varrer=False):
    """Primeira medida do nome, em gramas ou mililitros: (massa?, valor). tipo: 'massa', 'volume' ou 'qualquer'.

    As 11 famílias originais olham só a primeira medida do nome (como no site). Com `varrer`, procura a primeira medida DO TIPO
    pedido, para "Leite Desnatado 10g de Proteína ... 1l" não ser lido como 10 g."""
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(kg|gramas?|gr|g|ml|lt|litros?|l)\b", t):
        unidade = m.group(2)
        massa = unidade in ("kg", "g", "gr") or unidade.startswith("grama")
        if (tipo == "massa" and not massa) or (tipo == "volume" and massa):
            if varrer:
                continue
            return None
        v = float(m.group(1).replace(",", "."))
        if unidade == "kg" or (not massa and unidade != "ml"):
            v *= 1000
        return (massa, int(v + 0.5))
    return None


def texto_medida(m):
    massa, valor = m
    if valor < 1000:
        return f"{valor} {'g' if massa else 'ml'}"
    return f"{f'{valor / 1000:.3f}'.rstrip('0').rstrip('.').replace('.', ',')} {'kg' if massa else 'L'}"


# ============================== as 11 famílias que já existiam no site ==============================

def _arroz(t):
    if re.search(r"carreteiro|galinhada|\bmix\b", t):
        return None
    m = medida(t, "massa")
    if not m:
        return None
    variedade = escolher(t, [(r"parboiliz", "parboilizado"), (r"integral", "integral"), (r"arbor", "arbório"), (r"japon", "japonês"),
                             (r"risot|carnaroli|italian", "para risoto"), (r"quebrado", "quebrado")], "branco")
    tipo = escolher(t, [(r"fora de tipo", "fora de tipo"), (r"tipo 2|\bt2\b", "tipo 2")], "tipo 1")
    return _Analise([variedade, tipo], m, f"Arroz {variedade} {tipo}")


def _feijao(t):
    if re.search(r"pronto|tempero|caldinho", t):
        return None
    m = medida(t, "massa")
    if not m:
        return None
    variedade = escolher(t, [(r"carioca", "carioca"), (r"\bpreto\b|\bpto\b", "preto"), (r"\bbranco\b|\bbco\b", "branco"), (r"fradinho", "fradinho"),
                             (r"jalo", "jalo"), (r"vermelho", "vermelho"), (r"roxo", "roxo"), (r"rajado", "rajado"), (r"de corda", "de corda")], None)
    if not variedade:
        return None
    tipo = escolher(t, [(r"tipo 2", "tipo 2")], "tipo 1")
    return _Analise([variedade, tipo], m, f"Feijão {variedade} {tipo}")


def _oleo(t):
    if re.search(r"capilar|cabelo|corporal|bebe|bronz|sunless|babosa|amendoa|\bcoco\b|\buva\b|ricino|mosqueta|peroba|moveis|lubrificante|serum|finalizador|argan|queratina|tratamento|gergelim|eucalipto|avante|farmax|almotolia|oregano|cebola|alho", t):
        return None
    m = medida(t, "qualquer")
    if not m:
        return None
    if re.search(r"bagaco", t):      # "composto de bagaço de oliva" é outro produto
        return None
    tipo = escolher(t, [(r"composto|misto|soja e oliva", "composto"), (r"soja", "soja"), (r"girassol", "girassol"), (r"milho", "milho"),
                        (r"canola", "canola"), (r"algodao", "algodão")], None)
    if not tipo:
        return None
    return _Analise([tipo], m, "Óleo composto de soja e oliva" if tipo == "composto" else f"Óleo de {tipo}")


def _cafe(t):
    if re.search(r"capsula|dolce gusto|nespresso", t):
        return None
    m = medida(t, "massa")
    if not m:
        return None
    forma = escolher(t, [(r"com leite", "com leite"), (r"soluvel|liofilizado|granulado|instantaneo", "solúvel"), (r"em graos", "em grãos")], "em pó")
    forca = escolher(t, [(r"descafeinado", "descafeinado"), (r"extra ?forte|\+ ?forte", "extraforte"), (r"liofilizado", "liofilizado"),
                         (r"gourmet|premium|especial|superior|organico|prima qualit|estrada real", "gourmet"), (r"tradicional|tradicao", "tradicional")], "")
    return _Analise([forma, forca], m, f"Café {forma}{' ' + forca if forca else ''}")


def _manteiga(t):
    if re.search(r"karite|castanha|margarina|amanteigado|pipoca|biscoito|papel|tempero|coloracao", t):
        return None
    m = medida(t, "massa")
    if not m:
        return None
    sal = escolher(t, [(r"sem sal", "sem sal"), (r"com sal|\bc sal\b|cristais de sal", "com sal")], None)
    if not sal:
        return None
    tipo = escolher(t, [(r"bufala", "de búfala"), (r"zero lactose|sem lactose", "sem lactose"), (r"\bextra\b|gastronomique", "extra")], "")
    return _Analise([tipo, sal], m, f"Manteiga {tipo + ' ' if tipo else ''}{sal}")


def _acucar(t):
    if re.search(r"sach|zero|sem acucar", t):
        return None
    m = medida(t, "massa")
    if not m:
        return None
    tipo = escolher(t, [(r"confeiteiro|glace|glacucar|\bconf\b", "de confeiteiro"), (r"demerad|demerar|dourado", "demerara"), (r"mascavo", "mascavo"),
                        (r"refinado", "refinado"), (r"cristal|cristaal", "cristal")], None)
    if not tipo:
        return None
    extra = escolher(t, [(r"organic", "orgânico"), (r"light|magro|\bfit\b|diet|lowcucar", "light")], "")
    return _Analise([tipo, extra], m, f"Açúcar {tipo}{' ' + extra if extra else ''}")


def _macarrao(t):
    if re.search(r"instant|miojo|lamen|noodles|yakisoba|yakissoba", t):
        return None
    m = medida(t, "massa")
    if not m:
        return None
    formato = escolher(t, [(r"espaguetinho|spaghettini", "espaguetinho"), (r"espaguete|spaghetti", "espaguete"), (r"parafuso|fusilli", "parafuso"),
                           (r"penne|\bpena\b", "penne"), (r"linguine", "linguine"), (r"fettuccine|fetuccine|fettucine", "fettuccine"),
                           (r"talharim|tagliarinni|tagliatelle|ninho", "talharim"), (r"caracol", "caracol"), (r"alfabeto", "alfabeto"), (r"fidelinho", "fidelinho")], None)
    if not formato:
        return None
    massa = escolher(t, [(r"ovos", "com ovos"), (r"semola|semolao|grano duro|durum", "de sêmola")], "")
    return _Analise([formato, massa], m, f"Macarrão {formato}{' ' + massa if massa else ''}")


def _detergente(t):
    if re.search(r"sanitario|multiuso|uso geral|desengordurante|pastilha|bloco|limpador|cremoso", t):
        return None
    m = medida(t, "qualquer")
    if not m:
        return None
    forma = escolher(t, [(r"\bgel\b", "gel"), (r"\bpo\b", "em pó para lava-louças" if re.search(r"louca|maquina", t) else "em pó")], "líquido")
    return _Analise([forma], m, f"Detergente {forma}")


def _sabao(t):
    if re.search(r"sabonete|shampoo|condicionador", t):
        return None
    if re.search(r"\d+ ?(barras?|unidades?|und)\b", t) and re.search(r"cada|barras? de", t):   # pacote de barras: o tamanho é ambíguo
        return None
    m = medida(t, "qualquer")
    if not m:
        return None
    forma = escolher(t, [(r"liquido", "líquido"), (r"em po|\bpo\b", "em pó"), (r"barra|pedaco", "em barra"), (r"pasta", "em pasta")], None)
    if not forma:
        return None
    roupa = escolher(t, [(r"finas|delicad", "para roupas delicadas")], "")
    return _Analise([forma, roupa], m, f"Sabão {forma}{' ' + roupa if roupa else ''}")


def _amaciante(t):
    if re.search(r"carne|tempero|maggi|qualimax", t):
        return None
    m = medida(t, "volume")
    if not m:
        return None
    tipo = escolher(t, [(r"concentrad", "concentrado")], "")
    return _Analise([tipo], m, f"Amaciante{' ' + tipo if tipo else ''}")


def _papel(t):
    metros = re.search(r"(\d+(?:[.,]\d+)?) ?(?:m|metros?)\b", t)
    rolos = None
    for padrao in (r"leve ?(\d+)", r"\bl(\d+)p\d+", r"(\d+) ?rolos?", r"\b(\d+) ?r\b", r"\bcom ?(\d+)\b", r"(\d+) ?(?:unidades?|und)\b"):
        rolos = re.search(padrao, t)
        if rolos:
            break
    if not metros or not rolos:
        return None
    folha = escolher(t, [(r"folha dupla|\bfd\b|\bf d\b", "folha dupla"), (r"folha tripla", "folha tripla"), (r"folha simples|\bfs\b|\bf s\b", "folha simples")], "")
    m, n = metros.group(1).replace(",", "."), rolos.group(1)
    return _Analise([folha, m, n], None,
                    f"Papel higiênico{' ' + folha if folha else ''}, {n} {'rolo' if int(n) == 1 else 'rolos'} de {m.replace('.', ',')} m")


def _comeca(padrao):
    return lambda t: re.search(padrao, t) is not None


FAMILIAS = [
    Familia("arroz", "arroz", _comeca(r"^arroz "), _arroz),
    Familia("feijao", "feijão", _comeca(r"^feijao "), _feijao),
    Familia("oleo", "óleo", _comeca(r"^oleo "), _oleo),
    Familia("cafe", "café", _comeca(r"^cafe "), _cafe),
    Familia("manteiga", "manteiga", _comeca(r"^manteiga "), _manteiga),
    Familia("acucar", "açúcar", _comeca(r"^acucar "), _acucar),
    Familia("macarrao", "macarrão", _comeca(r"^macarrao (?!inst)"), _macarrao),
    Familia("detergente", "detergente", _comeca(r"\bdetergente\b"), _detergente),
    Familia("sabao", "sabão", _comeca(r"\bsabao\b"), _sabao),
    Familia("amaciante", "amaciante", _comeca(r"\bamaciante\b"), _amaciante),
    Familia("papel", "papel higiênico", _comeca(r"^papel higienico "), _papel),
]


# ============================== famílias declaradas ==============================

# Embalagem com várias unidades ("pack", "kit", "2 unidades", "leve 3"): o tamanho do produto fica ambíguo, então não entra.
_MULTIPACOTE = r"\b(pack|kit|combo|fardo)\b|\b([2-9]|\d{2,}) ?(un|und|unid|unidades?|potes?|frascos?|latas?|garrafas?|sacos?|caixas?)\b|\bleve \d+ ?(un|und|unid|unidades?|pag)"


@dataclass(frozen=True)
class Dim:
    """Uma dimensão que diferencia o produto (tipo, sabor, com/sem sal...). A 1ª regra (regex, valor) que casa vale."""
    regras: tuple
    obrigatoria: bool = False      # sem nenhuma regra casando, o produto fica de fora (não dá para garantir a equivalência)
    padrao: str = ""               # valor quando nenhuma casa e a dimensão não é obrigatória
    varios: bool = False           # vale TODA regra que casa ("bacon e picanha"), em ordem alfabética, e não só a primeira


def dim(*regras, obrigatoria=False, padrao="", varios=False):
    return Dim(tuple(regras), obrigatoria, padrao, varios)


def _todos(t, regras):
    """Todos os valores cujas regras casam, sem repetir e em ordem alfabética ('camomila e hortelã'); vazio se nenhum casa."""
    return " e ".join(sorted({valor for padrao, valor in regras if re.search(padrao, t)}))


def declarar(id_, titulo, *, casa, exclui=None, medida_tipo="massa", dims=(), multipacote=True):
    """Cria uma família: o produto precisa casar com `casa`, não casar com `exclui` nem ser multipacote, ter medida do tipo pedido
    e cada dimensão resolvida. O rótulo é o título mais os valores das dimensões."""
    def analisar(t):
        if exclui and re.search(exclui, t):
            return None
        if multipacote and re.search(_MULTIPACOTE, t):
            return None
        m = None
        if medida_tipo:
            m = medida(t, medida_tipo, varrer=True)
            if m is None:
                return None
        valores = []
        for d in dims:
            if d.varios:
                valor = _todos(t, d.regras) or (None if d.obrigatoria else d.padrao)
            else:
                valor = escolher(t, d.regras, None if d.obrigatoria else d.padrao)
            if valor is None:
                return None
            valores.append(valor)
        return _Analise(valores, m, " ".join([titulo] + [v for v in valores if v]))
    return Familia(id_, titulo.lower(), casa, analisar)


def _tudo(*padroes):
    """Casa só se TODOS os padrões aparecem (o primeiro, no começo do nome)."""
    return lambda t: all(re.search(p, t) for p in padroes)


def _saco_de_lixo(t):
    """Saco de lixo: capacidade (litros) e quantidade de sacos no pacote. Reforçado, cor preta e embalagem não contam."""
    if re.search(r"\b(kit|combo)\b", t):
        return None
    litros = re.search(r"(\d+) ?(?:l|lt|litros?)\b", t)
    quantidade = None
    for padrao in (r"(\d+) ?(?:un|uni|und|unid|unidades?)\b", r"\bc (\d+)\b", r"\bcom (\d+)\b", r"\brolo (\d+)\b"):
        quantidade = re.search(padrao, t)
        if quantidade:
            break
    if not litros or not quantidade:
        return None
    cor = escolher(t, [(r"azul", "azul"), (r"verde", "verde"), (r"branco|transparente", "branco")], "")
    perfume = escolher(t, [(r"lavanda|perfumad|aroma|floral|citrus", "perfumado")], "")
    l, n = litros.group(1), quantidade.group(1)
    return _Analise([l, n, cor, perfume], None, f"Saco de lixo{' ' + cor if cor else ''}{' ' + perfume if perfume else ''}, {l} L, {n} sacos")


_SABORES_IOGURTE = [
    (r"morango", "morango"), (r"\bcoco\b", "coco"), (r"ameixa", "ameixa"), (r"pessego", "pêssego"), (r"maracuja", "maracujá"), (r"baunilha", "baunilha"),
    (r"mamao", "mamão"), (r"banana", "banana"), (r"frutas vermelhas|frutas silvestres|vermelhas", "frutas vermelhas"), (r"blueberry|mirtilo", "mirtilo"),
    (r"salada de frutas", "salada de frutas"), (r"abacaxi", "abacaxi"), (r"\buvas?\b", "uva"), (r"chocolate", "chocolate"), (r"framboesa", "framboesa"),
    (r"goiaba", "goiaba"), (r"\bmanga\b", "manga"), (r"laranja", "laranja"), (r"limao", "limão"), (r"cereais|granola", "cereais"), (r"\bmel\b", "mel"),
    (r"vitamina", "vitamina"), (r"frutas amarelas", "frutas amarelas"), (r"\bkiwi\b", "kiwi"), (r"caramelo", "caramelo"), (r"cupuacu", "cupuaçu"), (r"acai", "açaí"), (r"melancia", "melancia"),
]


def _iogurte(t):
    """Iogurte: forma (colher, grego, líquido), sabores (todos os que aparecem: 'morango e banana' não é 'morango'), gordura, açúcar e lactose."""
    if re.search(r"vegano|vegetal|\bsoja\b|aveia|amendoa|castanha|\bkit\b|pack|combo", t) or re.search(_MULTIPACOTE, t):
        return None
    m = medida(t, "qualquer", varrer=True)
    if not m:
        return None
    sabores = sorted({valor for padrao, valor in _SABORES_IOGURTE if re.search(padrao, t)})
    if not sabores:
        if not re.search(r"natural|tradicional|integral|desnatado|grego|\bzero\b|light|sem lactose", t):
            return None
        sabores = ["natural"]
    forma = escolher(t, [(r"liquido|bebida lactea|para beber|drink", "líquido"), (r"grego", "grego")], "")
    gordura = escolher(t, [(r"parcialmente desnatado", "parcialmente desnatado"), (r"desnatado|0 gordura|zero gordura", "desnatado"), (r"integral", "integral")], "")
    acucar = escolher(t, [(r"zero acucar|sem acucar|diet|sem adicao de acucar|\bzero\b(?! lact)|0 acucar", "zero açúcar")], "")
    lactose = escolher(t, [SEM_LACTOSE], "")
    valores = [forma, " e ".join(sabores), gordura, acucar, lactose]
    return _Analise(valores, m, "Iogurte" + "".join(" " + v for v in valores if v))


SEM_LACTOSE = (r"zero lactose|sem lactose|delact|lactofree|nolac|0 lactose|lacfree|\bzero lact", "sem lactose")

FAMILIAS += [
    # ---- laticínios
    declarar("leite_condensado", "Leite condensado", casa=_comeca(r"^leite condensado"),
             exclui=r"doce de leite|creme|chantilly|brigadeiro|sabor|\bcoco\b|chocolate|pudim|mousse",
             dims=[dim(SEM_LACTOSE, (r"semi ?desnat", "semidesnatado"), (r"desnat|light|0 de gordura|zero gordura|\b0 gordura", "desnatado"), padrao="tradicional")]),
    declarar("leite_em_po", "Leite em pó", casa=_tudo(r"^leite ", r"\bpo\b"),
             exclui=r"condensado|achocolatado|infantil|formula|aptamil|\bnan\b|nestogeno|ninho fases|comfor|nanlac|crescimento|adulto|fortifi|sabor|cappuccino|coco|soja|vegetal|batido|sorvete|misto|mistura|composto|bebida lactea|1\+|3\+|\d ?anos|proteina|whey",
             dims=[dim((r"semi ?desnat", "semidesnatado"), (r"desnat", "desnatado"), (r"integral", "integral"), obrigatoria=True), dim(SEM_LACTOSE)]),
    declarar("leite", "Leite", casa=_comeca(r"^leite "), medida_tipo="volume",
             exclui=r"\bpo\b|condensado|creme|\bcoco\b|fermentado|achocolatado|composto lacteo|formula|infantil|\bnan\b|aptamil|nestogeno|ninho fases|cappuccino|chocolate|morango|baunilha|sabor|batido|iogurte|bebida|\bsoja\b|aveia|amendoa|vegetal|castanha|\barroz\b|semente|proteina|whey|quefir|kefir|coalhada|requeijao|doce de leite|pudim|queijo|manteiga|sorvete",
             dims=[dim((r"semi ?desnat", "semidesnatado"), (r"desnat", "desnatado"), (r"integral", "integral"), obrigatoria=True),
                   dim(SEM_LACTOSE), dim((r"\ba2\b|a2a2", "A2")), dim((r"organic", "orgânico")), dim((r"^(?!.*\b(uht|longa vida)\b).*(pasteuriz|\btipo a\b|\btipo b\b|\bfresco\b)", "pasteurizado"))]),
    declarar("creme_de_leite", "Creme de leite", casa=_comeca(r"^creme de leite"),
             exclui=r"culinario|sabor|\bnata\b|\bcoco\b|vegetal|batata|vegano|castanha|aveia|amendoa|soja|requeijao",
             dims=[dim((r"bate|chantilly|chantili|batido", "para bater"), (r"fresco|pasteuriz", "fresco"), SEM_LACTOSE, (r"\bleve\b|levissimo|light|0 gordura", "leve"), padrao="tradicional")]),
    declarar("queijo_ralado", "Queijo ralado", casa=_tudo(r"^(queijo|parmesao)", r"\bralado\b"),
             exclui=r"vegano|castanha|caju|mussarela|mistura|tempero|pizza|snack",
             dims=[dim((r"parmesao", "parmesão"), (r"grana|reggiano|padano", "grana"), (r"mix|tres queijos|3 queijos", "mix"))]),
    declarar("margarina", "Margarina", casa=_comeca(r"^margarina"),
             exclui=r"culinaria|folhado|massa folhada|industrial|pastel|confeitaria|\bpao\b",
             dims=[dim((r"sem sal", "sem sal"), (r"com sal|\bc sal\b|salgad", "com sal"), obrigatoria=True),
                   dim((r"light|0 gordura|\bleve\b", "light"), (r"vegetal|vegana|plant", "vegetal")), dim(SEM_LACTOSE)]),

    declarar("requeijao", "Requeijão", casa=_comeca(r"^requeijao"), exclui=r"sabor (?!(queijo )?cheddar)|mistura|vegano|castanha|doce|pizza|torrada|biscoito|pate",
             dims=[dim((r"cheddar", "cheddar"), (r"quatro queijos|4 queijos", "4 queijos"), (r"culinario", "culinário"), (r"parmesao", "parmesão"), (r"brie|gorgonzola|provolone", "com queijo especial"), padrao="cremoso"),
                   dim(SEM_LACTOSE), dim((r"light|ligth|0 gordura|zero gordura|\bleve\b", "light"))]),
    declarar("pao_de_forma", "Pão de forma", casa=_comeca(r"^pao (de )?forma"), exclui=r"hamburguer|hot ?dog|recheado|\bmix\b|bolinha|sovado|massa|\bmini\b",
             dims=[dim((r"sem gluten|off gluten|gluten free|zero gluten", "sem glúten"), (r"castanha|\bnozes?\b|quinoa|linhaca|chia|semente", "com sementes e castanhas"), (r"integral", "integral"),
                       (r"fibras|cereais|graos|centeio", "grãos"), (r"sem casca", "sem casca"), (r"\bleite\b", "de leite"), (r"\bcoco\b|chocolate|brigadeiro|doce de|\bdoce\b", "doce"), padrao="tradicional"),
                   dim(SEM_LACTOSE), dim((r"zero acucar|sem acucar|diet|light", "zero açúcar"))]),
    Familia("iogurte", "iogurte", _comeca(r"^iogurte"), _iogurte),
    Familia("saco_de_lixo", "saco de lixo", _comeca(r"^saco (de |para )?lixo"), _saco_de_lixo),

    # ---- mercearia
    declarar("sal", "Sal", casa=_comeca(r"^sal "),
             exclui=r"sach|unidades de|moedor|parrilla|parrilha|chimichurri|aromatiz|alho|cebola|pimenta|ervas|herbs|trufa|defumad|temperad|tempero|de frutas|\beno\b|substituto|ciliar",
             dims=[dim((r"rosa|himalai", "rosa do Himalaia"), (r"grosso|churrasco", "grosso"), (r"marinho", "marinho"), (r"light|baixo teor|reduzido|diet|hipo", "light"),
                       (r"refinado|iodado|fino|moido|tradicional|extra fino", "refinado"), obrigatoria=True)]),
    declarar("vinagre", "Vinagre", casa=_comeca(r"^vinagre "), medida_tipo="volume",
             exclui=r"aromatiz|limao|alho|ervas|pimenta|ameixa|framboesa|cebola|especiarias|creme|\bgel\b|molho|glaze|reducao|sache|spray|limpeza",
             dims=[dim((r"balsam", "balsâmico"), (r"maca", "de maçã"), (r"vinho tinto|\btinto\b", "de vinho tinto"), (r"vinho branco|\bbranco\b", "de vinho branco"),
                       (r"vinho", "de vinho"), (r"arroz", "de arroz"), (r"cereal", "de cereais"), (r"alcool", "de álcool"), (r"fruta", "de fruta"), obrigatoria=True),
                   dim((r"colorido", "colorido")), dim((r"organic", "orgânico")), dim((r"duplo|concentrad", "concentrado"))]),
    declarar("farinha_de_trigo", "Farinha de trigo", casa=_comeca(r"^farinha (de )?trigo"),
             exclui=r"mistura|bolo|pao de queijo|biscoito|rosca|semola|sabor",
             dims=[dim((r"tipo 00|\b00\b", "tipo 00"), (r"integral", "integral"), (r"tipo 2", "tipo 2"), padrao="tipo 1"),
                   dim((r"com fermento|\bc fermento|\bc fermen", "com fermento")),
                   dim((r"pastel", "para pastel"), (r"pizza", "para pizza"), (r"salgad", "para salgados"), (r"\bpaes?\b|panifica", "para pães"), (r"bolo", "para bolos"))]),
    declarar("farinha_de_mandioca", "Farinha de mandioca", casa=_comeca(r"^farinha (de )?mandioca"),
             exclui=r"polvilho|tapioca|farofa|bolo|\bpao\b|biscoito|mistura",
             dims=[dim((r"temperada", "temperada"), (r"biju|beiju", "biju"), (r"crua|puba", "crua"), padrao="torrada"),
                   dim((r"amarela", "amarela"), (r"branca|\bbca\b", "branca")), dim((r"\bfina\b", "fina"), (r"grossa", "grossa"))]),
    declarar("fuba", "Fubá", casa=_comeca(r"^fuba "), exclui=r"bolo|mistura|broa|broinha|canjica|biscoito|polenta|queijo|coco",
             dims=[dim((r"mimoso|\bfino\b", "mimoso"))]),
    declarar("molho_de_tomate", "Molho de tomate", casa=_comeca(r"^molho (de )?tomate"), exclui=r"\bpasta\b|extrato|ketchup|catchup",
             dims=[dim((r"bolonhesa", "bolonhesa"), (r"manjericao", "manjericão"), (r"\bpizza\b", "para pizza"), (r"passata|passatta|rustic", "passata"), (r"refogado", "refogado"),
                       (r"napolitana", "napolitana"), (r"alho|cebola", "com alho e cebola"), (r"azeitona", "com azeitona"), (r"picante|pimenta", "picante"),
                       (r"ervas|italiano|basilico", "com ervas"), (r"queijo", "com queijos"), (r"funghi|cogumelo", "com cogumelos"), (r"carne", "com carne"), (r"cebolinha", "com cebolinha"), (r"hot ?dog", "para hot dog"), (r"caseiro", "caseiro"), (r"sugo", "sugo"),
                       (r"pimentao", "com pimentão"), (r"quatro queijos|4 queijos", "com queijos"), padrao="tradicional"),
                   dim((r"sem adicao de acucar|sem acucar|zero acucar", "sem açúcar"))]),
    declarar("extrato_de_tomate", "Extrato de tomate", casa=_comeca(r"^extrato (de )?tomate"), exclui=r"suco|molho",
             dims=[dim((r"alho|cebola", "com alho e cebola"), (r"strogon", "para strogonoff"), (r"picante|pimenta", "picante"), (r"ervas|manjericao|basilico", "com ervas"), padrao="tradicional")]),
    declarar("milho_verde", "Milho verde", casa=_comeca(r"^milho verde"),
             exclui=r"ervilha|pipoca|amido|farinha|cremoso|creme|bolo|biscoito|palha|canjica|doce|salada|cozido no vapor",
             dims=[dim((r"congelad", "congelado"), padrao="em conserva")]),
    declarar("ervilha", "Ervilha", casa=_comeca(r"^ervilha"), exclui=r"\bmilho\b|\bseca\b|partida|pipoca|snack|pasta|crocante|torrada|wasabi|grao de bico",
             dims=[dim((r"congelad", "congelada"), padrao="em conserva")]),
    declarar("atum", "Atum", casa=_comeca(r"^atum "), exclui=r"racao|gato|pate|salada|hamburguer|sanduiche|tempero|maionese|empanado|snack|pasta",
             dims=[dim((r"ralado", "ralado"), (r"solido|posta|\bfile\b|lombo", "sólido"), (r"pedaco", "em pedaços"), (r"desfiado", "desfiado"), obrigatoria=True),
                   dim((r"oleo", "em óleo"), (r"natural|agua|proprio suco|caldo", "ao natural"), (r"tomate|molho", "ao molho"), (r"azeite", "no azeite"), obrigatoria=True),
                   dim((r"light|baixo sodio", "light"))]),
    declarar("sardinha", "Sardinha", casa=_comeca(r"^(file de )?sardinha"), exclui=r"eviscerada|congelad|espalmada|fresca|fish|racao|pate|salgad|\bseca\b|salmoura",
             dims=[dim((r"tomate|molho", "ao molho de tomate"), (r"oleo", "em óleo"), (r"natural|proprio suco|\bsuco\b", "ao natural"), obrigatoria=True),
                   dim((r"\bfile\b", "filé"), padrao=""), dim((r"pimenta|picante", "picante"))]),
    declarar("maionese", "Maionese", casa=_comeca(r"^maionese"), exclui=r"salada|molho|\bkit\b",
             dims=[dim((r"light|zero|\bfit\b|0 gordura|\bleve\b", "light"), (r"vegan|vegetal", "vegana"), (r"sem gluten", "sem glúten"), (r"alho", "com alho"), (r"verde|ervas", "com ervas"),
                       (r"churrasco", "de churrasco"), (r"picante|pimenta", "picante"), (r"bacon", "com bacon"), (r"cheddar|queijo", "com queijo"),
                       (r"mostarda", "com mostarda"), (r"limao", "com limão"), (r"temperada", "temperada"), (r"caseira", "caseira"),
                       (r"supreme|premium|gourmet", "premium"), padrao="tradicional")]),
    declarar("ketchup", "Ketchup", casa=_comeca(r"^(ketchup|catchup)"), exclui=r"\bkit\b",
             dims=[dim((r"picante", "picante"), (r"zero|light|diet|sem acucar", "light"), (r"bacon", "com bacon"), (r"cebola", "com cebola caramelizada"), (r"picles|pickles", "com picles"), (r"barbecue|bbq", "barbecue"),
                       (r"mostarda", "com mostarda"), (r"supreme|premium|gourmet", "premium"), padrao="tradicional")]),
    declarar("azeite", "Azeite de oliva", casa=_comeca(r"^azeite"), medida_tipo="volume",
             exclui=r"dende|aromatiz|trufa|limao|alho|pimenta|spray|composto|oleo composto|capsula|temperad|ervas|tapenade|oliva e (soja|girassol|canola|milho)|\bmix\b|misto",
             dims=[dim((r"extra ?virgem|extravirgem|\bevoo\b", "extra virgem"), (r"virgem", "virgem"), (r"oliva|unico|classico|suave|puro", "tipo único"), obrigatoria=True),
                   dim((r"intenso|robusto|picante", "intenso"), (r"suave|doce|maduro|delicado", "suave")),
                   dim((r"portugu", "português"), (r"italian", "italiano"), (r"espanh", "espanhol"), (r"greg", "grego"), (r"chilen", "chileno"),
                       (r"argentin", "argentino"), (r"brasileir", "brasileiro"))]),
    declarar("aveia", "Aveia", casa=_comeca(r"^aveia"), exclui=r"barra|biscoito|cookie|granola|mingau|bebida|leite|sabor|cereal|cobertura|proteinad|pasta",
             dims=[dim((r"farelo", "farelo"), (r"farinha", "farinha"), (r"finos?\b", "em flocos finos"), (r"floco|flc|regular|grosso|integral|tradicional", "em flocos"), obrigatoria=True),
                   dim((r"sem gluten", "sem glúten"))]),
    declarar("fermento", "Fermento em pó", casa=_tudo(r"^fermento ", r"\bpo\b|quimico"), exclui=r"biologico|fresco|seco|instantaneo|fermipan|levedura|bicarbonato de sodio$"),

    # ---- água
    declarar("agua_sanitaria", "Água sanitária", casa=_comeca(r"^agua sanitaria"), medida_tipo="volume", exclui=r"multiuso|perfumada"),
    declarar("agua_mineral", "Água mineral", casa=_comeca(r"^agua mineral"), medida_tipo="volume",
             exclui=r"tonica|saborizada|sabor|limao|laranja|\bcoco\b|aromatizada|retorn",
             dims=[dim((r"sem gas|nao gaseificada", "sem gás"), (r"com gas|gaseificada", "com gás"), obrigatoria=True), dim((r"alcalina|ph ?\d", "alcalina"))]),
]


# ============================== terceira leva: contagem de unidades, carnes processadas e chá ==============================

_UNIDADES = r"(\d+) ?(?:un|und|unid|unidades?)\b"
_NAO_E_PRODUTO_UNICO = r"\b(kit|combo|fardo)\b|\bgratis\b|brinde"


def _quantidade_do_pacote(t, minimo=6):
    """Quantas unidades vêm no pacote: 'Leve 28 Pague 26' vale 28; '66 un' vale 66. None se não diz, ou se 'Leve 3 Pague 2' (são vários pacotes)."""
    promocao = re.search(r"\bleve (\d+)\b", t)
    if promocao:
        n = int(promocao.group(1))
        return str(n) if n >= minimo else None
    achado = re.search(_UNIDADES, t) or re.search(r"\bcom (\d+)\b", t)
    return achado.group(1) if achado else None


def _fralda(t):
    """Fralda descartável: tamanho (P, M, G, XG...), formato (calça ou comum) e fraldas no pacote. Marca e linha não contam."""
    if re.search(_NAO_E_PRODUTO_UNICO + r"|geriatric|adult|incontinen|\bpano\b|\bpet\b|cachorro|treinamento", t):
        return None
    n = _quantidade_do_pacote(t)
    sem_nascido = re.sub(r"recem[ -]?nascido", "rn", t)
    tamanhos = set(re.findall(r"\b(rn|pp|p|m|g|gg|xg|xxg|xxxg)\b", sem_nascido))
    if not tamanhos:                    # alguns nomes escrevem o tamanho por extenso
        tamanhos = {sigla for palavra, sigla in (("extra grande", "xg"), ("grande", "g"), ("medio", "m"), ("pequeno", "p")) if re.search(r"\b" + palavra + r"\b", t)}
        if "xg" in tamanhos:
            tamanhos.discard("g")
    if not n or len(tamanhos) != 1:
        return None
    tamanho = tamanhos.pop().upper()
    formato = escolher(t, [(r"pants|calca", "calça")], "")
    linha = escolher(t, [(r"premium|supreme", "premium")], "")
    valores = [tamanho, formato, linha]
    return _Analise(valores + [n], None, "Fralda" + "".join(" " + v for v in valores if v) + f", {n} unidades")


def _absorvente(t):
    """Absorvente: tipo (externo, interno, protetor diário), abas, cobertura (suave, seca, gel), uso (noturno), tamanho e quantidade."""
    if re.search(_NAO_E_PRODUTO_UNICO + r"|geriatric|adult|incontinen|ducha|coletor|menstrual|calcinha|sabonete|cuidado intimo", t):
        return None
    n = _quantidade_do_pacote(t)
    if not n:
        return None
    tipo = escolher(t, [(r"interno|tampao|\bo\.?b\.?\b", "interno"), (r"protetor", "protetor diário")], "externo")
    abas = escolher(t, [(r"sem abas", "sem abas"), (r"abas", "com abas")], "")
    pele = _todos(t, [(r"suave", "suave"), (r"\bseca\b|\bdry\b", "seca"), (r"\bgel\b", "em gel")])
    uso = escolher(t, [(r"dia (e )?noite|noite (e )?dia", "dia e noite"), (r"noturn|noite|night", "noturno")], "")
    linha = _todos(t, [(r"\bplus\b", "plus"), (r"ultra ?fin", "ultrafino"), (r"longo", "longo"), (r"premium", "premium")])
    tamanho = escolher(t, [(r"\bmini\b", "mini"), (r"extra grande|\bxg\b|\bxxg\b", "extra grande"), (r"grande|\bg\b", "grande"), (r"medio|\bm\b|normal", "médio"),
                           (r"pequeno|\bp\b", "pequeno"), (r"\bsuper\b", "super")], "")
    valores = [tipo, abas, pele, uso, tamanho, linha]
    return _Analise(valores + [n], None, "Absorvente" + "".join(" " + v for v in valores if v) + f", {n} unidades")


def _papel_toalha(t):
    """Papel toalha: rolo ou interfolhas, folha simples ou dupla, rolos e folhas. Quando o nome diz 'cada' ou 'de N folhas', as folhas
    são por rolo e a conta é feita; quando diz só 'N folhas', a conta fica como está escrita (pode ser o total), então só junta com a mesma escrita."""
    if re.search(_NAO_E_PRODUTO_UNICO + r"|\bpano\b|umedecid|\blimpeza\b", t):
        return None
    numero = r"(\d{1,3}(?:\.\d{3})+|\d+)"
    folhas = re.search(numero + r" ?(?:folhas?|fls?|flhas?|toalhas?)\b", t)
    interfolhas = re.search(r"interfolha", t)
    if not folhas and interfolhas:
        folhas = re.search(numero + r" ?(?:un|und|unidades?)\b", t)
    if not folhas:
        return None
    promocao = re.search(r"\bleve (\d+)\b", t)       # "Leve 200 Pague 180 Folhas": o pacote traz 200
    f = int(promocao.group(1)) if promocao else int(folhas.group(1).replace(".", ""))
    rolos = re.search(r"(\d+) ?(?:rolos?|unidades?|und|un)\b", t) or re.search(r"\bc (\d+)\b", t)       # "120fls C/2" são 2 rolos
    r = int(rolos.group(1)) if rolos and not interfolhas else 1
    por_rolo = bool(re.search(numero + r" ?(?:folhas?|fls?|flhas?|toalhas?) cada\b", t) or re.search(r"rolos? de " + numero, t))
    folha = escolher(t, [(r"folha dupla|\bf ?d\b", "folha dupla"), (r"folha simples|\bf ?s\b", "folha simples")], "")
    if interfolhas:
        return _Analise(["interfolhas", folha, str(f)], None, f"Papel toalha interfolhas{' ' + folha if folha else ''}, {f} folhas")
    if por_rolo:
        return _Analise(["rolo", folha, f"{r}x{f}"], None, f"Papel toalha{' ' + folha if folha else ''}, {r} {'rolo' if r == 1 else 'rolos'} de {f} folhas")
    return _Analise(["rolo", folha, f"{r}:{f}"], None, f"Papel toalha{' ' + folha if folha else ''}, {r} {'rolo' if r == 1 else 'rolos'} com {f} folhas")


_ERVAS_DO_CHA = [
    (r"camomila", "camomila"), (r"erva[ -]?doce|funcho", "erva-doce"), (r"hortela", "hortelã"), (r"capim[ -]?cidreira", "capim-cidreira"),
    (r"erva[ -]?cidreira|(?<!capim )\bcidreira\b", "erva-cidreira"), (r"maracuja", "maracujá"), (r"\bboldo\b", "boldo"), (r"hibisco", "hibisco"), (r"gengibre", "gengibre"),
    (r"canela", "canela"), (r"\bmaca\b", "maçã"), (r"laranja", "laranja"), (r"limao", "limão"), (r"morango", "morango"), (r"frutas vermelhas", "frutas vermelhas"),
    (r"pessego", "pêssego"), (r"lichia", "lichia"), (r"cavalinha", "cavalinha"), (r"dente de leao", "dente-de-leão"), (r"melissa", "melissa"), (r"carqueja", "carqueja"),
    (r"espinheira", "espinheira-santa"), (r"\bmatte?\b", "mate"), (r"preto", "preto"), (r"verde", "verde"), (r"branco", "branco"), (r"jasmim", "jasmim"),
    (r"cranberry", "cranberry"), (r"mirtilo|blueberry", "mirtilo"), (r"baunilha", "baunilha"), (r"\bmel\b", "mel"), (r"tostado", "tostado"),
]


def _cha(t):
    """Chá: de sachê/folhas (ervas e tamanho em gramas) ou bebida pronta (sabor e volume). Misturas ('misto') ficam de fora: o nome corta os ingredientes."""
    if re.search(_NAO_E_PRODUTO_UNICO + r"|\bmisto\b|capsula|instantaneo|soluvel|\bpo\b|granulado|latte|\bkit\b|\b[2-9] ?(caixas?|pacotes?|garrafas?|latas?)\b", t):
        return None
    ervas = _todos(t, _ERVAS_DO_CHA)
    if not ervas:
        return None
    pronto = re.search(r"\bice\b|iced|pronto|garrafa|\bpet\b|\blata\b", t) is not None
    if not pronto and re.search(r"\bmatte?\b", t) and medida(t, "volume", varrer=True) and not medida(t, "massa", varrer=True):
        pronto = True                   # "Chá Matte Leão Limão 1,5L"
    if pronto:
        m = medida(t, "volume", varrer=True)
        if not m:
            return None
        zero = escolher(t, [(r"\bzero\b|sem (adicao de )?acucar|light|diet", "zero açúcar")], "")
        versao = _todos(t, [(r"\bnatural\b", "natural"), (r"\boriginal\b", "original")])     # "Matte Leão Natural" e "Original" são versões diferentes
        valores = [ervas, versao, zero]
        return _Analise(["pronto"] + valores, m, "Chá pronto" + "".join(" " + v for v in valores if v))
    m = medida(t, "massa", varrer=True)
    if not m:
        return None
    return _Analise(["sache", ervas], m, f"Chá {ervas}")


_CARNES_A_EXCLUIR = _NAO_E_PRODUTO_UNICO + r"|vegetal|vegano|vegana|plant|molho|tempero|\bpao\b|sanduiche|pizza|recheio|empanado"

FAMILIAS += [
    declarar("gelatina", "Gelatina", casa=_comeca(r"^gelatina"), exclui=r"dentadura|beijos|\bfini\b|pronta|\bpote\b|\bcopo\b|colageno|bovina|capsula",
             dims=[dim((r"sem sabor|incolor|neutra|\bnatural\b", "sem sabor"), (r"morango", "morango"), (r"\buva\b", "uva"), (r"abacaxi", "abacaxi"), (r"cereja", "cereja"),
                       (r"limao", "limão"), (r"framboesa", "framboesa"), (r"maracuja", "maracujá"), (r"laranja", "laranja"), (r"pessego", "pêssego"),
                       (r"tutti ?frutti", "tutti-frutti"), (r"melancia", "melancia"), (r"\bcoco\b", "coco"), (r"menta", "menta"), obrigatoria=True),
                   dim((r"zero|diet|sem acucar|light", "zero açúcar"))]),
    declarar("salsicha", "Salsicha", casa=_comeca(r"^salsicha"), exclui=_CARNES_A_EXCLUIR + r"|conserva|\blata\b|\bviena\b.*\bsache\b", multipacote=False,
             dims=[dim((r"hot[ -]?dog", "hot dog"), (r"viena", "viena"), (r"frango", "de frango"), (r"\bperu\b", "de peru"), (r"defumad", "defumada"), (r"\blight\b", "light"), varios=True)]),
    declarar("linguica", "Linguiça", casa=_comeca(r"^linguica"), exclui=_CARNES_A_EXCLUIR + r"|salsicha|churrasqueira|espeto", multipacote=False,
             dims=[dim((r"toscana", "toscana"), (r"calabresa", "calabresa"), (r"mista", "mista"), (r"frango", "de frango"), (r"pernil", "de pernil"), (r"lombo", "de lombo"),
                       (r"costela", "de costela"), (r"churrasco", "de churrasco"), (r"cuiabana", "cuiabana"), (r"blumenau", "blumenau"), (r"\bpato\b", "de pato"),
                       (r"mignon", "de filé mignon"), (r"coalho", "de queijo coalho"), (r"\bpaio\b", "paio"), (r"portuguesa", "portuguesa"), (r"mineira", "mineira"),
                       (r"suina|carne suina|\bporco\b", "suína"), obrigatoria=True),
                   dim((r"^(?!.*calabresa).*defumad", "defumada"), (r"cozida", "cozida")),
                   dim((r"\bfina\b|fininha", "fina")),
                   dim((r"bacon", "bacon"), (r"pimenta|apimentad|picante", "apimentada"), (r"\balho\b|alho poro", "alho"), (r"queijo", "queijo"), (r"ervas", "ervas"), (r"fatiada", "fatiada"), (r"angus", "angus"), varios=True)]),
    declarar("hamburguer", "Hambúrguer", casa=_comeca(r"^hamburguer"), exclui=_CARNES_A_EXCLUIR, multipacote=False,
             dims=[dim((r"misto|mista|aves? e bovin|frango e bovin|bovin\w* e (frango|aves?)", "misto"), (r"frango|aves", "de frango"), (r"suin", "suíno"),
                       (r"bovin|angus|picanha|maminha|fraldinha|costela|brisket|churrasco|carne", "bovino"), obrigatoria=True),
                   dim((r"angus", "angus"), (r"picanha", "picanha"), (r"costela", "costela"), (r"fraldinha", "fraldinha"), (r"brisket", "brisket"), (r"maminha", "maminha"),
                       (r"bacon", "bacon"), (r"queijo|cheddar", "queijo"), (r"\bfit\b", "fit"), (r"churrasco", "de churrasco"), (r"defumad", "defumado"), varios=True)]),
    Familia("cha", "chá", _comeca(r"^cha "), _cha),
    Familia("papel_toalha", "papel toalha", _comeca(r"^(papel toalha|toalha de papel)"), _papel_toalha),
    Familia("fralda", "fralda", _comeca(r"^fralda"), _fralda),
    Familia("absorvente", "absorvente", _comeca(r"^absorvente"), _absorvente),
]


# ============================== quarta leva: macarrão instantâneo, achocolatado, geleia, pipoca e caldo ==============================

def _pipoca(t):
    """Pipoca: de micro-ondas, pronta ou milho para pipoca (o grão), com o sabor (manteiga de cinema, natural...) e o peso."""
    if re.search(_NAO_E_PRODUTO_UNICO + r"|\bsaco\b|festas|romana|decor|pipoqueira|maquina|panela|tempero|chocolate|bombom|\boleo\b", t):
        return None
    m = medida(t, "massa", varrer=True)
    if not m:
        return None
    micro = re.search(r"micro ?ondas|microondas", t) is not None
    grao = not micro and re.search(r"^milho (de |para )?pipoca|^milho pipoca", t) is not None
    tipo = "para micro-ondas" if micro else "milho para pipoca" if grao else "pronta"
    if grao:
        qualidade = escolher(t, [(r"premium|gourmet", "premium")], "")
        return _Analise([tipo, qualidade], m, f"Milho para pipoca{' ' + qualidade if qualidade else ''}")
    sabor = escolher(t, [(r"manteiga light", "manteiga light"), (r"cinema", "manteiga de cinema"), (r"manteiga", "manteiga"), (r"bacon", "bacon"),
                         (r"cheddar", "cheddar"), (r"queijo", "queijo"), (r"doce|caramelo", "doce"), (r"natural", "natural"), (r"temperada", "temperada")], None)
    if not sabor:      # sem o sabor no nome não dá para saber se é a mesma pipoca
        return None
    return _Analise([tipo, sabor], m, f"Pipoca {tipo} {sabor}")


FAMILIAS += [
    declarar("macarrao_instantaneo", "Macarrão instantâneo", casa=_comeca(r"^(macarrao|mac) inst"), exclui=r"panela|caseiro",
             dims=[dim((r"cup noodles|\bcopo\b|\bcup\b", "em copo"), (r"yakissoba|\bu\.?f\.?o\b", "yakissoba"), (r"talharim", "talharim"), (r"espaguete", "espaguete"), padrao="lámen"),
                   dim((r"frango assado", "frango assado"), (r"galinha caipira", "galinha caipira"), (r"galinha|frango", "galinha"), (r"carne defumada", "carne defumada"), (r"carne", "carne"), (r"bacon", "bacon"),
                       (r"calabresa", "calabresa"), (r"picanha", "picanha"), (r"costela", "costela"), (r"legumes", "legumes"), (r"queijo", "queijo"),
                       (r"camarao", "camarão"), (r"parmegiana", "parmegiana"), (r"bolonhesa", "bolonhesa"), (r"caldinho de feijao", "caldinho de feijão"),
                       (r"tomate", "tomate"), (r"cheddar", "cheddar"), (r"nacho", "nacho"),
                       (r"\btradicional\b|yakissoba", "tradicional"), obrigatoria=True),
                   dim((r"picante", "picante"), (r"suave|turma da monica", "suave"), varios=True)]),
    declarar("achocolatado", "Achocolatado", casa=_comeca(r"^achocolatado"), exclui=r"capsula|dolce gusto|nescafe|kopenhagen|cobertura|barra|sorvete",
             dims=[dim((r"flocos|crocante", "flocos crocantes"), (r"granulado", "granulado"), padrao="em pó"),
                   dim((r"light|diet|zero|sem acucar", "light"), (r"menos acucar", "menos açúcar"), (r"\b60\b", "60% cacau"), (r"protein|proteina", "proteína"), (r"ovomaltine|malte", "com malte"),
                       (r"alpino", "alpino"), (r"sem lactose|zero lactose", "sem lactose"), (r"vegan|vegetal", "vegano"), varios=True)]),
    declarar("geleia", "Geleia", casa=_comeca(r"^geleia"), exclui=r"mocoto|\bmel\b|\breal\b",
             dims=[dim((r"frutas vermelhas|frutas silvestres", "frutas vermelhas"), (r"morango", "morango"), (r"amora", "amora"), (r"damasco", "damasco"), (r"goiaba", "goiaba"),
                       (r"\buva\b", "uva"), (r"mirtilo", "mirtilo"), (r"framboesa", "framboesa"), (r"figo", "figo"), (r"jabuticaba", "jabuticaba"), (r"laranja", "laranja"),
                       (r"abacaxi", "abacaxi"), (r"\bmaca\b", "maçã"), (r"maracuja", "maracujá"), (r"pessego", "pêssego"), (r"cereja", "cereja"), (r"pimenta", "pimenta"),
                       (r"cranberry", "cranberry"), (r"limao", "limão"), (r"\bmanga\b", "manga"), (r"banana", "banana"), (r"cupuacu", "cupuaçu"), obrigatoria=True),
                   dim((r"diet|zero|sem (adicao de )?acucar|light", "zero açúcar")),
                   dim((r"gourmet", "gourmet"), (r"polonesa", "polonesa"), (r"agridoce", "agridoce"), (r"jalapeno", "jalapeño"), varios=True)]),
    Familia("pipoca", "pipoca", _comeca(r"^(pipoca|milho (de |para )?pipoca)"), _pipoca),
    declarar("caldo", "Caldo", casa=_comeca(r"^caldo "), exclui=r"sazon|liquido|pronto|osso|receita|molho|" + _NAO_E_PRODUTO_UNICO, multipacote=False,
             dims=[dim((r"galinha caipira", "de galinha caipira"), (r"galinha|frango", "de galinha"), (r"carne", "de carne"), (r"legumes?", "de legumes"), (r"costela", "de costela"),
                       (r"camarao", "de camarão"), (r"peixe", "de peixe"), (r"bacon", "de bacon"), obrigatoria=True),
                   dim((r"menos sodio|reduzido|light|sem sal|menos sal", "menos sal"))]),
]


# ============================== quinta leva: cereal matinal (flocos de milho), farofa, cream cracker, maisena e ovos ==============================

def _quantidade_de_ovos(t):
    """Ovos na embalagem: '20 unidades', '20un', '12 Und', '2.5 Dúzias' (= 30), 'meia dúzia' (= 6). None se o nome não diz ou se não faz sentido."""
    if re.search(r"meia duzia", t):
        n = 6
    elif re.search(r"\b(uma|1) duzia\b", t):
        n = 12
    else:
        duzias = re.search(r"(\d+(?:[.,]\d+)?) ?duzias?\b", t)
        if duzias:
            n = round(float(duzias.group(1).replace(",", ".")) * 12)
        else:
            un = re.search(r"\b(\d+) ?(?:un|und|unid|unidades?|ovos)\b", t) or re.search(r"\bcom (\d+)\b", t)
            n = int(un.group(1)) if un else None
    return n if n and 4 <= n <= 60 else None


def _ovos(t):
    """Ovos: de galinha ou de codorna, cor, tipo (caipira, orgânico, cage free), tamanho e quantos vêm na embalagem."""
    if re.search(_NAO_E_PRODUTO_UNICO + r"|pascoa|chocolate|kinder|surpresa|congelad|cozid|mexid|fatiad|liquid|pasteuriz|\bclara|\bgema|em po\b|tinta|corante|colorid|decorad|bombom|conserva|salmoura|\bleve \d|\bpack\b|\b[2-9] ?bandejas?", t):
        return None
    n = _quantidade_de_ovos(t)
    if not n:                           # sem a quantidade no nome (ou em gramas) não dá para comparar
        return None
    especie = "de codorna" if re.search(r"codorna", t) else ""
    cor = escolher(t, [(r"\bvermelh", "vermelhos"), (r"\bbranc", "brancos")], "")
    tipo = _todos(t, [(r"cage free", "cage free"), (r"caipira", "caipira"), (r"label rouge", "label rouge"), (r"organic", "orgânicos")])
    tamanho = escolher(t, [(r"jumbo", "jumbo"), (r"\bextra\b", "extra"), (r"grande", "grandes"), (r"medio", "médios"), (r"pequeno", "pequenos")], "")
    partes = [especie, cor, tipo, tamanho]
    rotulo = "Ovos" + "".join(" " + p for p in (especie, cor, tipo) if p) + (f" {tamanho}" if tamanho else "") + f", {n} unidades"
    return _Analise(partes + [str(n)], None, rotulo)


# Sabores de farofa que a regra conhece. Os que ela não quer misturar com a farofa simples (ovos, linguiça, carne seca...) mandam o produto para fora.
_OUTROS_SABORES_DE_FAROFA = r"\bovos?\b|linguica|carne seca|carne de sol|charque|camarao|legumes|vegetais|abacaxi|castanha|passas|\buva\b|cenoura|couve|torresmo|churrasco|feijao"


def _farofa(t):
    """Farofa pronta: de mandioca ou de milho, temperada, crocante, com pedaços, o sabor (bacon, costela, picanha...) e o peso."""
    if re.search(_NAO_E_PRODUTO_UNICO + r"|congelad|" + _OUTROS_SABORES_DE_FAROFA, t) or re.search(_MULTIPACOTE, t):
        return None
    m = medida(t, "massa", varrer=True)
    if not m:
        return None
    base = "de milho" if re.search(r"milho", t) else "de mandioca"
    # "tradicional" e a farofa sem nada no nome são a mesma; "temperada", "crocante" e "com pedaços" são produtos diferentes
    tracos = [nome for padrao, nome in ((r"temperada|tempd", "temperada"), (r"crocante|caseirissima", "crocante"), (r"com pedacos|pedacos de", "com pedaços")) if re.search(padrao, t)]
    sabor = _todos(t, [(r"costelinha|costela", "costela"), (r"picanha", "picanha"), (r"bacon", "bacon"), (r"cebola", "cebola"), (r"banana", "banana"), (r"frango", "frango"),
                       (r"calabresa", "calabresa"), (r"picante|pimenta", "picante"), (r"alho", "alho"), (r"limao", "limão")])
    rotulo = f"Farofa {base}" + "".join(" " + x for x in tracos) + (f" sabor {sabor}" if sabor else "")
    return _Analise([base, *tracos, sabor], m, rotulo)


FAMILIAS += [
    # Só os flocos de milho: Nescau, Kit Kat, Snow Flakes, Crunch, Negresco etc. são produtos únicos de marca (não há "qualquer marca"): ficam no modo exato.
    declarar("cereal_matinal", "Cereal matinal de flocos de milho", casa=_tudo(r"^(cereal|sucrilhos|corn flakes)", r"sucrilhos|flocos de milho|corn flakes|corn sugar|milho com acucar"),
             exclui=r"\+|\bleve\b|\blv\b|\bpague\b|\bpg\b|zero|light|diet|sem acucar|integral|proteina|fibra|granola|aveia|barra|mix",
             dims=[dim((r"ovomaltine", "com ovomaltine"), (r"chocolate", "com chocolate"))]),
    Familia("farofa", "farofa", _comeca(r"^farofa"), _farofa),
    declarar("cream_cracker", "Biscoito cream cracker", casa=_tudo(r"cream ?crackers?"),
             exclui=r"recheio|recheado|sabor|queijo|cebola|ervas|gergelim|linhaca|chia|aveia|multigrao|gluten|kids|\bmini\b|pizza|chocolate|cobertura",
             dims=[dim((r"integral", "integral"), (r"light|diet|zero", "light"), (r"manteiga|amanteigado|\bamant\b", "amanteigado"), varios=True)]),
    declarar("biscoito_maisena", "Biscoito maisena", casa=_tudo(r"\b(biscoito|bisc|bolacha)\b", r"\bmai[sz]ena\b"),
             exclui=r"chocolate|choco|recheio|recheado|cobertura|sabor|coco|baunilha|morango|leite condensado|doce de leite|goiabada|banana|laranja|limao|cenoura|\bmini\b|amido",
             dims=[dim((r"sem gluten", "sem glúten"), (r"laminado", "laminado"), (r"manteiga|amanteigado", "amanteigado"), (r"integral", "integral"), (r"light|diet|zero", "light"), varios=True)]),
    Familia("ovos", "ovos", _comeca(r"^ovos? "), _ovos),
]


# ============================== sexta leva: hortifrúti (frutas, verduras e legumes) ==============================
# Uma família só, guiada por uma tabela de produtos. A chave junta produto + variedade + importada + orgânico + "como se compra":
#  - preço POR QUILO (unidade "kg": o preço é de 1 kg, qualquer que seja o peso do nome) vale "1 kg";
#  - pacote com o peso no nome vale esse peso, e o pacote de 1 kg é o mesmo que o preço por quilo;
#  - sem peso nenhum (alface, maço) vale "unidade".
# Veja docs/hortifruti.md. Só entra o que o mercado põe na categoria Hortifrúti (o filtro da coleta); aqui o nome só descarta o processado.

# (id, rótulo, gênero, começo do nome, variedades). A 1ª variedade que casa vale; sem nenhuma, a variedade fica vazia (o "comum").
# A ordem importa: "couve-flor" antes de "couve", "alho-poró" antes de "alho", "abobrinha" (que inclui "abóbora italiana") antes de "abóbora".
_PRODUTOS_HORTIFRUTI = [
    ("banana", "Banana", "f", r"banana\b", [(r"nanica|caturra", "nanica"), (r"da terra|\bterra\b", "da terra"), (r"\bmaca\b", "maçã"), (r"prata|\bprta\b", "prata")]),
    ("maca", "Maçã", "f", r"maca\b", [(r"fuji", "fuji"), (r"gala", "gala"), (r"granny", "granny smith"), (r"pink lady", "pink lady"), (r"golden", "golden"), (r"\bred\b|vermelha", "red")]),
    ("laranja", "Laranja", "f", r"laranja\b", [(r"pera", "pera"), (r"bahia", "bahia"), (r"serra d ?agua", "serra d'água"), (r"lima", "lima"), (r"seleta", "seleta")]),
    ("limao", "Limão", "m", r"limao\b", [(r"tahiti|taiti", "taiti"), (r"siciliano", "siciliano"), (r"cravo", "cravo")]),
    ("mamao", "Mamão", "m", r"mamao\b", [(r"formosa", "formosa"), (r"papaya|papaia", "papaia")]),
    ("melancia", "Melancia", "f", r"melancia\b", [(r"baby", "baby"), (r"amarela", "amarela")]),
    ("abacaxi", "Abacaxi", "m", r"abacaxi\b", [(r"perola", "pérola"), (r"havai", "havaí")]),
    ("manga", "Manga", "f", r"manga\b", [(r"palmer", "palmer"), (r"tommy", "tommy"), (r"keyte|keitt|kent", "keitt"), (r"rosa", "rosa"), (r"espada", "espada")]),
    ("uva", "Uva", "f", r"uva\b", [(r"niagara", "niágara"), (r"thompson", "thompson"), (r"vitoria", "vitória"), (r"red globe", "red globe"), (r"sweet green|verde", "verde sem semente"),
                                   (r"cherry|cereja", "cherry"), (r"rubi", "rubi"), (r"italia", "itália")]),
    ("morango", "Morango", "m", r"morango\b", []),
    ("abacate", "Abacate", "m", r"abacate\b", [(r"avocado|hass", "avocado")]),
    ("tomate", "Tomate", "m", r"tomate\b", [(r"com rama|\brama\b", "com rama"), (r"italiano", "italiano"), (r"salada|longa vida", "salada"), (r"cereja", "cereja"), (r"uva|grape", "uva"), (r"maca", "maçã")]),
    ("batata", "Batata", "f", r"batata\b", [(r"doce.*\broxa\b|\broxa\b.*doce", "doce roxa"), (r"doce.*\bbranca\b|\bbranca\b.*doce", "doce branca"), (r"doce", "doce"), (r"baroa", "baroa"), (r"bolinha", "bolinha"), (r"asterix|vermelha|rosada", "vermelha"), (r"inglesa|ingelsa|lavada", "inglesa")]),
    ("cebola", "Cebola", "f", r"cebola\b", [(r"roxa", "roxa"), (r"branca", "branca"), (r"mini|perola", "mini")]),
    ("cenoura", "Cenoura", "f", r"cenoura\b", [(r"baroa", "baroa")]),
    ("alho poro", "Alho-poró", "m", r"alho poro\b", []),
    ("alho", "Alho", "m", r"alho\b", [(r"roxo", "roxo")]),
    ("pepino", "Pepino", "m", r"pepino\b", [(r"japones|\bjap\b", "japonês"), (r"caipira", "caipira"), (r"baby|snack", "baby")]),
    ("abobrinha", "Abobrinha", "f", r"(abobrinha|abobora italiana)\b", []),
    ("abobora", "Abóbora", "f", r"abobora\b", [(r"japonesa|cabotia|kabotia", "japonesa"), (r"moranga", "moranga"), (r"jacare", "jacaré"), (r"menina", "menina"), (r"pump", "pump"), (r"vermelha", "vermelha")]),
    ("chuchu", "Chuchu", "m", r"chuchu\b", []),
    ("mandioca", "Mandioca", "f", r"(mandioca|aipim|macaxeira)\b", []),
    ("beterraba", "Beterraba", "f", r"beterraba\b", []),
    ("pimentao", "Pimentão", "m", r"pimentao\b", [(r"verde", "verde"), (r"amarelo", "amarelo"), (r"vermelho", "vermelho"), (r"laranja", "laranja"), (r"palermo|sweet", "sweet palermo"), (r"colorido|misto", "colorido")]),
    ("repolho", "Repolho", "m", r"repolho\b", [(r"roxo", "roxo"), (r"misto", "misto")]),
    ("brocolis", "Brócolis", "m", r"brocolis\b", [(r"ninja", "ninja")]),
    ("alface", "Alface", "f", r"alface\b", [(r"americana|americada", "americana"), (r"cresp", "crespa"), (r"lisa", "lisa"), (r"roxa", "roxa"), (r"mimosa", "mimosa"), (r"baby", "baby"), (r"croc", "crocante")]),
    ("couve flor", "Couve-flor", "f", r"couve ?flor\b", []),
    ("couve", "Couve", "f", r"couve\b", [(r"manteiga", "manteiga"), (r"baby", "baby")]),
]
# O que não é o produto fresco mesmo começando pelo nome dele: picado, ralado, congelado, conserva, fruta seca, doce, salgadinho, corte de carne ("maçã de peito")...
# ("batata doce" é legume: "doce" NÃO está aqui.)
_PROCESSADO_HORTIFRUTI = (r"processad|higieniz|ralad|picad|fatiad|descascad|cozid|vapor|a vacuo|rosti|frit|\bseco|\bsecos|\bpassas?\b|conserva|calda|triturad|florete|congelad"
                          r"|polpa|suco|geleia|chips|palha|molho|extrato|pure|desidratad|cristalizad|\bem po\b|flocos|granulad|\bpasta\b|crispy|rodelas|kitano|\bmuda"
                          r"|pelad|sem pele|peito|\bpre\b|ruffles|lays|pringles|doce de|bananada|mangada|\bsabor\b|temper|\bkit\b|\bcombo\b|\bpara conserva"
                          # abreviações e marcas de congelado, salgadinho e tempero que o nome sozinho não pega ("BATATA CONG", "ALHO TRITD", "Batata Tex Tubo"...)
                          r"|\bcong\b|air fryer|tritd|\btubo\b|\btex\b|truffle|\bpo\b|\bmassa\b|azeitona|ervas|speciale|\bsupreme\b|veg ?e? ?tal|sadia|seara"
                          r"|bem brasil|mais batata|\bmix\b|granola|wafer|sequilhos|torta|capim|amendoa|cobertura")
_ORGANICO = r"\borg\b|organic|orgchic"
_IMPORTADA = r"\bimp\b|importad|argentin|chilen"


def _produto_do_hortifruti(t):
    return next((p for p in _PRODUTOS_HORTIFRUTI if re.match(p[3], t)), None)


def _hortifruti(t, unidade=None):
    """Fruta, verdura ou legume fresco: produto, variedade, importada, orgânico e como se compra (por quilo, pacote com peso ou unidade)."""
    produto = _produto_do_hortifruti(t)
    t = re.sub(r"\b\d+ a \d+ unidades?\b", " ", t)           # "500 g (1 a 2 unidades)": o Super ABC diz quantas vêm, e não é um multipacote
    if produto is None or re.search(_PROCESSADO_HORTIFRUTI, t) or re.search(_MULTIPACOTE, t):
        return None
    id_, nome, genero, _, variedades = produto
    variedade = escolher(t, variedades, "")
    organico, importada = re.search(_ORGANICO, t) is not None, re.search(_IMPORTADA, t) is not None
    if unidade == "kg":                                          # o preço é de 1 kg, seja qual for o peso que o nome cita (ele é o de cada porção)
        m = (True, 1000)
    else:
        m = medida(t, "massa", varrer=True)
        if m is None and re.search(r"\b(quilo|kg)\b", t):      # "Batata Bolinha Quilo" (unidade "un", sem número): é o pacote de 1 kg
            m = (True, 1000)
    final = "a" if genero == "f" else "o"
    rotulo = nome + (f" {variedade}" if variedade else "") + (f" importad{final}" if importada else "") + (f" orgânic{final}" if organico else "")
    if m is None:
        rotulo += ", unidade"
    return _Analise([id_, variedade, "importada" if importada else "", "organico" if organico else "", "" if m else "un"], m, rotulo)


FAMILIAS.append(Familia("hortifruti", "frutas, verduras e legumes", lambda t: _produto_do_hortifruti(t) is not None, _hortifruti, usa_unidade=True))

# ============================== sétima leva: cortes de carne e queijos a peso ==============================
# Uma família só, como a do hortifrúti, para os produtos da lista de carnes e frios a peso (docs/carnes_e_frios.md): oito cortes bovinos (patinho, acém, coxão mole, músculo,
# alcatra, fraldinha, picanha, contra filé) e os queijos minas e parmesão. A chave junta o corte (ou o tipo do queijo) e o que muda o preço do quilo:
#  - a FORMA (peça, fatiada, bife, cubos, moída; o queijo, fatiado, fração, cilindro...), o ESTADO (congelado; o resto vale como resfriado), o TEMPERO e a FAIXA
#    DE QUALIDADE ("premium" é o que o nome diz: Angus, Wagyu, Reserva, Maturatta...). Premium e congelado NUNCA se juntam com o comum e o fresco;
#  - o preço POR QUILO (unidade "kg": o preço é de 1 kg, seja qual for o peso do nome, que é o da porção) vale "1 kg"; o embalado de peso fixo ("un") vale o peso do nome.
# Sem peso (por quilo ou no nome), ou com o nome de outra coisa (a mesma peça de porco, o queijo ralado, o vegano), o produto fica sem chave: só aparece no modo exato.
# Veja docs/carnes_e_frios.md.

_PREFIXO_DE_CORTE = r"(?:carne\s+)?(?:bovina\s+|bovino\s+|bov\s+)?(?:bife\s+(?:de\s+)?|steak\s+)?"
# (id, rótulo, gênero, o corte depois do prefixo, partes do mesmo corte: (regex, nome)). Em alcatra, "miolo", "bombom" e "coração" são partes; em acém, o "miolo".
_CORTES_BOVINOS = [
    ("patinho", "Patinho", "m", r"patinho", []),
    ("acem", "Acém", "m", r"(?:miolo\s+(?:de\s+|do\s+)?)?acem", [(r"miolo", "miolo")]),
    ("coxao mole", "Coxão mole", "m", r"coxao\s+mole", []),
    ("musculo", "Músculo", "m", r"musculo", []),
    ("alcatra", "Alcatra", "f", r"(?:(?:miolo|bombom|coracao)\s+(?:de\s+|da\s+)?)?alcatra", [(r"miolo", "miolo"), (r"bombom", "bombom"), (r"coracao", "coração")]),
    ("fraldinha", "Fraldinha", "f", r"fraldinha", []),
    ("picanha", "Picanha", "f", r"picanha", []),
    ("contra file", "Contra filé", "m", r"contra\s?file", []),
]
_FORMAS_DE_CORTE = [(r"moid", ("moída", "moído")), (r"\bcubos?\b|strog", ("em cubos", "em cubos")), (r"\bbifes?\b|steak|babybeef", ("em bifes", "em bifes")),
                    (r"fatiad|\bfat\b", ("fatiada", "fatiado")), (r"\bpeca\b|pedaco|inteir|noix|principal|porcionad|\bporc\b", ("em peça", "em peça"))]
# O que o nome diz de qualidade. Uma marca premium que o nome não traz (um açougue de grife sem a palavra) fica entre os comuns: o preço dela aparece como o de um comum.
_PREMIUM_DE_CORTE = r"angus|wagyu|kobe|carapreta|reserva|maturatta|maturad|premium|gourmet|\bprime\b|dry ?aged|bassi"
_CONGELADO = r"\bcong\b|congelad|congela\b"
_TEMPERADO = r"temperad|\btemp\b"


def _corte_bovino(t):
    for corte in _CORTES_BOVINOS:
        if re.match(_PREFIXO_DE_CORTE + corte[3] + r"\b", t):
            return corte
    return None


def _tipo_de_queijo(t):
    if re.match(r"queijo\s+(?:supernosso\s+|abc\s+)?minas\b", t):
        return "minas"
    if re.match(r"(?:queijo\s+)?parmesao\b", t):
        return "parmesao"
    return None


def _a_peso(t):
    return _corte_bovino(t) or _tipo_de_queijo(t)


def _concorda(par, genero):
    return par[0] if genero == "f" else par[1]


def _carne_ou_queijo_a_peso(t, unidade=None):
    """Corte bovino ou queijo minas ou parmesão: o que o nome diz sobre forma, estado, tempero e faixa de qualidade, e o peso (1 kg por quilo; o do nome no embalado)."""
    produto = _a_peso(t)
    t = re.sub(r"\b\d+ a \d+ unidades?\b", " ", t)           # "500 g (1 a 2 unidades)": o Super ABC diz quantas vêm, e não é um multipacote
    if produto is None or re.search(r"suin|ralad|\bral\b|vegano|castanha", t) or re.search(_MULTIPACOTE, t):
        return None
    if unidade == "kg":                                          # o preço é de 1 kg, seja qual for o peso que o nome cita (ele é o de cada porção)
        m = (True, 1000)
    else:
        m = medida(t, "massa", varrer=True)
        if m is None:
            return None
    if isinstance(produto, tuple):
        id_, nome, genero, _, partes = produto
        parte = escolher(t, partes, "")
        forma = escolher(t, [(padrao, _concorda(par, genero)) for padrao, par in _FORMAS_DE_CORTE], "")
        peso_do_nome = medida(t, "massa", varrer=True)
        if not forma and peso_do_nome and peso_do_nome[1] >= 1000:      # sem a forma no nome, uma porção de 1 kg ou mais de corte é a peça ("Picanha Montana 1.5Kg")
            forma = "em peça"
        congelado = re.search(_CONGELADO, t) is not None
        temperado = re.search(_TEMPERADO, t) is not None
        premium = re.search(_PREMIUM_DE_CORTE, t) is not None
        palavras = [nome + (f" {parte}" if parte else ""), forma, ("congelada" if genero == "f" else "congelado") if congelado else "",
                    ("temperada" if genero == "f" else "temperado") if temperado else "", "premium" if premium else ""]
        partes_da_chave = ["corte", id_, parte, forma, "congelado" if congelado else "", "temperado" if temperado else "", "premium" if premium else ""]
        return _Analise(partes_da_chave, m, " ".join(p for p in palavras if p))
    if produto == "minas":
        tipo = escolher(t, [(r"frescal", "frescal"), (r"meia cura|\bmc\b|semi ?curad", "meia cura"), (r"curad|maturad", "curado"), (r"padrao|\bpad\b", "padrão")], "")
        especiais = _todos(t, [(r"zero lactose|sem lactose|lacfree|zero lact\b", "zero lactose"), (r"light", "light"), (r"artesanal", "artesanal"), (r"bufala|bufalo", "de búfala"),
                               (r"defumad", "defumado"), (r"acafrao|pimenta|pimentinha|cachaca|condimentad|calamel|\bmel\b|ervas|temperad", "temperado")])
        fatiado = re.search(r"fatiad|\bfat\b", t) is not None
        palavras = ["Queijo minas", tipo, "fatiado" if fatiado else "", especiais]
        return _Analise(["queijo", "minas", tipo, "fatiado" if fatiado else "", especiais], m, " ".join(p for p in palavras if p))
    forma = "fatiado" if re.search(r"fatiad|lascas", t) else ""                  # o cilindro, a fração e a peça são o mesmo pedaço: o peso diz o tamanho
    maturado = re.search(r"maturad|\b\d+ meses\b|reserva", t) is not None
    importado = re.search(r"importad|argentin|\barg\b|italian|reggiano|grana padano", t) is not None
    palavras = ["Queijo parmesão", forma, "maturado" if maturado else "", "importado" if importado else ""]
    return _Analise(["queijo", "parmesao", forma, "maturado" if maturado else "", "importado" if importado else ""], m, " ".join(p for p in palavras if p))


FAMILIAS.append(Familia("carnes_a_peso", "cortes de carne e queijos a peso", lambda t: _a_peso(t) is not None, _carne_ou_queijo_a_peso, usa_unidade=True))


# ============================== a interface ==============================

def equivalencia(nome, familias=None, unidade=None) -> Optional[Equivalencia]:
    """A chave e o rótulo do produto, ou None se ele não se encaixa em nenhuma regra.

    A primeira família que casa com o nome decide: se ela recusa o produto, ele fica sem chave. Por isso as famílias mais
    específicas ("leite condensado") vêm antes das gerais ("leite"). `familias` troca a lista (os testes usam as 11 originais).
    `unidade` ("kg": o preço é por quilo; "un" ou vazia) só importa ao hortifrúti.
    """
    t = normalizar(nome)
    if re.search(r"\b\d+ ?x ?\d+", t):      # caixas e multipacotes ("24x40g")
        return None
    for f in (FAMILIAS if familias is None else familias):
        if not f.casa(t):
            continue
        if unidade == "kg" and not f.usa_unidade:       # o preço é por quilo e o peso do nome é o da porção: só as famílias que leem a unidade sabem comparar
            return None
        r = f.analisar(t, unidade) if f.usa_unidade else f.analisar(t)
        if not r:
            return None
        sufixo = ("" if r.m is None else f"{r.m[1]}{'g' if r.m[0] else 'ml'}")
        return Equivalencia("|".join([f.id, *r.partes, sufixo]), r.rotulo + (f", {texto_medida(r.m)}" if r.m else ""))
    return None


def familias_equivalentes():
    """Os títulos das famílias, na ordem em que foram declaradas (para o site dizer 'vale para arroz, feijão, ...')."""
    return [f.titulo for f in FAMILIAS]


def com_equivalencia(produtos):
    """Cópias dos produtos com `chave_equivalencia` e `rotulo_equivalencia` quando o produto se encaixa em alguma família."""
    saida = []
    for p in produtos:
        e = equivalencia(p.get("nome", ""), unidade=p.get("unidade"))
        saida.append({**p, "chave_equivalencia": e.chave, "rotulo_equivalencia": e.rotulo} if e else p)
    return saida
