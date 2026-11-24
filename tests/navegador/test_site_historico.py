"""Gráfico do histórico de preços no site: o botão do cartão, a janela, o desenho (linhas em degraus, pontas, rótulos), o quadro de preços do mouse
e do teclado, a tabela, os estados (carregando, erro, sem histórico) e o respeito à privacidade (o pedido do gráfico não leva o CEP).

Teste de ponta a ponta no navegador, com a API de mentira: o próprio teste responde a /comparar (produtos com `chave_historico`, como a API os manda) e a
/historico (os intervalos de preço). As contas do gráfico estão em tests/test_historico_grafico.js; a API real, em tests/test_serie_de_precos.py.

Rodar com:  python tests/navegador/test_site_historico.py   (precisa do Playwright e do Chromium: veja docs/testes.md)
"""
import asyncio
import json
import os
import re
import sys
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

from _comum import SAIDA, URL  # noqa: E402  (tests/navegador/_comum.py)

falhas, ok = [], 0
HOJE_ISO = "2026-11-24"
HOJE = "2026-11-24T10:44:50+00:00"
MERCADOS = ["Apoio Entrega", "Atacadao", "Supernosso", "Super ABC"]
CORES = {"Apoio Entrega": "rgb(42, 120, 214)", "Atacadao": "rgb(235, 104, 52)", "Supernosso": "rgb(98, 80, 214)", "Super ABC": "rgb(27, 175, 122)"}
CHAVE_ABC = "n:0123456789abcdef0123"


def confere(cond, texto):
    global ok
    if cond:
        ok += 1
    else:
        falhas.append(texto)
    print(("OK    " if cond else "FALHA ") + texto, flush=True)


def opcao(mercado, nome, varejo, ean, chave=None, unidade=None, familia=False):
    o = {"supermercado": mercado, "nome": nome, "preco_varejo": varejo, "preco_atacado": varejo, "quantidade_atacado": 1, "atualizado_em": HOJE,
         "id": f"{mercado}-{ean}", "termo": "arroz", "ean": ean}
    if familia:
        o["chave_equivalencia"], o["rotulo_equivalencia"] = "arroz|5kg", "Arroz, 5 kg"
    if chave:
        o["chave_historico"] = chave
    if unidade:
        o["unidade"] = unidade
    return o


def grupo(base, ean, *opcoes):
    return {"produto_base": base, "ean": ean, "id_do_grupo": ean, "vencedor_preco_baixo": min(opcoes, key=lambda o: o["preco_varejo"])["supermercado"], "opcoes_de_compra": list(opcoes)}


# A chave do histórico de cada mercado em cada produto, e os intervalos de preço que a API de mentira devolve para ela.
H = {
    ("Atacadao", "v:100:1"): [{"desde": "2026-11-04", "ate": "2026-11-11", "preco": 24.99}, {"desde": "2026-11-12", "ate": None, "preco": 22.5}],
    ("Supernosso", "v:200:2"): [{"desde": "2026-11-04", "ate": None, "preco": 24.99}],
    ("Apoio Entrega", "v:300:3"): [{"desde": "2026-11-04", "ate": "2026-11-19", "preco": 20.0}, {"desde": "2026-11-20", "ate": None, "preco": 21.99}],
    ("Super ABC", CHAVE_ABC): [{"desde": "2026-11-06", "ate": "2026-11-09", "preco": 23.0}, {"desde": "2026-11-15", "ate": None, "preco": 22.5}],   # com buraco; termina no mesmo preço do Atacadão
    ("Atacadao", "v:400:4"): [{"desde": "2026-11-18", "ate": None, "preco": 3.79}],                          # banana por quilo, sem mudança
    ("Supernosso", "v:500:5"): [{"desde": "2026-11-18", "ate": None, "preco": 4.99}],
    ("Atacadao", "v:600:6"): [], ("Supernosso", "v:700:7"): [],                                            # produto sem histórico nenhum
    ("Atacadao", "v:800:8"): [{"desde": "2026-11-04", "ate": None, "preco": 9.9}], ("Supernosso", "v:810:8"): [{"desde": "2026-11-04", "ate": None, "preco": 9.5}],   # o do pedido que falha
    ("Atacadao", "v:900:9"): [{"desde": "2026-11-04", "ate": None, "preco": 5.0}], ("Supernosso", "v:910:9"): [{"desde": "2026-11-04", "ate": None, "preco": 6.0}],   # o do pedido lento
    ("Atacadao", "v:950:10"): [{"desde": "2026-11-04", "ate": None, "preco": 4.0}], ("Supernosso", "v:960:10"): [{"desde": "2026-11-04", "ate": None, "preco": 4.5}],   # o aberto logo depois de fechar outro
}


