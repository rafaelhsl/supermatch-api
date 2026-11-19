"""Gera site/og.png (a imagem que aparece quando o link do Supermatch é compartilhado) a partir de docs/og/og.html.

Rodar com:  python docs/og/gerar_og.py   (precisa do Playwright e do Chromium: veja docs/testes.md; as letras vêm do Google Fonts, então precisa de internet)
Tira uma foto de 1200 x 630 px da página e grava site/og.png. Depois de mudar o texto ou as cores de og.html, rode de novo e confira a imagem.
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

RAIZ = Path(__file__).resolve().parents[2]
ORIGEM = RAIZ / "docs" / "og" / "og.html"
DESTINO = RAIZ / "site" / "og.png"


async def gerar():
    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=True)
        pagina = await nav.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
        await pagina.goto(ORIGEM.as_uri(), wait_until="networkidle")
        await pagina.evaluate("document.fonts.ready")
        await pagina.wait_for_timeout(500)
        await pagina.screenshot(path=str(DESTINO), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        await nav.close()
    print(f"{DESTINO} gravado ({DESTINO.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    asyncio.run(gerar())
