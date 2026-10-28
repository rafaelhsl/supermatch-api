"""Diagnóstico temporário do Apoio nos servidores do GitHub (não usa chave e não toca no banco).

Roda as 11 buscas do Apoio uma a uma (sem repetição automática) e, para cada falha, mostra o que a
página estava exibindo e quais respostas com erro HTTP (403, 429...) o site devolveu.
"""
import asyncio
import sys
import time

from playwright.async_api import Browser

from robos_comum import FalhaNoRobo
from Scraper_Apoio_v2 import buscar_no_apoio

ITENS = ["Arroz", "Feijao", "Oleo", "Cafe", "Manteiga", "Açucar", "Macarrao", "Detergente", "Sabao", "Amaciante", "Higienico"]
CEP = "32607600"

respostas_com_erro = []
_novo_contexto = Browser.new_context


async def novo_contexto(self, *args, **kwargs):
    contexto = await _novo_contexto(self, *args, **kwargs)
    contexto.on("response", lambda r: respostas_com_erro.append(f"{r.status} {r.url[:110]}") if r.status >= 400 else None)
    return contexto


Browser.new_context = novo_contexto


async def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    resumo = []
    for item in ITENS:
        respostas_com_erro.clear()
        inicio = time.time()
        try:
            produtos = await buscar_no_apoio(CEP, item)
            resultado = f"{len(produtos)} itens"
        except FalhaNoRobo as erro:
            resultado = f"FALHOU: {erro.motivo}"
        duracao = time.time() - inicio
        print(f"\n>>> {item}: {resultado} ({duracao:.0f}s) | respostas com erro HTTP: {len(respostas_com_erro)}", flush=True)
        for linha in respostas_com_erro[:6]:
            print(f"      {linha}", flush=True)
        resumo.append((item, resultado))

    print("\n=== RESUMO DO DIAGNÓSTICO DO APOIO ===")
    for item, resultado in resumo:
        print(f"  {item:<12} {resultado[:150]}")


asyncio.run(main())