def resposta_comparar(com_chave=True):
    c = (lambda k: k) if com_chave else (lambda k: None)
    grupos = [
        grupo("Arroz Camil 5kg", "7891000000001",
              opcao("Atacadao", "Arroz Camil 5kg", 22.5, "7891000000001", c("v:100:1"), familia=True),
              opcao("Supernosso", "Arroz Camil 5kg", 24.99, "7891000000001", c("v:200:2"), familia=True),
              opcao("Apoio Entrega", "Arroz Camil 5kg", 21.99, "7891000000001", c("v:300:3"), familia=True),
              opcao("Super ABC", "Arroz Camil 5kg", 22.5, "7891000000001", c(CHAVE_ABC), familia=True)),
        grupo("Feijão Preto 1kg", "7891000000002",                                     # sem chave: sem botão
              opcao("Atacadao", "Feijão Preto 1kg", 7.5, "7891000000002"), opcao("Supernosso", "Feijão Preto 1kg", 7.9, "7891000000002")),
        grupo("Banana Prata 600g", "7891000000003",
              opcao("Atacadao", "Banana Prata 600g", 3.79, "7891000000003", c("v:400:4"), unidade="kg"),
              opcao("Supernosso", "Banana Prata 600g", 4.99, "7891000000003", c("v:500:5"), unidade="kg")),
        grupo("Arroz Sem Historico 1kg", "7891000000004",
              opcao("Atacadao", "Arroz Sem Historico 1kg", 5.5, "7891000000004", c("v:600:6")), opcao("Supernosso", "Arroz Sem Historico 1kg", 5.7, "7891000000004", c("v:700:7"))),
        grupo("Arroz Que Falha 2kg", "7891000000005",
              opcao("Atacadao", "Arroz Que Falha 2kg", 9.9, "7891000000005", c("v:800:8")), opcao("Supernosso", "Arroz Que Falha 2kg", 9.5, "7891000000005", c("v:810:8"))),
        grupo("Arroz Lento 3kg", "7891000000006",
              opcao("Atacadao", "Arroz Lento 3kg", 5.0, "7891000000006", c("v:900:9")), opcao("Supernosso", "Arroz Lento 3kg", 6.0, "7891000000006", c("v:910:9"))),
        grupo("Arroz Rapido 4kg", "7891000000007",
              opcao("Atacadao", "Arroz Rapido 4kg", 4.0, "7891000000007", c("v:950:10")), opcao("Supernosso", "Arroz Rapido 4kg", 4.5, "7891000000007", c("v:960:10"))),
    ]
    return {"status": "sucesso", "cep": "x", "uf": "MG", "item": "arroz", "mercados_consultados": MERCADOS, "equivalencia_familias": ["arroz"], "carrinho_comparativo": grupos}


class ApiDeMentira:
    """Responde a /saude, /comparar e /historico e anota o que o site pediu."""

    def __init__(self, com_chave=True):
        self.com_chave, self.historico, self.comparar = com_chave, [], []
        self.falhar_vezes = {"v:800:8": 1}          # o Arroz Que Falha dá 503 na primeira vez
        self.atraso = {"v:900:9": 1.2}              # o Arroz Lento demora 1,2 s

    async def __call__(self, rota):
        cab = {"access-control-allow-origin": "*"}
        url = urlparse(rota.request.url)
        if url.path.endswith("/saude"):
            return await rota.fulfill(status=200, content_type="application/json", headers=cab, body="{}")
        if url.path.endswith("/comparar"):
            self.comparar.append(rota.request.url)
            return await rota.fulfill(status=200, content_type="application/json", headers=cab, body=json.dumps(resposta_comparar(self.com_chave)))
        if url.path.endswith("/historico"):
            self.historico.append(rota.request.url)
            pares = [p.partition("|")[::2] for p in parse_qs(url.query).get("chaves", [""])[0].split(",")]
            chaves = {c for _, c in pares}
            for c in chaves:
                if self.falhar_vezes.get(c, 0) > 0:
                    self.falhar_vezes[c] -= 1
                    return await rota.fulfill(status=503, content_type="application/json", headers=cab, body=json.dumps({"detail": "O histórico de preços está indisponível agora."}))
            for c in chaves:
                if c in self.atraso:
                    await asyncio.sleep(self.atraso[c])
            produtos = [{"mercado": m, "chave": c, "intervalos": H.get((m, c), [])} for m, c in pares]
            return await rota.fulfill(status=200, content_type="application/json", headers=cab, body=json.dumps({"hoje": HOJE_ISO, "produtos": produtos}))
        await rota.fulfill(status=404, headers=cab, body="")


