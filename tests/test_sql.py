"""Testes dos scripts SQL de docs/sql/ (os que você roda à mão no SQL Editor do Supabase). Só texto: não precisa de banco.

Rodar com:  python tests/test_sql.py

Esses arquivos mexem no banco de produção por mão humana, então valem duas regras:
1. Nada que apague ou reescreva dado (drop, delete, truncate, update): os scripts só acrescentam.
2. Pode rodar de novo sem erro (if not exists em tudo que cria ou acrescenta; "create or replace" nas funções).
3. Tabela nova nasce com RLS ligado (a chave pública não lê nem escreve) e função nova nasce fechada: só a chave secreta (service_role) pode chamá-la.
   (O que está dentro do corpo de uma função, entre $$ e $$, só roda quando a função é chamada, não quando o script é rodado: por isso fica fora da regra 1.)
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
    """Os comandos do script, separados por ';'. Um corpo de função entre $$ e $$ tem ';' dentro e continua sendo UM comando só."""
    pedacos, atual, dentro = [], [], False
    texto = sem_comentarios(sql)
    i = 0
    while i < len(texto):
        if texto.startswith("$$", i):
            dentro = not dentro
            atual.append("$$")
            i += 2
            continue
        if texto[i] == ";" and not dentro:
            pedacos.append("".join(atual))
            atual = []
        else:
            atual.append(texto[i])
        i += 1
    pedacos.append("".join(atual))
    return [c.strip() for c in pedacos if c.strip()]


def cabecalho(comando):
    """O comando sem o corpo da função (o que está entre $$ e $$ só roda quando a função é chamada)."""
    return re.sub(r"\$\$.*?\$\$", "$$ $$", comando, flags=re.S)


scripts = sorted(PASTA.glob("*.sql"))
confere(len(scripts) >= 4, f"scripts em docs/sql: {[s.name for s in scripts]}")
for script in scripts:
    texto = script.read_text(encoding="utf-8")
    cmds = comandos(texto)
    confere(cmds, f"{script.name}: sem nenhum comando")
    todos = [" ".join(c.lower().split()) for c in cmds]
    for cmd in cmds:
        baixo = " ".join(cabecalho(cmd).lower().split())
        # ("on delete cascade" dentro de um create table é opção de chave estrangeira, não um comando que apaga dado: por isso só o começo do comando conta)
        perigoso = re.match(r"(drop|delete|truncate|update|insert)\b", baixo) or (baixo.startswith("alter table") and re.search(r"\b(drop|rename)\b|alter column \w+ (set data )?type", baixo))
        confere(not perigoso, f"{script.name}: comando que apaga, renomeia ou reescreve dado: {baixo[:70]}")
        if re.match(r"create (unique )?(table|index)\b", baixo):
            confere("if not exists" in baixo, f"{script.name}: precisa de 'if not exists' para poder rodar de novo: {baixo[:70]}")
        if re.match(r"create (or replace )?function\b", baixo):
            confere(baixo.startswith("create or replace function"), f"{script.name}: função precisa de 'create or replace' para poder rodar de novo: {baixo[:70]}")
            nome = re.match(r"create or replace function (\w+)\s*\(", baixo)
            confere(nome is not None, f"{script.name}: não entendi o nome da função: {baixo[:70]}")
            if nome:
                fechada = [t for t in todos if re.match(rf"revoke all on function {nome.group(1)}\(", t)]
                confere(len(fechada) == 1 and all(p in fechada[0] for p in ("public", "anon", "authenticated")),
                        f"{script.name}: a função {nome.group(1)} precisa de 'revoke all ... from public, anon, authenticated' (por padrão qualquer um pode chamar)")
                abertas = [t for t in todos if re.match(rf"grant execute on function {nome.group(1)}\(", t)]
                confere(len(abertas) == 1 and abertas[0].endswith("to service_role"), f"{script.name}: a função {nome.group(1)} só pode ser liberada para service_role: {abertas}")
            confere("security definer" not in baixo, f"{script.name}: função com 'security definer' roda com os direitos do dono: precisa de revisão de segurança, não entra por aqui")
        if re.match(r"create table\b", baixo):
            tabela = re.match(r"create table (?:if not exists )?(\w+)", baixo)
            confere(tabela is not None and f"alter table {tabela.group(1)} enable row level security" in todos,
                    f"{script.name}: a tabela {tabela.group(1) if tabela else '?'} precisa de 'alter table ... enable row level security' (sem política: só a chave secreta acessa)")
        if re.match(r"create policy\b", baixo):
            confere(False, f"{script.name}: política de acesso liberaria a chave pública: {baixo[:70]}")
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
