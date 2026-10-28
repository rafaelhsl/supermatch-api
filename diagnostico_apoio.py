"""Diagnóstico temporário do Apoio nos servidores do GitHub (não usa chave e não toca no banco).

Compara o robô com o navegador padrão e com um navegador que se apresenta como brasileiro (idioma,
fuso horário e geolocalização de BH), em 3 buscas. Hipótese: o Apoio decide a disponibilidade dos
produtos pela região do visitante, e o IP do GitHub (EUA) recebe "Item indisponível".
"""
import asyncio
import sys
import time

from playwright.async_api import Browser

from robos_comum import FalhaNoRobo
from Scraper_Apoio_v2 import buscar_no_apoio

ITENS = ["Arroz", "Cafe", "Oleo"]
CEP = "32607600"

VARIANTES = {
    "padrao": {},
    "brasileiro": {
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "geolocation": {"latitude": -19.9167, "longitude": -43.9345},
        "permissions": ["geolocation"],
        "extra_http_headers": {"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5"},
    },
}
variante_atual = {"opcoes": {}}
_novo_contexto = Browser.new_context


async def novo_contexto(self, *args, **kwargs):
    kwargs.update(variante_atual["opcoes"])
    return await _novo_contexto(self, *args, **kwargs)


Browser.new_context = novo_contexto


async def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    resumo = []
    for nome, opcoes in VARIANTES.items():
        variante_atual["opcoes"] = opcoes
        for item in ITENS:
            inicio = time.time()
            try:
                produtos = await buscar_no_apoio(CEP, item)
                resultado = f"{len(produtos)} itens"
            except FalhaNoRobo as erro:
                resultado = "FALHOU: " + erro.motivo[:60]
            print(f"\n>>> [{nome}] {item}: {resultado} ({time.time() - inicio:.0f}s)", flush=True)
            resumo.append((nome, item, resultado))

    print("\n=== RESUMO DO DIAGNÓSTICO DO APOIO ===")
    for nome, item, resultado in resumo:
        print(f"  {nome:<11} {item:<8} {resultado}")


asyncio.run(main())
