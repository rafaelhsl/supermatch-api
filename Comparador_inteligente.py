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

def cruzar_multiplos_produtos(lista_de_resultados_dos_robos, limite_confianca=75):
    todos_produtos = []
    for lista_mercado in lista_de_resultados_dos_robos:
        if lista_mercado:
            todos_produtos.extend(lista_mercado)

    grupos_de_produtos = []

    for produto in todos_produtos:
        nome_limpo = normalizar_nome(produto['nome'])
        medida_produto = extrair_medida(produto['nome'])
        tags_produto = extrair_tags_chave(produto['nome'])
        
        encaixou_em_algum_grupo = False
        mercado_atual = produto['supermercado']
        
        for grupo in grupos_de_produtos:
            nome_grupo_limpo = normalizar_nome(grupo['produto_base'])
            medida_grupo = extrair_medida(grupo['produto_base'])
            tags_grupo = extrair_tags_chave(grupo['produto_base'])
            
            # --- O LEÃO DE CHÁCARA ---
            # 1. Se os pesos forem diferentes, bloqueia e vira grupo novo!
            if medida_produto and medida_grupo and medida_produto != medida_grupo:
                continue 
                
            # 2. Se um for "Grão" e o outro "Pó" (ou Extraforte vs Tradicional), bloqueia!
            if tags_produto != tags_grupo and (len(tags_produto) > 0 and len(tags_grupo) > 0):
                continue

            # Só depois de passar pela segurança, ele faz a matemática de texto
            pontuacao = fuzz.token_sort_ratio(nome_limpo, nome_grupo_limpo)
            
            if pontuacao >= limite_confianca:
                if mercado_atual in grupo['opcoes_dict']:
                    preco_existente = grupo['opcoes_dict'][mercado_atual]['preco_varejo']
                    if produto['preco_varejo'] < preco_existente:
                        grupo['opcoes_dict'][mercado_atual] = produto
                else:
                    grupo['opcoes_dict'][mercado_atual] = produto
                    
                encaixou_em_algum_grupo = True
                break
        
        if not encaixou_em_algum_grupo:
            grupos_de_produtos.append({
                "produto_base": produto['nome'],
                "opcoes_dict": { mercado_atual: produto }
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
            
        resultados_finais.append({
            "produto_base": grupo['produto_base'],
            "vencedor_preco_baixo": vencedor_str,
            "opcoes_de_compra": opcoes
        })

    return resultados_finais