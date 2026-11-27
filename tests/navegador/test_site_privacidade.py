"""Aviso de privacidade do CEP no site: a janela "Privacidade e seus dados" abre do rodapé e da janela do CEP, cabe na tela, e o botão
"Apagar meus dados deste aparelho" apaga tudo o que o site guardou (inclusive as chaves da versão anterior) sem tocar no que não é dele.

Teste de ponta a ponta no navegador, com a API de mentira. O que o aviso afirma sobre os endereços e o armazenamento é conferido em
tests/test_privacidade.js; o que a API escreve no log, em tests/test_privacidade.py.

Rodar com:  python tests/navegador/test_site_privacidade.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from _comum import SAIDA, URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0
PERMITIDOS = {"127.0.0.1", "supermatch-api.onrender.com", "brasilapi.com.br", "viacep.com.br"}      # 127.0.0.1 é o próprio site, servido pelo teste (_comum.py); o Google não está na lista


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


def limpo(texto):
    return " ".join(texto.replace("\xa0", " ").split())


async def abrir(nav, vp, mobile, guardado=None):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    destinos = set()
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.on("request", lambda r: destinos.add(urlparse(r.url).hostname) if r.url.startswith("http") else None)

    async def api(rota):
        cab = {"access-control-allow-origin": "*"}
        corpo = "{}" if urlparse(rota.request.url).path.endswith("/saude") else json.dumps({"status": "sucesso", "carrinho_comparativo": []})
        await rota.fulfill(status=200, content_type="application/json", headers=cab, body=corpo)

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    if guardado:
        await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }", guardado)
        await pg.reload()
    return ctx, pg, destinos


async def aberta(pg, id_):
    return await pg.evaluate("(i) => document.getElementById(i).open", id_)


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 800}, True), ("celular-estreito", {"width": 320, "height": 700}, True), ("desktop", {"width": 1280, "height": 900}, False)):
            print(f"\n===== {rotulo} =====")

            # --- 1. primeira visita: a janela do CEP já avisa para onde o CEP vai e leva ao aviso inteiro
            ctx, pg, destinos = await abrir(nav, vp, mobile)
            confere(await aberta(pg, "janelaCep"), "primeira visita: a janela do CEP abre sozinha")
            texto_cep = limpo(await pg.locator("#janelaCep").inner_text())
            confere("Usamos o CEP só para achar a sua cidade e os mercados que entregam aí" in texto_cep, "a janela do CEP diz para que serve o CEP")
            await pg.locator("#abrirPrivacidadeCep").evaluate("(e) => e.click()")
            confere(await aberta(pg, "janelaPrivacidade") and await aberta(pg, "janelaCep"), "«Como tratamos seus dados» abre o aviso por cima da janela do CEP")
            titulo = limpo(await pg.locator("#janelaPrivacidade h2").inner_text())
            confere(titulo == "Privacidade e seus dados", f"título do aviso: «{titulo}»")
            texto = limpo(await pg.locator("#janelaPrivacidade").inner_text())
            for trecho in ("não tem cadastro, anúncios nem rastreadores", "não usa cookies", "BrasilAPI e ViaCEP", "5 primeiros dígitos do CEP", "guardados por 7 dias", "Netlify", "Render"):
                confere(trecho in texto, f"o aviso diz: «{trecho}»")
            for trecho in ("Quem responde por isto", "A Econolista é mantida por Rafael Lima"):
                confere(trecho in texto, f"o aviso diz: «{trecho}»")
            email = pg.locator("#contatoEmail")
            confere(limpo(await email.inner_text()) == "rafaelhsts@gmail.com", f"o e-mail do responsável aparece escrito: «{limpo(await email.inner_text())}»")
            href = await email.get_attribute("href")
            confere(href == "mailto:rafaelhsts@gmail.com?subject=Econolista%3A%20privacidade", f"o link abre o e-mail com assunto: {href}")
            dentro = await email.evaluate("(e) => { const r = e.getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth && r.height > 0; }")
            confere(dentro, f"o e-mail cabe na tela de {vp['width']} px")
            await pg.locator("#fecharPrivacidade").evaluate("(e) => e.click()")
            confere(not await aberta(pg, "janelaPrivacidade") and await aberta(pg, "janelaCep"), "«Fechar» volta para a janela do CEP, que continua aberta")
            await pg.locator("#cancelarCep").evaluate("(e) => e.click()")

            # --- 2. do rodapé; cabe na tela; teclado
            await pg.locator("#abrirPrivacidade").focus()
            await pg.keyboard.press("Enter")
            confere(await aberta(pg, "janelaPrivacidade"), "o link do rodapé abre o aviso (pelo teclado)")
            caixa = await pg.evaluate("""() => { const j = document.querySelector('#janelaPrivacidade .janela'); const r = j.getBoundingClientRect();
                return { esq: r.left, dir: r.right, larg: window.innerWidth, estouro: j.scrollWidth > j.clientWidth + 1 }; }""")
            confere(caixa["esq"] >= 0 and caixa["dir"] <= caixa["larg"] and not caixa["estouro"], f"o aviso cabe na tela de {vp['width']} px: {caixa}")
            botoes = await pg.evaluate("""() => [...document.querySelectorAll('#janelaPrivacidade .acoes button')].map((b) => { const r = b.getBoundingClientRect(); return [r.left >= 0, r.right <= window.innerWidth, r.height >= 40]; })""")
            confere(all(all(x) for x in botoes) and len(botoes) == 2, f"os dois botões do aviso aparecem inteiros e com altura de toque: {botoes}")
            await pg.screenshot(path=str(SAIDA / f"privacidade-{rotulo}.png"))
            await pg.keyboard.press("Escape")
            confere(not await aberta(pg, "janelaPrivacidade"), "Esc fecha o aviso")
            confere(await pg.evaluate("document.activeElement.id") == "abrirPrivacidade", "o foco volta para o link do rodapé")
            confere(not (destinos - PERMITIDOS), f"o navegador só falou com os endereços que o aviso cita: {sorted(d for d in destinos if d)}")
            await ctx.close()

            # --- 3. apagar os meus dados: tudo o que é do site (sm_*, user_*), nada do que não é
            seed = {"sm_cep": json.dumps("30130010"), "sm_cidade": json.dumps("Belo Horizonte/MG"), "sm_modo": json.dumps("equivalente"), "sm_lista": json.dumps([]),
                    "user_cep": "30130010", "user_cidade": "Belo Horizonte/MG", "outro_site": "fica"}
            ctx, pg, _ = await abrir(nav, vp, mobile, seed)
            confere(not await aberta(pg, "janelaCep"), "com CEP guardado, a janela do CEP não abre")
            await pg.locator("#abrirPrivacidade").evaluate("(e) => e.click()")
            async with pg.expect_navigation():
                await pg.locator("#apagarMeusDados").evaluate("(e) => e.click()")
            sobrou = await pg.evaluate("() => Object.keys(localStorage).sort()")
            confere(sobrou == ["outro_site"], f"depois de «Apagar meus dados» sobra só o que não é do site: {sobrou}")
            confere(await aberta(pg, "janelaCep"), "sem CEP guardado, a janela do CEP abre de novo (a chave da versão anterior não trouxe o CEP de volta)")
            await ctx.close()
        await nav.close()


if __name__ == "__main__":
    asyncio.run(rodar())
    print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
    for f in falhas:
        print("  -", f)
    sys.exit(1 if falhas else 0)
