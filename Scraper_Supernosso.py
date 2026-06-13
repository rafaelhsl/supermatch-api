import asyncio
import re
from playwright.async_api import async_playwright

def estruturar_produto_supernosso_json(texto_bruto):
    partes = [p.strip() for p in texto_bruto.split('|') if p.strip()]
    
    # 1. Encontrar o nome real (pulando lixo da VTEX IO)
    nome = "Produto Desconhecido"
    for p in partes:
        p_lower = p.lower()
        # Ignora tags promocionais, preços quebrados e botões
        if "%" in p_lower or "patrocinado" in p_lower or "de:" in p_lower or "por:" in p_lower or "comprar" in p_lower or "adicionar" in p_lower:
            continue
        # Se não tem R$ e tem mais de 4 letras, encontramos o nome do produto!
        if "r$" not in p_lower and len(p) > 4:
            nome = p
            break

    # Se mesmo assim não achou nome (era só lixo da prateleira), descarta
    if nome == "Produto Desconhecido":
        return None

    produto = {
        "supermercado": "Supernosso",
        "nome": nome,
        "preco_varejo": None,
        "preco_atacado": None,
        "quantidade_atacado": 1, # Supernosso não tem regra de atacado para consumidor final
        "texto_original": texto_bruto
    }

    # 2. Caçador de Preços
    precos_encontrados = re.findall(r'R\$\s*(\d+,\d{2})', texto_bruto)
    precos_float = [float(p.replace(',', '.')) for p in precos_encontrados]

    if not precos_float:
        return None

    # No modelo do Supernosso (De / Por), o menor preço é sempre o preço de venda atual.
    preco_real = min(precos_float)
    
    produto["preco_varejo"] = preco_real
    produto["preco_atacado"] = preco_real

    return produto

async def buscar_no_supernosso(cep_usuario: str, item_usuario: str):
    print(f"🤖 [Supernosso] Iniciando robô invisível para buscar '{item_usuario}'...")
    
    async with async_playwright() as p:
        # Modo invisível ativado (headless=True)
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context(viewport={'width': 1366, 'height': 768})
        page = await context.new_page()

        await page.goto("https://www.supernosso.com/", wait_until="domcontentloaded")
        
        # Tentativa rápida de limpar cookies
        try:
            btn_cookies = page.locator("button:has-text('Aceitar'), button:has-text('Entendi')").first
            await btn_cookies.click(timeout=3000, force=True)
        except: pass 

        # PASSO B: Pesquisar o Produto (COM SEU NOVO CÓDIGO)
        try:
            # Usando o placeholder exato que você descobriu!
            search_bar = page.locator("input[placeholder*='procure' i]:visible").first
            await search_bar.wait_for(state="visible", timeout=5000)
            await search_bar.click(force=True) 
            await search_bar.fill(item_usuario, force=True) 
            await search_bar.press("Enter")
            await page.wait_for_timeout(7000) 
        except Exception as e:
            print(f"❌ [Supernosso] Erro na busca: {e}")

        # PASSO C: Tentar Adicionar para forçar pop-up de CEP (Modo VTEX IO)
        try:
            btn_comprar = page.locator(
                "button:has-text('Comprar'):visible, "
                "button:has-text('Adicionar'):visible"
            ).first
            await btn_comprar.wait_for(state="visible", timeout=5000)
            await btn_comprar.click(force=True)
            await page.wait_for_timeout(3000)
        except: pass

        # PASSO D: Inserir o CEP
        try:
            # Seletores clássicos de CEP VTEX IO
            cep_input = page.locator("input[name*='postalCode' i], input[placeholder*='CEP' i]").first
            await cep_input.wait_for(state='visible', timeout=5000)
            await cep_input.fill(cep_usuario, force=True)
            
            btn_confirmar_cep = page.locator(
                "button:has-text('Confirmar'):visible, "
                "button:has-text('Salvar'):visible"
            ).first
            await btn_confirmar_cep.click(force=True)
            await page.wait_for_timeout(6000)
        except: pass

        # PASSO E: Ler a prateleira
        textos_produtos = await page.evaluate('''() => {
            const items = [];
            const cards = document.querySelectorAll("article, section.vtex-product-summary-2-x-container, div[class*='shelf-item']");
            cards.forEach(card => {
                const text = card.innerText;
                if (text && text.includes('R$')) {
                    items.push(text.replace(/\\n/g, ' | ').trim());
                }
            });
            return [...new Set(items)];
        }''')

        # Converte para JSON filtrando os lixos
        lista_final_json = []
        for texto in textos_produtos:
            produto = estruturar_produto_supernosso_json(texto)
            if produto:
                lista_final_json.append(produto)

        await browser.close()
        print(f"✅ [Supernosso] Extração concluída! Encontrados {len(lista_final_json)} itens limpos.")
        return lista_final_json

# --- BLOCO DE TESTE LOCAL ---
# Se você rodar este arquivo sozinho, ele testa. Se a API chamar, ele obedece a API.
if __name__ == "__main__":
    async def teste():
        resultados = await buscar_no_supernosso("32607600", "Cafe")
        import json
        print(json.dumps(resultados[:3], indent=4, ensure_ascii=False))
    asyncio.run(teste())