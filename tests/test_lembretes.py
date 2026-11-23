"""Testes dos lembretes por data (lembretes.py, dados/lembretes.json e .github/workflows/lembretes.yml), sem rede e sem o `gh` de verdade.

Rodar com:  python tests/test_lembretes.py
"""
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import lembretes as lem  # noqa: E402


def um(quando, titulo="T", vence="2099-01-01", texto="x"):
    return {"quando": date.fromisoformat(quando), "vence": date.fromisoformat(vence), "titulo": titulo, "texto": texto}


class GhFalso:
    """Responde como o `gh`: lista as issues que existem e guarda as que lhe pedem para abrir."""

    def __init__(self, existentes=(), falha_na_lista=False):
        self.existentes, self.criadas, self.chamadas, self.falha_na_lista = list(existentes), [], [], falha_na_lista

    def __call__(self, argumentos):
        self.chamadas.append(argumentos)
        if argumentos[:2] == ["issue", "list"]:
            if self.falha_na_lista:
                raise RuntimeError("gh: sem permissão")
            return json.dumps([{"title": t} for t in self.existentes])
        if argumentos[:2] == ["issue", "create"]:
            titulo = argumentos[argumentos.index("--title") + 1]
            self.criadas.append({"titulo": titulo, "corpo": argumentos[argumentos.index("--body") + 1], "dono": argumentos[argumentos.index("--assignee") + 1] if "--assignee" in argumentos else None})
            self.existentes.append(titulo)
            return f"https://github.com/o/r/issues/{len(self.criadas)}\n"
        raise AssertionError(f"chamada inesperada ao gh: {argumentos}")


def arquivo_temporario(lembretes):
    pasta = Path(tempfile.mkdtemp())
    caminho = pasta / "lembretes.json"
    caminho.write_text(json.dumps({"lembretes": lembretes}), encoding="utf-8")
    return caminho


# ---------------------------------------------------------------- quando abrir

def teste_so_abre_quando_chega_o_dia():
    ls = [um("2027-10-13", "A"), um("2027-11-06", "B")]
    assert lem.a_criar(ls, date(2027, 10, 12), set()) == []                       # véspera: nada
    assert [l["titulo"] for l in lem.a_criar(ls, date(2027, 10, 13), set())] == ["A"]    # no dia: o primeiro
    assert [l["titulo"] for l in lem.a_criar(ls, date(2027, 11, 6), set())] == ["A", "B"]


def teste_lembrete_atrasado_ainda_abre():
    """Melhor tarde que nunca: se o workflow ficou parado (ou o GitHub o desligou por inatividade), o lembrete sai quando voltar."""
    assert [l["titulo"] for l in lem.a_criar([um("2027-10-13", "A")], date(2027, 12, 1), set())] == ["A"]


def teste_nao_abre_duas_vezes_a_mesma_issue_nem_se_ela_foi_fechada():
    ls = [um("2027-10-13", "A"), um("2027-11-06", "B")]
    assert [l["titulo"] for l in lem.a_criar(ls, date(2028, 1, 1), {lem.PREFIXO + "A"})] == ["B"]
    assert lem.a_criar(ls, date(2028, 1, 1), {lem.PREFIXO + "A", lem.PREFIXO + "B"}) == []
    assert [l["titulo"] for l in lem.a_criar(ls, date(2028, 1, 1), {"A"})] == ["A", "B"]      # o título tem de ser o da issue, com o prefixo


# ---------------------------------------------------------------- o que acontece de verdade

def rodar(caminho, hoje, gh, saida=None, criar=True, fingindo=False):
    """principal() num dia `hoje` (AAAA-MM-DD): pelo relógio de verdade (injetado) ou, com fingindo=True, pelo --hoje (o modo de teste)."""
    argumentos = (["--criar"] if criar else []) + ["--arquivo", str(caminho)] + (["--hoje", hoje] if fingindo else [])
    escritas = saida if saida is not None else []
    return lem.principal(argumentos, gh, escritas.append, relogio=lambda: date.fromisoformat(hoje))


DOIS = [{"quando": "2027-10-13", "vence": "2027-11-13", "titulo": "A", "texto": "texto A"},
        {"quando": "2027-11-06", "vence": "2027-11-13", "titulo": "B", "texto": "texto B"}]


def teste_principal_abre_so_o_que_chegou_e_so_uma_vez():
    caminho = arquivo_temporario(DOIS)
    gh = GhFalso()
    assert rodar(caminho, "2027-10-14", gh) == 0
    assert [c["titulo"] for c in gh.criadas] == ["Lembrete: A"] and "texto A" in gh.criadas[0]["corpo"] and "13/10/2027" in gh.criadas[0]["corpo"]
    assert "prazo é 13/11/2027" in gh.criadas[0]["corpo"] and "14/10/2027" in gh.criadas[0]["corpo"] and "TESTE" not in gh.criadas[0]["corpo"]
    listagens = [c for c in gh.chamadas if c[:2] == ["issue", "list"]]
    assert listagens and all(c[c.index("--state") + 1] == "all" for c in listagens), "tem de olhar as issues fechadas também"
    rodar(caminho, "2027-10-15", gh)                                            # no dia seguinte: nada de novo
    assert len(gh.criadas) == 1
    rodar(caminho, "2027-11-06", gh)                                            # no dia do segundo: só o segundo
    assert [c["titulo"] for c in gh.criadas] == ["Lembrete: A", "Lembrete: B"]


