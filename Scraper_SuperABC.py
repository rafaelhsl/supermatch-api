import asyncio
import re
from playwright.async_api import async_playwright
from robos_comum import exigir_produtos

from busca import sem_acento
from robos_comum import BuscaNaoRealizada, abortar, cidade_do_cep, eh_etiqueta_promocional, url_mostra_busca

def estruturar_produto_regex_json(texto_bruto, supermercado_nome):
    partes = [p.strip() for p in texto_bruto.split('|') if p.strip()]
    nome = next((p for p in partes if not eh_etiqueta_promocional(p)), "Produto Desconhecido")
    
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

async def escolher_unidade(page, browser, mercado, cep):
    """Escolhe a unidade do Super ABC que fica na cidade do CEP.

    O site não localiza unidade por CEP: só filtra por nome ou endereço. Por isso o robô descobre a
    cidade do CEP e escolhe uma unidade dessa cidade. Sem unidade na cidade, aborta.
    """
    info = await asyncio.to_thread(cidade_do_cep, cep)
    if not info:
        await abortar(browser, mercado, f"não consegui descobrir a cidade do CEP {cep}")
    cidade, uf = info
    cidade_norm = sem_acento(cidade)

    try:
        await page.locator("div.trocar-loja").first.click(timeout=8000)  # abre a lista de unidades
        busca = page.locator("input[placeholder*='Buscar por loja' i]").first
        await busca.wait_for(state="visible", timeout=8000)
        await busca.fill(cidade)
        await page.wait_for_timeout(2000)
    except Exception as erro:
        await abortar(browser, mercado, f"não consegui abrir a lista de unidades ({str(erro)[:90]})")

    # Só vale unidade cujo endereço termina em "<cidade> - <UF>": a busca também acha ruas e bairros com o mesmo nome.
    unidades = page.locator("div.loja")
    escolhida = None
    for i in range(await unidades.count()):
        unidade = unidades.nth(i)
        if not await unidade.is_visible():
            continue
        texto = sem_acento(await unidade.inner_text())
        if re.search(rf",\s*{re.escape(cidade_norm)}\s*-\s*{uf.lower()}\b", texto):
            escolhida = unidade
            break
    if escolhida is None:
        await abortar(browser, mercado, f"o Super ABC não tem unidade em {cidade}/{uf}", definitiva=True)

    try:
        await escolhida.locator("button").first.click(timeout=8000)
    except Exception as erro:
        await abortar(browser, mercado, f"não consegui selecionar a unidade de {cidade} ({str(erro)[:90]})")

    # Confirmação: o botão do cabeçalho passa a mostrar a unidade e "<cidade> / <UF>".
    cabecalho = ""
    for _ in range(10):
        await page.wait_for_timeout(1000)
        cabecalho = " ".join((await page.locator("div.trocar-loja").first.inner_text()).split())
        if cidade_norm in sem_acento(cabecalho):
            break
    else:
        await abortar(browser, mercado, f"o cabeçalho do site não passou a mostrar a unidade de {cidade} (mostra: {cabecalho[:60]})")
    print(f"📍 [{mercado}] Unidade confirmada: {cabecalho.strip()}")
    await page.wait_for_timeout(2000)

async def buscar_na_plataforma_regex(url_mercado: str, nome_mercado: str, item_usuario: str, cep_usuario: str = None):
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
            
        # Com CEP, escolhe a unidade da cidade dele. Sem CEP, mantém a unidade padrão do site (Divinópolis).
        if cep_usuario:
            await escolher_unidade(page, browser, nome_mercado, cep_usuario)

        # Fecha um possível pop-up inicial de loja. O botão "Entrar" não entra aqui: ele abre o login.
        try:
            btn_confirmar = page.locator("button:has-text('Confirmar'), button:has-text('Continuar')").first
            await btn_confirmar.click(timeout=3000, force=True)
        except: pass

        # PASSO B: Pesquisar (Otimizado para Angular / Regex Solutions)
        # A página tem dois campos de busca iguais (desktop e celular): só o visível serve.
        # Com vários robôs ao mesmo tempo a busca às vezes não sai da página inicial, então tenta até 3 vezes.
        for tentativa in (1, 2, 3):
            try:
                search_bar = page.locator(
                    "input.input-busca-produto:visible, "
                    "input[placeholder*='O que você procura' i]:visible"
                ).first
                await search_bar.wait_for(state="visible", timeout=10000)
                await search_bar.click(click_count=2)
                await search_bar.fill(item_usuario)
                await search_bar.press("Enter")
                print(f"⏳ [{nome_mercado}] Pesquisa feita! Aguardando a prateleira...")
                for _ in range(10):
                    if url_mostra_busca(page.url, item_usuario):
                        break
                    await page.wait_for_timeout(1000)
                if url_mostra_busca(page.url, item_usuario):
                    break
            except Exception as e:
                print(f"❌ [{nome_mercado}] Erro na barra de busca (tentativa {tentativa}): {e}")
                # TIRA UMA FOTO PARA NÓS VERMOS O QUE ESTÁ BLOQUEANDO A TELA!
                await page.screenshot(path=f"debug_erro_{nome_mercado.replace(' ', '')}.png")

        if not url_mostra_busca(page.url, item_usuario):
            await abortar(browser, nome_mercado, f"a busca por '{item_usuario}' não abriu a página de resultados ({page.url[:90]})", erro=BuscaNaoRealizada)
        await page.wait_for_timeout(8000)  # deixa a prateleira carregar

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

        await exigir_produtos(browser, nome_mercado, lista_final_json, page)
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
