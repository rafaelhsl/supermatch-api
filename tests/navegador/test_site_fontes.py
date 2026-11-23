"""Fontes do site no navegador: as três famílias carregam dos arquivos daqui (site/fonts/), cada arquivo é baixado uma vez só, nenhum pedido
sai para o Google e o site continua com as suas letras mesmo que o Google esteja fora do ar ou bloqueado.

Rodar com:  python tests/navegador/test_site_fontes.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from _comum import SAIDA, URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


async def abrir(nav, vp, mobile, bloquear_o_google):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    visto = {"google": [], "fontes": [], "avisos": []}
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: (visto["avisos"].append(m.text) if m.type == "warning" else falhas.append(f"console.error: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None))
    pg.on("request", lambda r: (visto["google"].append(r.url) if any(h in r.url for h in ("googleapis", "gstatic")) else None, visto["fontes"].append(r.url) if "/fonts/" in r.url and r.url.endswith(".woff2") else None))

    async def api(rota):
        cab = {"access-control-allow-origin": "*"}
        corpo = "{}" if urlparse(rota.request.url).path.endswith("/saude") else json.dumps({"status": "sucesso", "carrinho_comparativo": []})
        await rota.fulfill(status=200, content_type="application/json", headers=cab, body=corpo)

    await pg.route("https://supermatch-api.onrender.com/**", api)
    if bloquear_o_google:
        await pg.route(lambda u: any(h in u for h in ("googleapis", "gstatic")), lambda rota: rota.abort())
    await pg.goto(URL)
    await pg.evaluate("document.fonts.ready")
    await pg.wait_for_timeout(1500)
    return ctx, pg, visto


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 800}, True), ("celular-estreito", {"width": 320, "height": 700}, True), ("desktop", {"width": 1280, "height": 900}, False)):
            print(f"\n===== {rotulo} =====")
            # Com o Google BLOQUEADO: se o site dependesse dele, as letras não carregariam (e o teste mostra isso)
            ctx, pg, visto = await abrir(nav, vp, mobile, bloquear_o_google=True)
            confere(visto["google"] == [], f"nenhum pedido ao Google (nem tentativa, nem bloqueado): {visto['google']}")
            carregadas = await pg.evaluate("() => [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family.replace(/\"/g, '') + ' ' + f.weight).sort()")
            familias = sorted({c.rsplit(' ', 1)[0] for c in carregadas})
            confere(familias == ["Hanken Grotesk", "Martian Mono", "Unbounded"], f"as três famílias carregaram, com o Google bloqueado: {carregadas}")
            confere(await pg.evaluate("() => document.fonts.check('800 20px Unbounded') && document.fonts.check('400 16px \"Hanken Grotesk\"') && document.fonts.check('600 12px \"Martian Mono\"')"), "document.fonts.check confirma as três")
            confere(len(visto["fontes"]) == 3 and len({u.rsplit('/', 1)[-1] for u in visto["fontes"]}) == 3, f"cada arquivo de fonte é baixado uma vez só (o preload não duplica): {[u.rsplit('/', 1)[-1] for u in visto['fontes']]}")
            confere(not [a for a in visto["avisos"] if "preload" in a.lower()], f"nenhum aviso de preload não usado: {[a for a in visto['avisos'] if 'preload' in a.lower()]}")
            # o texto da primeira tela usa mesmo as fontes (e não a do sistema)
            usadas = await pg.evaluate("""() => { const f = (sel) => getComputedStyle(document.querySelector(sel)).fontFamily.split(',')[0].replace(/"/g, '').trim();
                return { titulo: f('h1'), texto: f('body'), mono: f('#cupom .meta') }; }""")
            confere(usadas["titulo"] == "Unbounded" and usadas["texto"] == "Hanken Grotesk", f"o título é Unbounded e o texto é Hanken Grotesk: {usadas}")
            larg = await pg.evaluate("""() => { const el = document.querySelector('h1'); const r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect().width; }""")
            confere(larg > 100, f"o título tem largura de verdade ({larg:.0f} px)")
            await pg.screenshot(path=str(SAIDA / f"fontes-{rotulo}.png"))
            await ctx.close()

            # E sem bloquear nada: o mesmo resultado, ainda sem nenhum pedido ao Google
            ctx, pg, visto = await abrir(nav, vp, mobile, bloquear_o_google=False)
            confere(visto["google"] == [], "sem bloqueio: nenhum pedido ao Google")
            await ctx.close()
        await nav.close()


if __name__ == "__main__":
    asyncio.run(rodar())
    print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
    for f in falhas:
        print("  -", f)
    sys.exit(1 if falhas else 0)
