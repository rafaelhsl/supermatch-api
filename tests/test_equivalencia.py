"""Testes do motor de produto equivalente (equivalencia.py).

Rodar com:  python tests/test_equivalencia.py

Duas partes:
1. PARIDADE: as 11 famílias que viviam em site/index.html foram traduzidas para Python. Os casos do teste em JavaScript
   (o antigo tests/test_equivalencia.js, já removido) foram extraídos para tests/casos_equivalencia_legado.json e rodam aqui contra as 11 famílias
   originais. Se um caso falhar, a tradução mudou o comportamento.
2. FAMÍLIAS NOVAS: casos de nomes reais dos mercados. "juntam" garante que marcas diferentes caem no mesmo grupo; "separam",
   que o que não é equivalente nunca é juntado; "fora", que o que não dá para garantir fica sem chave.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import equivalencia as eq  # noqa: E402

QUANTAS_ORIGINAIS = 11
ORIGINAIS = eq.FAMILIAS[:QUANTAS_ORIGINAIS]
LEGADO = json.loads((Path(__file__).parent / "casos_equivalencia_legado.json").read_text(encoding="utf-8"))
ok, erros = 0, []


def confere(condicao, texto):
    global ok
    if condicao:
        ok += 1
    else:
        erros.append(texto)


def chave(nome, familias=None):
    r = eq.equivalencia(nome, familias)
    return r.chave if r else None


def juntam(*nomes, familias=None):
    chaves = [chave(n, familias) for n in nomes]
    confere(chaves[0] is not None and all(c == chaves[0] for c in chaves), f"deveriam ser equivalentes: {' | '.join(nomes)}  ->  {chaves}")


def separam(a, b, familias=None):
    ca, cb = chave(a, familias), chave(b, familias)
    confere(ca is not None and cb is not None and ca != cb, f"deveriam ser reconhecidos e diferentes: {a} -> {ca} | {b} -> {cb}")


def fora(nome, familias=None):
    confere(chave(nome, familias) is None, f"deveria ficar de fora: {nome} -> {chave(nome, familias)}")


# ============================== 1. paridade com o motor em JavaScript ==============================

for caso in LEGADO["juntam"]:
    juntam(*caso, familias=ORIGINAIS)
for a, b in LEGADO["separam"]:
    separam(a, b, familias=ORIGINAIS)
for nome in LEGADO["fora"]:
    fora(nome, familias=ORIGINAIS)
confere(len(LEGADO["juntam"]) == 19 and len(LEGADO["separam"]) == 21 and len(LEGADO["fora"]) == 23, "o arquivo de casos legados mudou de tamanho")
confere([f.id for f in ORIGINAIS] == ["arroz", "feijao", "oleo", "cafe", "manteiga", "acucar", "macarrao", "detergente", "sabao", "amaciante", "papel"],
        f"as 11 primeiras famílias mudaram de lugar: {[f.id for f in ORIGINAIS]}")

# o rótulo e a chave do exemplo que o teste em JavaScript confere
r = eq.equivalencia("Arroz Branco Camil Tipo 1 5kg")
confere(r is not None and r.rotulo == "Arroz branco tipo 1, 5 kg" and r.chave == "arroz|branco|tipo 1|5000g", f"rótulo/chave do arroz: {r}")


# ============================== 2. famílias novas ==============================

if __name__ == "__main__":
    # os casos novos vêm do módulo tests/casos_equivalencia_novos.py, para este arquivo não crescer sem fim
    try:
        from casos_equivalencia_novos import CASOS
    except ImportError:
        CASOS = {"juntam": [], "separam": [], "fora": []}
    for caso in CASOS["juntam"]:
        juntam(*caso)
    for a, b in CASOS["separam"]:
        separam(a, b)
    for nome in CASOS["fora"]:
        fora(nome)
    # toda família declarada tem pelo menos um caso que a prova
    cobertas = {eq.equivalencia(n).chave.split("|")[0] for caso in [*LEGADO["juntam"], *CASOS["juntam"]] for n in caso if eq.equivalencia(n)}
    faltam = [f.id for f in eq.FAMILIAS if f.id not in cobertas]
    confere(not faltam, f"famílias sem caso 'juntam' que as prove: {faltam}")

    # sanidade da interface
    confere(len(eq.familias_equivalentes()) == len(eq.FAMILIAS) and "arroz" in eq.familias_equivalentes() and "leite" in eq.familias_equivalentes(), "lista de famílias")
    com = eq.com_equivalencia([{"nome": "Arroz Branco Camil Tipo 1 5kg", "id": 1}, {"nome": "Shampoo Qualquer 350ml", "id": 2}])
    confere(com[0]["chave_equivalencia"].startswith("arroz|") and "chave_equivalencia" not in com[1], f"com_equivalencia: {com}")
    confere("chave_equivalencia" not in {"nome": "x"}, "o produto original não é alterado")
    original = {"nome": "Arroz Branco Camil Tipo 1 5kg"}
    eq.com_equivalencia([original])
    confere(original == {"nome": "Arroz Branco Camil Tipo 1 5kg"}, "com_equivalencia devolve cópias")

    if erros:
        print(f"{len(erros)} falha(s):\n  - " + "\n  - ".join(erros))
        sys.exit(1)
    print(f"ok: {ok} verificações passaram")
