"""Testes do disjuntor por mercado (disjuntor.py), sem rede.

Rodar com:  python tests/test_disjuntor.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import disjuntor as d  # noqa: E402


def teste_abre_depois_de_n_falhas_seguidas():
    corte = d.Disjuntor(3)
    corte.errou("a")
    corte.errou("b")
    assert not corte.aberto and corte.seguidas == 2            # duas falhas ainda não abrem
    corte.errou("c")
    assert corte.aberto and corte.seguidas == 3                # a terceira abre


def teste_um_acerto_no_meio_zera_a_contagem():
    corte = d.Disjuntor(3)
    for _ in range(10):                                        # falha, falha, acerto, falha, falha, acerto...: nunca 3 seguidas
        corte.errou("x")
        corte.errou("x")
        corte.acertou()
    assert not corte.aberto and corte.seguidas == 0


def teste_depois_de_aberto_fica_aberto():
    corte = d.Disjuntor(2)
    corte.errou("x")
    corte.errou("x")
    assert corte.aberto
    corte.acertou()                                            # um robô que já estava em andamento terminou bem: não reabre o mercado
    assert corte.aberto


def teste_limite_zero_desliga_o_disjuntor():
    corte = d.Disjuntor(0)
    for _ in range(500):
        corte.errou("x")
    assert not corte.aberto


def teste_limite_padrao_e_lido_na_hora():
    assert d.Disjuntor().limite == d.LIMITE_DE_FALHAS_SEGUIDAS == 6
    anterior = d.LIMITE_DE_FALHAS_SEGUIDAS
    d.LIMITE_DE_FALHAS_SEGUIDAS = 2
    try:
        assert d.Disjuntor().limite == 2                       # o padrão vale no momento em que o disjuntor nasce
    finally:
        d.LIMITE_DE_FALHAS_SEGUIDAS = anterior


def teste_a_explicacao_diz_quantas_vezes_e_o_que_aconteceu():
    corte = d.Disjuntor(2)
    corte.errou("HTTP 403 em https://www.atacadao.com.br/api/graphql")
    corte.errou("HTTP 403 em https://www.atacadao.com.br/api/graphql")
    texto = corte.motivo_de_pulo()
    assert texto.startswith(d.NAO_TENTADO) and "2 vezes seguidas" in texto and "HTTP 403" in texto
    assert d.foi_pulado(texto)


def teste_a_explicacao_nao_carrega_um_erro_gigante():
    corte = d.Disjuntor(1)
    corte.errou("x" * 5000)
    assert len(corte.explicacao()) < 400


def teste_foi_pulado_so_reconhece_o_que_o_disjuntor_escreveu():
    assert d.foi_pulado(d.Disjuntor(1).motivo_de_pulo())
    assert not d.foi_pulado("HTTP 403 em https://x")
    assert not d.foi_pulado("o robô não tentado nunca")        # a palavra no meio do texto não conta
    assert not d.foi_pulado("") and not d.foi_pulado(None)


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_")]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
