"""Produto equivalente: o mesmo tipo de produto no mesmo tamanho, de qualquer marca.

Cada família abaixo diz o que DIFERENCIA um produto do outro (arroz parboilizado não é arroz branco; leite desnatado não é
leite integral; vinagre de maçã não é vinagre de álcool) e o que não importa (marca, embalagem, "pacote", "caixa com tampa").
O tamanho (g, kg, ml, L) sempre conta. O resultado é uma chave: produtos com a mesma chave são equivalentes.

Na dúvida, não junta: o produto que não cabe em nenhuma regra fica sem chave e só aparece no modo "exato". Errar por juntar
de menos é seguro; juntar o que não é equivalente engana a pessoa.

As 11 primeiras famílias (arroz a papel higiênico) são a tradução fiel das que viviam em site/index.html; o teste
tests/test_equivalencia.py as confere com os mesmos casos do teste em JavaScript. As demais são declaradas pela função
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
    analisar: Callable[[str], Optional[_Analise]]


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
    Familia("macarrao", "macarrão", _comeca(r"^macarrao "), _macarrao),
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


def dim(*regras, obrigatoria=False, padrao=""):
    return Dim(tuple(regras), obrigatoria, padrao)


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


# ============================== a interface ==============================

def equivalencia(nome, familias=None) -> Optional[Equivalencia]:
    """A chave e o rótulo do produto, ou None se ele não se encaixa em nenhuma regra.

    A primeira família que casa com o nome decide: se ela recusa o produto, ele fica sem chave. Por isso as famílias mais
    específicas ("leite condensado") vêm antes das gerais ("leite"). `familias` troca a lista (os testes usam as 11 originais).
    """
    t = normalizar(nome)
    if re.search(r"\b\d+ ?x ?\d+", t):      # caixas e multipacotes ("24x40g")
        return None
    for f in (FAMILIAS if familias is None else familias):
        if not f.casa(t):
            continue
        r = f.analisar(t)
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
        e = equivalencia(p.get("nome", ""))
        saida.append({**p, "chave_equivalencia": e.chave, "rotulo_equivalencia": e.rotulo} if e else p)
    return saida
