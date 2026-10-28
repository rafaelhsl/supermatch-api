import asyncio
import re
from playwright.async_api import async_playwright
from robos_comum import exigir_produtos

from robos_comum import (BuscaNaoRealizada, abortar, cep_com_ponto_e_hifen, eh_etiqueta_promocional,
                         esperar_na_pagina, esperar_recarregamento, url_mostra_busca)

def estruturar_produto_supernosso_json(texto_bruto):
    partes = [p.strip() for p in texto_bruto.split('|') if p.strip()]

    # 1. Encontrar o nome real (pulando lixo da VTEX IO)
    nome = "Produto Desconhecido"
    for p in partes:
        p_lower = p.lower()
        # Ignora tags promocionais ("Leve 4 Pague 3"), preços quebrados e botões
        if "%" in p_lower or "patrocinado" in p_lower or "de:" in p_lower or "por:" in p_lower or "comprar" in p_lower or "adicionar" in p_lower:
            continue
        if eh_etiqueta_promocional(p) or p_lower in ("lista", "listas"):
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

async def definir_localizacao(page, browser, cep):
    """Informa o CEP, escolhe o horário da entrega e confirma que o cabeçalho passou a mostrar o CEP.

    Se o site não atender o CEP, ou se o CEP não for assumido, aborta com LocalizacaoNaoConfirmada.
    """
    try:
        await page.wait_for_load_state("load", timeout=15000)
    except Exception:
        pass  # alguns rastreadores do site nunca terminam de carregar: segue mesmo assim

    # O painel de CEP abre pelo cabeçalho. Clicar em "Comprar" também abriria, mas adicionaria um produto.
    # Com vários robôs ao mesmo tempo a página demora a ficar interativa e o primeiro clique pode se perder.
    campo = page.locator("input[name='cep']:visible").first
    for tentativa in (1, 2, 3):
        try:
            await page.get_by_text("qual a forma de entrega?", exact=False).first.click(timeout=20000)
            await campo.wait_for(state="visible", timeout=8000)
            break
        except Exception as erro:
            if tentativa == 3:
                await abortar(browser, "Supernosso", f"não consegui abrir o painel de CEP do site ({str(erro)[:90]})")
    try:
        await campo.click()
        # Digita tecla por tecla: o campo tem máscara e ignora o preenchimento direto.
        await campo.press_sequentially(cep, delay=70)
        await page.locator("form:has(input[name='cep']:visible) button[type='submit']").first.click(force=True)
    except Exception as erro:
        await abortar(browser, "Supernosso", f"não consegui informar o CEP no site ({str(erro)[:90]})")

    # O site responde de dois jeitos: oferece horários de entrega ou diz que não atende a região.
    horario = page.get_by_text(re.compile(r"entre \d{1,2}:\d{2} e \d{1,2}:\d{2}")).first
    nao_atende = page.get_by_text("não atendemos a sua região", exact=False).first
    botao_enviar = page.locator("form:has(input[name='cep']:visible) button[type='submit']").first
    for tentativa in (1, 2):
        try:
            await horario.or_(nao_atende).wait_for(state="visible", timeout=15000)
            break
        except Exception:
            if tentativa == 2:
                await abortar(browser, "Supernosso", "o site não respondeu ao CEP informado")
            await botao_enviar.click(force=True)  # o site às vezes ignora o primeiro envio: tenta de novo
    if await nao_atende.is_visible():
        await abortar(browser, "Supernosso", "o site informa que não atende a região deste CEP", definitiva=True)

    await horario.click(force=True)  # escolhe a entrega agendada: existe em BH e na região metropolitana

    # Confirmação: depois de escolher a entrega, o site recarrega e o cabeçalho passa a dizer "entrega no cep 30.130-010".
    esperado = cep_com_ponto_e_hifen(cep)
    confirmou = await esperar_na_pagina(
        page,
        "(c) => /entrega no cep/i.test(document.body.innerText) && document.body.innerText.includes(c)",
        esperado,
        segundos=20,
    )
    if not confirmou:
        await abortar(browser, "Supernosso", f"o cabeçalho do site não passou a mostrar o CEP {esperado}")
    print(f"📍 [Supernosso] Localização confirmada: entrega no CEP {esperado}")

    # Logo depois de confirmar, o site recarrega a página: a busca só pode começar depois disso.
    await esperar_recarregamento(page)

async def buscar_no_supernosso(cep_usuario: str, item_usuario: str):
    print(f"🤖 [Supernosso] Iniciando robô invisível para buscar '{item_usuario}' no CEP {cep_usuario}...")
    
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

        # PASSO A: Definir a localização e só seguir se o site confirmar o CEP
        await definir_localizacao(page, browser, cep_usuario)

        # PASSO B: Pesquisar o Produto (COM SEU NOVO CÓDIGO)
        try:
            # Usando o placeholder exato que você descobriu!
            search_bar = page.locator("input[placeholder*='procure' i]:visible").first
            await search_bar.wait_for(state="visible", timeout=5000)
            await search_bar.click(force=True) 
            await search_bar.fill(item_usuario, force=True) 
            await search_bar.press("Enter")
            # Depois de o site recarregar, o Enter às vezes não abre os resultados: confere e, se preciso, clica na lupa
            for _ in range(6):
                if url_mostra_busca(page.url, item_usuario):
                    break
                await page.wait_for_timeout(1000)
            else:
                await page.get_by_role("button", name=re.compile("buscar produtos", re.I)).first.click(force=True)
            await page.wait_for_timeout(7000)
        except Exception as e:
            print(f"❌ [Supernosso] Erro na busca: {e}")

        # Sem a página de resultados, o que está na tela são vitrines da home, não a busca
        if not url_mostra_busca(page.url, item_usuario):
            await abortar(browser, "Supernosso", f"a busca por '{item_usuario}' não abriu a página de resultados ({page.url[:90]})", erro=BuscaNaoRealizada)

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

        await exigir_produtos(browser, "Supernosso", lista_final_json)
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