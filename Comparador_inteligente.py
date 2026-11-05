import re
from thefuzz import fuzz

# --- 1. BLINDAGEM DE PESOS E MEDIDAS ---
def extrair_medida(nome):
    nome = nome.lower()
    # Busca padrões normais: 500g, 1kg, 1.5l, 900 ml
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|litro|litros)\b', nome)
    
    # Se o mercado esquecer a letra (ex: "Pacote 250"), caça números clássicos
    if not match:
        match = re.search(r'\b(250|500|900|1000)\b', nome)
        if match:
            return f"{match.group(1)}g" # Assume gramas por segurança
        return None

    valor = match.group(1).replace(',', '.')
    unidade = match.group(2).replace('litros', 'l').replace('litro', 'l')
    
    # MÁGICA: Normaliza unidades (1kg vira 1000.0g) para comparar mercados diferentes
    if unidade == 'kg':
        valor = str(float(valor) * 1000)
        unidade = 'g'
    elif unidade == 'l':
        valor = str(float(valor) * 1000)
        unidade = 'ml'
        
    return f"{float(valor)}{unidade}"

# --- 2. BLINDAGEM DE SIGNIFICADO (Tags) ---
def extrair_tags_chave(nome):
    nome = nome.lower()
    tags = set()
    
    # Estado do Produto
    if "grao" in nome or "grãos" in nome or "grão" in nome: tags.add("grao")
    elif "po " in nome or "pó " in nome or "moido" in nome or "moído" in nome: tags.add("po")
    
    # Tipo
    if "soluvel" in nome or "solúvel" in nome: tags.add("soluvel")
    if "descafeinado" in nome: tags.add("descafeinado")
    
    # Variantes clássicas de café/alimentos
    if "extraforte" in nome or "extra forte" in nome: tags.add("extraforte")
    elif "tradicional" in nome: tags.add("tradicional")
    elif "gourmet" in nome: tags.add("gourmet")
    elif "premium" in nome: tags.add("premium")
    
    return tags

def normalizar_nome(nome):
    nome = nome.lower()
    nome = nome.replace('ã', 'a').replace('õ', 'o').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    
    # ARRANCAMOS as medidas do texto base para elas não confundirem o thefuzz
    nome = re.sub(r'\d+(?:[.,]\d+)?\s*(kg|g|ml|l|litro|litros)\b', '', nome)
    nome = re.sub(r'\b(250|500|900|1000)\b', '', nome)
    
    palavras_ignoradas = ['pacote', 'garrafa', 'pet', 'unidade', 'tipo 1', '-', 'branco', 'agulhinha']
    for palavra in palavras_ignoradas:
        nome = nome.replace(palavra, '')
    return re.sub(r'\s+', ' ', nome).strip()

def _chave_do_ean(ean):
    """0630941446201 (EAN-13) e 630941446201 (UPC-12) são o mesmo código: compara sem os zeros à esquerda."""
    return str(ean).lstrip('0')


def _medidas_conflitam(medida_a, medida_b):
    return bool(medida_a and medida_b and medida_a != medida_b)


def _entrar_no_grupo(grupo, produto):
    """O grupo guarda uma opção por mercado: a mais barata."""
    mercado = produto['supermercado']
    atual = grupo['opcoes_dict'].get(mercado)
    if atual is None or produto['preco_varejo'] < atual['preco_varejo']:
        grupo['opcoes_dict'][mercado] = produto


LIMITE_NOME_IDENTICO = 95   # pontuação mínima para juntar grupos de EAN diferente (nome praticamente igual)


def _juntar_grupos_de_ean_diferente(grupos, limite=LIMITE_NOME_IDENTICO):
    """O mesmo produto às vezes tem um EAN em cada mercado (cadastro diferente). Junta dois grupos de EAN diferente só se:
    o nome é praticamente idêntico (pontuação a partir de `limite`), a medida e as tags não discordam e eles não têm
    nenhum mercado em comum (se os dois vendem no mesmo mercado, são produtos distintos ali). Nomes só parecidos
    ("Heineken Zero" x "Heineken") ficam abaixo do limite e não se juntam.
    """
    com_ean = [g for g in grupos if g.get('ean')]
    removidos = set()
    for i, grupo in enumerate(com_ean):
        if id(grupo) in removidos:
            continue
        for outro in com_ean[i + 1:]:
            if id(outro) in removidos or _chave_do_ean(outro['ean']) == _chave_do_ean(grupo['ean']):
                continue
            if set(grupo['opcoes_dict']) & set(outro['opcoes_dict']) or _medidas_conflitam(grupo['medida'], outro['medida']):
                continue
            if grupo['tags'] != outro['tags'] and grupo['tags'] and outro['tags']:
                continue
            if fuzz.token_sort_ratio(grupo['nome_limpo'], outro['nome_limpo']) >= limite:
                for produto in outro['opcoes_dict'].values():
                    _entrar_no_grupo(grupo, produto)
                grupo['medida'] = grupo['medida'] or outro['medida']
                removidos.add(id(outro))
    return [g for g in grupos if id(g) not in removidos]


