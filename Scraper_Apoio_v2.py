import re
from urllib.parse import quote
from playwright.async_api import async_playwright
from robos_comum import exigir_produtos

from robos_comum import (BuscaNaoRealizada, abortar, cep_com_hifen, eh_etiqueta_promocional,
                         esperar_na_pagina, esperar_recarregamento, url_mostra_busca)

def estruturar_produto_apoio_json(texto_bruto):
    partes =[p.strip() for p in texto_bruto.split('|') if p.strip()]
    nome = "Produto Desconhecido"
    for p in partes:
        p_minusculo = p.lower()
        # "%" só indica etiqueta de desconto quando o texto é curto ("20% OFF"); nomes como "100% Arábica" têm "%"
        if (len(p) < 25 and "%" in p_minusculo) or p_minusculo in["oferta", "promoção", "termina em breve", "ver tudo", "unidade", "peso variável"]:
            continue
        if eh_etiqueta_promocional(p):
            continue
        if "r$" in p_minusculo:
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

async def definir_localizacao(page, browser, cep, escolher_entrega=True):
    """Informa o CEP no painel do carrinho e confirma que o site atende a região.

    O ícone do carrinho abre o painel "Informe seu CEP" sem adicionar produto algum. Se o site não
    atender o CEP, o painel não mostra "Atendemos sua região" e o robô aborta.
    """
    esperado = cep_com_hifen(cep)
    try:
        # Clica por JavaScript: o clique do mouse falhava de vez em quando com "fora da tela".
        await page.evaluate("() => document.querySelector('a.btn-top-cart').click()")
        campo = page.locator("#cepInput, input[name='cep']").first
        await campo.wait_for(state="visible", timeout=8000)
        await campo.fill(cep, force=True)
    except Exception as erro:
        await abortar(browser, "Apoio", f"não consegui informar o CEP no site ({str(erro)[:90]})")

    # O campo tem máscara e formata o CEP (32607-600) com um pequeno atraso. Se o botão for clicado antes,
    # o clique é ignorado e o painel fica parado.
    await esperar_na_pagina(
        page,
        "() => /[0-9]{5}-[0-9]{3}/.test((document.querySelector('#cepInput, input[name=cep]') || {}).value || '')",
        segundos=5,
    )

    # O quadro aparece primeiro com "00000-000" e só depois mostra o CEP digitado.
    for tentativa in (1, 2, 3):
        try:
            await page.evaluate(
                "() => [...document.querySelectorAll('button')]"
                ".find(b => b.offsetParent && /^buscar$/i.test(b.innerText.trim())).click()"
            )
        except Exception:
            pass  # o painel já pode ter sido fechado pela própria confirmação
        confirmou = await esperar_na_pagina(
            page,
            "(c) => { const q = document.querySelector('.cart__body--cep-validado--box');"
            " return !!q && q.innerText.includes(c) && /atendemos sua regi/i.test(q.innerText); }",
            esperado,
            segundos=10,
        )
        if confirmou:
            break
    if not confirmou:
        await abortar(browser, "Apoio", f"o site não confirmou 'Atendemos sua região' para o CEP {esperado} (não atende ou não respondeu)")

    if not escolher_entrega:
        # Escolher "Quero receber" faz o site reavaliar a região do endereço e, nos períodos em que a entrega
        # dali está indisponível, jogar a sessão no canal de vendas 1 (todo produto "indisponível"), desfazendo
        # até o ?sc= da URL. Para ler preços isso não é preciso: o canal já define preço e estoque.
        print(f"📍 [Apoio] Localização confirmada: atende o CEP {esperado} (sem escolher a entrega)")
        return

    try:  # "Quero receber": entrega em casa
        await page.evaluate("() => document.querySelector(\"li[data-type='click-delivery']\").click()")
    except Exception as erro:
        await abortar(browser, "Apoio", f"o CEP foi aceito, mas não consegui escolher a entrega em casa ({str(erro)[:80]})")
    print(f"📍 [Apoio] Localização confirmada: atende o CEP {esperado}")
    await esperar_recarregamento(page, segundos=6)

