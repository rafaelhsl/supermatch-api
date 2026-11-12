"""Confere os arquivos de bibliotecas: o da API cobre o que ela importa e não traz o Playwright; o completo cobre o projeto todo.

Rodar com:  python tests/test_requirements.py   (não precisa instalar nada: só lê o código)

O Render instala `requirements-api.txt`; a carga diária do GitHub instala `requirements.txt`. Se alguém passar a importar na API um
pacote que falta no primeiro, o deploy só quebra no Render, depois do merge. Este teste mostra isso antes.
"""
import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOCAIS = {p.stem for p in RAIZ.glob("*.py")}
falhas = []
verificacoes = 0


def confere(condicao, texto):
    global verificacoes
    verificacoes += 1
    if not condicao:
        falhas.append(texto)


def pacotes_do_arquivo(nome):
    """Nomes de pacote de um requirements (segue as linhas `-r outro.txt`)."""
    pacotes = set()
    for linha in (RAIZ / nome).read_text(encoding="utf-8").splitlines():
        linha = linha.split("#")[0].strip()
        if not linha:
            continue
        if linha.startswith("-r "):
            pacotes |= pacotes_do_arquivo(linha[3:].strip())
        else:
            pacotes.add(linha.split("==")[0].split(">")[0].split("<")[0].split("[")[0].strip().lower().replace("_", "-"))
    return pacotes


def imports_externos(arquivo, vistos=None):
    """Pacotes de fora (nem biblioteca padrão, nem módulo do repositório) que `arquivo` importa, seguindo os módulos locais."""
    vistos = set() if vistos is None else vistos
    if arquivo in vistos:
        return set()
    vistos.add(arquivo)
    externos = set()
    for no in ast.walk(ast.parse((RAIZ / f"{arquivo}.py").read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            nomes = [a.name.split(".")[0] for a in no.names]
        elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            nomes = [no.module.split(".")[0]]
        else:
            continue
        for nome in nomes:
            if nome in LOCAIS:
                externos |= imports_externos(nome, vistos)
            elif nome not in sys.stdlib_module_names:
                externos.add(nome.lower().replace("_", "-"))
    return externos


api = pacotes_do_arquivo("requirements-api.txt")
tudo = pacotes_do_arquivo("requirements.txt")
usados_pela_api = imports_externos("api_supabase")

confere(usados_pela_api == {"fastapi", "uvicorn", "supabase", "thefuzz"}, f"a API deveria importar só fastapi, uvicorn, supabase e thefuzz, e importa: {sorted(usados_pela_api)}")
confere(usados_pela_api <= api, f"requirements-api.txt não cobre o que a API importa (faltam: {sorted(usados_pela_api - api)}); o deploy do Render quebraria")
confere("playwright" not in api, "o Playwright não pode estar no requirements-api.txt: a API não o usa e o Render baixaria 53 MB e o Node.js à toa")
confere("playwright" not in usados_pela_api, "a API não deveria importar o Playwright (nem indiretamente)")
confere(api <= tudo, f"requirements.txt deveria incluir tudo do requirements-api.txt (faltam: {sorted(api - tudo)})")

# o completo cobre qualquer módulo da raiz: robôs, carga, coletor...
todos_os_externos = set()
for modulo in sorted(LOCAIS):
    todos_os_externos |= imports_externos(modulo)
confere(todos_os_externos <= tudo, f"requirements.txt não cobre o que o projeto importa (faltam: {sorted(todos_os_externos - tudo)})")
confere("playwright" in tudo and "playwright" in todos_os_externos, "os robôs usam o Playwright, e o requirements.txt completo o traz")

# a versão do Python que o Render usa
versao = (RAIZ / ".python-version").read_text(encoding="utf-8").strip()
partes = versao.split(".")
confere(len(partes) == 3 and all(p.isdigit() for p in partes), f".python-version deveria ter a versão completa (por exemplo 3.14.3), tem: {versao!r}")

if falhas:
    print(f"{len(falhas)} falha(s):\n  - " + "\n  - ".join(falhas))
    sys.exit(1)
print(f"ok: {verificacoes} verificações passaram")
