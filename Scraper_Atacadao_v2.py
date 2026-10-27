import asyncio
import re
from playwright.async_api import async_playwright
from robos_comum import exigir_produtos

from robos_comum import (BuscaNaoRealizada, abortar, cep_com_hifen, eh_etiqueta_promocional,
                         esperar_na_pagina, url_mostra_busca)

def estruturar_produto_atacadao_json(texto_bruto):
    partes = [p.strip() for p in texto_bruto.split('|') if p.strip()]
    nome = next((p for p in partes if not eh_etiqueta_promocional(p)), "Produto Desconhecido")
    
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
    elif len(precos_float) >= 1:
        produto["preco_varejo"] = min(precos_float)
        produto["preco_atacado"] = min(precos_float)
    else:
        return None
        
    return produto

async def confirmar_localizacao(page, browser, cep, erro_saga):
    """Confirma que o cabeçalho passou a dizer "Entregue pela Loja - <loja> para o CEP <cep>"."""
    esperado = cep_com_hifen(cep)
    confirmou = await esperar_na_pagina(
        page,
        "(c) => /Entregue pela Loja/i.test(document.body.innerText) && document.body.innerText.includes(c)",
        esperado,
        segundos=15,
    )
    if not confirmou:
        detalhe = f" (erro ao informar o CEP: {str(erro_saga)[:80]})" if erro_saga else ""
        await abortar(browser, "Atacadão", f"o cabeçalho do site não passou a mostrar 'Entregue pela Loja ... para o CEP {esperado}'{detalhe}")
    texto = await page.evaluate("() => document.body.innerText")
    achou = re.search(r"Entregue pela Loja\s*-\s*(.+?)\s+para o CEP", texto, re.S)
    print(f"📍 [Atacadão] Localização confirmada: loja {achou.group(1).strip() if achou else '?'}, CEP {esperado}")

async def buscar_no_atacadao(cep_usuario: str, item_usuario: str):
    print(f"🤖 [Atacadão] Iniciando robô invisível para buscar '{item_usuario}'...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            await page.goto("https://www.atacadao.com.br/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000) 
        except Exception as e:
            print(f"⚠️ [Atacadão] Site instável. Abortando. Erro: {e}")
            await browser.close()
            return []

        # --- A SAGA DA LOCALIZAÇÃO ---
        
        print("🍪 [Atacadão] Fechando cookies...")
        try:
            btn_cookies = page.locator("button:has-text('Aceitar todos'), text='Aceitar todos'").first
            await btn_cookies.click(timeout=3000, force=True)
        except: pass

        print("📍 [Atacadão] Clicando em 'Informar Localização'...")
        await page.evaluate('''() => {
            let botoes = document.querySelectorAll('button');
            for(let b of botoes) {
                if(b.innerText && b.innerText.toUpperCase().includes('INFORMAR LOCALIZAÇÃO')) {
                    b.click(); break;
                }
            }
        }''')
        await page.wait_for_timeout(3000)

        # OS PASSOS QUE VOCÊ DESCOBRIU:
        erro_saga = None
        try:
            print("🚚 [Atacadão] Selecionando 'Entrega em Casa'...")
            btn_entrega = page.locator("button:has-text('Entrega em Casa')").first
            await btn_entrega.wait_for(state='visible', timeout=5000)
            await btn_entrega.click(force=True)
            await page.wait_for_timeout(2000)

            print(f"📍 [Atacadão] Digitando o CEP {cep_usuario}...")
            cep_input = page.locator("#location-search").first
            # press_sequentially simula uma pessoa digitando tecla por tecla!
            # Isso evita que o auto-avanço do site quebre.
            await cep_input.press_sequentially(cep_usuario, delay=100)
            await page.wait_for_timeout(3000) # Espera a tela deslizar para o Número

            print("🏠 [Atacadão] Preenchendo Número...")
            num_input = page.locator("input[placeholder*='Ex:']").first
            await num_input.wait_for(state='visible', timeout=5000)
            await num_input.fill("100", force=True) # Número genérico para passar
            
            print("✅ [Atacadão] Confirmando...")
            btn_confirmar = page.locator("button:has-text('Confirmar')").first
            await btn_confirmar.click(force=True)
            await page.wait_for_timeout(5000) # Espera o modal sumir
        except Exception as e:
            erro_saga = e
            print(f"   ⚠️ Falha na saga de localização: {e}")
        # -----------------------------------

        # O robô só segue se o site confirmar que assumiu o CEP; senão os preços seriam de outro lugar
        await confirmar_localizacao(page, browser, cep_usuario, erro_saga)

        # PASSO B: Pesquisar (Agora com o seletor exato da imagem: "procura")
        try:
            print(f"🛒 [Atacadão] Procurando a barra de pesquisa...")
            search_bar = page.locator(
                "input[placeholder*='procura' i]:visible, "
                "input[placeholder*='procur' i]:visible, "
                "input[placeholder*='busc' i]:visible"
            ).first
            
            await search_bar.wait_for(state="visible", timeout=10000)
            await search_bar.click(force=True) 
            await search_bar.fill(item_usuario, force=True) 
            await search_bar.press("Enter")
            
            print(f"✅ [Atacadão] Digitou '{item_usuario}' e apertou Enter! Aguardando os produtos...")
            await page.wait_for_timeout(10000) # Espera a prateleira carregar
        except Exception as e:
            print(f"❌ [Atacadão] Erro ao tentar pesquisar: {e}")

        if not url_mostra_busca(page.url, item_usuario):
            await abortar(browser, "Atacadão", f"a busca por '{item_usuario}' não abriu a página de resultados ({page.url[:90]})", erro=BuscaNaoRealizada)

        # 📸 A Câmera continua ligada caso algo dê errado
        await page.screenshot(path="debug_atacadao_prateleira.png")

        textos_produtos = await page.evaluate('''() => {
            const items =[];
            const cards = document.querySelectorAll("article, [data-testid*='product-card'], div[class*='ProductCard'], div[class*='product-item']");
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

        lista_final_json = []
        for texto in textos_produtos:
            produto = estruturar_produto_atacadao_json(texto)
            if produto:
                lista_final_json.append(produto)

        await exigir_produtos(browser, "Atacadão", lista_final_json)
        await browser.close()
        print(f"✅ [Atacadão] Extração concluída! Encontrados {len(lista_final_json)} itens.")
        return lista_final_json

# --- BLOCO DE TESTE LOCAL ---
if __name__ == "__main__":
    async def teste():
        res = await buscar_no_atacadao("32607600", "Cafe")
        import json
        print(json.dumps(res[:3], indent=4, ensure_ascii=False))
    asyncio.run(teste())
