"""Entrega por cidade no site: só os mercados que entregam na cidade do CEP aparecem (barracas, pílulas, cupom e aviso).

Teste de ponta a ponta no navegador, com a API do Supermatch e a de CEP (BrasilAPI) de mentira: nada sai para a rede.
O mapa de quem entrega onde é o do site (bloco @entrega de site/index.html); a lógica pura dele é conferida por tests/test_entrega.js.

Rodar com:  python tests/navegador/test_site_entrega.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

from _comum import SAIDA, URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0
HOJE = "2026-11-10T09:30:00+00:00"
MERCADOS = ["Apoio Entrega", "Atacadao", "Supernosso", "Super ABC"]
PRECOS = {"Apoio Entrega": 25.9, "Atacadao": 21.9, "Supernosso": 27.5, "Super ABC": 24.5}     # o Atacadão é o mais barato de propósito
CIDADES = {                                                                                     # CEP -> (cidade, UF) que a API de CEP devolveria
    "30130010": ("Belo Horizonte", "MG"),
    "32041000": ("Contagem", "MG"),
    "33120563": ("Santa Luzia", "MG"),
    "34000132": ("Nova Lima", "MG"),
    "32481000": ("Brumadinho", "MG"),
    "32510050": ("Igarapé", "MG"),
}


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


def resposta(termo):
    """Seis produtos, cada um à venda nos quatro mercados (o site é que tira os que não entregam na cidade)."""
    grupos = []
    for i in range(1, 7):
        opcoes = [{"supermercado": m, "nome": f"Arroz Marca {i} 5kg", "preco_varejo": PRECOS[m] + i, "preco_atacado": PRECOS[m] + i, "quantidade_atacado": 1,
                   "atualizado_em": HOJE, "id": f"{m}-{i}", "termo": termo, "ean": f"789000000000{i}"} for m in MERCADOS]
        grupos.append({"produto_base": f"Arroz Marca {i} 5kg", "ean": f"789000000000{i}", "vencedor_preco_baixo": "Atacadao", "opcoes_de_compra": opcoes})
    return {"status": "sucesso", "cep": "x", "uf": "MG", "item": termo, "mercados_consultados": MERCADOS, "equivalencia_familias": [], "carrinho_comparativo": grupos}


async def abrir(nav, vp, mobile, storage=None):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)

    async def api(rota):
        u = urlparse(rota.request.url)
        cabecalhos = {"access-control-allow-origin": "*"}
        if u.path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", headers=cabecalhos, body="{}")
        termo = parse_qs(u.query).get("item", [""])[0]
        await rota.fulfill(status=200, content_type="application/json", headers=cabecalhos, body=json.dumps(resposta(termo)))

    async def brasilapi(rota):
        cep = urlparse(rota.request.url).path.rsplit("/", 1)[-1]
        cabecalhos = {"access-control-allow-origin": "*"}
        if cep in CIDADES:
            cidade, uf = CIDADES[cep]
            return await rota.fulfill(status=200, content_type="application/json", headers=cabecalhos, body=json.dumps({"cep": cep, "city": cidade, "state": uf}))
        await rota.fulfill(status=404, content_type="application/json", headers=cabecalhos, body=json.dumps({"message": "CEP não encontrado"}))

    async def viacep(rota):                       # a reserva do site, se a primeira falhar: aqui, CEP que não existe
        await rota.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps({"erro": True}))

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.route("https://brasilapi.com.br/**", brasilapi)
    await pg.route("https://viacep.com.br/**", viacep)
    await pg.goto(URL)
    if storage:
        await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }", storage)
        await pg.reload()
    await pg.wait_for_timeout(500)
    return ctx, pg


async def cep(pg, valor):
    if not await pg.locator("#janelaCep").evaluate("d => d.open"):
        await pg.click("#botaoCep")
        await pg.wait_for_timeout(200)
    await pg.fill("#campoCep", valor)
    await pg.click("#formCep button[type=submit]")
    await pg.wait_for_timeout(700)


async def barracas(pg):
    return await pg.locator("#barracas .nome-m").all_inner_texts()


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 844}, True), ("desktop", {"width": 1366, "height": 860}, False)):
            print(f"\n===== {rotulo} =====")
            ctx, pg = await abrir(nav, vp, mobile)
            confere(len(await barracas(pg)) == 4, "antes de informar o CEP, as 4 barracas aparecem")

            await cep(pg, "30130-010")
            b = await barracas(pg)
            confere(sorted(b) == sorted(["Apoio Entrega", "Atacadão", "Supernosso", "Super ABC"]), f"BH tem os 4 mercados: {b}")
            confere(await pg.locator("#notaEntrega").is_hidden(), "BH: sem aviso de entrega parcial")

            await cep(pg, "32041-000")
            b = await barracas(pg)
            confere(sorted(b) == ["Apoio Entrega", "Atacadão", "Supernosso"], f"Contagem não tem Super ABC: {b}")

            await cep(pg, "33120-563")
            b = await barracas(pg)
            confere(sorted(b) == ["Apoio Entrega", "Atacadão", "Supernosso"], f"Santa Luzia: {b}")
            confere(await pg.locator("#notaEntrega").is_visible(), "Santa Luzia: aviso de entrega parcial visível")
            nota = await pg.locator("#notaEntrega").inner_text()
            confere("Atacadão" in nota and "Santa Luzia" in nota and "depende do bairro" in nota, f"texto do aviso: «{nota}»")
            confere(await pg.locator("#barracas .parcial-b").count() == 1, "só a barraca do Atacadão leva 'Só em parte da cidade'")
            await pg.screenshot(path=str(SAIDA / f"entrega-{rotulo}-santa-luzia.png"))
            if mobile:
                caixas = await pg.evaluate("() => [...document.querySelectorAll('#barracas li')].map((e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.width)]; })")
                confere(len(caixas) == 3 and caixas[2][1] > caixas[0][1] * 1.8, f"no celular, a terceira barraca ocupa a linha toda: {caixas}")

            # busca e pílulas
            await pg.fill("#campoBusca", "arroz")
            await pg.press("#campoBusca", "Enter")
            await pg.wait_for_selector(".produto", timeout=15000)
            pilulas = await pg.evaluate("() => [...document.querySelectorAll('.produto')].slice(0, 6).map((p) => p.querySelectorAll('.pilula').length)")
            confere(len(pilulas) >= 4 and all(n == 3 for n in pilulas), f"cada produto mostra 3 mercados em Santa Luzia: {pilulas}")      # a 1ª página tem 4 produtos
            nomes_p = await pg.locator(".pilula .nome").all_inner_texts()
            confere(not any("Super ABC" in n for n in nomes_p), "nenhuma pílula do Super ABC")
            for _ in range(2):
                await pg.evaluate("() => document.querySelector('[data-add]').click()")
                await pg.wait_for_timeout(250)
            await pg.locator("#cupom .linha").first.wait_for()
            # abre o cupom do Atacadão
            await pg.locator("[data-mercado='Atacadao']").click()
            await pg.wait_for_timeout(500)
            confere(await pg.locator("#cupom .aviso-entrega").count() == 1, "o cupom do Atacadão avisa que ele entrega só em parte")
            txt = await pg.locator("#cupom .aviso-entrega").inner_text()
            confere("Atacadão" in txt and "Santa Luzia" in txt, f"aviso do cupom: «{txt}»")
            await pg.locator("[data-mercado='Apoio Entrega']").click()
            await pg.wait_for_timeout(500)
            confere(await pg.locator("#cupom .aviso-entrega").count() == 0, "o cupom do Apoio não leva aviso")
            # o Atacadão é o mais barato nesta API de mentira: o painel tem de avisar que ele só entrega em parte da cidade
            venc = await pg.evaluate("() => { const c = Supermatch.comparar(); return c.melhor.mercado.id; }")
            aviso_painel = await pg.locator("#painel .aviso").count()
            confere(venc == "Atacadao" and aviso_painel == 1, f"o Atacadão (mais barato) vence e o painel avisa da entrega parcial (vencedor: {venc}, avisos: {aviso_painel})")
            await pg.screenshot(path=str(SAIDA / f"entrega-{rotulo}-santa-luzia-lista.png"), full_page=True)

            # trocar de cidade refaz tudo, sem recarregar
            await cep(pg, "30130-010")
            pilulas = await pg.evaluate("() => [...document.querySelectorAll('.produto')].slice(0, 6).map((p) => p.querySelectorAll('.pilula').length)")
            confere(len(pilulas) >= 4 and all(n == 4 for n in pilulas), f"ao mudar para BH, os resultados passam a mostrar 4 mercados: {pilulas}")
            confere(len(await barracas(pg)) == 4, "ao mudar para BH, voltam as 4 barracas")
            confere(await pg.locator("#cupom .aviso-entrega").count() == 0, "ao mudar para BH, o aviso do cupom some")

            # cidades com poucos mercados
            await cep(pg, "34000-132")
            b = await barracas(pg)
            confere(sorted(b) == ["Apoio Entrega", "Supernosso"], f"Nova Lima só tem Apoio e Supernosso: {b}")
            await cep(pg, "32481-000")
            b = await barracas(pg)
            confere(b == ["Atacadão"], f"Brumadinho só tem o Atacadão: {b}")
            await pg.screenshot(path=str(SAIDA / f"entrega-{rotulo}-brumadinho.png"))

            # cidade sem nenhum mercado
            await cep(pg, "32510-050")
            msg = await pg.locator("#erroCep").inner_text()
            confere("Não há dados para o CEP inserido" in msg and "Igarapé" in msg and "Nenhum dos mercados" in msg, f"Igarapé recusado: «{msg}»")
            confere(await pg.evaluate("() => JSON.parse(localStorage.getItem('sm_cidade')) !== 'Igarapé/MG'"), "Igarapé não é guardado")
            sobra = await pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            confere(sobra <= 1, f"sem rolagem horizontal ({sobra}px)")
            await ctx.close()

            # CEP guardado de uma cidade sem mercado é descartado
            ctx, pg = await abrir(nav, vp, mobile, storage={"sm_cep": '"32510050"', "sm_cidade": '"Igarapé/MG"'})
            confere(await pg.locator("#janelaCep").evaluate("d => d.open"), "CEP guardado de Igarapé pede novo CEP")
            await ctx.close()
        await nav.close()


asyncio.run(rodar())
print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
for f in falhas:
    print("  -", f)
sys.exit(1 if falhas else 0)
