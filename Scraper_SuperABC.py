import asyncio
import re
from playwright.async_api import async_playwright

def estruturar_produto_regex_json(texto_bruto, supermercado_nome):
    partes = [p.strip() for p in texto_bruto.split('|') if p.strip()]
    nome = partes[0] if partes else "Produto Desconhecido"
    
    # Se o nome for muito curto, não é um produto válido
    if len(nome) < 4:
        return None
        
    # --- A MÁGICA DA TESOURA ---
    # Corta o texto na palavra "Preço por" e guarda só a primeira metade!
    texto_limpo = re.split(r'Preço por', texto_bruto, flags=re.IGNORECASE)[0]
    
    # Caçador de Preços (agora só vai achar o preço da unidade ou o "De/Por")
    precos_encontrados = re.findall(r'R\$\s*(\d+,\d{2})', texto_limpo)
    precos_float = [float(p.replace(',', '.')) for p in precos_encontrados]
    
    if not precos_float:
        return None
        
    # Pega o menor preço (caso tenha promoção "De / Por")
    preco_real = min(precos_float)
    
    return {
        "supermercado": supermercado_nome,
        "nome": nome,
        "preco_varejo": preco_real,
        "preco_atacado": preco_real, # Regex Solutions não usa atacado B2C no padrão
        "quantidade_atacado": 1,
        "texto_original": texto_bruto
    }

async def buscar_na_plataforma_regex(url_mercado: str, nome_mercado: str, item_usuario: str):
    print(f"🤖 [{nome_mercado}] Iniciando robô invisível para buscar '{item_usuario}'...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Blindagem Anti-Queda
        try:
            await page.goto(url_mercado, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)
        except Exception as e:
            print(f"⚠️ [{nome_mercado}] Site instável. Abortando. Erro: {e}")
            await browser.close()
            return []
            
        # Fechar possíveis pop-ups iniciais de loja (Clica no primeiro botão que parecer "Confirmar" ou "Entrar")
        try:
            btn_entrar = page.locator("button:has-text('Entrar'), button:has-text('Confirmar'), button:has-text('Continuar')").first
            await btn_entrar.click(timeout=3000, force=True)
        except: pass

        # PASSO B: Pesquisar
        try:
            search_bar = page.locator(
                "input[type='search']:visible, "
                "input[placeholder*='busc' i]:visible, "
                "input[placeholder*='pesquis' i]:visible, "
                "input[placeholder*='procur' i]:visible"
            ).first
            
            await search_bar.wait_for(state="visible", timeout=10000)
            await search_bar.click(force=True)
            await search_bar.fill(item_usuario, force=True)
            await search_bar.press("Enter")
            await page.wait_for_timeout(8000) # Espera a prateleira carregar
        except Exception as e:
            print(f"❌ [{nome_mercado}] Erro na barra de busca: {e}")

        # PASSO C: Ler a Prateleira (Usando o padrão que você mapeou)
        textos_produtos = await page.evaluate('''() => {
            const items = [];
            const cards = document.querySelectorAll("article, div[class*='product'], div[class*='item'], li");
            cards.forEach(card => {
                const text = card.innerText;
                if (text && text.includes('R$') && text.length < 300) {
                    items.push(text.replace(/\\n/g, ' | ').trim());
                }
            });
            return [...new Set(items)];
        }''')

        lista_final_json = []
        for texto in textos_produtos:
            produto = estruturar_produto_regex_json(texto, nome_mercado)
            if produto:
                lista_final_json.append(produto)

        await browser.close()
        print(f"✅ [{nome_mercado}] Extração concluída! Encontrados {len(lista_final_json)} itens.")
        return lista_final_json

# (Para teste local, caso você queira rodar o arquivo isolado)
if __name__ == "__main__":
    async def teste():
        res = await buscar_na_plataforma_regex("https://superabconline.com.br/", "Super ABC", "Cafe")
        import json
        print(json.dumps(res[:3], indent=4, ensure_ascii=False))
    asyncio.run(teste())
