"""Diagnóstico temporário: depois de CEP + "Quero receber" + abrir ?sc=15, quando o canal do carrinho vira 15
e quando a prateleira mostra preço? Não usa chave e não toca no banco."""
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.async_api import async_playwright

from robos_comum import esperar_na_pagina

CEP = "32607600"
ESPERADO = "32607-600"
JS_MEDIDA = '''() => {
  const cs = [...document.querySelectorAll("article, section.vtex-product-summary-2-x-container, div[class*='shelf-item'], div[class*='box-item'], li[layout]")];
  return [cs.length, cs.filter(c => c.innerText && c.innerText.includes("R$")).length,
          (document.body.innerText.match(/indispon[ií]vel/gi) || []).length];
}'''
JS_CANAL = '''async () => { try { const o = await (await fetch("/api/checkout/pub/orderForm", {credentials: "same-origin"})).json(); return o.salesChannel; } catch (e) { return "?"; } }'''
JS_COOKIE = "() => (document.cookie.match(/VTEXSC=[^;]*/) || ['sem VTEXSC'])[0]"
JS_CONFIRMOU = ("(c) => { const q = document.querySelector('.cart__body--cep-validado--box');"
                " return !!q && q.innerText.includes(c) && /atendemos sua regi/i.test(q.innerText); }")
JS_CEP_FORMATADO = "() => /[0-9]{5}-[0-9]{3}/.test((document.querySelector('#cepInput, input[name=cep]') || {}).value || '')"
JS_BUSCAR = "() => [...document.querySelectorAll('button')].find(b => b.offsetParent && /^buscar$/i.test(b.innerText.trim())).click()"


def agora():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


async def sessao(p, com_cep):
    navegador = await p.chromium.launch(headless=True)
    pagina = await (await navegador.new_context(viewport={"width": 1366, "height": 768})).new_page()
    linhas = []
    try:
        await pagina.goto("https://www.apoioentrega.com/", wait_until="domcontentloaded", timeout=60000)
        for seletor in ("text='Sou pessoa física'", "button:has-text('Aceitar'), button:has-text('Entendi')"):
            try:
                await pagina.locator(seletor).first.click(timeout=3000, force=True)
            except Exception:
                pass
        if com_cep:
            await pagina.evaluate("() => document.querySelector('a.btn-top-cart').click()")
            campo = pagina.locator("#cepInput, input[name='cep']").first
            await campo.wait_for(state="visible", timeout=8000)
            await campo.fill(CEP, force=True)
            await esperar_na_pagina(pagina, JS_CEP_FORMATADO, segundos=5)
            for _ in range(3):
                try:
                    await pagina.evaluate(JS_BUSCAR)
                except Exception:
                    pass
                if await esperar_na_pagina(pagina, JS_CONFIRMOU, ESPERADO, segundos=10):
                    break
            await pagina.evaluate("() => document.querySelector(\"li[data-type='click-delivery']\").click()")
            await asyncio.sleep(8)
            linhas.append(f"antes do ?sc=15: canal do carrinho={await pagina.evaluate(JS_CANAL)} | {await pagina.evaluate(JS_COOKIE)}")
        inicio = time.time()
        await pagina.goto("https://www.apoioentrega.com/Arroz?sc=15", wait_until="domcontentloaded", timeout=60000)
        for espera in (0, 3, 6, 10, 15):
            await asyncio.sleep(max(0, espera - (time.time() - inicio)))
            cards, com_preco, indisp = await pagina.evaluate(JS_MEDIDA)
            linhas.append(f"{time.time() - inicio:4.1f}s depois de abrir ?sc=15: canal do carrinho={await pagina.evaluate(JS_CANAL)} | {await pagina.evaluate(JS_COOKIE)} | prateleira: cards={cards} com_R$={com_preco} indisp={indisp}")
    except Exception as erro:
        linhas.append("ERRO: " + str(erro)[:100])
    finally:
        await navegador.close()
    return linhas


async def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    async with async_playwright() as p:
        for rodada in (1, 2, 3):
            for com_cep in (True, False):
                print(f"\n##### [{agora()} UTC] rodada {rodada} - {'COM CEP + receber' if com_cep else 'SEM CEP (so ?sc=15)'}", flush=True)
                for linha in await sessao(p, com_cep):
                    print("   " + linha, flush=True)


asyncio.run(main())
