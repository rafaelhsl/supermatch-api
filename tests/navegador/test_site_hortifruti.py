"""Preço por quilo no site (docs/hortifruti.md): "R$ 7,99/kg" no quadro do mercado, "2 kg na lista" no cartão e "2 kg × R$ 7,99/kg" no cupom.
Produto comum (pacote, unidade, ou API sem o campo `unidade`) continua exatamente como era.

Teste de ponta a ponta no navegador, com a API de mentira (a `unidade` vem pronta, como a API a mandaria). A regra que decide quando um
preço é por quilo é testada em tests/test_unidade.js; a que grava e devolve a unidade, em tests/test_carga.py e tests/test_api_catalogo.py.

Rodar com:  python tests/navegador/test_site_hortifruti.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import sys
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from _comum import SAIDA, URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0
HOJE = "2026-11-18T10:44:50+00:00"
MERCADOS = ["Apoio Entrega", "Atacadao", "Supernosso", "Super ABC"]


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


def opcao(mercado, nome, varejo, ean, unidade=None, chave=None, rotulo=None):
    o = {"supermercado": mercado, "nome": nome, "preco_varejo": varejo, "preco_atacado": varejo, "quantidade_atacado": 1,
         "atualizado_em": HOJE, "id": f"{mercado}-{ean}", "termo": "teste", "ean": ean}
    if unidade is not None:
        o["unidade"] = unidade
    if chave:
        o["chave_equivalencia"], o["rotulo_equivalencia"] = chave, rotulo
    return o


def grupo(base, ean, *opcoes):
    return {"produto_base": base, "ean": ean, "id_do_grupo": ean, "vencedor_preco_baixo": min(opcoes, key=lambda o: o["preco_varejo"])["supermercado"], "opcoes_de_compra": list(opcoes)}


BANANA, ROTULO_BANANA = "hortifruti|banana|prata|1000g", "Banana prata, 1 kg"


def resposta(com_unidade=True):
    u = (lambda v: v) if com_unidade else (lambda v: None)
    grupos = [
        # 0. tomate: o preço é por quilo nos dois mercados (o nome cita a bandeja de 500 g, mas R$ 7,99 é do quilo)
        grupo("Tomate Italiano 500g", "t1",
              opcao("Supernosso", "Tomate Italiano 500g", 7.99, "t1", u("kg")),
              opcao("Atacadao", "Tomate Italiano 500g", 6.49, "t1", u("kg"))),
        # 1. produto comum, com a mesma unidade "un" dos pacotes: nada muda
        grupo("Detergente Ypê Neutro 500ml", "d1",
              opcao("Supernosso", "Detergente Ypê Neutro 500ml", 2.99, "d1", u("un")),
              opcao("Atacadao", "Detergente Ypê Neutro 500ml", 2.79, "d1", u("un")),
              opcao("Apoio Entrega", "Detergente Ypê Neutro 500ml", 3.1, "d1")),
        # 2. alface vendida por unidade (`un`): é por unidade, não por quilo
        grupo("Alface Crespa Unidade", "a1",
              opcao("Supernosso", "Alface Crespa Unidade", 3.49, "a1", u("un")),
              opcao("Atacadao", "Alface Crespa Unidade", 2.99, "a1", u("un"))),
        # 3. família de banana: um mercado vende por quilo, o outro a bandeja de 1 kg (preço do pacote, que é o mesmo quilo)
        grupo("Banana Prata Sn 800g", "b1", opcao("Supernosso", "Banana Prata Sn 800g", 5.99, "b1", u("kg"), BANANA, ROTULO_BANANA)),     # por quilo: o 800g é o da porção
        grupo("Banana Prata Bandeja 1Kg", "b2", opcao("Atacadao", "Banana Prata Bandeja 1Kg", 6.49, "b2", u("un"), BANANA, ROTULO_BANANA)),
        # 4. o robô do Super ABC não informa a unidade: sem `unidade`, é como está
        grupo("Cenoura Pacote 1kg", "c1", opcao("Supernosso", "Cenoura Pacote 1kg", 4.5, "c1"), opcao("Atacadao", "Cenoura Pacote 1kg", 4.2, "c1")),
    ]
    return {"status": "sucesso", "cep": "x", "uf": "MG", "item": "teste", "mercados_consultados": MERCADOS, "equivalencia_familias": ["hortifruti"], "carrinho_comparativo": grupos}


async def abrir(nav, vp, mobile, com_unidade=True):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)

    async def api(rota):
        cab = {"access-control-allow-origin": "*"}
        if urlparse(rota.request.url).path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", headers=cab, body="{}")
        await rota.fulfill(status=200, content_type="application/json", headers=cab, body=json.dumps(resposta(com_unidade)))

    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }", {"sm_cep": json.dumps("30130010"), "sm_cidade": json.dumps("Belo Horizonte/MG")})
    await pg.reload()
    await pg.fill("#campoBusca", "teste")
    await pg.press("#campoBusca", "Enter")
    await pg.wait_for_selector(".produto", timeout=15000)
    return ctx, pg


async def clicar(alvo):
    """Clique direto no elemento (a rolagem animada da página faz o clique "de verdade" do Playwright desistir por tempo; aqui importa o texto, não a rolagem)."""
    await alvo.evaluate("(e) => e.click()")


async def foto_da_pagina_inteira(pg, caminho):
    """Foto da página inteira, sem a barra fixa do celular (que sairia desenhada no meio da imagem)."""
    await pg.add_style_tag(content="#barraMovel { display: none !important; }")
    imagem = await pg.screenshot(full_page=True)
    try:
        caminho.write_bytes(imagem)
    except OSError as erro:                  # a foto é só para a pessoa olhar: no Windows a gravação às vezes falha, e isso não é defeito do site
        print(f"AVISO: não consegui gravar a foto {caminho.name}: {erro}", flush=True)


def limpo(texto):
    return " ".join(texto.replace("\xa0", " ").split())


async def contas_do_cupom(pg):
    """A primeira linha do cabeçalho do cupom: "2 itens, 1 unidade e 1 kg"."""
    return limpo((await pg.locator("#cupom .meta").inner_text()).split("\n")[0])


def cartao(pg, base):
    return pg.locator("article.produto", has=pg.locator("h3", has_text=base))


def quadro(pg, base, mercado):
    return cartao(pg, base).locator("li.pilula", has_text=mercado)


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

            # --- 1. o quadro do mercado: "/kg" só onde o preço é por quilo
            q = quadro(pg, "Tomate Italiano", "Supernosso")
            confere(limpo(await q.locator(".valor").inner_text()) == "R$ 7,99/kg", f"tomate no Supernosso: «{limpo(await q.locator('.valor').inner_text())}»")
            confere(limpo(await quadro(pg, "Tomate Italiano", "Atacadão").locator(".valor").inner_text()) == "R$ 6,49/kg", "tomate no Atacadão: R$ 6,49/kg")
            confere(await cartao(pg, "Tomate Italiano").locator(".por").count() == 2, "tomate: os dois quadros dizem /kg")
            confere(await cartao(pg, "Detergente").locator(".por").count() == 0, "detergente (un): sem /kg")
            confere(limpo(await quadro(pg, "Detergente", "Supernosso").locator(".valor").inner_text()) == "R$ 2,99", "detergente: o preço é só o preço")
            confere(await cartao(pg, "Alface").locator(".por").count() == 0, "alface por unidade (un): sem /kg")
            confere(await cartao(pg, "Cenoura").locator(".por").count() == 0, "cenoura sem `unidade` (como o robô do Super ABC manda): sem /kg")
            donos = await pg.evaluate("() => [...new Set([...document.querySelectorAll('.por')].map((e) => e.closest('article.produto').querySelector('h3').textContent.trim()))].sort()")
            confere(all(d.startswith(("Tomate", "Banana")) for d in donos) and any(d.startswith("Tomate") for d in donos), f"o «/kg» só aparece nos cartões de preço por quilo (tomate e banana): {donos}")

            # --- 2. legível e sem estourar o quadro (quadro amarelo = o mais barato; branco = os outros)
            amarelo = quadro(pg, "Tomate Italiano", "Atacadão")
            confere("menor" in await amarelo.get_attribute("class"), "o Atacadão (R$ 6,49) é o mais barato do tomate: quadro amarelo")
            for alvo, nome in ((amarelo.locator(".por"), "no quadro amarelo"), (quadro(pg, "Tomate Italiano", "Supernosso").locator(".por"), "no quadro branco")):
                razao = await alvo.evaluate(CONTRASTE)
                confere(razao >= 4.5, f"contraste do «/kg» {nome}: {razao:.1f}:1 (mínimo 4,5:1)")
            estouros = await pg.evaluate("() => [...document.querySelectorAll('.pilula')].filter((e) => e.scrollWidth > e.clientWidth + 1).length")
            confere(estouros == 0, f"nenhum quadro de mercado estoura a largura ({estouros})")
            fora = await pg.evaluate("() => [...document.querySelectorAll('.produtos *, #cupom *')].filter((e) => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).length")
            confere(fora == 0, f"nada dos resultados nem do cupom passa da borda da tela ({fora} elementos)")
            await foto_da_pagina_inteira(pg, SAIDA / f"hortifruti-{rotulo}-1-resultados.png")

            # --- 3. o cartão: "1 kg na lista" e os rótulos dos botões
            tomate, detergente = cartao(pg, "Tomate Italiano"), cartao(pg, "Detergente")
            confere(limpo(await tomate.locator("h3").inner_text()) == "Tomate Italiano", f"título do tomate por quilo, sem o «500g» da porção: «{limpo(await tomate.locator('h3').inner_text())}»")
            confere(limpo(await detergente.locator("h3").inner_text()) == "Detergente Ypê Neutro 500ml", "título do detergente: o peso do produto comum fica")
            confere(limpo(await cartao(pg, "Cenoura").locator("h3").inner_text()) == "Cenoura Pacote 1kg", "título da cenoura sem `unidade`: o nome inteiro")
            await clicar(tomate.locator("[data-add]"))
            await clicar(detergente.locator("[data-add]"))
            await pg.locator("#cupom .linha").first.wait_for()
            confere(limpo(await tomate.get_by_text("na lista").first.inner_text()) == "1 kg na lista", "cartão do tomate: «1 kg na lista»")
            confere(limpo(await detergente.get_by_text("na lista").first.inner_text()) == "1 na lista", "cartão do detergente: «1 na lista», sem kg")
            confere(await tomate.locator("button[aria-label='Tirar 1 kg de Tomate Italiano']").count() == 1, "botão − do tomate: «Tirar 1 kg de Tomate Italiano» (sem o 500g)")
            confere(await tomate.locator("button[aria-label='Colocar mais 1 kg de Tomate Italiano']").count() == 1, "botão + do tomate: «Colocar mais 1 kg de…»")
            confere(await detergente.locator("button[aria-label='Tirar uma unidade de Detergente Ypê Neutro 500ml']").count() == 1, "botão − do detergente: o texto de sempre («uma unidade»)")
            confere(await detergente.locator("button[aria-label='Colocar mais uma unidade de Detergente Ypê Neutro 500ml']").count() == 1, "botão + do detergente: o texto de sempre")

            # --- 4. o cupom: a linha do tomate conta em quilos; a do detergente, como sempre
            await clicar(pg.locator("[data-mercado='Supernosso']"))
            await pg.wait_for_timeout(300)
            lt, ld = pg.locator("#cupom .linha").nth(0), pg.locator("#cupom .linha").nth(1)
            confere("Tomate Italiano 500g" not in limpo(await pg.locator("#cupom").inner_text()) and "Tomate Italiano" in limpo(await lt.inner_text()), "cupom: o tomate por quilo aparece sem o «500g»")
            confere("sai da pesagem" in limpo(await pg.locator("#cupom").inner_text()), "cupom com item por quilo: avisa que o valor final sai da pesagem")
            confere(await contas_do_cupom(pg) == "2 itens, 1 unidade e 1 kg", f"cabeçalho do cupom com 1 kg de tomate e 1 detergente: «{await contas_do_cupom(pg)}»")
            confere(limpo(await lt.locator(".un").inner_text()) == "1 kg × R$ 7,99/kg", f"cupom, tomate, 1 kg: «{limpo(await lt.locator('.un').inner_text())}»")
            confere(limpo(await lt.locator("output").inner_text()) == "1 kg", f"cupom, tomate, controle: «{limpo(await lt.locator('output').inner_text())}»")
            confere(limpo(await ld.locator("output").inner_text()) == "1" and limpo(await ld.locator(".un").inner_text()) == "", "cupom, detergente, 1: «1» e sem texto embaixo, como antes")
            await clicar(lt.locator("[data-lmais]"))
            await pg.wait_for_timeout(200)
            lt = pg.locator("#cupom .linha").nth(0)
            confere(limpo(await lt.locator(".un").inner_text()) == "2 kg × R$ 7,99/kg", f"cupom, tomate, 2 kg: «{limpo(await lt.locator('.un').inner_text())}»")
            confere(limpo(await lt.locator(".valor").inner_text()) == "R$ 15,98", f"cupom, tomate, 2 kg = R$ 15,98: «{limpo(await lt.locator('.valor').inner_text())}»")
            confere(limpo(await pg.locator("#cupom .total strong").inner_text()) == "R$ 18,97", f"total no Supernosso (2 × 7,99 + 2,99): «{limpo(await pg.locator('#cupom .total strong').inner_text())}»")
            confere(await lt.locator("button[aria-label='Tirar 1 kg de Tomate Italiano']").count() == 1, "cupom: botão − do tomate diz «Tirar 1 kg de…»")
            await clicar(detergente.locator("[data-mais]"))
            await pg.wait_for_timeout(200)
            ld = pg.locator("#cupom .linha").nth(1)
            confere(await contas_do_cupom(pg) == "2 itens, 2 unidades e 2 kg", f"cabeçalho do cupom com 2 kg de tomate e 2 detergentes: «{await contas_do_cupom(pg)}»")
            confere(limpo(await ld.locator(".un").inner_text()) == "2 × R$ 2,99", f"cupom, detergente, 2: «{limpo(await ld.locator('.un').inner_text())}» (como antes)")
            await foto_da_pagina_inteira(pg, SAIDA / f"hortifruti-{rotulo}-2-cupom.png")

            # --- 5. no mercado que não vende o item o cupom continua falando em quilos; no outro, o preço do quilo dele
            await clicar(pg.locator("[data-mercado='Atacadao']"))
            await pg.wait_for_timeout(300)
            confere(limpo(await pg.locator("#cupom .linha").nth(0).locator(".un").inner_text()) == "2 kg × R$ 6,49/kg", "cupom do Atacadão: 2 kg × R$ 6,49/kg")
            await clicar(pg.locator("[data-mercado='Apoio Entrega']"))
            await pg.wait_for_timeout(300)
            falta = pg.locator("#cupom .linha.falta")
            confere(await falta.count() == 1 and "Tomate" in await falta.inner_text(), "cupom do Apoio: o tomate aparece como «sem preço» (o Apoio não o vende)")
            confere(await falta.locator("button[aria-label='Tirar 1 kg de Tomate Italiano']").count() == 1, "linha «sem preço» do tomate: os botões também falam em quilos")
            await ctx.close()

            # --- 6. modo equivalente: banana por quilo (Supernosso) e a bandeja de 1 kg (Atacadão) na mesma família
            ctx, pg = await abrir(nav, vp, mobile)
            await clicar(pg.locator('.modo button[data-modo="equivalente"]'))
            await pg.wait_for_timeout(500)
            banana = cartao(pg, ROTULO_BANANA)
            confere(await banana.count() == 1, f"modo equivalente: um cartão «{ROTULO_BANANA}»: {await banana.count()}")
            confere(limpo(await banana.locator("li.pilula", has_text="Supernosso").locator(".valor").inner_text()) == "R$ 5,99/kg", "banana, Supernosso (por quilo): R$ 5,99/kg")
            confere(limpo(await banana.locator("li.pilula", has_text="Supernosso").locator(".real").inner_text()) == "Banana Prata Sn", "modo equivalente, produto por quilo: o nome do mercado sai sem o «800g» da porção")
            confere(limpo(await banana.locator("li.pilula", has_text="Atacadão").locator(".real").inner_text()) == "Banana Prata Bandeja 1kg", "modo equivalente, bandeja (pacote): o peso do pacote fica")
            confere(limpo(await banana.locator("li.pilula", has_text="Atacadão").locator(".valor").inner_text()) == "R$ 6,49", "banana, Atacadão (bandeja de 1 kg): R$ 6,49, sem /kg (é o preço do pacote)")
            await clicar(banana.locator("[data-add]"))
            await pg.locator("#cupom .linha").first.wait_for()
            confere("1 kg na lista" in limpo(await banana.inner_text()), "cartão da banana: «1 kg na lista»")
            confere(await contas_do_cupom(pg) == "1 item, 1 kg", f"cabeçalho do cupom só com 1 kg de banana: «{await contas_do_cupom(pg)}»")
            await clicar(pg.locator("[data-mercado='Atacadao']"))
            await pg.wait_for_timeout(300)
            confere(limpo(await pg.locator("#cupom .linha").nth(0).locator(".un").inner_text()) == "1 kg × R$ 6,49/kg", "cupom do Atacadão (bandeja de 1 kg): 1 kg × R$ 6,49/kg")
            await clicar(pg.locator("[data-mercado='Supernosso']"))
            await pg.wait_for_timeout(300)
            confere("Leva: Banana Prata Sn" in limpo(await pg.locator("#cupom .linha").nth(0).inner_text()) and "800g" not in limpo(await pg.locator("#cupom .linha").nth(0).inner_text()),
                    "cupom no Supernosso, modo equivalente: «Leva: Banana Prata Sn», sem o peso da porção")
            await foto_da_pagina_inteira(pg, SAIDA / f"hortifruti-{rotulo}-3-equivalente.png")
            await ctx.close()

            # --- 7. API sem o campo `unidade` (antiga): o site é o de sempre, sem erro
            ctx, pg = await abrir(nav, vp, mobile, com_unidade=False)
            confere(await pg.locator(".por").count() == 0, "sem `unidade` na API: nenhum /kg na tela")
            await clicar(cartao(pg, "Tomate Italiano").locator("[data-add]"))
            await pg.locator("#cupom .linha").first.wait_for()
            confere("1 na lista" in limpo(await cartao(pg, "Tomate Italiano").inner_text()) and "kg na lista" not in limpo(await cartao(pg, "Tomate Italiano").inner_text()), "sem `unidade`: «1 na lista»")
            await clicar(pg.locator("[data-mercado='Supernosso']"))
            await pg.wait_for_timeout(300)
            confere(limpo(await pg.locator("#cupom .linha").nth(0).locator(".un").inner_text()) == "", "sem `unidade`: o cupom não escreve nada embaixo de 1 unidade")
            confere(await contas_do_cupom(pg) == "1 item, 1 unidade", f"sem `unidade`: o cabeçalho do cupom é o de sempre: «{await contas_do_cupom(pg)}»")
            confere("sai da pesagem" not in limpo(await pg.locator("#cupom").inner_text()), "sem `unidade`: nenhum aviso de pesagem")
            confere(limpo(await cartao(pg, "Tomate Italiano").locator("h3").inner_text()) == "Tomate Italiano 500g", "sem `unidade`: o título é o nome inteiro, com o 500g")
            await ctx.close()
        await nav.close()


if __name__ == "__main__":
    asyncio.run(rodar())
    print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
    for f in falhas:
        print("  -", f)
    sys.exit(1 if falhas else 0)
