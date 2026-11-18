"""Testes dos scripts SQL de docs/sql/ (os que você roda à mão no SQL Editor do Supabase). Só texto: não precisa de banco.

Rodar com:  python tests/test_sql.py

Esses arquivos mexem no banco de produção por mão humana, então valem duas regras:
1. Nada que apague ou reescreva dado (drop, delete, truncate, update): os scripts só acrescentam.
2. Pode rodar de novo sem erro (if not exists em tudo que cria ou acrescenta).
"""
import re
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "docs" / "sql"
ok, erros = 0, []


def confere(condicao, texto):
    global ok
    if condicao:
        ok += 1
    else:
        erros.append(texto)


def sem_comentarios(sql):
    return "\n".join(re.sub(r"--.*$", "", linha) for linha in sql.splitlines())


def comandos(sql):
    return [c.strip() for c in sem_comentarios(sql).split(";") if c.strip()]


scripts = sorted(PASTA.glob("*.sql"))
confere(len(scripts) >= 3, f"scripts em docs/sql: {[s.name for s in scripts]}")
for script in scripts:
    texto = script.read_text(encoding="utf-8")
    cmds = comandos(texto)
    confere(cmds, f"{script.name}: sem nenhum comando")
    for cmd in cmds:
        baixo = " ".join(cmd.lower().split())
        # ("on delete cascade" dentro de um create table é opção de chave estrangeira, não um comando que apaga dado: por isso só o começo do comando conta)
        perigoso = re.match(r"(drop|delete|truncate|update|insert)\b", baixo) or (baixo.startswith("alter table") and re.search(r"\b(drop|rename)\b|alter column \w+ (set data )?type", baixo))
        confere(not perigoso, f"{script.name}: comando que apaga, renomeia ou reescreve dado: {baixo[:70]}")
        if re.match(r"create (unique )?(table|index)\b", baixo):
            confere("if not exists" in baixo, f"{script.name}: precisa de 'if not exists' para poder rodar de novo: {baixo[:70]}")
        if re.match(r"alter table\b", baixo) and re.search(r"\badd column\b", baixo):
            colunas = re.findall(r"add column (?:if not exists )?", baixo)
            confere(len(colunas) == baixo.count("add column") and baixo.count("add column") == baixo.count("add column if not exists"),
                    f"{script.name}: toda coluna nova precisa de 'if not exists': {baixo[:70]}")

# a coluna do hortifrúti: só `unidade text`, vazia, sem restrição que quebre a carga se um mercado mandar uma unidade que não conhecemos
unidade = PASTA / "coluna_unidade.sql"
confere(unidade.exists(), "docs/sql/coluna_unidade.sql não existe")
if unidade.exists():
    cmds = [" ".join(c.lower().split()) for c in comandos(unidade.read_text(encoding="utf-8"))]
    confere(cmds[0] == "alter table produtos add column if not exists unidade text", f"coluna_unidade.sql: o 1º comando mudou: {cmds[0]}")
    confere(not any("check" in c or "not null" in c or "default" in c for c in cmds), "coluna_unidade.sql: sem check, not null nem default (a carga não pode quebrar por causa dela)")
    confere(len(cmds) == 2 and cmds[1] == "notify pgrst, 'reload schema'", f"coluna_unidade.sql: comandos inesperados: {cmds}")

if erros:
    print(f"{len(erros)} falha(s):\n  - " + "\n  - ".join(erros))
    sys.exit(1)
print(f"ok: {ok} verificações passaram")
