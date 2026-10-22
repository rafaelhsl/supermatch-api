"""Diagnostico temporario do Super ABC: mostra o que o robo enxerga em cada endereco.

Uso: python diagnostico_superabc.py [pasta_de_saida]

Nao acessa o Supabase e nao usa nenhuma chave. Salva uma captura de tela e o HTML de cada teste
na pasta de saida (padrao: ./diagnostico_superabc).
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

# Permite importar Scraper_SuperABC mesmo quando o script roda com -I (sem a pasta atual no path).
sys.path.insert(0, str(Path(__file__).resolve().parent))

URLS = {
    "www": "https://www.superabc.com.br/",           # usado hoje por alimentar_banco.py
    "online": "https://superabconline.com.br/",       # usado no teste local do scraper
}
SELETOR_BUSCA = "input.input-busca-produto, input[placeholder*='O que você procura' i]"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
# "producao" repete exatamente o que o scraper faz; "pt-BR" simula um navegador brasileiro.
VARIANTES = {
    "producao": {},
    "pt-BR": {"locale": "pt-BR", "timezone_id": "America/Sao_Paulo"},
}


async def onde_estou(contexto):
    """Onde o site 'acha' que o robo esta (so pais, regiao e provedor; nunca o IP)."""
    try:
        resposta = await contexto.request.get("https://ipinfo.io/json", timeout=15000)
        dados = await resposta.json()
        return {k: dados.get(k) for k in ("country", "region", "city", "org")}
    except Exception as erro:
        return {"erro": str(erro)[:120]}


async def testar(p, rotulo, url, variante, opcoes, saida):
    print(f"\n{'=' * 70}\n[{rotulo} | {variante}] {url}\n{'=' * 70}")
    navegador = await p.chromium.launch(headless=True)
    contexto = await navegador.new_context(
        viewport={"width": 1366, "height": 768}, user_agent=USER_AGENT, **opcoes
    )
    pagina = await contexto.new_page()

    respostas_ruins = []
    pagina.on(
        "response",
        lambda r: respostas_ruins.append(f"{r.status} {r.url[:110]}") if r.status >= 400 else None,
    )

    status = None
    try:
        resposta = await pagina.goto(url, wait_until="domcontentloaded", timeout=60000)
        status = resposta.status if resposta else None
        await pagina.wait_for_timeout(4000)
    except Exception as erro:
        print(f"  ERRO ao abrir a pagina: {str(erro)[:200]}")

    try:
        titulo = await pagina.title()
        texto = await pagina.evaluate(
            "() => document.body ? document.body.innerText.replace(/\\s+/g, ' ').substring(0, 300) : 'Pagina vazia'"
        )
    except Exception as erro:
        titulo, texto = "?", f"(falhou ao ler a pagina: {str(erro)[:100]})"

    achou_busca = await pagina.locator(SELETOR_BUSCA).count()
    print(f"  status HTTP ........ {status}")
    print(f"  titulo ............. {titulo!r}")
    print(f"  URL final .......... {pagina.url}")
    print(f"  barra de busca ..... {'ENCONTRADA' if achou_busca else 'NAO encontrada'} ({achou_busca})")
    print(f"  texto da tela ...... {texto}")
    print(f"  o site ve o robo em  {await onde_estou(contexto)}")

    if respostas_ruins:
        print(f"  respostas com erro HTTP ({len(respostas_ruins)}), as primeiras:")
        for linha in respostas_ruins[:8]:
            print(f"     {linha}")

    nome = f"{rotulo}_{variante}"
    try:
        await pagina.screenshot(path=str(saida / f"{nome}.png"), full_page=False)
        (saida / f"{nome}.html").write_text(await pagina.content(), encoding="utf-8")
    except Exception as erro:
        print(f"  (nao consegui salvar captura/HTML: {str(erro)[:100]})")

    await navegador.close()


async def rodar_scraper_real():
    """Roda a mesma funcao que a carga diaria usa, em cada endereco, e conta os itens."""
    from Scraper_SuperABC import buscar_na_plataforma_regex

    print(f"\n{'=' * 70}\nSCRAPER REAL (busca por 'Cafe')\n{'=' * 70}")
    resultado = {}
    for rotulo, url in URLS.items():
        itens = await buscar_na_plataforma_regex(url, "Super ABC", "Cafe")
        resultado[rotulo] = len(itens)
        print(f"  >>> {rotulo} ({url}): {len(itens)} itens")
        for item in itens[:2]:
            print(f"      {item['nome']} - R$ {item['preco_varejo']}")
    return resultado


async def main(saida):
    saida.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        for rotulo, url in URLS.items():
            for variante, opcoes in VARIANTES.items():
                await testar(p, rotulo, url, variante, opcoes, saida)
    await rodar_scraper_real()
    print(f"\nCapturas e HTML salvos em: {saida.resolve()}")


if __name__ == "__main__":
    # O console do Windows (cp1252) quebra com caracteres que os sites usam, como setas.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("diagnostico_superabc")
    asyncio.run(main(pasta))
