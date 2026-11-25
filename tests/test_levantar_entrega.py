"""Testes da parte de levantar_entrega.py que não precisa de navegador: como as sondagens viram a situação da cidade.

Rodar com:  python tests/test_levantar_entrega.py
"""
import asyncio
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletor_vtex  # noqa: E402
import levantar_entrega as le  # noqa: E402
import robos_comum  # noqa: E402
import test_coletor_vip as tv  # noqa: E402     # a loja falsa do Super ABC


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


def teste_atualizar_site():
    import tempfile
    tabela = {"Betim": {"Atacadao": {"situacao": "atende"}, "Super ABC": {"situacao": "nao_atende"}},
              "Sabará": {"Atacadao": {"situacao": "parcial"}, "Super ABC": {"situacao": "nao_atende"}}}
    antes = "<script>\n  /* @entrega-inicio */\n  const ENTREGA_POR_CIDADE = {};\n  /* @entrega-fim */\n  const resto = 1;\n</script>\n"
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / "index.html"
        arquivo.write_text(antes, encoding="utf-8")
        original = le.SITE
        le.SITE = arquivo
        try:
            assert le.atualizar_site(tabela) is True
            depois = arquivo.read_text(encoding="utf-8")
            assert le.atualizar_site(tabela) is True and arquivo.read_text(encoding="utf-8") == depois   # idempotente
            sem_marca = Path(pasta) / "sem_marca.html"
            sem_marca.write_text("<html></html>", encoding="utf-8")
            le.SITE = sem_marca
            assert le.atualizar_site(tabela) is False
        finally:
            le.SITE = original
    assert '"Betim": {' in depois and '"Atacadao": "atende"' in depois and '"Sabará"' in depois      # só a situação vai para o site
    assert "ceps_testados" not in depois
    assert depois.count("@entrega-inicio") == 1 and depois.count("@entrega-fim") == 1 and "const resto = 1;" in depois


def teste_ultima_sondagem_diz_a_data_de_cada_mercado_quando_diferem():
    r = lambda mercado, data: {"mercado": mercado, "data": data}
    assert le.ultima_sondagem([]) == "sem dados"
    assert le.ultima_sondagem([r("Atacadao", "2026-10-30T09:00:00+00:00"), r("Super ABC", "2026-10-30T10:00:00+00:00")]) == "2026-10-30"
    assert le.ultima_sondagem([r("Atacadao", "2026-10-30T09:00:00+00:00"), r("Atacadao", "2026-10-29T09:00:00+00:00"), r("Super ABC", "2026-11-25T10:00:00+00:00")]) \
        == "Atacadão 2026-10-30; Super ABC 2026-11-25"


def teste_documento_nao_abre_parenteses_dentro_dos_parenteses():
    amostras = [{"cidade": "Belo Horizonte", "cep": "30130010", "bairro": "Centro", "logradouro": "Rua"}]
    resultados = [{"mercado": "Super ABC", "cep": "30130010", "cidade": "Belo Horizonte", "bairro": "Centro", "status": "atende", "data": "2026-11-25T10:00:00+00:00",
                   "detalhe": "ABC - Belo Horizonte (Horto)"},
                  {"mercado": "Super ABC", "cep": "32600055", "cidade": "Betim", "bairro": "Centro", "status": "atende", "data": "2026-10-30T10:00:00+00:00",
                   "detalhe": "ABC Atacado e Varejo Betim Betim / MG"}]
    doc = le.gerar_documento({"Belo Horizonte": {m: le.situacao_da_cidade([]) for m in le.MERCADOS}}, resultados, amostras)
    assert "entrega (Belo Horizonte - Horto)" in doc and "(Horto))" not in doc
    doc = le.gerar_documento({"Betim": {m: le.situacao_da_cidade([]) for m in le.MERCADOS}}, resultados, [dict(amostras[0], cidade="Betim", cep="32600055")])
    assert "entrega (Betim Betim)" in doc                                                      # o texto de uma sondagem antiga, do robô, continua legível


# ---------------- o Super ABC pela API da loja ----------------

UNIDADES_DA_REDE = [tv.unidade(1, "ABC - Divinópolis (Goiás)", "Divinópolis"), tv.unidade(19, "ABC - Belo Horizonte (Horto)", "Belo Horizonte"),
                    tv.unidade(24, "ABC - Belo Horizonte (Barreiro)", "Belo Horizonte"), tv.unidade(8, "ABC - Betim", "Betim")]
CIDADE_DO_CEP = {"30130010": ("Belo Horizonte", "MG"), "32600055": ("Betim", "MG"), "32041000": ("Contagem", "MG"), "99999999": None}
CONSULTAS_DO_CEP = []          # cada consulta de cidade, para o teste da repetição


