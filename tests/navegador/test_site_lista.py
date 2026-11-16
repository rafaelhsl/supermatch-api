"""Lista de compras que busca os precos de hoje ao abrir a pagina: teste de ponta a ponta no navegador, com uma API falsa.

Rodar com:  python tests/navegador/test_site_lista.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
import time
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

from _comum import SAIDA, URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0
AGORA_MS = int(time.time() * 1000)
H = 3600 * 1000
ONTEM = "2026-11-09T12:00:00+00:00"
HOJE = "2026-11-10T09:30:00+00:00"


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


def opcao(mercado, nome, preco, atualizado=ONTEM, termo=None, ean=None, chave=None, rotulo=None):
    o = {"supermercado": mercado, "nome": nome, "preco_varejo": preco, "preco_atacado": preco, "quantidade_atacado": 1, "atualizado_em": atualizado, "id": f"{mercado}-{nome}-{preco}"}
    if termo:
        o["termo"] = termo
    if ean:
        o["ean"] = ean
    if chave:
        o["chave_equivalencia"], o["rotulo_equivalencia"] = chave, rotulo
    return o


def grupo(base, ean, *opcoes):
    g = {"produto_base": base, "vencedor_preco_baixo": opcoes[0]["supermercado"], "opcoes_de_compra": list(opcoes)}
    if ean:
        g["ean"] = ean
    return g


SAL = ("sal|refinado|1000g", "Sal refinado, 1 kg")


def lista_guardada(com_velhos=True):
    """O que o navegador já tinha salvo: preços de ontem."""
    velho = AGORA_MS - 5 * H if com_velhos else AGORA_MS
    return [
        {"grupo": grupo("Arroz Tio João Tipo 1 5kg", "7893500000001", opcao("Atacadao", "Arroz Tio João 5kg", 20.0, termo="arroz", ean="7893500000001")), "qtd": 2, "em": velho},
        {"grupo": grupo("Café Pilão 500g", None, opcao("Atacadao", "Café Pilão 500g", 20.0)), "qtd": 1},     # item de versão antiga: sem termo e sem hora
        {"grupo": {"produto_base": "Sal refinado, 1 kg", "equivalente": True, "chave": SAL[0], "opcoes_de_compra": [opcao("Atacadao", "Sal Cisne 1kg", 3.0, termo="sal", chave=SAL[0], rotulo=SAL[1])]}, "qtd": 3, "em": velho},
        {"grupo": grupo("Feijão Carioca Camil 1kg", "7891", opcao("Atacadao", "Feijão Carioca Camil 1kg", 10.0, termo="feijão", ean="7891")), "qtd": 1, "em": AGORA_MS},    # em dia: não consulta
        {"grupo": grupo("Macarrão Adria 500g", "7892", opcao("Atacadao", "Macarrão Adria 500g", 5.0, termo="macarrão", ean="7892")), "qtd": 1, "em": velho},                    # sumiu do catálogo
    ]


def resposta(termo, cenario):
    base = {"status": "sucesso", "cep": "x", "uf": "MG", "item": termo, "mercados_consultados": ["Atacadao"], "equivalencia_familias": ["sal", "arroz"]}
    if termo == "arroz":
        g = [grupo("Arroz Tio João Branco 5kg (nome de hoje)", "07893500000001", opcao("Atacadao", "Arroz Tio João 5kg", 18.5, HOJE, "arroz", "7893500000001"), opcao("Supernosso", "Arroz Tio João 5kg", 19.9, HOJE, "arroz"))]
    elif termo == "cafe":
        g = [grupo("Café Pilão 500g", None, opcao("Atacadao", "Café Pilão 500g", 19.0, HOJE, "café"))]
    elif termo == "sal":
        g = [{"produto_base": "x", "opcoes_de_compra": [opcao("Atacadao", "Sal Refinado Lebre 1kg", 2.4, HOJE, "sal", chave=SAL[0], rotulo=SAL[1])]}]
    elif termo == "macarrão":
        g = [grupo("Macarrão Renata 500g", "7000", opcao("Atacadao", "Macarrão Renata 500g", 4.0, HOJE, "macarrão", "7000"))]      # o Adria não aparece mais
    else:
        g = []
    return {**base, "carrinho_comparativo": g}


async def abrir(nav, vp, mobile, lista, cenario="ok", atraso_s=0.0):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pedidos = []
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)

    async def api(rota):
        u = urlparse(rota.request.url)
        if u.path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", body="{}")
        termo = parse_qs(u.query).get("item", [""])[0]
        pedidos.append(termo)
        if atraso_s:
            await asyncio.sleep(atraso_s)
        if cenario == "fora":
            return await rota.fulfill(status=503, content_type="application/json", headers={"access-control-allow-origin": "*"}, body="{}")
        await rota.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps(resposta(termo, cenario)))

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }",
                      {"sm_cep": json.dumps("30130010"), "sm_cidade": json.dumps("Belo Horizonte/MG"), "sm_lista": json.dumps(lista)})
    return ctx, pg, pedidos


async def meta(pg):
    return " ".join((await pg.locator("#cupom .meta").inner_text()).split())


async def guardada(pg):
    return json.loads(await pg.evaluate("localStorage.getItem('sm_lista')"))


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 800}, True), ("desktop", {"width": 1280, "height": 900}, False)):
            print(f"\n===== {rotulo} =====")
            # --- 1. itens velhos são consultados; o em dia não; cada termo uma vez só
            ctx, pg, pedidos = await abrir(nav, vp, mobile, lista_guardada())
            await pg.reload()
            await pg.wait_for_function("() => /Preços de/.test(document.querySelector('#cupom .meta')?.innerText || '') && !/Atualizando/.test(document.querySelector('#cupom .meta').innerText)", timeout=15000)
            await pg.wait_for_timeout(300)
            confere(sorted(pedidos) == ["arroz", "cafe", "macarrão", "sal"], f"consulta só os termos dos itens velhos, uma vez cada (feijão está em dia): {sorted(pedidos)}")
            lista = await guardada(pg)
            por_nome = {i["grupo"]["produto_base"]: i for i in lista}
            confere(set(por_nome) == {"Arroz Tio João Tipo 1 5kg", "Café Pilão 500g", "Sal refinado, 1 kg", "Feijão Carioca Camil 1kg", "Macarrão Adria 500g"}, f"os itens e os nomes continuam os mesmos (o nome de hoje do arroz não troca o da lista): {sorted(por_nome)}")
            confere([o["preco_varejo"] for o in por_nome["Arroz Tio João Tipo 1 5kg"]["grupo"]["opcoes_de_compra"]] == [18.5, 19.9], "arroz: preços de hoje, achado pelo código de barras")
            confere(por_nome["Arroz Tio João Tipo 1 5kg"]["qtd"] == 2 and por_nome["Sal refinado, 1 kg"]["qtd"] == 3, "as quantidades não mudam")
            confere(por_nome["Café Pilão 500g"]["grupo"]["opcoes_de_compra"][0]["preco_varejo"] == 19.0 and por_nome["Café Pilão 500g"]["grupo"]["opcoes_de_compra"][0].get("termo") == "café", "item antigo (sem termo nem hora): achado pela primeira palavra e já ganha o termo certo")
            confere(por_nome["Sal refinado, 1 kg"]["grupo"]["opcoes_de_compra"][0]["preco_varejo"] == 2.4 and por_nome["Sal refinado, 1 kg"]["grupo"]["equivalente"] is True, "sal (equivalente): preço de hoje, achado pela chave")
            confere(por_nome["Feijão Carioca Camil 1kg"]["grupo"]["opcoes_de_compra"][0]["preco_varejo"] == 10.0, "item em dia: não foi tocado")
            confere(por_nome["Macarrão Adria 500g"]["grupo"]["opcoes_de_compra"][0]["preco_varejo"] == 5.0, "produto que sumiu do catálogo: fica o último preço")
            confere(all(i.get("em", 0) > AGORA_MS - 5000 for n, i in por_nome.items() if n != "Macarrão Adria 500g"), "os itens atualizados ganham a hora nova")
            m = await meta(pg)
            confere("1 item sem preço novo: ficou o último que a lista tinha" in m, f"o cupom avisa do item que ficou sem preço novo: «{m}»")
            confere("Preços de 09/11" in m or "Preços de 10/11" in m, f"a data do cupom é a do preço mais antigo: «{m}»")
            await pg.screenshot(path=str(SAIDA / f"lista-{rotulo}-1-atualizada.png"))

            # --- 2. voltando à página logo depois: nada para consultar
            antes = len(pedidos)
            await pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            await pg.wait_for_timeout(500)
            confere(len(pedidos) == antes + 1 and pedidos[-1] == "macarrão", f"ao voltar à página só o item que ainda está velho (o que ficou sem preço novo) é consultado de novo: {pedidos[antes:]}")
            await ctx.close()

            # --- 3. tudo em dia: nenhuma consulta e nenhum aviso
            ctx, pg, pedidos = await abrir(nav, vp, mobile, lista_guardada(com_velhos=False)[3:4])
            await pg.reload(); await pg.wait_for_timeout(900)
            confere(pedidos == [], f"lista em dia: nenhuma consulta: {pedidos}")
            confere("sem preço novo" not in await meta(pg) and "Atualizando" not in await meta(pg), "lista em dia: nenhum aviso")
            await ctx.close()

            # --- 4. API fora do ar: a lista fica como estava e o cupom avisa
            ctx, pg, pedidos = await abrir(nav, vp, mobile, lista_guardada(), cenario="fora")
            await pg.reload()
            await pg.wait_for_function("() => /Não deu para atualizar/.test(document.querySelector('#cupom .meta')?.innerText || '')", timeout=15000)
            lista = await guardada(pg)
            confere(len(lista) == 5 and lista[0]["grupo"]["opcoes_de_compra"][0]["preco_varejo"] == 20.0 and lista[0]["qtd"] == 2, "API fora do ar: a lista continua com os preços e as quantidades de antes")
            confere("sem preço novo" not in await meta(pg), "API fora do ar: o aviso é um só, o de falha")
            await ctx.close()

            # --- 5. enquanto espera, o cupom diz que está atualizando; e dá para mexer na lista
            ctx, pg, pedidos = await abrir(nav, vp, mobile, lista_guardada(), atraso_s=1.2)
            await pg.reload()
            await pg.wait_for_function("() => /Atualizando os preços/.test(document.querySelector('#cupom .meta')?.innerText || '')", timeout=8000)
            confere(True, "enquanto consulta: «Atualizando os preços…»")
            await pg.screenshot(path=str(SAIDA / f"lista-{rotulo}-2-atualizando.png"))
            await pg.locator("[data-lmais]").first.click()
            await pg.wait_for_function("() => !/Atualizando/.test(document.querySelector('#cupom .meta').innerText)", timeout=15000)
            lista = await guardada(pg)
            primeiro = lista[0]
            confere(primeiro["qtd"] == 3 and primeiro["grupo"]["opcoes_de_compra"][0]["preco_varejo"] == 18.5, f"a quantidade mudada durante a consulta é mantida e o preço novo entra: qtd={primeiro['qtd']}")
            await ctx.close()

            # --- 6. limpar a lista zera o aviso
            ctx, pg, pedidos = await abrir(nav, vp, mobile, lista_guardada())
            await pg.reload()
            await pg.wait_for_function("() => /sem preço novo/.test(document.querySelector('#cupom .meta')?.innerText || '')", timeout=15000)
            await pg.click("#limpar"); await pg.wait_for_timeout(300)
            confere("Lista vazia" in await pg.locator("#cupom").inner_text(), "lista limpa mostra o cupom vazio")
            confere(await pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "sem rolagem horizontal")
            await ctx.close()
        await nav.close()


asyncio.run(rodar())
print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
for f in falhas:
    print("  -", f)
sys.exit(1 if falhas else 0)
