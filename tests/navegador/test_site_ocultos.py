"""Aviso 'N produtos que apenas citam a palavra foram ocultados': teste de ponta a ponta no navegador, com uma API falsa.

Rodar com:  python tests/navegador/test_site_ocultos.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
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


def opcao(mercado, nome, preco, so_cita=False):
    o = {"supermercado": mercado, "nome": nome, "preco_varejo": preco, "preco_atacado": preco, "quantidade_atacado": 1, "atualizado_em": "2026-11-05T12:00:00+00:00", "id": f"{mercado}-{nome}"}
    if so_cita:
        o["so_cita"] = True
    return o


def grupo(nome, *opcoes):
    return {"produto_base": nome, "vencedor_preco_baixo": opcoes[0]["supermercado"], "opcoes_de_compra": list(opcoes)}


PRINCIPAIS = [grupo(f"Arroz Marca {i}", opcao("Apoio Entrega", f"Arroz Marca {i}", 5 + i), opcao("Supernosso", f"Arroz Marca {i}", 5.5 + i)) for i in range(3)]
SO_CITAM = [grupo("Condicionador com Arroz Preto", opcao("Supernosso", "Condicionador com Arroz Preto", 20, True)),
            grupo("Sopa de Arroz", opcao("Apoio Entrega", "Sopa de Arroz", 3, True), opcao("Super ABC", "Sopa de Arroz", 3.2, True))]


def resposta(termo, todos, cenario):
    """O que a API falsa devolve. `cenario`: 'ocultos' (padrão), 'antiga' (sem os campos novos), 'limite'."""
    base = {"status": "sucesso", "cep": "x", "uf": "MG", "item": termo, "mercados_consultados": ["Apoio Entrega", "Supernosso"]}
    if cenario == "antiga":
        return {**base, "ocultos": 3, "carrinho_comparativo": PRINCIPAIS}
    if cenario == "limite":
        return {**base, "ocultos": 120, "ocultos_so_citam": 0, "ocultos_pelo_limite": 120, "so_citam_por_mercado": {}, "carrinho_comparativo": PRINCIPAIS}
    por_mercado = {"Supernosso": 1, "Apoio Entrega": 1, "Super ABC": 1}
    if todos:
        return {**base, "ocultos": 0, "ocultos_so_citam": 0, "ocultos_pelo_limite": 0, "so_citam_por_mercado": por_mercado, "carrinho_comparativo": PRINCIPAIS + SO_CITAM}
    return {**base, "ocultos": 3, "ocultos_so_citam": 3, "ocultos_pelo_limite": 0, "so_citam_por_mercado": por_mercado, "carrinho_comparativo": PRINCIPAIS}


async def abrir(nav, vp, mobile, cidade, cep, cenario):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pedidos = []
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)

    async def api(rota):
        u = urlparse(rota.request.url)
        if u.path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", body="{}")
        q = parse_qs(u.query)
        pedidos.append({"item": q.get("item", [""])[0], "todos": q.get("todos", [""])[0]})
        await rota.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"},
                           body=json.dumps(resposta(q.get("item", [""])[0], q.get("todos", [""])[0] == "1", cenario)))

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }", {"sm_cep": json.dumps(cep), "sm_cidade": json.dumps(cidade)})
    await pg.reload()
    await pg.wait_for_timeout(700)
    return ctx, pg, pedidos


async def buscar(pg, termo):
    await pg.fill("#campoBusca", termo)
    await pg.press("#campoBusca", "Enter")
    await pg.wait_for_timeout(700)


async def texto_nota(pg):
    return [" ".join((await n.inner_text()).split()) for n in await pg.query_selector_all(".nota-busca")]


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 800}, True), ("desktop", {"width": 1280, "height": 900}, False)):
            print(f"\n===== {rotulo} =====")
            # --- Belo Horizonte: os 4 mercados entregam
            ctx, pg, pedidos = await abrir(nav, vp, mobile, "Belo Horizonte/MG", "30130010", "ocultos")
            await buscar(pg, "arroz")
            notas = await texto_nota(pg)
            confere(notas == ["3 produtos que apenas citam “arroz” foram ocultados. Mostrar também"], f"aviso inicial: {notas}")
            confere(len(await pg.query_selector_all(".produto")) == 3, "3 cartões antes de mostrar")
            confere(pedidos[-1] == {"item": "arroz", "todos": ""}, f"a 1ª busca não pede todos: {pedidos[-1]}")
            await pg.screenshot(path=str(SAIDA / f"ocultos-{rotulo}-1-oculto.png"))

            await pg.click("#alternarCitam"); await pg.wait_for_timeout(700)
            confere(pedidos[-1] == {"item": "arroz", "todos": "1"}, f"'Mostrar também' pede todos=1: {pedidos[-1]}")
            notas = await texto_nota(pg)
            confere(notas == ["Mostrando também 3 produtos que apenas citam “arroz”. Ocultar de novo"], f"aviso depois de mostrar: {notas}")
            esperado = 4 if mobile else 5   # no celular a tela mostra 4 cartões por vez, com "Mostrar mais"
            confere(len(await pg.query_selector_all(".produto")) == esperado, f"{esperado} cartões depois de mostrar (3 + 2 que só citam; no celular, 4 por vez)")
            confere(await pg.evaluate("document.activeElement && document.activeElement.id") == "alternarCitam", "o foco volta para o botão novo")
            await pg.screenshot(path=str(SAIDA / f"ocultos-{rotulo}-2-mostrando.png"))

            await pg.click("#alternarCitam"); await pg.wait_for_timeout(700)
            confere(pedidos[-1] == {"item": "arroz", "todos": ""}, f"'Ocultar de novo' volta à busca normal: {pedidos[-1]}")
            confere((await texto_nota(pg))[0].startswith("3 produtos que apenas citam"), "o aviso de ocultados volta")
            confere(len(await pg.query_selector_all(".produto")) == 3, "volta a 3 cartões")

            await pg.click("#alternarCitam"); await pg.wait_for_timeout(500)
            await buscar(pg, "feijão")
            confere(pedidos[-1] == {"item": "feijão", "todos": ""}, f"uma busca nova volta a esconder: {pedidos[-1]}")
            confere((await texto_nota(pg))[0].startswith("3 produtos que apenas citam “feijão”"), "o aviso da busca nova cita o termo novo")

            # troca de modo não some com o aviso
            await pg.click('[data-modo="equivalente"]'); await pg.wait_for_timeout(400)
            confere(len(await pg.query_selector_all(".nota-busca")) in (0, 1), "no modo equivalente a tela segue sem erro")
            await pg.click('[data-modo="exato"]'); await pg.wait_for_timeout(300)
            confere(len(await texto_nota(pg)) == 1, "de volta ao exato o aviso está lá")

            # texto digitado com HTML não vira elemento
            await buscar(pg, '<img src=x onerror="window.__xss=1">')
            confere(await pg.evaluate("window.__xss") is None, "termo com HTML não executa nada")
            confere('<img' in (await texto_nota(pg))[0], "o termo aparece como texto no aviso")
            confere(await pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "sem rolagem horizontal")
            await ctx.close()

            # --- Contagem: o Super ABC não entrega; só 2 dos 3 ocultados contam
            ctx, pg, pedidos = await abrir(nav, vp, mobile, "Contagem/MG", "32041000", "ocultos")
            await buscar(pg, "arroz")
            notas = await texto_nota(pg)
            confere(notas == ["2 produtos que apenas citam “arroz” foram ocultados. Mostrar também"], f"Contagem não conta o Super ABC: {notas}")
            await pg.click("#alternarCitam"); await pg.wait_for_timeout(700)
            confere((await texto_nota(pg))[0].startswith("Mostrando também 2 produtos"), f"Contagem mostrando: {(await texto_nota(pg))[0]}")
            confere(len(await pg.query_selector_all(".produto")) == (4 if mobile else 5), "os 2 grupos extras aparecem (4 por vez no celular)")
            await ctx.close()

            # --- API antiga (sem os campos novos): nenhuma nota
            ctx, pg, pedidos = await abrir(nav, vp, mobile, "Belo Horizonte/MG", "30130010", "antiga")
            await buscar(pg, "arroz")
            confere(await texto_nota(pg) == [], "API antiga: nenhuma nota, a tela funciona igual")
            confere(len(await pg.query_selector_all(".produto")) == 3, "API antiga: cartões normais")
            await ctx.close()

            # --- teto de resultados
            ctx, pg, pedidos = await abrir(nav, vp, mobile, "Belo Horizonte/MG", "30130010", "limite")
            await buscar(pg, "a")
            notas = await texto_nota(pg)
            confere(notas == ["Há mais 120 produtos além dos mostrados. Digite mais palavras para refinar a busca."], f"aviso do teto, sem botão: {notas}")
            confere(await pg.query_selector("#alternarCitam") is None, "o aviso do teto não tem botão")
            await pg.screenshot(path=str(SAIDA / f"ocultos-{rotulo}-3-teto.png"))
            await ctx.close()
        await nav.close()


asyncio.run(rodar())
print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
for f in falhas:
    print("  -", f)
sys.exit(1 if falhas else 0)
