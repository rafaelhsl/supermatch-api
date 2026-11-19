"""Testes do que a API escreve no log sobre o CEP (api_supabase.py), sem rede e sem banco.

O aviso de privacidade do site diz que "nos nossos registros ficam o que você buscou e só os 5 primeiros dígitos do CEP". Estes testes é que
tornam essa frase verdadeira: o CEP inteiro, junto com o IP que o provedor registra, localiza uma casa.

Rodar com:  python tests/test_privacidade.py   (precisa de fastapi, uvicorn, supabase e thefuzz, do requirements.txt)
"""
import contextlib
import io
import logging
import os
import re
import sys
from pathlib import Path
from unittest import mock

os.environ.setdefault("SUPABASE_KEY", "chave-falsa-so-para-importar")      # a API cria o cliente ao importar
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import api_supabase as api  # noqa: E402


def teste_so_os_5_primeiros_digitos_vao_para_o_log():
    assert api.cep_para_o_log("30130010") == "30130-***"
    assert api.cep_para_o_log("30130-010") == "30130-***"
    assert api.cep_para_o_log(" 32607600 ") == "32607-***"
    assert api.cep_para_o_log(30130010) == "30130-***"


def teste_o_que_nao_e_cep_nao_vai_para_o_log():
    for lixo in ("", "abc", "301", "1234", None, "'; drop table produtos; --", "<script>alert(1)</script>", "../../etc/passwd"):
        assert api.cep_para_o_log(lixo) == "(CEP inválido)", lixo
    assert "\n" not in api.cep_para_o_log("30130\n010") and api.cep_para_o_log("30130\n010") == "30130-***"      # quebra de linha não forja linha de log


def pelo_log_de_acesso(caminho):
    """Escreve no logger do uvicorn como ele escreve (host, método, caminho, versão, status) e devolve o que sairia."""
    saida = io.StringIO()
    manipulador = logging.StreamHandler(saida)
    log = logging.getLogger("uvicorn.access")
    antes = log.level
    log.addHandler(manipulador)
    log.setLevel(logging.INFO)
    try:
        log.info('%s - "%s %s HTTP/%s" %d', "10.0.0.7:51234", "GET", caminho, "1.1", 200)
    finally:
        log.removeHandler(manipulador)
        log.setLevel(antes)
    return saida.getvalue().strip()


def teste_o_log_de_acesso_do_uvicorn_esconde_o_cep():
    assert any(isinstance(f, api.EsconderCepDoLogDeAcesso) for f in logging.getLogger("uvicorn.access").filters)      # ligado ao importar a API
    linha = pelo_log_de_acesso("/comparar?cep=30130010&item=arroz")
    assert "30130010" not in linha and "cep=30130-***&item=arroz" in linha and linha.startswith('10.0.0.7:51234 - "GET /comparar?')
    assert linha.endswith('HTTP/1.1" 200')                                                                         # o resto da linha fica intacto
    assert "cep=30130-***" in pelo_log_de_acesso("/comparar?item=arroz&cep=30130-010&todos=1") and "30130-010" not in pelo_log_de_acesso("/comparar?cep=30130-010")
    assert "cep=30130-***" in pelo_log_de_acesso("/comparar?CEP=30130010&item=x")                                    # caixa alta
    assert "cep=30130-***" in pelo_log_de_acesso("/comparar?cep=30130%2D010&item=x")                                 # hífen codificado
    assert "cep=30130-***&item=x" in pelo_log_de_acesso("/comparar?cep=%33%30%31%33%30%30%31%30&item=x")             # dígitos codificados: o começo mostrado é o certo
    assert "cep=(CEP inválido)" in pelo_log_de_acesso("/comparar?cep=&item=x")
    assert pelo_log_de_acesso("/saude") == '10.0.0.7:51234 - "GET /saude HTTP/1.1" 200'                              # sem CEP, nada muda
    assert "30130010" not in pelo_log_de_acesso("/comparar?item=arroz&cep=30130010")                                 # no fim do endereço


def teste_o_filtro_nao_quebra_registros_de_outro_formato():
    filtro = api.EsconderCepDoLogDeAcesso()
    for args in (None, (), ("so um",), {"a": 1}, ("a", "b", 3, "d", 5)):
        registro = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "mensagem", None, None)
        registro.args = args
        assert filtro.filter(registro) is True and registro.args == args


def teste_a_linha_de_pedido_recebido_so_traz_o_comeco_do_cep():
    class Busca:                                   # o que buscar_detalhado devolve, vazio
        produtos, ocultos_so_citam, ocultos_pelo_limite, so_citam_por_mercado = [], 0, 0, {}

    saida = io.StringIO()
    with mock.patch.object(api, "carregar_catalogo", lambda uf: []), mock.patch.object(api, "obter_uf_pelo_cep", lambda cep: "MG"), \
            mock.patch.object(api, "buscar_detalhado", lambda *a, **k: Busca()), contextlib.redirect_stdout(saida):
        api.buscar_e_comparar(cep="30130010", item="arroz")
    texto = saida.getvalue()
    assert "30130010" not in texto and "30130-***" in texto and "Item: 'arroz'" in texto


def teste_so_cep_de_8_digitos_vira_consulta_ao_viacep():
    chamadas = []

    def abrir(requisicao, timeout=None):
        chamadas.append(requisicao.full_url)
        raise OSError("sem rede nos testes")

    with mock.patch.object(api.urllib.request, "urlopen", abrir):
        for ruim in ("", "123", "../../x", "30130?x=1", "301300100", None):
            assert api.obter_uf_pelo_cep(ruim) == "BR", ruim
        assert chamadas == []                                                      # o parâmetro livre não vira endereço de consulta
        assert api.obter_uf_pelo_cep("30130-010") == "BR"                          # (sem rede: cai no padrão)
        assert chamadas == ["https://viacep.com.br/ws/30130010/json/"]             # mas a consulta usa só os dígitos


def teste_nenhum_outro_log_da_api_escreve_o_cep_cru():
    """Qualquer print/logging de api_supabase.py que cite o CEP tem de passar por cep_para_o_log."""
    fonte = (RAIZ / "api_supabase.py").read_text(encoding="utf-8")
    for numero, linha in enumerate(fonte.splitlines(), 1):
        if re.search(r"\b(print|logging|log|logger)\b.*\(", linha) and re.search(r"\{cep\b|%s.*\bcep\b|\bcep\s*\)", linha):
            assert "cep_para_o_log(" in linha, f"api_supabase.py:{numero} escreve o CEP cru no log: {linha.strip()}"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