def cruzar_multiplos_produtos(lista_de_resultados_dos_robos, limite_confianca=75):
    """Agrupa os produtos de vários mercados que são o mesmo produto, uma opção (a mais barata) por mercado.

    1) Mesmo código de barras (EAN) = mesmo produto, sem adivinhar pelo nome. Só não junta se as medidas do nome
       discordarem (EAN repetido por engano no cadastro).
    2) O que não tem EAN (o robô do Super ABC não o lê) entra no grupo mais parecido pelo nome, como sempre foi:
       mesma medida, mesmas tags de significado e nome com pontuação de similaridade a partir de `limite_confianca`.
    Grupos de EAN diferentes só se juntam pelo caso estrito de `_juntar_grupos_de_ean_diferente`.
    """
    todos_produtos = []
    for lista_mercado in lista_de_resultados_dos_robos:
        if lista_mercado:
            todos_produtos.extend(lista_mercado)

    grupos_de_produtos = []
    grupos_por_ean = {}   # ean -> grupos (quase sempre um só)

    # --- 1. MESMO CÓDIGO DE BARRAS ---
    for produto in (p for p in todos_produtos if p.get('ean')):
        medida_produto = extrair_medida(produto['nome'])
        candidatos = grupos_por_ean.setdefault(_chave_do_ean(produto['ean']), [])
        grupo = next((g for g in candidatos if not _medidas_conflitam(medida_produto, g['medida'])), None)
        if grupo is None:
            grupo = {
                "produto_base": produto['nome'],
                "nome_limpo": normalizar_nome(produto['nome']),
                "medida": medida_produto,
                "tags": extrair_tags_chave(produto['nome']),
                "ean": produto['ean'],
                "opcoes_dict": {},
            }
            candidatos.append(grupo)
            grupos_de_produtos.append(grupo)
        elif not grupo['medida']:
            grupo['medida'] = medida_produto   # o primeiro nome não trazia a medida; o seguinte traz
        _entrar_no_grupo(grupo, produto)

    # --- 1b. EAN DIFERENTE, MESMO PRODUTO: só com nome praticamente idêntico em mercados diferentes ---
    grupos_de_produtos = _juntar_grupos_de_ean_diferente(grupos_de_produtos)

    # --- 2. SEM CÓDIGO DE BARRAS: parecido pelo nome ---
    for produto in (p for p in todos_produtos if not p.get('ean')):
        nome_limpo = normalizar_nome(produto['nome'])
        medida_produto = extrair_medida(produto['nome'])
        tags_produto = extrair_tags_chave(produto['nome'])

        encaixou_em_algum_grupo = False

        for grupo in grupos_de_produtos:
            # Nome limpo, medida e tags do grupo foram calculados uma única vez, quando ele foi criado
            medida_grupo = grupo['medida']
            tags_grupo = grupo['tags']

            # --- O LEÃO DE CHÁCARA ---
            # 1. Se os pesos forem diferentes, bloqueia e vira grupo novo!
            if _medidas_conflitam(medida_produto, medida_grupo):
                continue

            # 2. Se um for "Grão" e o outro "Pó" (ou Extraforte vs Tradicional), bloqueia!
            if tags_produto != tags_grupo and (len(tags_produto) > 0 and len(tags_grupo) > 0):
                continue

            # Só depois de passar pela segurança, ele faz a matemática de texto
            if fuzz.token_sort_ratio(nome_limpo, grupo['nome_limpo']) >= limite_confianca:
                _entrar_no_grupo(grupo, produto)
                encaixou_em_algum_grupo = True
                break

        if not encaixou_em_algum_grupo:
            grupos_de_produtos.append({
                "produto_base": produto['nome'],
                "nome_limpo": nome_limpo,
                "medida": medida_produto,
                "tags": tags_produto,
                "opcoes_dict": { produto['supermercado']: produto }
            })

    resultados_finais = []
    for grupo in grupos_de_produtos:
        opcoes = list(grupo['opcoes_dict'].values())
        opcoes.sort(key=lambda x: x['preco_varejo'])
        vencedor = opcoes[0]

        if len(opcoes) > 1:
            vencedor_str = vencedor['supermercado']
        else:
            vencedor_str = f"{vencedor['supermercado']} (Exclusivo)"

        resultado = {
            "produto_base": grupo['produto_base'],
            "vencedor_preco_baixo": vencedor_str,
            "opcoes_de_compra": opcoes
        }
        if grupo.get('ean'):
            resultado["ean"] = grupo['ean']
        resultados_finais.append(resultado)

    return resultados_finais
