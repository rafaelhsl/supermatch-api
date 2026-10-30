"""Testes da parte de levantar_entrega.py que não precisa de navegador: como as sondagens viram a situação da cidade.

Rodar com:  python tests/test_levantar_entrega.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import levantar_entrega as le  # noqa: E402


def sond(status):
    return {"status": status}


def teste_situacao_da_cidade():
    s = le.situacao_da_cidade
    assert s([])["situacao"] == "sem_dados"
    assert s([sond("atende")] * 3) == {"situacao": "atende", "ceps_que_atendem": 3, "ceps_testados": 3, "ceps_em_duvida": 0}
    assert s([sond("atende"), sond("nao_atende")])["situacao"] == "parcial"
    assert s([sond("atende"), sond("nao_confirmou")])["situacao"] == "parcial"
    assert s([sond("nao_atende"), sond("nao_confirmou")])["situacao"] == "nao_atende"
    # o robô se perdeu: não dá para afirmar nada sobre a cidade inteira
    assert s([sond("inconclusivo")])["situacao"] == "duvidoso"
    assert s([sond("atende"), sond("inconclusivo")])["situacao"] == "duvidoso"
    assert s([sond("nao_atende"), sond("inconclusivo")])["situacao"] == "duvidoso"
    assert s([sond("atende"), sond("inconclusivo")])["ceps_em_duvida"] == 1


def teste_celula_e_documento():
    info = le.situacao_da_cidade([sond("atende"), sond("atende"), sond("nao_confirmou")])
    assert le.celula(info) == "Só em parte (2 de 3)"
    assert le.celula(le.situacao_da_cidade([])) == "Sem dados"

    amostras = [{"cidade": "Betim", "cep": "32607600", "bairro": "Teixeirinha", "logradouro": "Avenida Um"},
                {"cidade": "Contagem", "cep": "32041000", "bairro": "Centro", "logradouro": "Praça"},
                {"cidade": "Contagem", "cep": "32040030", "bairro": "Centro", "logradouro": "Rua"}]
    resultados = []
    for a in amostras:
        for m in le.MERCADOS:
            status = "nao_atende" if (m == "Super ABC" and a["cidade"] == "Contagem") else "atende"
            if m in le.SO_UMA_POR_CIDADE and a["cep"] == "32040030":
                continue   # o Super ABC só é sondado uma vez por cidade
            resultados.append({"mercado": m, "cep": a["cep"], "cidade": a["cidade"], "bairro": a["bairro"], "status": status,
                               "data": "2026-10-30T10:00:00+00:00", "detalhe": "loja Betim, CEP 32607-600" if m == "Atacadao" else None})
    original = (le.ler_json, le.AMOSTRAS, le.RESULTADOS)
    le.ler_json = lambda caminho, padrao: resultados if caminho == le.RESULTADOS else amostras
    try:
        tabela, res, am = le.montar_tabela()
    finally:
        le.ler_json = original[0]
    assert tabela["Betim"]["Super ABC"]["situacao"] == "atende"
    assert tabela["Contagem"]["Super ABC"]["situacao"] == "nao_atende"
    assert tabela["Contagem"]["Super ABC"]["ceps_testados"] == 2      # a sondagem do Super ABC vale pela cidade inteira
    assert tabela["Contagem"]["Apoio Entrega"]["situacao"] == "atende"
    doc = le.gerar_documento(tabela, res, am)
    assert "# Entrega por cidade" in doc and "| Contagem |" in doc and "32041-000" in doc
    assert "mesma da cidade" in doc                                    # o segundo CEP de Contagem herda o resultado do Super ABC
    assert "Última sondagem: 2026-10-30" in doc


if __name__ == "__main__":
    teste_situacao_da_cidade()
    teste_celula_e_documento()
    print("ok: 2 testes passaram")
