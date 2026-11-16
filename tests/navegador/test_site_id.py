"""Identificador do grupo (id_do_grupo): o produto que mudou de nome de um dia para o outro continua sendo o mesmo item da lista.

Rodar com:  python tests/navegador/test_site_id.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
import time
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

from _comum import URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0
AGORA_MS = int(time.time() * 1000)
H = 3600 * 1000


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


def opcao(mercado, nome, preco, termo="manteiga", ean=None):
    o = {"supermercado": mercado, "nome": nome, "preco_varejo": preco, "preco_atacado": preco, "quantidade_atacado": 1, "atualizado_em": "2026-11-12T09:30:00+00:00",
         "id": f"{mercado}-{nome}-{preco}", "termo": termo}
    if ean:
        o["ean"] = ean
    return o


def grupo(base, ean, idg, *opcoes):
    g = {"produto_base": base, "vencedor_preco_baixo": opcoes[0]["supermercado"], "opcoes_de_compra": list(opcoes)}
    if ean:
        g["ean"] = ean
    if idg:
        g["id_do_grupo"] = idg
    return g


E = "7891000100103"


def resposta(termo):
    base = {"status": "sucesso", "cep": "x", "uf": "MG", "item": termo, "mercados_consultados": ["Atacadao", "Supernosso"], "equivalencia_familias": ["manteiga"]}
    if termo == "manteiga":
        g = [grupo("Manteiga Président Com Sal 200 g (nome de hoje)", E, E.lstrip("0"), opcao("Atacadao", "Manteiga Président Com Sal 200 g", 9.5, ean=E), opcao("Supernosso", "Manteiga Président c/ sal 200g", 10.2, ean=E)),
             grupo("Manteiga Aviação sem sal 200g", "7891000100200", "7891000100200", opcao("Atacadao", "Manteiga Aviação sem sal 200g", 11.0, ean="7891000100200"))]
    elif termo == "refrigerante":
        g = [grupo("Refrigerante Mate Couro 200ml", "7896478801361", "7896478801361|200.0ml", opcao("Atacadao", "Refrigerante Mate Couro 200ml", 3.0, "refrigerante", "7896478801361")),
             grupo("Refrigerante Mate Couro 1L", "7896478801361", "7896478801361|1000.0ml", opcao("Atacadao", "Refrigerante Mate Couro 1L", 8.0, "refrigerante", "7896478801361"))]
    else:
        g = []
    return {**base, "carrinho_comparativo": g}


def item_guardado(base, ean, preco, qtd, idg=None, termo="manteiga", em=None):
    g = {"produto_base": base, "opcoes_de_compra": [opcao("Atacadao", base, preco, termo, ean)]}
    if ean:
        g["ean"] = ean
    if idg:
        g["id_do_grupo"] = idg
    return {"grupo": g, "qtd": qtd, "em": em if em is not None else AGORA_MS - 6 * H}


async def abrir(nav, vp, mobile, lista):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))

    async def api(rota):
        u = urlparse(rota.request.url)
        if u.path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", body="{}")
        termo = parse_qs(u.query).get("item", [""])[0]
        await rota.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps(resposta(termo)))

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }",
                      {"sm_cep": json.dumps("30130010"), "sm_cidade": json.dumps("Belo Horizonte/MG"), "sm_lista": json.dumps(lista)})
    await pg.reload()
    return ctx, pg


async def esperar_atualizacao(pg):
    await pg.wait_for_function("() => /Preços de/.test(document.querySelector('#cupom .meta')?.innerText || '') && !/Atualizando/.test(document.querySelector('#cupom .meta').innerText)", timeout=15000)
    await pg.wait_for_timeout(300)


async def guardada(pg):
    return json.loads(await pg.evaluate("localStorage.getItem('sm_lista')"))


async def buscar(pg, termo):
    await pg.fill("#campoBusca", termo)
    await pg.press("#campoBusca", "Enter")
    await pg.wait_for_timeout(800)


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 800}, True), ("desktop", {"width": 1280, "height": 900}, False)):
            print(f"\n===== {rotulo} =====")
            # --- 1. item guardado pelo NOME de ontem: a atualização lhe dá o id, e a busca de hoje o reconhece como "na lista"
            ctx, pg = await abrir(nav, vp, mobile, [item_guardado("Manteiga Président Com sal 200g", E, 9.0, 1)])
            await esperar_atualizacao(pg)
            lista = await guardada(pg)
            confere(len(lista) == 1 and lista[0]["grupo"]["id_do_grupo"] == E.lstrip("0"), f"o item guardado ganha o id_do_grupo na atualização: {lista[0]['grupo'].get('id_do_grupo')}")
            confere(lista[0]["grupo"]["produto_base"] == "Manteiga Président Com sal 200g", "o nome que a pessoa viu na lista não muda")
            await buscar(pg, "manteiga")
            cartoes = await pg.evaluate("() => [...document.querySelectorAll('.produto')].map(c => [c.querySelector('h3').innerText.trim(), !!c.querySelector('.passos'), !!c.querySelector('[data-add]')])")
            confere(len(cartoes) == 2, f"a busca de hoje traz 2 cartões: {cartoes}")
            confere(cartoes[0][1] is True and cartoes[0][2] is False, f"o produto que mudou de nome aparece como já na lista (com os botões de quantidade): {cartoes[0]}")
            confere(cartoes[1][2] is True and cartoes[1][1] is False, "o outro produto continua com «Adicionar à lista»")
            await pg.locator(".produto").first.locator("[data-mais]").click(); await pg.wait_for_timeout(300)
            lista = await guardada(pg)
            confere(len(lista) == 1 and lista[0]["qtd"] == 2, f"aumentar a quantidade não cria um segundo item: {len(lista)} item(ns), qtd {lista[0]['qtd']}")
            await pg.locator(".produto").nth(1).locator("[data-add]").click(); await pg.wait_for_timeout(300)
            lista = await guardada(pg)
            confere(len(lista) == 2 and lista[1]["grupo"]["id_do_grupo"] == "7891000100200", "outro produto entra como item novo, com id")
            await ctx.close()

            # --- 2. duplicados do esquema antigo (mesmo produto, nomes diferentes) viram um item, somando as quantidades
            ctx, pg = await abrir(nav, vp, mobile, [item_guardado("Manteiga Président Com sal 200g", E, 9.0, 1), item_guardado("Manteiga Président c/ sal 200 g", E, 9.1, 2)])
            await esperar_atualizacao(pg)
            lista = await guardada(pg)
            confere(len(lista) == 1 and lista[0]["qtd"] == 3, f"os dois itens do mesmo produto viram um, com a soma das quantidades: {[(i['grupo']['produto_base'], i['qtd']) for i in lista]}")
            confere("2 itens" not in (await pg.locator("#cupom .meta").inner_text()) and "1 item," in (await pg.locator("#cupom .meta").inner_text()), "o cupom mostra 1 item")
            await ctx.close()

            # --- 3. dois grupos dividem o código de barras: o id (com o tamanho) escolhe o certo; sem id, o nome decide; sem nome igual, não chuta
            ctx, pg = await abrir(nav, vp, mobile, [
                item_guardado("Refrigerante Mate Couro 1L", "7896478801361", 7.0, 1, idg="7896478801361|1000.0ml", termo="refrigerante"),
                item_guardado("Refrigerante Mate Couro 200ml", "7896478801361", 2.5, 1, termo="refrigerante"),
            ])
            await esperar_atualizacao(pg)
            lista = {i["grupo"]["produto_base"]: i["grupo"]["opcoes_de_compra"][0]["preco_varejo"] for i in await guardada(pg)}
            confere(lista == {"Refrigerante Mate Couro 1L": 8.0, "Refrigerante Mate Couro 200ml": 3.0}, f"os dois tamanhos do mesmo código ficam cada um com o seu preço: {lista}")
            ids = [i["grupo"].get("id_do_grupo") for i in await guardada(pg)]
            confere(ids == ["7896478801361|1000.0ml", "7896478801361|200.0ml"], f"e o item sem id ganha o do tamanho certo: {ids}")
            await ctx.close()

            ctx, pg = await abrir(nav, vp, mobile, [item_guardado("Refrigerante Mate Couro (nome de ontem)", "7896478801361", 7.0, 1, termo="refrigerante")])
            await esperar_atualizacao(pg)
            lista = await guardada(pg)
            confere(lista[0]["grupo"]["opcoes_de_compra"][0]["preco_varejo"] == 7.0 and "id_do_grupo" not in lista[0]["grupo"], "dois grupos com o mesmo código e nenhum com o nome do item: não escolhe no chute, mantém o preço")
            confere("1 item sem preço novo" in await pg.locator("#cupom .meta").inner_text(), "e o cupom avisa")
            await ctx.close()
        await nav.close()


asyncio.run(rodar())
print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
for f in falhas:
    print("  -", f)
sys.exit(1 if falhas else 0)