def teste_a_issue_vai_para_o_dono():
    caminho = arquivo_temporario(DOIS[:1])
    import os
    gh = GhFalso()
    anterior = os.environ.get("GITHUB_REPOSITORY_OWNER")
    os.environ["GITHUB_REPOSITORY_OWNER"] = "rafaelhsl"
    try:
        rodar(caminho, "2027-10-13", gh)
    finally:
        os.environ.pop("GITHUB_REPOSITORY_OWNER") if anterior is None else os.environ.__setitem__("GITHUB_REPOSITORY_OWNER", anterior)
    assert gh.criadas[0]["dono"] == "rafaelhsl"


def teste_sem_criar_nao_abre_nada():
    caminho = arquivo_temporario(DOIS[:1])
    gh, saida = GhFalso(), []
    rodar(caminho, "2027-12-01", gh, saida, criar=False)
    assert gh.criadas == [] and any("para abrir (rode com --criar)" in s for s in saida)
    antes = []
    rodar(caminho, "2027-10-01", GhFalso(), antes, criar=False)
    assert any("daqui a 12 dia(s)" in s for s in antes)                              # antes do dia: diz quantos dias faltam


def teste_se_nao_da_para_saber_o_que_ja_existe_nao_cria_issue_repetida():
    caminho = arquivo_temporario(DOIS[:1])
    gh = GhFalso(falha_na_lista=True)
    try:
        rodar(caminho, "2027-12-01", gh)
    except RuntimeError:
        pass
    else:
        raise AssertionError("sem poder listar as issues, criar de verdade tem de falhar (o workflow fica vermelho e o dono é avisado)")
    assert gh.criadas == []
    saida = []
    rodar(caminho, "2027-12-01", gh, saida, criar=False)                           # só olhando, segue e avisa
    assert any("não consegui consultar" in s for s in saida) and gh.criadas == []


# ---------------------------------------------------------------- o teste (--hoje) não atrapalha o de verdade

def teste_com_data_fingida_a_issue_sai_com_titulo_de_teste():
    caminho = arquivo_temporario(DOIS[:1])
    gh = GhFalso()
    rodar(caminho, "2027-10-14", gh, fingindo=True)
    assert [c["titulo"] for c in gh.criadas] == ["TESTE: Lembrete: A"]
    assert gh.criadas[0]["corpo"].startswith("**ISSUE DE TESTE**") and "texto A" in gh.criadas[0]["corpo"]


def teste_a_issue_de_teste_nao_impede_o_lembrete_de_verdade():
    """O erro que isto evita: a issue de teste (mesmo título, fechada) faria a regra "uma issue por título" calar o lembrete do dia 13/10/2027."""
    caminho = arquivo_temporario(DOIS[:1])
    gh = GhFalso()
    rodar(caminho, "2027-10-14", gh, fingindo=True)                                # o teste, depois fechado: a issue continua na lista (estado "all")
    assert gh.existentes == ["TESTE: Lembrete: A"]
    rodar(caminho, "2027-10-13", gh)                                               # o dia de verdade
    assert [c["titulo"] for c in gh.criadas] == ["TESTE: Lembrete: A", "Lembrete: A"], "o lembrete de verdade tem de abrir mesmo depois de um teste"
    rodar(caminho, "2027-10-14", gh)                                               # e agora o de verdade não repete
    assert len(gh.criadas) == 2


def teste_o_teste_pode_ser_repetido_e_nao_depende_do_que_ja_existe():
    caminho = arquivo_temporario(DOIS[:1])
    gh = GhFalso(existentes=["Lembrete: A"])                                       # a de verdade já existe
    rodar(caminho, "2027-10-14", gh, fingindo=True)
    rodar(caminho, "2027-10-14", gh, fingindo=True)
    assert [c["titulo"] for c in gh.criadas] == ["TESTE: Lembrete: A", "TESTE: Lembrete: A"]
    assert lem.a_criar([um("2027-10-13", "A")], date(2027, 10, 14), {"Lembrete: A"}, teste=False) == []        # (sem teste, a existente vale)


def teste_a_saida_avisa_quando_e_teste():
    caminho = arquivo_temporario(DOIS[:1])
    saida = []
    rodar(caminho, "2027-10-14", GhFalso(), saida, criar=False, fingindo=True)
    assert any("TESTE" in s and "data fingida" in s for s in saida)
    sem = []
    rodar(caminho, "2027-10-14", GhFalso(), sem, criar=False)
    assert not any("TESTE" in s for s in sem)


