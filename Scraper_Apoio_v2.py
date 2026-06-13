import re
from playwright.async_api import async_playwright

def estruturar_produto_apoio_json(texto_bruto):
    partes =[p.strip() for p in texto_bruto.split('|') if p.strip()]
    nome = "Produto Desconhecido"
    for p in partes:
        p_minusculo = p.lower()
        if "%" in p_minusculo or p_minusculo in["oferta", "promoção", "termina em breve", "ver tudo"]:
            continue
        if len(p) > 4: 
            nome = p
            break

    produto = {
        "supermercado": "Apoio Entrega",
        "nome": nome,
        "preco_varejo": None,
        "preco_atacado": None,
        "quantidade_atacado": 1, 
        "texto_original": texto_bruto
    }

    precos_encontrados = re.findall(r'R\$\s*(\d+,\d{2})', texto_bruto)
    precos_float =[float(p.replace(',', '.')) for p in precos_encontrados]

    if not precos_float:
        return None

    match_qtd = re.search(r'acima de (\d+)', texto_bruto, re.IGNORECASE)

    if match_qtd and len(precos_float) >= 2:
        produto["quantidade_atacado"] = int(match_qtd.group(1))
        produto["preco_atacado"] = min(precos_float)
        produto["preco_varejo"] = max(precos_float)
    else:
        preco_real = min(precos_float)
        produto["preco_varejo"] = preco_real
        produto["preco_atacado"] = preco_real

    return produto

# --- MUDANÇA AQUI: Agora é uma função que recebe CEP e ITEM ---
async def buscar_no_apoio(cep_usuario: str, item_usuario: str):
    print(f"🤖 [Apoio] Iniciando robô invisível para buscar '{item_usuario}' no CEP {cep_usuario}...")
    
    async with async_playwright() as p:
        # headless=True! O robô agora é silencioso e invisível.
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context(viewport={'width': 1366, 'height': 768})
        page = await context.new_page()

        await page.goto("https://www.apoioentrega.com/", wait_until="domcontentloaded", timeout=60000)
        
        try:
            btn_pf = page.locator("text='Sou pessoa física'").first
            await btn_pf.click(timeout=3000, force=True)
        except: pass
            
        try:
            btn_cookies = page.locator("button:has-text('Aceitar'), button:has-text('Entendi')").first
            await btn_cookies.click(timeout=2000, force=True)
        except: pass 

        try:
            search_bar = page.locator("input.fulltext-search-box:visible").first
            await search_bar.wait_for(state="visible", timeout=5000)
            await search_bar.click(force=True) 
            # Usa a variável que veio da API
            await search_bar.fill(item_usuario, force=True) 
            await search_bar.press("Enter")
            await page.wait_for_timeout(7000) 
        except Exception as e:
            print(f"❌ [Apoio] Erro na busca: {e}")

        try:
            btn_comprar = page.locator(
                "button:has-text('Comprar'):visible, "
                "a:has-text('Comprar'):visible, "
                "button:has-text('Adicionar'):visible"
            ).first
            await btn_comprar.wait_for(state="visible", timeout=5000)
            await btn_comprar.click(force=True)
            await page.wait_for_timeout(3000)
        except: pass

        try:
            cep_input = page.locator("#cepInput, input[name='cep']").first
            await cep_input.wait_for(state='visible', timeout=5000)
            # Usa a variável de CEP que veio da API
            await cep_input.fill(cep_usuario, force=True)
            
            btn_confirmar_cep = page.locator(
                "button:has-text('Confirmar'):visible, "
                "button:has-text('Salvar'):visible, "
                "button:has-text('Buscar'):visible, "
                "button:has-text('OK'):visible, "
                "button:has-text('Calcular'):visible"
            ).first
            await btn_confirmar_cep.click(force=True)
            
            msg_sucesso = page.locator(".cart__body--cep-validado--box .positive").first
            await msg_sucesso.wait_for(state="visible", timeout=5000)

            opcao_entrega = page.locator("li[data-type='click-delivery']").first
            await opcao_entrega.wait_for(state="visible", timeout=5000)
            await opcao_entrega.click(force=True)
            
            await page.wait_for_timeout(6000)
        except: pass

        textos_produtos = await page.evaluate('''() => {
            const items =[];
            const cards = document.querySelectorAll("article, section.vtex-product-summary-2-x-container, div[class*='shelf-item'], div[class*='box-item'], li[layout]");
            cards.forEach(card => {
                const text = card.innerText;
                if (text && text.includes('R$')) {
                    items.push(text.replace(/\\n/g, ' | ').trim());
                }
            });
            return [...new Set(items)];
        }''')

        lista_final_json =[]
        for texto in textos_produtos:
            produto = estruturar_produto_apoio_json(texto)
            if produto:
                lista_final_json.append(produto)

        await browser.close()
        print(f"✅ [Apoio] Extração concluída! Encontrados {len(lista_final_json)} itens.")
        
        # Em vez de imprimir (print), a função DEVOLVE os dados para a API
        return lista_final_json