async def abrir(nav, vp, mobile, api):
    ctx = await nav.new_context(viewport=vp, locale="pt-BR", timezone_id="America/Sao_Paulo", has_touch=mobile, is_mobile=mobile)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: falhas.append(f"pageerror: {e}"))
    pg.on("console", lambda m: falhas.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
    await pg.route("https://supermatch-api.onrender.com/**", api)
    await pg.goto(URL)
    await pg.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }", {"sm_cep": json.dumps("30130010"), "sm_cidade": json.dumps("Belo Horizonte/MG")})
    await pg.reload()
    await pg.fill("#campoBusca", "arroz")
    await pg.press("#campoBusca", "Enter")
    await pg.wait_for_selector(".produto", timeout=15000)
    while await pg.locator("#verMais").count():           # no celular a busca mostra 4 produtos de início
        await clicar(pg.locator("#verMais"))
        await pg.wait_for_timeout(200)
    return ctx, pg


def cartao(pg, nome):
    return pg.locator("article.produto", has=pg.locator("h3", has_text=nome))


async def clicar(alvo):
    """Clique direto no elemento (o site rola com animação, e o clique "de verdade" do Playwright desiste por tempo a 320 px)."""
    await alvo.evaluate("(e) => e.click()")


def limpo(texto):
    return " ".join(texto.replace("\xa0", " ").split())


CONTRASTE = """(el) => {
  const canal = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = (r, g, b) => 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
  const cor = (s) => { const m = s.match(/[\\d.]+/g).map(Number); return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
  const fundoDe = (e) => { while (e) { const c = cor(getComputedStyle(e).backgroundColor); if (c.a > 0) return c; e = e.parentElement; } return { r: 255, g: 255, b: 255, a: 1 }; };
  const t = cor(getComputedStyle(el).color), f = fundoDe(el);
  const l1 = lum(t.r, t.g, t.b), l2 = lum(f.r, f.g, f.b);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}"""


async def abrir_grafico(pg, nome):
    botao = cartao(pg, nome).locator("[data-historico]")
    await botao.focus()                                   # o clique de uma pessoa também põe o foco no botão
    await clicar(botao)
    await pg.wait_for_selector("#janelaHistorico[open]", timeout=5000)


async def esperar_grafico(pg):
    await pg.wait_for_selector("#histPlot .g-svg", timeout=8000)
    await pg.evaluate("() => document.fonts.ready.then(() => 0)")      # a fonte termina de carregar e pode mexer no layout
    await pg.wait_for_timeout(200)                                      # (e o desenho refeito por causa da barra de rolagem)


async def fechar(pg):
    await pg.click("#fecharHistorico")
    await pg.wait_for_selector("#janelaHistorico:not([open])", state="attached", timeout=3000)


