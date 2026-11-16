"""Produto equivalente no site, com API falsa: as chaves vêm da API; sem chaves (API antiga) o site não adivinha pelo nome e avisa.

Rodar com:  python tests/navegador/test_site_equivalencia.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
from urllib.parse import parse_qs, urlparse

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


def opcao(mercado, nome, preco, chave=None, rotulo=None):
    o = {"supermercado": mercado, "nome": nome, "preco_varejo": preco, "preco_atacado": preco, "quantidade_atacado": 1,
         "atualizado_em": "2026-11-05T12:00:00+00:00", "id": f"{mercado}-{nome}"}
    if chave:
        o["chave_equivalencia"], o["rotulo_equivalencia"] = chave, rotulo
    return o


def grupo(*opcoes):
    return {"produto_base": opcoes[0]["nome"], "vencedor_preco_baixo": opcoes[0]["supermercado"], "opcoes_de_compra": list(opcoes)}


SAL = ("sal|refinado|1000g", "Sal refinado, 1 kg")
FAMILIAS = ["arroz", "feijão", "sal", "leite condensado", "água mineral"]
BASE = {"status": "sucesso", "cep": "x", "uf": "MG", "mercados_consultados": ["Apoio Entrega", "Supernosso", "Atacadao"]}


def resposta(termo, cenario):
    if termo == "sal":
        sal = [grupo(opcao("Apoio Entrega", "Sal Refinado Cisne 1kg", 3.2, *SAL)), grupo(opcao("Atacadao", "Sal Refinado Globo 1kg", 2.4, *SAL)),
               grupo(opcao("Supernosso", "Sal Refinado Lebre Pacote 1 Kg", 3.0, *SAL)),
               grupo(opcao("Supernosso", "Sal com Moedor Lemon Pepper 70g", 12))]
        if cenario == "antiga":                       # a API antiga não manda chave nenhuma
            sal = [grupo(*[{k: v for k, v in o.items() if not k.endswith("_equivalencia")} for o in g["opcoes_de_compra"]]) for g in sal]
        return sal
    if termo == "arroz":
        arroz = [grupo(opcao("Apoio Entrega", "Arroz Branco Camil Tipo 1 5kg", 24.9, "arroz|branco|tipo 1|5000g", "Arroz branco tipo 1, 5 kg")),
                 grupo(opcao("Atacadao", "Arroz Branco Tio João Tipo 1 5kg", 23.5, "arroz|branco|tipo 1|5000g", "Arroz branco tipo 1, 5 kg"))]
        if cenario == "antiga":
            arroz = [grupo(*[{k: v for k, v in o.items() if not k.endswith("_equivalencia")} for o in g["opcoes_de_compra"]]) for g in arroz]
        return arroz
    return [grupo(opcao("Supernosso", "Sabonete Dove 90g", 3), opcao("Apoio Entrega", "Sabonete Dove 90 g", 3.2))]   # sem família


async def abrir(nav, vp, mobile, cenario):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)

    async def api(rota):
        u = urlparse(rota.request.url)
        if u.path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", body="{}")
        termo = parse_qs(u.query).get("item", [""])[0]
        corpo = {**BASE, "item": termo, "carrinho_comparativo": resposta(termo, cenario)}
        if cenario == "nova":
            corpo["equivalencia_familias"] = FAMILIAS
        await rota.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps(corpo))

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }",
                      {"sm_cep": json.dumps("30130010"), "sm_cidade": json.dumps("Belo Horizonte/MG")})
    await pg.reload()
    await pg.wait_for_timeout(600)
    return ctx, pg


async def buscar(pg, termo):
    await pg.fill("#campoBusca", termo)
    await pg.press("#campoBusca", "Enter")
    await pg.wait_for_timeout(700)


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 800}, True), ("desktop", {"width": 1280, "height": 900}, False)):
            print(f"\n===== {rotulo} =====")
            # --- API nova: as chaves vêm do servidor
            ctx, pg = await abrir(nav, vp, mobile, "nova")
            await buscar(pg, "sal")
            await pg.click('.modo button[data-modo="equivalente"]'); await pg.wait_for_timeout(400)
            cartoes = await pg.query_selector_all(".produto")
            confere(len(cartoes) == 1, f"API nova: o sal vira 1 cartão equivalente ({len(cartoes)}); o sal com moedor, sem chave, fica de fora")
            titulo = (await pg.locator(".produto h3").first.inner_text()).strip()
            confere(titulo == "Sal refinado, 1 kg", f"o nome do cartão é o rótulo da API: «{titulo}»")
            confere(await pg.locator(".produto .qualquer").count() == 1, "o cartão diz 'Qualquer marca'")
            txt = " ".join((await pg.locator(".produto").first.inner_text()).split())
            confere("R$ 2,40" in txt.replace("\xa0", " ") and "R$ 3,00" in txt.replace("\xa0", " ") and "R$ 3,20" in txt.replace("\xa0", " "), f"os 3 mercados aparecem com o preço de cada um: «{txt[:140]}»")
            await pg.screenshot(path=str(SAIDA / f"equiv-{rotulo}-1-nova.png"))
            # adicionar à lista: o item leva o nome real do produto mais barato do mercado
            await pg.locator("[data-add]").first.click(); await pg.wait_for_timeout(300)
            confere(await pg.locator("#cupom .linha").count() == 1, "o item equivalente entra na lista")
            confere("Leva:" in (await pg.locator("#cupom").inner_text()), "o cupom diz qual produto cada mercado entrega")
            # sem família: mensagem com a lista que a API mandou
            await buscar(pg, "sabonete")
            msg = " ".join((await pg.locator("#resultados").inner_text()).split())
            confere("Nenhum produto equivalente para “sabonete”" in msg, f"busca sem família: «{msg[:70]}…»")
            confere("vale para arroz, feijão, sal, leite condensado e água mineral." in msg, f"a mensagem usa a lista da API: «{msg}»")
            confere("papel higiênico" not in msg, "sem a lista fixa antiga")
            await pg.screenshot(path=str(SAIDA / f"equiv-{rotulo}-2-sem-familia.png"))
            # de volta ao exato, o produto sem família aparece normalmente
            await pg.click('#resultados [data-modo="exato"]'); await pg.wait_for_timeout(400)
            confere(await pg.locator(".produto").count() == 1, "no modo exato o sabonete aparece")
            await ctx.close()

            # --- API sem equivalência (sem chaves): o site não adivinha pelo nome e avisa
            ctx, pg = await abrir(nav, vp, mobile, "antiga")
            await buscar(pg, "arroz")
            await pg.click('.modo button[data-modo="equivalente"]'); await pg.wait_for_timeout(400)
            confere(await pg.locator(".produto").count() == 0, "API sem chaves: nenhum cartão equivalente (o site não usa mais motor próprio)")
            msg = " ".join((await pg.locator("#resultados").inner_text()).split())
            confere("Nenhum produto equivalente para “arroz”" in msg and "A comparação por equivalência não está disponível agora." in msg, f"API sem chaves: avisa que a equivalência não está disponível: «{msg}»")
            confere("arroz, feijão" not in msg, "API sem chaves: sem lista fixa de famílias")
            await pg.click('#resultados [data-modo="exato"]'); await pg.wait_for_timeout(400)
            confere(await pg.locator(".produto").count() >= 1, "API sem chaves: o modo exato segue funcionando")
            await ctx.close()
        await nav.close()


asyncio.run(rodar())
print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
for f in falhas:
    print("  -", f)
sys.exit(1 if falhas else 0)