async def abrir_busca_no_canal(page, browser, item, canal):
    """Abre a busca do Apoio já no canal de vendas informado (parâmetro `sc` da URL).

    O Apoio vende por canal de vendas. No canal regional do CEP (15 para Betim) os produtos têm preço e
    estoque; no canal 1, o padrão, todos aparecem como "Item indisponível" (estoque 0). Depois do CEP o site
    deveria mover a sessão para o canal regional, mas nos servidores do GitHub isso falha com frequência.
    """
    url = f"https://www.apoioentrega.com/{quote(item)}?sc={canal}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as erro:
        await abortar(browser, "Apoio", f"não consegui abrir a busca no canal de vendas {canal} ({str(erro)[:80]})", erro=BuscaNaoRealizada)

    # O canal do CARRINHO é um sinal instável e só informativo: logo depois de abrir a página ele marca o canal
    # antigo (1), passa para o da URL uns 3 s depois e, em alguns períodos, nem chega em 15 s, enquanto a
    # prateleira já mostra os preços. Abortar por ele derrubou duas cargas reais. Quem decide é a prateleira:
    # no canal 1 todo produto aparece "indisponível" (sem preço), então preço na tela prova que o canal é o certo,
    # e sem preço a busca falha em exigir_produtos (e a carga repete).
    chegou = await esperar_na_pagina(
        page,
        "async (c) => { try { const o = await (await fetch('/api/checkout/pub/orderForm', {credentials: 'same-origin'})).json();"
        " return String(o.salesChannel) === String(c); } catch (e) { return false; } }",
        str(canal),
        segundos=6,
    )
    cookie = await page.evaluate("() => (document.cookie.match(/VTEXSC=[^;]*/) || ['sem VTEXSC'])[0]")
    print(f"🛒 [Apoio] Busca aberta com ?sc={canal} (carrinho {'já no canal' if chegou else 'ainda no canal antigo'}; {cookie})")
    await page.wait_for_timeout(3000)


# --- MUDANÇA AQUI: Agora é uma função que recebe CEP e ITEM ---
async def buscar_no_apoio(cep_usuario: str, item_usuario: str, canal_de_vendas: str = None):
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

        # PASSO A: Definir a localização e só seguir se o site confirmar o CEP
        await definir_localizacao(page, browser, cep_usuario, escolher_entrega=not canal_de_vendas)

        if canal_de_vendas:
            # O site às vezes deixa a sessão presa no canal de vendas 1, onde todo produto aparece como
            # "Item indisponível". Abrir a busca já no canal certo evita isso.
            await abrir_busca_no_canal(page, browser, item_usuario, canal_de_vendas)
        else:
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

        # Sem a página de resultados, o que está na tela não é a busca
        if not url_mostra_busca(page.url, item_usuario):
            await abortar(browser, "Apoio", f"a busca por '{item_usuario}' não abriu a página de resultados ({page.url[:90]})", erro=BuscaNaoRealizada)

        # Nos servidores do GitHub a prateleira demora mais que os 7 s fixos: 4 de 11 buscas voltaram com 0 itens.
        # Espera os produtos aparecerem de verdade (até 20 s) e deixa o resto da lista terminar de carregar.
        await esperar_na_pagina(
            page,
            '''() => [...document.querySelectorAll("article, section.vtex-product-summary-2-x-container, div[class*='shelf-item'], div[class*='box-item'], li[layout]")]
                      .some(card => card.innerText && card.innerText.includes("R$"))''',
            segundos=20,
        )
        await page.wait_for_timeout(2000)

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

        await exigir_produtos(browser, "Apoio", lista_final_json, page)
        await browser.close()
        print(f"✅ [Apoio] Extração concluída! Encontrados {len(lista_final_json)} itens.")
        
        # Em vez de imprimir (print), a função DEVOLVE os dados para a API
        return lista_final_json