def cidade_do_cep_de_mentira(cep, timeout=5):
    CONSULTAS_DO_CEP.append(cep)
    if cep == "88888888":                                     # o ViaCEP falha na 1ª consulta e responde na 2ª
        return None if CONSULTAS_DO_CEP.count(cep) == 1 else ("Betim", "MG")
    return CIDADE_DO_CEP[cep]


def sondar_super_abc(cep, loja):
    """`le.sondar("Super ABC", cep)` com a loja falsa no lugar da rede e a cidade do CEP de mentira."""
    with mock.patch.object(coletor_vtex, "ClienteHttp", lambda: loja), mock.patch.object(robos_comum, "cidade_do_cep", cidade_do_cep_de_mentira):
        return asyncio.run(le.sondar("Super ABC", cep))      # o que o robô imprime é capturado por `sondar` (é dali que sai o `detalhe`)


def teste_super_abc_com_unidade_na_cidade_atende():
    catalogo = {"arroz": [tv.produto(1, "Arroz Tipo 1 Camil 5 Kg", "18.90")]}
    betim = sondar_super_abc("32600055", tv.LojaFalsa(catalogo, unidades=UNIDADES_DA_REDE))
    assert betim["status"] == "atende" and betim["produtos"] == 1 and betim["detalhe"] == "ABC - Betim", betim
    muitos = {"arroz": [tv.produto(i, f"Arroz {i}") for i in range(100)]}                                     # 5 páginas na loja
    loja = tv.LojaFalsa(muitos, unidades=UNIDADES_DA_REDE)
    bh = sondar_super_abc("30130010", loja)
    assert bh["status"] == "atende" and bh["detalhe"] == "ABC - Belo Horizonte (Horto)", bh                  # duas unidades na cidade: a primeira da lista
    assert all("/centro_distribuicao/19/" in u for u in tv.buscas(loja)) and len(tv.buscas(loja)) == 1          # busca "arroz" na unidade da cidade, uma página só


def teste_super_abc_sem_unidade_na_cidade_nao_atende_de_vez():
    loja = tv.LojaFalsa({"arroz": [tv.produto(1, "Arroz")]}, unidades=UNIDADES_DA_REDE)
    contagem = sondar_super_abc("32041000", loja)
    assert contagem["status"] == "nao_atende" and "não tem unidade em Contagem/MG" in contagem["motivo"], contagem
    assert tv.buscas(loja) == [] and loja.logins == 1                                                          # definitivo: nenhuma busca, nenhuma repetição


def teste_super_abc_unidade_sem_produto_ainda_atende_com_a_observacao():
    resultado = sondar_super_abc("32600055", tv.LojaFalsa({"arroz": [tv.produto(1, "Arroz", disponivel=False)]}, unidades=UNIDADES_DA_REDE))
    assert resultado["status"] == "atende" and "não trouxe nenhum produto" in resultado["motivo"] and resultado["observacao"], resultado


def teste_super_abc_falha_passageira_e_inconclusiva_e_nao_recusa():
    # cidade do CEP desconhecida (ViaCEP e BrasilAPI fora do ar): não dá para dizer nada sobre a cidade
    resultado = sondar_super_abc("99999999", tv.LojaFalsa({}, unidades=UNIDADES_DA_REDE))
    assert resultado["status"] == "inconclusivo" and "cidade do CEP" in resultado["motivo"], resultado
    # a chave pública do site mudou: o login falha, e isso também não diz que a cidade não é atendida
    resultado = sondar_super_abc("32600055", tv.LojaFalsa({}, unidades=UNIDADES_DA_REDE, chave_certa=False))
    assert resultado["status"] == "inconclusivo" and "login anônimo" in resultado["motivo"], resultado
    assert le.situacao_da_cidade([resultado])["situacao"] == "duvidoso"


def teste_super_abc_repete_a_falha_passageira_como_os_robos():
    del CONSULTAS_DO_CEP[:]
    resultado = sondar_super_abc("88888888", tv.LojaFalsa({"arroz": [tv.produto(1, "Arroz")]}, unidades=UNIDADES_DA_REDE))
    assert resultado["status"] == "atende" and CONSULTAS_DO_CEP == ["88888888", "88888888"], (resultado, CONSULTAS_DO_CEP)


def teste_super_abc_nao_usa_mais_o_robo_de_navegador():
    texto = Path(le.__file__).read_text(encoding="utf-8")
    assert "Scraper_SuperABC" not in texto and "superabconline" not in texto


if __name__ == "__main__":
    testes = [fn for nome, fn in sorted(globals().items()) if nome.startswith("teste_")]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
