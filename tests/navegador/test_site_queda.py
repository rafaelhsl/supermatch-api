"""Selo "caiu X% em 7 dias" no site: aparece no quadro do mercado onde o preço caiu e na linha do cupom, e em mais nenhum lugar.

Teste de ponta a ponta no navegador, com a API de mentira (as marcas `queda_preco` vêm prontas, como a API as mandaria). A regra
que decide quando um produto ganha a marca é testada em tests/test_quedas.py; a que valida a marca no site, em tests/test_queda.js.

Rodar com:  python tests/navegador/test_site_queda.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from _comum import SAIDA, URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0
HOJE = "2026-11-16T10:44:50+00:00"
MERCADOS = ["Apoio Entrega", "Atacadao", "Supernosso", "Super ABC"]


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


CHAVE, ROTULO = "margarina|500g", "Margarina, 500 g"          # a família dos três produtos de 500 g


def opcao(mercado, nome, varejo, ean, queda=None, atacado=None, qtd_atacado=1, familia=False):
    o = {"supermercado": mercado, "nome": nome, "preco_varejo": varejo, "preco_atacado": atacado if atacado is not None else varejo, "quantidade_atacado": qtd_atacado,
         "atualizado_em": HOJE, "id": f"{mercado}-{ean}", "termo": "margarina", "ean": ean}
    if queda:
        o["queda_preco"] = {"preco_antes": queda[0], "percentual": queda[1], "dias": 7}
    if familia:
        o["chave_equivalencia"], o["rotulo_equivalencia"] = CHAVE, ROTULO
    return o


def grupo(base, ean, *opcoes):
    return {"produto_base": base, "ean": ean, "id_do_grupo": ean, "vencedor_preco_baixo": min(opcoes, key=lambda o: o["preco_varejo"])["supermercado"], "opcoes_de_compra": list(opcoes)}


def resposta(com_selo=True):
    s = (lambda q: q) if com_selo else (lambda q: None)
    grupos = [
        # 1. o mais barato (Supernosso) é o que caiu: 14,99 -> 7,99; o Apoio caiu menos
        grupo("Margarina Becel 500g", "7891000000001",
              opcao("Supernosso", "Margarina Becel 500g", 7.99, "7891000000001", s((14.99, 47)), familia=True),
              opcao("Apoio Entrega", "Margarina Becel 500g", 8.5, "7891000000001", s((10.0, 15)), familia=True),
              opcao("Atacadao", "Margarina Becel 500g", 9.49, "7891000000001", familia=True)),
        # 2. quem caiu NÃO é o mais barato; e o Supernosso tem preço de atacado a partir de 6 unidades
        grupo("Margarina Qualy 500g", "7891000000002",
              opcao("Atacadao", "Margarina Qualy 500g", 5.0, "7891000000002", familia=True),
              opcao("Supernosso", "Margarina Qualy 500g", 6.0, "7891000000002", s((8.0, 25)), atacado=5.5, qtd_atacado=6, familia=True),
              opcao("Apoio Entrega", "Margarina Qualy 500g", 6.4, "7891000000002", familia=True)),
        # 3. a marca da API não bate com o preço da tela: dizia 99%, mas 6,00 -> 4,99 é 17%; o site refaz a conta
        grupo("Margarina Delícia 500g", "7891000000003",
              opcao("Atacadao", "Margarina Delícia 500g", 4.99, "7891000000003", s((6.0, 99)), familia=True),
              opcao("Supernosso", "Margarina Delícia 500g", 5.29, "7891000000003", familia=True)),
        # 4. marca velha: o preço de hoje (3,50) é MAIOR que o de antes (3,20), então o selo não pode aparecer
        grupo("Margarina Primor 250g", "7891000000004",
              opcao("Apoio Entrega", "Margarina Primor 250g", 3.5, "7891000000004", s((3.2, 9))),
              opcao("Atacadao", "Margarina Primor 250g", 3.39, "7891000000004")),
    ]
    return {"status": "sucesso", "cep": "x", "uf": "MG", "item": "margarina", "mercados_consultados": MERCADOS, "equivalencia_familias": ["margarina"], "carrinho_comparativo": grupos}


async def abrir(nav, vp, mobile, com_selo=True):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)

    async def api(rota):
        cab = {"access-control-allow-origin": "*"}
        if urlparse(rota.request.url).path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", headers=cab, body="{}")
        await rota.fulfill(status=200, content_type="application/json", headers=cab, body=json.dumps(resposta(com_selo)))

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }", {"sm_cep": json.dumps("30130010"), "sm_cidade": json.dumps("Belo Horizonte/MG")})
    await pg.reload()
    await pg.fill("#campoBusca", "margarina")
    await pg.press("#campoBusca", "Enter")
    await pg.wait_for_selector(".produto", timeout=15000)
    return ctx, pg


async def clicar(alvo):
    """Clique direto no elemento. O site rola a página com animação (scroll-behavior: smooth) e, a 320 px, o clique "de verdade" do
    Playwright tenta antes de a rolagem acabar e desiste por tempo. O que este teste confere é o selo, não a rolagem."""
    await alvo.evaluate("(e) => e.click()")


async def foto_da_pagina_inteira(pg, caminho):
    """Foto da página inteira. Ela junta a página toda numa imagem só, e a barra "Sua lista / Ver cupom", que no celular fica FIXA
    colada na base da janela (e acompanha a rolagem), sairia desenhada no meio da imagem, parecendo fora do lugar. Por isso a barra
    some da foto. (A posição dela na janela é conferida pela foto só da janela; no site ela está certa.)"""
    await pg.add_style_tag(content="#barraMovel { display: none !important; }")
    imagem = await pg.screenshot(full_page=True)
    try:
        caminho.write_bytes(imagem)
    except OSError as erro:                  # a foto é só para a pessoa olhar: no Windows a gravação às vezes falha, e isso não é defeito do site
        print(f"AVISO: não consegui gravar a foto {caminho.name}: {erro}", flush=True)


def limpo(texto):
    return " ".join(texto.replace("\xa0", " ").split())


def quadro(pg, produto, mercado):
    return pg.locator("article.produto").nth(produto).locator("li.pilula", has_text=mercado)


CONTRASTE = """(el) => {
  const canal = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = (r, g, b) => 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
  const cor = (s) => { const m = s.match(/[\\d.]+/g).map(Number); return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
  const fundoDe = (e) => { while (e) { const c = cor(getComputedStyle(e).backgroundColor); if (c.a > 0) return { e, c }; e = e.parentElement; } return { c: { r: 255, g: 255, b: 255, a: 1 } }; };
  const sobre = (de, base) => ({ r: de.r * de.a + base.r * (1 - de.a), g: de.g * de.a + base.g * (1 - de.a), b: de.b * de.a + base.b * (1 - de.a) });
  let fundo = cor(getComputedStyle(el).backgroundColor), base = fundoDe(el.parentElement).c;
  const f = fundo.a > 0 ? (fundo.a < 1 ? sobre(fundo, base) : fundo) : base;
  const t = cor(getComputedStyle(el).color);
  const l1 = lum(t.r, t.g, t.b), l2 = lum(f.r, f.g, f.b);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}"""


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        for rotulo, vp, mobile in (("celular", {"width": 390, "height": 800}, True), ("celular-estreito", {"width": 320, "height": 700}, True), ("desktop", {"width": 1280, "height": 900}, False)):
            print(f"\n===== {rotulo} =====")
            ctx, pg = await abrir(nav, vp, mobile)

            # --- 1. o selo aparece onde o preço caiu
            q = quadro(pg, 0, "Supernosso")
            confere(await q.locator(".queda").count() == 1, "Becel: o Supernosso (mais barato, caiu 47%) leva o selo")
            confere(limpo(await q.locator(".queda").inner_text()) == "↓ Caiu 47% em 7 dias", f"texto do selo: «{limpo(await q.locator('.queda').inner_text())}»")
            confere(limpo(await q.locator(".era").inner_text()) == "Era R$ 14,99", f"preço de antes: «{limpo(await q.locator('.era').inner_text())}»")
            confere("menor" in await q.get_attribute("class"), "o quadro do mais barato continua com a placa amarela (e o selo não o tira dali)")
            confere(limpo(await quadro(pg, 0, "Apoio").locator(".queda").inner_text()) == "↓ Caiu 15% em 7 dias", "Becel: o Apoio também caiu, e mostra o dele (15%)")
            confere(await quadro(pg, 0, "Atacadão").locator(".queda").count() == 0, "Becel: o Atacadão não caiu e não leva selo")
            confere(await quadro(pg, 1, "Supernosso").locator(".queda").count() == 1 and "menor" not in await quadro(pg, 1, "Supernosso").get_attribute("class"),
                    "Qualy: o selo aparece mesmo quando quem caiu não é o mais barato")
            confere(limpo(await quadro(pg, 2, "Atacadão").locator(".queda").inner_text()) == "↓ Caiu 17% em 7 dias", "Delícia: a API dizia 99%; o site refaz a conta com os preços da tela e mostra 17%")
            confere(await quadro(pg, 2, "Supernosso").locator(".queda").count() == 0, "Delícia: o Supernosso não tem marca, não tem selo")
            confere(await pg.locator("article.produto").nth(3).locator(".queda").count() == 0, "Primor: marca velha (o preço de hoje é maior que o de antes) não gera selo")
            confere(await pg.locator(".queda").count() == 4, f"na tela inteira há exatamente 4 selos: {await pg.locator('.queda').count()}")
            confere(await pg.locator(".queda span[aria-hidden='true']").count() == 4, "a seta é enfeite: some para o leitor de tela, que ouve só o texto")

            # --- 2. legível e sem estourar o quadro
            for alvo, nome in ((quadro(pg, 0, "Supernosso").locator(".queda"), "no quadro amarelo (o mais barato)"), (quadro(pg, 0, "Apoio").locator(".queda"), "no quadro branco")):
                razao = await alvo.evaluate(CONTRASTE)
                confere(razao >= 4.5, f"contraste do selo {nome}: {razao:.1f}:1 (mínimo 4,5:1)")
            for alvo, nome in ((quadro(pg, 0, "Supernosso").locator(".era"), "«Era R$…» no quadro amarelo"), (quadro(pg, 0, "Apoio").locator(".era"), "«Era R$…» no quadro branco")):
                razao = await alvo.evaluate(CONTRASTE)
                confere(razao >= 4.5, f"contraste de {nome}: {razao:.1f}:1 (mínimo 4,5:1)")
            estouros = await pg.evaluate("() => [...document.querySelectorAll('.pilula')].filter((e) => e.scrollWidth > e.clientWidth + 1).length")
            confere(estouros == 0, f"nenhum quadro de mercado estoura a largura ({estouros})")
            # (não confere a página inteira: a 320 px o botão do CEP do cabeçalho já passa da borda, com ou sem selo; aqui importa o que o selo mexe)
            fora = await pg.evaluate("() => [...document.querySelectorAll('.produtos *, #cupom *')].filter((e) => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).length")
            confere(fora == 0, f"nada dos resultados nem do cupom passa da borda da tela ({fora} elementos)")
            await foto_da_pagina_inteira(pg, SAIDA / f"queda-{rotulo}-1-resultados.png")

            # --- 3. cupom: a linha do item que caiu leva o selo; escolher o mercado que não caiu tira o selo
            await clicar(pg.locator("article.produto").nth(0).locator("[data-add]"))
            await pg.locator("#cupom .linha").first.wait_for()
            await clicar(pg.locator("[data-mercado='Supernosso']"))
            await pg.wait_for_timeout(300)
            linha = pg.locator("#cupom .linha").first
            confere(limpo(await linha.locator(".queda-linha").inner_text()) == "↓ Caiu 47% em 7 dias (era R$ 14,99)", f"cupom do Supernosso: «{limpo(await linha.locator('.queda-linha').inner_text())}»")
            await foto_da_pagina_inteira(pg, SAIDA / f"queda-{rotulo}-2-cupom.png")
            await clicar(pg.locator("[data-mercado='Atacadao']"))
            await pg.wait_for_timeout(300)
            confere(await pg.locator("#cupom .queda-linha").count() == 0, "cupom do Atacadão (que não caiu): sem selo")

            # --- 4. preço de atacado: o selo é do varejo, então não aparece quando o cupom cobra o de atacado
            await clicar(pg.locator("article.produto").nth(1).locator("[data-add]"))
            await clicar(pg.locator("[data-mercado='Supernosso']"))
            await pg.wait_for_timeout(300)
            confere(await pg.locator("#cupom .queda-linha").count() == 2, "Qualy no cupom do Supernosso, 1 unidade (preço de varejo): selo nas duas linhas")
            for _ in range(5):                                                                  # 6 unidades: entra o preço de atacado
                await clicar(pg.locator("#cupom [data-lmais]").nth(1))
                await pg.wait_for_timeout(120)
            confere("atacado" in limpo(await pg.locator("#cupom .linha").nth(1).locator(".un").inner_text()), "com 6 unidades o cupom cobra o preço de atacado")
            confere(await pg.locator("#cupom .queda-linha").count() == 1, "linha cobrada no atacado: sem selo (a queda era do varejo); a do Becel continua")
            await ctx.close()

            # --- 5. modo equivalente: o quadro mostra o mais barato da família em cada mercado, e o selo é DESSE produto
            ctx, pg = await abrir(nav, vp, mobile)
            await clicar(pg.locator('.modo button[data-modo="equivalente"]'))
            await pg.wait_for_timeout(500)
            familia = pg.locator("article.produto", has=pg.locator("h3", has_text=ROTULO))
            confere(await familia.count() == 1, f"modo equivalente: um cartão «{ROTULO}»: {await familia.count()}")
            quadro_f = lambda mercado: familia.locator("li.pilula", has_text=mercado)
            confere(await quadro_f("Supernosso").locator(".queda").count() == 0, "equivalente, Supernosso: o mais barato é a Delícia (sem marca); o selo do Becel (47%) não vale aqui")
            confere(limpo(await quadro_f("Atacadão").locator(".queda").inner_text()) == "↓ Caiu 17% em 7 dias", "equivalente, Atacadão: o mais barato é a Delícia, e o selo dela aparece")
            confere(await quadro_f("Apoio").locator(".queda").count() == 0, "equivalente, Apoio: o mais barato é a Qualy (sem marca); o selo do Becel (15%) não vale aqui")
            await foto_da_pagina_inteira(pg, SAIDA / f"queda-{rotulo}-3-equivalente.png")
            await ctx.close()

            # --- 6. API sem a marca (antiga, ou histórico fora do ar): nada de selo e nenhum erro
            ctx, pg = await abrir(nav, vp, mobile, com_selo=False)
            confere(await pg.locator(".queda").count() == 0 and await pg.locator(".era").count() == 0, "sem a marca da API: nenhum selo na tela")
            await clicar(pg.locator("article.produto").nth(0).locator("[data-add]"))
            await pg.locator("#cupom .linha").first.wait_for()
            confere(await pg.locator("#cupom .queda-linha").count() == 0, "sem a marca da API: nenhum selo no cupom")
            await ctx.close()
        await nav.close()


if __name__ == "__main__":
    asyncio.run(rodar())
    print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
    for f in falhas:
        print("  -", f)
    sys.exit(1 if falhas else 0)
