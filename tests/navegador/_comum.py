"""Parte comum dos testes de navegador (tests/navegador/test_*.py): onde está o site e onde ficam as capturas de tela.

Não é um teste: o nome começa com "_" de propósito, para o workflow não rodá-lo.
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# O site é um arquivo só; os testes o abrem direto do disco (file://), sem servidor.
# SITE_URL troca o endereço (por exemplo, para conferir uma cópia alterada do arquivo): fora isso, vale o site/index.html do repositório.
URL = os.environ.get("SITE_URL") or (RAIZ / "site" / "index.html").as_uri()

# Capturas de tela dos testes (para olhar quando algo falha). Fora do Git; no GitHub o workflow as guarda se um teste falhar.
SAIDA = Path(os.environ.get("SM_CAPTURAS") or RAIZ / "tests" / "navegador" / "capturas")
SAIDA.mkdir(parents=True, exist_ok=True)

# Os textos têm acento e emoji: sem isso o console do Windows (cp1252) quebra ao imprimir.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
