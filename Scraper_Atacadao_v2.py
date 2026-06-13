import re
from playwright.async_api import async_playwright

def estruturar_produto_atacadao_json(texto_bruto):
    partes =[p.strip() for p in texto_bruto.split('|') if p.strip()]
    nome = partes[0] if partes else "Produto Desconhecido"
    
    produto = {
        "supermercado": "Atacadao",
        "nome": nome,
        "preco_varejo": None,
        "preco_atacado": None,
        "quantidade_atacado": 1,
        "texto_original": texto_bruto
    }
    
    precos_encontrados = re.findall(r'R\$\s*(\d+,\d{2})', texto_bruto)
    precos_float = [float(p.replace(',', '.')) for p in precos_encontrados]
    
    if not precos_float: return None
    
    match_qtd = re.search(r'A partir de (\d+)', texto_bruto, re.IGNORECASE)
    if match_qtd and len(precos_float) >= 2:
        produto["quantidade_atacado"] = int(match_qtd.group(1))
        produto["preco_atacado"] = min(precos_float)
        produto["preco_varejo"] = max(precos_float)
    else:
        produto["preco_varejo"] = min(precos_float)
        produto["preco_atacado"] = min(precos_float)
        
    return produto

async def buscar_no_atacadao(cep_usuario: str, item_usuario: str):
    print(f"🤖 [Atacadão] Iniciando robô invisível para buscar '{item_usuario}'...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # --- BLINDAGEM ANTI-QUEDA DE REDE ---
        try:
            # domcontentloaded é mais rápido. 60000ms dá 1 minuto pro servidor respirar
            await page.goto("https://www.atacadao.com.br/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000) 
        except Exception as e:
            print(f"⚠️ [Atacadão] Site fora do ar ou muito lento. Abortando este item. Erro: {e}")
            await browser.close()
            return [] # Retorna vazio, mas NÃO QUEBRA os outros robôs!
        # ------------------------------------

        try:
            search_bar = page.locator("input[type='search']:visible, input[placeholder*='busc' i]:visible, input[placeholder*='pesquis' i]:visible").first
            await search_bar.wait_for(state="visible", timeout=5000)
            await search_bar.click(force=True) 
            await search_bar.fill(item_usuario, force=True) 
            await search_bar.press("Enter")
            await page.wait_for_timeout(8000) 
        except: pass

        try:
            btn_comprar = page.locator("button:has-text('Adicionar'):visible, button:has-text('Comprar'):visible").first
            await btn_comprar.wait_for(state="visible", timeout=5000)
            await btn_comprar.click(force=True)
            await page.wait_for_timeout(4000)
        except: pass

        try:
            cep_input = page.locator("input[name*='cep' i]:visible, input[placeholder*='CEP' i]:visible, input[placeholder*='00000' i]:visible").first
            await cep_input.wait_for(state='visible', timeout=5000)
            await cep_input.fill(cep_usuario, force=True)
            
            btn_confirmar_cep = page.locator("button:has-text('Confirmar'):visible, button:has-text('Buscar'):visible, button:has-text('Salvar'):visible").first
            await btn_confirmar_cep.click(force=True)
            await page.wait_for_timeout(6000)
        except: pass

        textos_produtos = await page.evaluate('''() => {
            const items =[];
            const cards = document.querySelectorAll("article, [data-testid*='product-card'], div[class*='ProductCard']");
            cards.forEach(card => {
                const text = card.innerText;
                if (text && text.includes('R$')) {
                    let cleanText = text.replace(/\\n/g, ' | ').trim();
                    if (cleanText.length > 15 && cleanText.length < 400 && !cleanText.includes("Departamento")) {
                        items.push(cleanText);
                    }
                }
            });
            return [...new Set(items)];
        }''')

        lista_final_json =[]
        for texto in textos_produtos:
            produto = estruturar_produto_atacadao_json(texto)
            if produto:
                lista_final_json.append(produto)

        await browser.close()
        print(f"✅ [Atacadão] Extração concluída! Encontrados {len(lista_final_json)} itens.")
        return lista_final_json
