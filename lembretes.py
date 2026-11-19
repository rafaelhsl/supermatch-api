"""Lembretes por data: abre uma issue no GitHub (o dono recebe o e-mail) quando chega o dia de um lembrete de dados/lembretes.json.

Para que serve: o token do GitHub que o cron-job.org usa para disparar a carga diária vence em 13/11/2027, e a versão da API que ele manda
(`X-GitHub-Api-Version: 2022-11-28`) deixa de funcionar em 10/03/2028. Se ninguém lembrar, a carga das 07:30 para de rodar sem barulho.

Rodar (sem criar nada, só mostra o que cada lembrete faria):  python lembretes.py
Criar de verdade (é o que o workflow lembretes.yml faz todo dia): python lembretes.py --criar   (precisa do `gh` e do GH_TOKEN)
Testar com outra data:                                             python lembretes.py --hoje 2027-10-14
Um lembrete só abre uma issue: se já existe uma com o mesmo título (aberta ou fechada), não abre outra.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / "dados" / "lembretes.json"
BRASILIA = timezone(timedelta(hours=-3))       # o dia do dono: sem horário de verão desde 2019
PREFIXO = "Lembrete: "
CAMPOS = ("quando", "vence", "titulo", "texto")


def hoje_em_brasilia():
    return datetime.now(BRASILIA).date()


def carregar(caminho=ARQUIVO):
    """Os lembretes, com as datas como `date`. Recusa o arquivo mal formado: um lembrete que não dispara é pior que nenhum."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    lembretes, titulos = [], set()
    for i, bruto in enumerate(dados["lembretes"], 1):
        faltam = [c for c in CAMPOS if not str(bruto.get(c, "")).strip()]
        if faltam:
            raise ValueError(f"lembrete {i}: faltam os campos {faltam}")
        l = dict(bruto, quando=date.fromisoformat(bruto["quando"]), vence=date.fromisoformat(bruto["vence"]))
        if l["quando"] >= l["vence"]:
            raise ValueError(f"lembrete {i} ({l['titulo']}): a data do lembrete tem de ser ANTES de vencer")
        if titulo_da_issue(l) in titulos:
            raise ValueError(f"lembrete {i}: título repetido ({l['titulo']}); o título é o que impede de abrir a issue duas vezes")
        titulos.add(titulo_da_issue(l))
        lembretes.append(l)
    return lembretes


def titulo_da_issue(lembrete):
    return PREFIXO + lembrete["titulo"]


def corpo_da_issue(lembrete, hoje):
    return (f"{lembrete['texto']}\n\n---\n_Aberta sozinha por `lembretes.py` (dados/lembretes.json) em {hoje.strftime('%d/%m/%Y')}; "
            f"o lembrete era para {lembrete['quando'].strftime('%d/%m/%Y')} e o prazo é {lembrete['vence'].strftime('%d/%m/%Y')}._")


def a_criar(lembretes, hoje, titulos_existentes):
    """Os lembretes que já chegaram (ou passaram: melhor tarde que nunca) e ainda não têm issue."""
    return [l for l in lembretes if l["quando"] <= hoje and titulo_da_issue(l) not in titulos_existentes]


def executar_gh(argumentos):
    return subprocess.run(["gh", *argumentos], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def issues_existentes(executar):
    """Os títulos de todas as issues, abertas e fechadas."""
    return {i["title"] for i in json.loads(executar(["issue", "list", "--state", "all", "--limit", "1000", "--json", "title"]) or "[]")}


def criar(lembrete, hoje, executar, dono=""):
    argumentos = ["issue", "create", "--title", titulo_da_issue(lembrete), "--body", corpo_da_issue(lembrete, hoje)]
    if dono:
        argumentos += ["--assignee", dono]
    return executar(argumentos).strip()


def principal(argv=None, executar=executar_gh, escrever=print):
    parser = argparse.ArgumentParser(description="Abre uma issue por lembrete de dados/lembretes.json quando chega o dia.")
    parser.add_argument("--criar", action="store_true", help="abre as issues de verdade (sem isso, só mostra o que faria)")
    parser.add_argument("--hoje", help="AAAA-MM-DD: finge que hoje é esse dia (para testar)")
    parser.add_argument("--arquivo", default=str(ARQUIVO))
    args = parser.parse_args(argv)

    hoje = date.fromisoformat(args.hoje) if args.hoje else hoje_em_brasilia()
    lembretes = carregar(args.arquivo)
    try:
        existentes = issues_existentes(executar)
    except Exception as erro:
        if args.criar:
            raise                                               # criar sem saber o que já existe abriria issue repetida: o workflow fica vermelho
        existentes = set()
        escrever(f"(não consegui consultar as issues: {str(erro)[:120]}; mostro como se não houvesse nenhuma)")

    pendentes = a_criar(lembretes, hoje, existentes)
    escrever(f"Hoje é {hoje.strftime('%d/%m/%Y')}: {len(lembretes)} lembrete(s), {len(pendentes)} para abrir agora.")
    for l in lembretes:
        if l in pendentes:
            estado = "PARA ABRIR AGORA" if args.criar else "para abrir (rode com --criar)"
        elif titulo_da_issue(l) in existentes:
            estado = "já tem issue"
        else:
            estado = f"daqui a {(l['quando'] - hoje).days} dia(s), em {l['quando'].strftime('%d/%m/%Y')}"
        escrever(f"  - {l['titulo']}: {estado}")
    if args.criar:
        dono = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
        for l in pendentes:
            escrever(f"Aberta: {criar(l, hoje, executar, dono)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(principal())