# ---------------------------------------------------------------- o arquivo de lembretes

def teste_arquivo_mal_formado_e_recusado():
    ruins = [
        ([{"quando": "2027-10-13", "vence": "2027-11-13", "titulo": "A"}], "faltam"),                                              # sem texto
        ([{"quando": "13/10/2027", "vence": "2027-11-13", "titulo": "A", "texto": "x"}], ""),                                       # data fora do padrão
        ([{"quando": "2027-11-13", "vence": "2027-11-13", "titulo": "A", "texto": "x"}], "ANTES"),                                  # lembrar no dia de vencer
        ([{"quando": "2027-12-01", "vence": "2027-11-13", "titulo": "A", "texto": "x"}], "ANTES"),
        ([{"quando": "2027-10-13", "vence": "2027-11-13", "titulo": "A", "texto": "x"}] * 2, "repetido"),                         # o título é a chave
        ([{"quando": "2027-10-13", "vence": "2027-11-13", "titulo": "  ", "texto": "x"}], "faltam"),
    ]
    for lembretes, trecho in ruins:
        try:
            lem.carregar(arquivo_temporario(lembretes))
        except (ValueError, KeyError) as erro:
            assert trecho in str(erro), (lembretes, str(erro))
        else:
            raise AssertionError(f"devia recusar: {lembretes}")


def teste_os_lembretes_do_repositorio():
    ls = lem.carregar()
    assert len(ls) >= 3
    for l in ls:
        assert (l["vence"] - l["quando"]).days >= 6, f"{l['titulo']}: lembrar com pelo menos uma semana de folga"
        assert len(l["texto"]) > 80 and len(l["titulo"]) > 20
    texto_todo = " ".join(l["titulo"] + " " + l["texto"] for l in ls)
    assert "cron-job.org" in texto_todo and "X-GitHub-Api-Version" in texto_todo and "docs/carga_diaria.md" in texto_todo
    renovar = next(l for l in ls if l["titulo"].startswith("Renovar o token"))
    assert "X-GitHub-Api-Version" in renovar["texto"] and "10/03/2028" in renovar["texto"], "na renovação do token é que se troca a versão da API (ela deixa de funcionar em 10/03/2028)"
    assert "dados/lembretes.json" in renovar["texto"], "o lembrete manda acrescentar os próximos lembretes (senão o de 2028 em diante some)"
    assert "Não cole o token" in texto_todo or "Não cole o token".lower() in texto_todo.lower(), "o lembrete repete: o token não vai em conversa nenhuma"


def teste_as_datas_dos_lembretes_batem_com_a_documentacao():
    """O token vence em 13/11/2027 e a versão da API do GitHub deixa de funcionar em 10/03/2028 (docs/carga_diaria.md)."""
    docs = (RAIZ / "docs" / "carga_diaria.md").read_text(encoding="utf-8")
    assert "13/11/2027" in docs and "10/03/2028" in docs
    ls = lem.carregar()
    vencimentos = {l["vence"] for l in ls}
    assert date(2027, 11, 13) in vencimentos and date(2028, 3, 10) in vencimentos
    assert [l for l in ls if "13/11/2027" in l["titulo"]] and [l for l in ls if "10/03/2028" in l["titulo"]]
    assert min(l["quando"] for l in ls if l["vence"] == date(2027, 11, 13)) <= date(2027, 10, 15), "o primeiro aviso do token sai com ~um mês de folga"


# ---------------------------------------------------------------- o workflow

def teste_o_workflow_so_pode_abrir_issue():
    fluxo = (RAIZ / ".github" / "workflows" / "lembretes.yml").read_text(encoding="utf-8")
    assert re.search(r"permissions:\s*\n\s+contents: read\s*\n\s+issues: write\s*\n", fluxo), "permissões mínimas: ler o código e abrir issue"
    assert not re.search(r"secrets\.", fluxo), "o workflow não usa nenhum segredo: só o token da própria execução"
    assert "GH_TOKEN: ${{ github.token }}" in fluxo
    assert not re.search(r"contents:\s*write|actions:\s*write|pull-requests:\s*write", fluxo)
    assert "schedule:" in fluxo and re.search(r"cron: '\d+ \d+ \* \* \*'", fluxo) and not re.search(r"cron: '0 ", fluxo), "diário e fora do minuto 00 (em que o GitHub mais atrasa)"
    minuto = int(re.search(r"cron: '(\d+) ", fluxo).group(1))
    assert minuto not in (0, 15, 30, 45)
    assert "workflow_dispatch:" in fluxo
    assert "python lembretes.py" in fluxo and "--criar" in fluxo
    # disparado à mão, só cria se pedir "sim"; agendado cria sempre
    assert "github.event_name == 'schedule' || inputs.criar == 'sim'" in fluxo
    assert re.search(r"criar:.*?default: nao", fluxo, re.S)
    assert "actions/checkout@v7" in fluxo and "actions/setup-python@v7" in fluxo       # as mesmas versões dos outros workflows (Node 24)


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
