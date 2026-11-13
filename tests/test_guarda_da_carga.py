"""Testes da guarda da carga de reserva (guarda_da_carga.py) e do acordo dela com o run-name do workflow.

Rodar com:  python tests/test_guarda_da_carga.py   (só biblioteca padrão)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import guarda_da_carga as guarda  # noqa: E402

COMPLETA = "Carga (disparada) | gravar=sim | mercados=todos | coleta=api"
AGORA = datetime(2026, 11, 13, 18, 50, tzinfo=timezone.utc)          # 15:50 em Brasília, quando a de reserva costuma começar


def execucao(criada, titulo=COMPLETA, conclusao="success"):
    return {"createdAt": criada, "displayTitle": titulo, "conclusion": conclusao}


def decide(evento, execucoes, agora=AGORA):
    return guarda.decidir(evento, json.dumps(execucoes), agora)


def teste_carga_completa_de_hoje_faz_a_de_reserva_pular():
    pular, motivo = decide("schedule", [execucao("2026-11-13T10:30:12Z")])
    assert pular is True and "já foi feita" in motivo, motivo


def teste_sem_carga_hoje_a_de_reserva_carrega():
    assert decide("schedule", [])[0] is False
    assert decide("schedule", [execucao("2026-11-12T18:52:59Z")])[0] is False                      # a de ontem não conta


def teste_o_dia_e_o_de_brasilia_nao_o_utc():
    # 02:59 UTC é 23:59 de ontem em Brasília; 03:00 UTC já é hoje
    assert decide("schedule", [execucao("2026-11-13T02:59:59Z")])[0] is False
    assert decide("schedule", [execucao("2026-11-13T03:00:00Z")])[0] is True
    # o reverso: a de reserva às 01:30 UTC de 14/11 ainda é 13/11 em Brasília, então a carga das 10:30 UTC de 13/11 conta
    assert decide("schedule", [execucao("2026-11-13T10:30:00Z")], datetime(2026, 11, 14, 1, 30, tzinfo=timezone.utc))[0] is True


def teste_teste_e_carga_parcial_nao_contam():
    assert decide("schedule", [execucao("2026-11-13T10:30:00Z", "Carga (disparada) | gravar=nao | mercados=todos | coleta=api")])[0] is False
    assert decide("schedule", [execucao("2026-11-13T10:30:00Z", "Carga (disparada) | gravar=sim | mercados=Supernosso | coleta=api")])[0] is False
    assert decide("schedule", [execucao("2026-11-13T10:30:00Z", "Robô da Madrugada (Scraper)")])[0] is False        # título antigo, sem as marcas
    assert decide("schedule", [execucao("2026-11-13T10:30:00Z", COMPLETA, conclusao="failure")])[0] is False       # a que falhou não conta


def teste_so_a_execucao_agendada_pode_ser_pulada():
    hoje = [execucao("2026-11-13T10:30:12Z")]
    for evento in ("workflow_dispatch", "push", ""):
        assert decide(evento, hoje)[0] is False, evento


def teste_na_duvida_carrega():
    for entrada in ("", "isto não é json", "{}", '[{"createdAt": "ontem", "displayTitle": "%s"}]' % COMPLETA, "null"):
        pular, motivo = guarda.decidir("schedule", entrada, AGORA)
        assert pular is False, (entrada, motivo)


def teste_a_saida_do_script_serve_para_o_github_output():
    env = {**os.environ, "EVENTO": "schedule"}
    saida = subprocess.run([sys.executable, str(RAIZ / "guarda_da_carga.py")], input="[]", capture_output=True, text=True, env=env, encoding="utf-8")
    assert saida.returncode == 0 and saida.stdout.strip() == "pular=nao", (saida.stdout, saida.stderr)
    assert "carga" in saida.stderr                                                                  # o motivo vai para o log, não para o GITHUB_OUTPUT


def teste_o_run_name_do_workflow_traz_as_marcas_que_a_guarda_procura():
    """Se alguém mudar o run-name do workflow, a guarda deixaria de reconhecer a carga de hoje (e a de reserva rodaria à toa)."""
    texto = (RAIZ / ".github" / "workflows" / "main.yml").read_text(encoding="utf-8")
    achado = re.search(r"^run-name: (.+)$", texto, re.M)
    assert achado, "main.yml deveria ter um run-name"
    run_name = achado.group(1)
    assert "gravar=${{" in run_name and "mercados=${{" in run_name, run_name
    # monta o título como o GitHub montaria numa carga completa e confere que a guarda a reconhece
    titulo = re.sub(r"\$\{\{.*?\}\}", "x", run_name)
    assert not guarda.e_carga_completa(titulo)                                                      # só com os valores certos
    simulado = run_name
    simulado = re.sub(r"\$\{\{[^}]*github\.event_name[^}]*\}\}", "disparada", simulado)
    simulado = re.sub(r"gravar=\$\{\{[^}]*\}\}", "gravar=sim", simulado)
    simulado = re.sub(r"mercados=\$\{\{[^}]*\}\}", "mercados=todos", simulado)
    simulado = re.sub(r"coleta=\$\{\{[^}]*\}\}", "coleta=api", simulado)
    assert guarda.e_carga_completa(simulado), simulado
    assert "needs: decidir" in texto and "pular" in texto                                           # o job de carga espera a decisão


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