async def rodar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        telas = (("celular", {"width": 390, "height": 800}, True), ("celular-estreito", {"width": 320, "height": 700}, True), ("desktop", {"width": 1280, "height": 900}, False))
        if os.environ.get("SM_TELAS"):                       # para depurar: SM_TELAS=desktop roda só essa tela
            telas = tuple(t for t in telas if t[0] in os.environ["SM_TELAS"].split(","))
        for rotulo, vp, mobile in telas:
            print(f"\n===== {rotulo} =====")
            api = ApiDeMentira()
            ctx, pg = await abrir(nav, vp, mobile, api)

            # --- 1. o botão só aparece onde a API mandou a chave do histórico
            confere(await pg.locator("article.produto [data-historico]").count() == 6, f"6 dos 7 produtos têm o botão (o Feijão não tem chave): {await pg.locator('article.produto [data-historico]').count()}")
            confere(await cartao(pg, "Feijão Preto").locator("[data-historico]").count() == 0, "o produto sem chave do histórico fica sem botão")
            botao = cartao(pg, "Camil").locator("[data-historico]")
            confere(limpo(await botao.inner_text()) == "Ver histórico de preços", f"texto do botão: «{limpo(await botao.inner_text())}»")
            confere("Camil" in (await botao.get_attribute("aria-label") or ""), "o botão diz de que produto é o histórico, para o leitor de tela")
            caixa = await botao.bounding_box()
            confere(caixa["height"] >= 40, f"o botão tem altura de toque (≥ 40 px): {caixa['height']:.0f}")
            confere(len(api.historico) == 0, "abrir a busca não chama /historico: só quando a pessoa pede o gráfico")

            # --- 2. abrir o gráfico: o pedido não leva CEP, só o mercado e a chave
            await abrir_grafico(pg, "Camil")
            await esperar_grafico(pg)
            confere(len(api.historico) == 1, f"um pedido a /historico: {len(api.historico)}")
            pedido = api.historico[0]
            consulta = parse_qs(urlparse(pedido).query)
            confere(list(consulta) == ["chaves"], f"o pedido só tem o parâmetro 'chaves': {list(consulta)}")
            confere("30130010" not in pedido and "cep" not in pedido.lower(), "o pedido do gráfico não leva o CEP")
            pares = set(consulta["chaves"][0].split(","))
            confere(pares == {"Apoio Entrega|v:300:3", "Atacadao|v:100:1", "Supernosso|v:200:2", f"Super ABC|{CHAVE_ABC}"}, f"os quatro mercados do cartão, com as chaves dele: {sorted(pares)}")
            confere(await pg.locator("#tituloHistorico").inner_text() == "Histórico de preços" and "Arroz Camil 5kg" in await pg.locator("#histProduto").inner_text(), "o título e o produto")
            confere("em reais" in await pg.locator("#histUnidade").inner_text() and "quilo" not in await pg.locator("#histUnidade").inner_text(), "a unidade do eixo está dita (reais)")

            # --- 3. o desenho
            linhas = pg.locator("#histPlot path.g-linha")
            confere(await linhas.count() == 4, f"uma linha por mercado: {await linhas.count()}")
            cores = [await linhas.nth(i).evaluate("(e) => getComputedStyle(e).stroke") for i in range(4)]
            confere(sorted(cores) == sorted(CORES.values()), f"as linhas usam as cores dos mercados: {cores}")
            confere(await linhas.first.evaluate("(e) => getComputedStyle(e).strokeWidth") == "2px", "linha de 2 px")
            ds = [await linhas.nth(i).get_attribute("d") for i in range(4)]
            confere(all("L" not in d_ for d_ in ds), "nenhuma linha diagonal: só degraus (H e V)")
            confere(sum("V" in d_ for d_ in ds) == 2, f"os dois mercados que mudaram de preço têm degrau (V): {sum('V' in d_ for d_ in ds)}")
            confere(sum(d_.count("M") == 2 for d_ in ds) == 1, "o Super ABC (com buraco) tem dois traços separados")
            fins = pg.locator("#histPlot circle.g-fim")
            confere(await fins.count() == 4, f"uma ponta marcada por mercado: {await fins.count()}")
            confere(float(await fins.first.get_attribute("r")) * 2 >= 8, "marcador da ponta com pelo menos 8 px")
            confere(await fins.first.evaluate("(e) => getComputedStyle(e).strokeWidth") == "2px", "anel de 2 px em volta do marcador")
            rotulos = pg.locator("#histPlot text.g-rotulo")
            textos = sorted([limpo(await rotulos.nth(i).text_content()) for i in range(await rotulos.count())])
            confere(textos == ["21,99", "22,50", "22,50", "24,99"], f"o preço de hoje ao lado de cada ponta: {textos}")
            # (tudo numa chamada só: várias chamadas medem o layout em instantes diferentes)
            medidas = await pg.evaluate("""() => {
              const p = document.querySelector("#histPlot").getBoundingClientRect();
              const r = [...document.querySelectorAll("#histPlot text.g-rotulo")].map((e) => e.getBoundingClientRect());
              return { centros: r.map((b) => b.top + b.height / 2).sort((a, b) => a - b), dentro: r.every((b) => b.left >= p.left - 1 && b.right <= p.right + 1), plot: { x: p.x, width: p.width } };
            }""")
            centros = medidas["centros"]                                                     # (a caixa do texto tem folga em cima e embaixo: o que vale é a distância entre os centros)
            menor_folga = min(b - a for a, b in zip(centros, centros[1:]))
            confere(menor_folga >= 14, f"os rótulos das pontas não se sobrepõem (dois dos quatro têm o mesmo preço): menor distância entre eles {menor_folga:.1f} px")
            plot = medidas["plot"]
            confere(medidas["dentro"], "os rótulos cabem dentro do gráfico (não são cortados)")
            eixo = pg.locator("#histPlot text.g-eixo")
            confere(await eixo.count() >= 4, f"eixos com rótulos: {await eixo.count()}")
            datas = [limpo(await eixo.nth(i).text_content()) for i in range(await eixo.count())]
            confere("24/11" in datas, f"o eixo das datas termina em hoje (24/11): {datas}")
            confere(await pg.locator("#histPlot .g-grade").count() >= 2, "linhas de grade finas")
            confere(await pg.locator("#histPlot .g-svg").get_attribute("aria-hidden") == "true", "o SVG é escondido do leitor de tela (a tabela é o equivalente)")
            svg = await pg.locator("#histPlot .g-svg").bounding_box()
            confere(abs(svg["width"] - plot["width"]) <= 1, f"o desenho ocupa a largura da janela: {svg['width']:.0f} de {plot['width']:.0f}")

            # --- 4. a frase, a legenda e a tabela
            confere(limpo(await pg.locator(".hist-frase").inner_text()) == "A última mudança foi no Apoio Entrega: o preço subiu de R$ 20,00 para R$ 21,99 em 20/11.", f"a frase: «{limpo(await pg.locator('.hist-frase').inner_text())}»")
            leg = [limpo(await pg.locator(".hist-legenda li").nth(i).inner_text()) for i in range(await pg.locator(".hist-legenda li").count())]
            confere(leg == ["Apoio Entrega", "Atacadão", "Supernosso", "Super ABC"], f"a legenda, na ordem fixa dos mercados: {leg}")
            linhas_t = pg.locator(".hist-tabela tbody tr")
            confere(await linhas_t.count() == 4, f"uma linha na tabela por mercado: {await linhas_t.count()}")
            tabela = {}
            for i in range(4):
                nome = limpo(await linhas_t.nth(i).locator("th").inner_text())
                tabela[nome.split(" ")[0] + (" " + nome.split(" ")[1] if nome.startswith(("Apoio", "Super ")) else "")] = [limpo(await linhas_t.nth(i).locator("td").nth(k).inner_text()) for k in range(3)]
            confere(tabela["Atacadão"] == ["22,50", "22,50", "24,99"], f"Atacadão: hoje, menor, maior: {tabela['Atacadão']}")
            confere(tabela["Supernosso"] == ["24,99", "24,99", "24,99"], f"Supernosso (nunca mudou): {tabela['Supernosso']}")
            confere(tabela["Apoio Entrega"] == ["21,99", "20,00", "21,99"], f"Apoio Entrega: {tabela['Apoio Entrega']}")
            confere(tabela["Super ABC"] == ["22,50", "22,50", "23,00"], f"Super ABC: {tabela['Super ABC']}")
            textos_t = limpo(await pg.locator(".hist-tabela").inner_text())
            confere("Última mudança em 12/11" in textos_t and "Não mudou desde 04/11" in textos_t and "Última mudança em 20/11" in textos_t, "a tabela diz quando cada preço mudou ou que não mudou")
            confere(await pg.locator(".hist-tabela caption").count() == 1 and await pg.locator(".hist-tabela th[scope='col']").count() == 4, "tabela com legenda e cabeçalhos de coluna")
            for alvo, nome in ((pg.locator(".hist-frase"), "a frase"), (pg.locator(".hist-tabela small").first, "o texto pequeno da tabela"), (pg.locator(".hist-nota"), "a nota"), (pg.locator("#histUnidade"), "a unidade")):
                razao = await alvo.evaluate(CONTRASTE)
                confere(razao >= 4.5, f"contraste de {nome}: {razao:.1f}:1 (mínimo 4,5:1)")

            # --- 5. o mouse (ou o dedo): linha vertical, pontos e o quadro com os preços de todos os mercados
            area = await pg.locator("#histPlot").bounding_box()
            confere(await pg.locator("#histDica").is_hidden(), "sem o ponteiro no gráfico, não há quadro")
            await pg.mouse.move(area["x"] + area["width"] * 0.5, area["y"] + 60)
            await pg.locator("#histDica").wait_for(state="visible", timeout=2000)
            dica = limpo(await pg.locator("#histDica").inner_text())
            confere(re.search(r"\b\d\d/11\b", dica) is not None and "Atacadão" in dica and "Supernosso" in dica and "Apoio Entrega" in dica and "Super ABC" in dica, f"o quadro lista os quatro mercados: «{dica}»")
            confere(await pg.locator("#gMira").get_attribute("visibility") == "visible", "a linha vertical acompanha o ponteiro")
            confere(await pg.locator("#histDica").evaluate("(e) => { const p = e.parentElement.getBoundingClientRect(), b = e.getBoundingClientRect(); return b.left >= p.left - 1 && b.right <= p.right + 1; }"), "o quadro cabe dentro do gráfico")
            # perto do começo: o Super ABC e o Atacadão ainda não tinham registro/mudança
            await pg.mouse.move(area["x"] + 45, area["y"] + 60)
            await pg.wait_for_timeout(150)
            antes = limpo(await pg.locator("#histDica").inner_text())
            confere("04/11" in antes and "R$ 24,99" in antes and "sem registro" in antes, f"em 04/11 o Atacadão custava R$ 24,99 e o Super ABC ainda não tinha registro: «{antes}»")
            pontos_visiveis = await pg.locator("#histPlot .g-ponto[visibility='visible']").count()
            confere(pontos_visiveis == 3, f"em 04/11 só três mercados têm ponto no gráfico: {pontos_visiveis}")
            # no fim: o quadro passa para a esquerda da linha
            await pg.mouse.move(area["x"] + area["width"] - 40, area["y"] + 60)
            await pg.wait_for_timeout(150)
            confere("(hoje)" in limpo(await pg.locator("#histDica").inner_text()) and "R$ 22,50" in limpo(await pg.locator("#histDica").inner_text()), "no último dia o quadro diz 'hoje' e traz os preços de hoje")
            confere(await pg.locator("#histDica").evaluate("(e) => { const p = e.parentElement.getBoundingClientRect(), b = e.getBoundingClientRect(); return b.left >= p.left - 1 && b.right <= p.right + 1; }"), "no fim do gráfico o quadro continua dentro dele")
            await pg.mouse.move(5, 5)
            await pg.wait_for_timeout(150)
            confere(await pg.locator("#histDica").is_hidden(), "o mouse saiu do gráfico: o quadro some")
            await pg.screenshot(path=str(SAIDA / f"historico-{rotulo}-1-janela.png"))

            # --- 6. o teclado
            await pg.focus("#fecharHistorico")
            await pg.keyboard.press("Tab")
            await pg.wait_for_timeout(150)
            confere(await pg.evaluate("() => document.activeElement.id") == "histPlot", "Tab leva do botão de fechar ao gráfico")
            confere("(hoje)" in limpo(await pg.locator("#histDica").inner_text()), "o gráfico recebe o foco no teclado: mostra hoje")
            leitor = limpo(await pg.locator("#histLeitor").inner_text())
            confere("Atacadão: R$ 22,50" in leitor, f"o leitor de tela ouve os preços do dia: «{leitor}»")
            await pg.keyboard.press("ArrowLeft")
            confere("23/11" in limpo(await pg.locator("#histDica").inner_text()), "seta para a esquerda: o dia anterior (23/11)")
            await pg.keyboard.press("Home")
            confere("04/11" in limpo(await pg.locator("#histDica").inner_text()), "Home: o primeiro dia (04/11)")
            await pg.keyboard.press("ArrowLeft")
            confere("04/11" in limpo(await pg.locator("#histDica").inner_text()), "seta para a esquerda no primeiro dia: fica nele")
            await pg.keyboard.press("End")
            confere("(hoje)" in limpo(await pg.locator("#histDica").inner_text()), "End: hoje")
            await pg.keyboard.press("ArrowRight")
            confere("(hoje)" in limpo(await pg.locator("#histDica").inner_text()), "seta para a direita em hoje: fica em hoje")
            foco = await pg.locator("#histPlot").evaluate("(e) => { const c = getComputedStyle(e); return c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) >= 2; }")
            confere(foco, "o gráfico focado pelo teclado tem contorno visível")

            # --- 7. nada estoura
            estouro = await pg.evaluate("() => { const j = document.querySelector('#janelaHistorico .janela'); return j.scrollWidth - j.clientWidth; }")
            confere(estouro <= 1, f"a janela não tem rolagem para o lado ({estouro}px)")
            dentro = await pg.evaluate("() => { const j = document.querySelector('#janelaHistorico .janela').getBoundingClientRect(); return j.left >= 0 && j.right <= document.documentElement.clientWidth + 1; }")
            confere(dentro, "a janela cabe na largura da tela")
            fora = await pg.evaluate("() => { const j = document.querySelector('#janelaHistorico .janela').getBoundingClientRect(); return [...document.querySelectorAll('#janelaHistorico .janela *')].filter((e) => e.getBoundingClientRect().width && e.getBoundingClientRect().right > j.right + 1).length; }")
            confere(fora == 0, f"nada passa da borda direita da janela ({fora} elementos)")
            await pg.locator("#janelaHistorico .janela").evaluate("(e) => { e.scrollTop = e.scrollHeight; }")
            await pg.screenshot(path=str(SAIDA / f"historico-{rotulo}-2-tabela.png"))
            await pg.locator("#janelaHistorico .janela").evaluate("(e) => { e.scrollTop = 0; }")

            # --- 8. o tamanho da janela muda com o gráfico aberto: o desenho acompanha
            if rotulo == "desktop":
                await pg.set_viewport_size({"width": 420, "height": 800})
                await pg.wait_for_timeout(400)
                plot2 = await pg.locator("#histPlot").bounding_box()
                svg2 = await pg.locator("#histPlot .g-svg").bounding_box()
                confere(plot2["width"] < 400 and abs(svg2["width"] - plot2["width"]) <= 1, f"a janela encolheu e o desenho foi refeito na largura nova: {svg2['width']:.0f} de {plot2['width']:.0f}")
                confere(await pg.locator("#histPlot path.g-linha").count() == 4, "depois de refeito ainda tem as quatro linhas")
                await pg.set_viewport_size(vp)
                await pg.wait_for_timeout(300)

            # --- 9. fechar: o botão, o Esc e o foco volta para o botão que abriu
            await fechar(pg)
            try:                                               # o foco volta no evento "close", um instante depois de a janela fechar (e depois de redimensionar a tela, o botão é outro elemento)
                await pg.wait_for_function("() => document.activeElement && document.activeElement.dataset.historico !== undefined", timeout=2000)
                foco_voltou = True
            except Exception:
                foco_voltou = False
            confere(foco_voltou, "o foco volta para o botão que abriu o gráfico")
            await abrir_grafico(pg, "Camil")
            await esperar_grafico(pg)
            await pg.keyboard.press("Escape")
            await pg.wait_for_selector("#janelaHistorico:not([open])", state="attached", timeout=3000)
            confere(True, "a tecla Esc fecha a janela")
            confere(len(api.historico) == 1, f"abrir de novo o mesmo produto não chama a API outra vez (fica guardado): {len(api.historico)} pedidos")

            # --- 10. nenhum preço mudou, e produto por quilo
            await abrir_grafico(pg, "Banana")
            await esperar_grafico(pg)
            confere(limpo(await pg.locator(".hist-frase").inner_text()) == "Nenhum dos preços mudou desde 18/11.", f"série reta: «{limpo(await pg.locator('.hist-frase').inner_text())}»")
            confere("por quilo" in await pg.locator("#histUnidade").inner_text(), "produto vendido a peso: a unidade diz 'por quilo'")
            retas = [await pg.locator("#histPlot path.g-linha").nth(i).get_attribute("d") for i in range(await pg.locator("#histPlot path.g-linha").count())]
            confere(len(retas) == 2 and all("V" not in d_ for d_ in retas), f"duas linhas retas, sem degrau: {retas}")
            await pg.focus("#fecharHistorico")
            await pg.keyboard.press("Tab")
            await pg.wait_for_timeout(120)
            confere("R$ 3,79/kg" in limpo(await pg.locator("#histDica").inner_text()), f"o quadro de um produto por quilo traz /kg: «{limpo(await pg.locator('#histDica').inner_text())}»")
            confere("Não mudou desde 18/11" in limpo(await pg.locator(".hist-tabela").inner_text()), "a tabela diz que não mudou desde 18/11")
            await pg.screenshot(path=str(SAIDA / f"historico-{rotulo}-3-reta.png"))
            await fechar(pg)

            # --- 11. produto sem nenhum histórico
            await abrir_grafico(pg, "Sem Historico")
            await pg.wait_for_selector("#histCorpo .estado strong:has-text('Ainda não há histórico')", timeout=5000)      # (antes da resposta a janela diz "Buscando…")
            confere(True, "produto sem histórico: a janela explica, sem gráfico vazio")
            confere(await pg.locator("#histPlot").count() == 0, "e não desenha gráfico nenhum")
            await fechar(pg)

            # --- 12. a API falha: mensagem clara e "Tentar de novo" que funciona
            await abrir_grafico(pg, "Que Falha")
            await pg.wait_for_selector("#histTentar", timeout=5000)
            confere("Não deu para carregar" in await pg.locator("#histCorpo .estado strong").inner_text(), "API fora do ar (503): a janela diz que não deu para carregar")
            await clicar(pg.locator("#histTentar"))
            await esperar_grafico(pg)
            confere(await pg.locator("#histPlot path.g-linha").count() == 2, "'Tentar de novo' funciona: o gráfico aparece")
            await fechar(pg)

            # --- 13. resposta que chega depois de a pessoa fechar e abrir outro produto não pinta por cima
            await abrir_grafico(pg, "Lento")                       # demora 1,2 s
            await pg.wait_for_timeout(200)
            await fechar(pg)
            await abrir_grafico(pg, "Banana")                      # já está guardado: aparece na hora
            await esperar_grafico(pg)
            await pg.wait_for_timeout(1500)                        # a resposta do Lento chega agora
            confere("Banana" in await pg.locator("#histProduto").inner_text() and "Nenhum dos preços mudou desde 18/11." in limpo(await pg.locator(".hist-frase").inner_text()), "a resposta atrasada de outro produto não sobrescreve a janela atual")
            await fechar(pg)

            # --- 13b. fechar e abrir outro produto no mesmo instante: o evento "close" do <dialog> chega depois e não pode cancelar a carga nova
            await abrir_grafico(pg, "Camil")
            await esperar_grafico(pg)
            await pg.evaluate("""() => {
              document.querySelector("#fecharHistorico").click();
              [...document.querySelectorAll("article.produto")].find((a) => a.querySelector("h3").textContent.includes("Rapido")).querySelector("[data-historico]").click();
            }""")
            await pg.wait_for_selector("#histProduto:has-text('Rapido')", timeout=3000)
            await esperar_grafico(pg)
            confere(await pg.locator("#histPlot path.g-linha").count() == 2, "fechar e abrir outro produto (ainda sem cache) no mesmo instante: o gráfico novo aparece (o 'close' atrasado não o cancela)")
            await fechar(pg)
            await ctx.close()

            # --- 14. modo equivalente: a tabela diz qual produto cada linha é
            ctx, pg = await abrir(nav, vp, mobile, ApiDeMentira())
            await clicar(pg.locator('.modo button[data-modo="equivalente"]'))
            await pg.wait_for_timeout(500)
            await clicar(pg.locator("article.produto", has=pg.locator("h3", has_text="Arroz, 5 kg")).locator("[data-historico]"))
            await esperar_grafico(pg)
            confere("Arroz Camil 5kg" in limpo(await pg.locator(".hist-tabela").inner_text()) and "produto que hoje sai mais barato" in await pg.locator(".hist-nota").inner_text(), "equivalente: a tabela traz o produto de cada mercado e a nota explica")
            await ctx.close()

            # --- 15. API antiga, sem a chave: nenhum botão e nenhum erro
            ctx, pg = await abrir(nav, vp, mobile, ApiDeMentira(com_chave=False))
            confere(await pg.locator("[data-historico]").count() == 0, "API sem chave_historico: nenhum botão do gráfico")
            await ctx.close()
        await nav.close()


if __name__ == "__main__":
    asyncio.run(rodar())
    print(f"\nRESUMO: {ok} ok, {len(falhas)} falhas")
    for f in falhas:
        print("  -", f)
    sys.exit(1 if falhas else 0)
