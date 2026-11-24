"""Ajudantes para ler os scripts SQL de docs/sql/ (usados por tests/test_sql.py e tests/test_medidor_de_uso.py). Não é um teste: o CI só roda tests/test_*.py."""
import re


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


def corpo(comando):
    """O que está entre $$ e $$ (o corpo da função), ou None."""
    achou = re.search(r"\$\$(.*?)\$\$", comando, flags=re.S)
    return achou.group(1) if achou else None


def normalizado(comando):
    """O comando em minúsculas e com os espaços e quebras de linha reduzidos a um espaço."""
    return " ".join(comando.lower().split())
