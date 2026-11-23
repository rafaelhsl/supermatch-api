"""Parte comum dos testes de navegador (tests/navegador/test_*.py): onde está o site e onde ficam as capturas de tela.

Não é um teste: o nome começa com "_" de propósito, para o workflow não rodá-lo.
"""
import functools
import http.server
import os
import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

class _ServidorQuieto(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".html": "text/html; charset=utf-8", ".woff2": "font/woff2", ".png": "image/png"}

    def log_message(self, *argumentos):                  # sem uma linha de log por arquivo servido
        pass


def _servir_o_site():
    """Serve a pasta site/ num endereço local (http://127.0.0.1:porta), como o Netlify a serve, e devolve o endereço da página.

    Até 23/11/2026 os testes abriam o arquivo direto do disco (file://). Com as fontes em site/fonts/ isso deixou de servir: o navegador trata
    file:// como origem "nula" e barra o preload de fonte (CORS), um erro que não existe no site publicado. O servidor torna o teste igual ao
    de verdade (mesma origem, o tipo certo de cada arquivo) e cada processo de teste ganha a sua porta.
    """
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_ServidorQuieto, directory=str(RAIZ / "site")))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{servidor.server_address[1]}/index.html"


# SITE_URL troca o endereço (por exemplo, para conferir uma cópia alterada do arquivo): fora isso, vale o site/ do repositório, servido daqui.
URL = os.environ.get("SITE_URL") or _servir_o_site()

# Capturas de tela dos testes (para olhar quando algo falha). Fora do Git; no GitHub o workflow as guarda se um teste falhar.
SAIDA = Path(os.environ.get("SM_CAPTURAS") or RAIZ / "tests" / "navegador" / "capturas")
SAIDA.mkdir(parents=True, exist_ok=True)

# Os textos têm acento e emoji: sem isso o console do Windows (cp1252) quebra ao imprimir.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
