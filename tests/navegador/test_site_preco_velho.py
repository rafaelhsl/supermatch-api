"""Aviso de "preço velho" no site: quando o preço mais antigo da tela tem mais de 36 h, a busca e o cupom avisam, com a data; no dia a dia, nada.

Teste de ponta a ponta no navegador, com a API de mentira: as datas `atualizado_em` são calculadas a partir de agora, então valem as do relógio de verdade.
A regra está em tests/test_preco_velho.js.

Rodar com:  python tests/navegador/test_site_preco_velho.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from _comum import SAIDA, URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0
BRASILIA = timezone(timedelta(hours=-3))          # sem horário de verão desde 2019


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


def limpo(texto):
    return " ".join(texto.replace("\xa0", " ").split())


def ha(horas):
    return (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()


def dia_de_brasilia(iso):
    return datetime.fromisoformat(iso).astimezone(BRASILIA).strftime("%d/%m")


def opcao(mercado, nome, preco, ean, quando):
    return {"supermercado": mercado, "nome": nome, "preco_varejo": preco, "preco_atacado": preco, "quantidade_atacado": 1, "atualizado_em": quando,
            "id": f"{mercado}-{ean}", "termo": "arroz", "ean": ean}


def resposta(horas_atacadao, horas_supernosso):
    atacadao, supernosso = ha(horas_atacadao), ha(horas_supernosso)
    grupo = {"produto_base": "Arroz Camil Tipo 1 5kg", "ean": "7896006711155", "id_do_grupo": "7896006711155", "vencedor_preco_baixo": "Atacadao",
             "opcoes_de_compra": [opcao("Atacadao", "Arroz Camil Tipo 1 5kg", 22.5, "7896006711155", atacadao), opcao("Supernosso", "Arroz Camil Tipo 1 5kg", 24.99, "7896006711155", supernosso)]}
    return {"status": "sucesso", "cep": "x", "uf": "MG", "item": "arroz", "mercados_consultados": ["Atacadao", "Supernosso"], "equivalencia_familias": [], "carrinho_comparativo": [grupo]}, atacadao, supernosso


CONTRASTE = """(el) => {
  const canal = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = (r, g, b) => 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
  const cor = (s) => { const m = s.match(/[\\d.]+/g).map(Number); return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
  const fundoDe = (e) => { while (e) { const c = cor(getComputedStyle(e).backgroundColor); if (c.a > 0) return c; e = e.parentElement; } return { r: 255, g: 255, b: 255, a: 1 }; };
  const f = fundoDe(el), t = cor(getComputedStyle(el).color);
  const l1 = lum(t.r, t.g, t.b), l2 = lum(f.r, f.g, f.b);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}"""


async def abrir(nav, vp, mobile, horas_atacadao, horas_supernosso):
    corpo, atacadao, supernosso = resposta(horas_atacadao, horas_supernosso)
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)

    async def api(rota):
        cab = {"access-control-allow-origin": "*"}
        if urlparse(rota.request.url).path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", headers=cab, body="{}")
        await rota.fulfill(status=200, content_type="application/json", headers=cab, body=json.dumps(corpo))

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }", {"sm_cep": json.dumps("30130010"), "sm_cidade": json.dumps("Belo Horizonte/MG")})
    await pg.reload()
    await pg.fill("#campoBusca", "arroz")
    await pg.press("#campoBusca", "Enter")
    await pg.wait_for_selector(".produto", timeout=15000)
    return ctx, pg, min(atacadao, supernosso)


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 800}, True), ("celular-estreito", {"width": 320, "height": 700}, True), ("desktop", {"width": 1280, "height": 900}, False)):
            print(f"\n===== {rotulo} =====")

            # --- 1. o dia a dia: preço de hoje cedo e de ontem a esta hora não avisam
            for horas in (3, 24, 35):
                ctx, pg, _ = await abrir(nav, vp, mobile, horas, horas)
                confere(await pg.locator(".aviso-velho").count() == 0, f"preço de {horas} h atrás: nenhum aviso nos resultados")
                await pg.locator("article.produto").first.locator("[data-add]").evaluate("(e) => e.click()")
                await pg.locator("#cupom .linha").first.wait_for()
                confere(await pg.locator(".aviso-velho").count() == 0, f"preço de {horas} h atrás: nenhum aviso no cupom")
                await ctx.close()

            # --- 2. coleta que não veio: avisa, com a data, na busca e no cupom
            ctx, pg, mais_antigo = await abrir(nav, vp, mobile, 72, 72)
            esperado = dia_de_brasilia(mais_antigo)
            aviso = pg.locator("main .aviso-velho")
            confere(await aviso.count() == 1, "preço de 3 dias atrás: um aviso nos resultados")
            texto = limpo(await aviso.inner_text())
            confere(texto.startswith("Atenção: Estes preços são de ") and f"são de {esperado} (há 3 dias)" in texto and texto.endswith("Confira no site do mercado antes de comprar."), f"texto do aviso: «{texto}» (data esperada {esperado})")
            confere(await aviso.get_attribute("role") == "status", "o aviso é anunciado ao leitor de tela (role=status)")
            razao = await aviso.evaluate(CONTRASTE)
            confere(razao >= 4.5, f"contraste do aviso: {razao:.1f}:1 (mínimo 4,5:1)")
            confere(await aviso.evaluate("(e) => e.scrollWidth <= e.clientWidth + 1 && e.getBoundingClientRect().right <= document.documentElement.clientWidth"), "o aviso cabe na largura da tela")
            await pg.screenshot(path=str(SAIDA / f"preco-velho-{rotulo}-1-busca.png"))
            await pg.locator("article.produto").first.locator("[data-add]").evaluate("(e) => e.click()")
            await pg.locator("#cupom .linha").first.wait_for()
            no_cupom = pg.locator("#cupom .aviso-velho")
            confere(await no_cupom.count() == 1 and f"são de {esperado} (há 3 dias)" in limpo(await no_cupom.inner_text()), "o cupom repete o aviso, com a mesma data")
            razao = await no_cupom.evaluate(CONTRASTE)
            confere(razao >= 4.5, f"contraste do aviso no cupom: {razao:.1f}:1")
            confere(await pg.evaluate("() => [...document.querySelectorAll('#cupom *')].filter((e) => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).length") == 0, "nada do cupom passa da borda da tela")
            await pg.screenshot(path=str(SAIDA / f"preco-velho-{rotulo}-2-cupom.png"))
            await ctx.close()

            # --- 3. vale o preço MAIS ANTIGO da tela: um mercado em dia e o outro atrasado avisa, com a data do atrasado
            ctx, pg, mais_antigo = await abrir(nav, vp, mobile, 2, 100)
            aviso = pg.locator("main .aviso-velho")
            confere(await aviso.count() == 1 and f"são de {dia_de_brasilia(mais_antigo)} (há 4 dias)" in limpo(await aviso.inner_text()), "um mercado atrasado basta: o aviso traz a data do mais antigo (há 4 dias)")
            await ctx.close()

            # --- 4. a fronteira, com o relógio de verdade: 37 h avisa
            ctx, pg, _ = await abrir(nav, vp, mobile, 37, 37)
            confere(await pg.locator("main .aviso-velho").count() == 1 and "há 1 dia)" in limpo(await pg.locator("main .aviso-velho").inner_text()), "preço de 37 h atrás: avisa («há 1 dia»)")
            await ctx.close()
        await nav.close()


if __name__ == "__main__":
    asyncio.run(rodar())
    print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
    for f in falhas:
        print("  -", f)
    sys.exit(1 if falhas else 0)
