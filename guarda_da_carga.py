"""Decide se a carga agendada do GitHub (a de reserva) deve ser pulada porque a carga de hoje já foi feita.

Usado pelo primeiro job de .github/workflows/main.yml (veja docs/carga_diaria.md). A carga principal é disparada de manhã por
um serviço externo; o agendador do GitHub só cobre o dia em que isso falhou. Então, numa execução AGENDADA, o workflow lista as
últimas execuções bem-sucedidas e passa o JSON para este script, que imprime `pular=sim` ou `pular=nao` (para o GITHUB_OUTPUT).

A decisão erra sempre para o lado de carregar: qualquer dúvida ou erro vira `pular=nao`. Pular por engano deixaria o site um dia
com preços velhos; carregar a mais só repete o trabalho (a carga repetida no mesmo dia não duplica nada).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

BRASILIA = timedelta(hours=-3)      # o Brasil não tem horário de verão desde 2019


def dia_em_brasilia(momento_utc):
    return (momento_utc + BRASILIA).date()


def e_carga_completa(titulo):
    """O título da execução vem do `run-name` do workflow: 'Carga (disparada) | gravar=sim | mercados=todos | coleta=api'.
    Só conta a carga que grava no banco e cobre todos os mercados; teste (gravar=nao) e carga de um mercado só não contam."""
    return "gravar=sim" in titulo and "mercados=todos" in titulo


def carga_de_hoje(execucoes, agora_utc):
    """A primeira execução bem-sucedida de hoje (dia de Brasília) que foi uma carga completa, ou None."""
    hoje = dia_em_brasilia(agora_utc)
    for execucao in execucoes:
        if execucao.get("conclusion", "success") != "success" or not e_carga_completa(execucao.get("displayTitle", "")):
            continue
        criada = datetime.fromisoformat(execucao["createdAt"].replace("Z", "+00:00"))
        if dia_em_brasilia(criada) == hoje:
            return execucao
    return None


def decidir(evento, entrada_json, agora_utc=None):
    """(pular, motivo). Só a execução agendada pode ser pulada."""
    agora_utc = agora_utc or datetime.now(timezone.utc)
    if evento != "schedule":
        return False, "disparo manual ou externo: sempre carrega"
    try:
        feita = carga_de_hoje(json.loads(entrada_json), agora_utc)
    except Exception as erro:       # lista ilegível, data estranha...: na dúvida, carrega
        return False, f"não consegui conferir as execuções ({erro!r}): carrega por segurança"
    if feita:
        return True, f"a carga de hoje já foi feita ({feita['displayTitle']!r}, criada em {feita['createdAt']}): pula a de reserva"
    return False, "nenhuma carga completa e bem-sucedida hoje: a de reserva carrega"


if __name__ == "__main__":
    pular, motivo = decidir(os.environ.get("EVENTO", ""), sys.stdin.read())
    print(motivo, file=sys.stderr)
    print("pular=" + ("sim" if pular else "nao"))
