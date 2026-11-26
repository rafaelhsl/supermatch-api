"""Testes do coletor do Super ABC (coletor_vip.py), sem rede: a loja (VIP Commerce) é falsa.

Rodar com:  python tests/test_coletor_vip.py

A `LojaFalsa` responde como a loja respondeu em 25/11/2026 (login anônimo, sessão, lista de unidades e busca de 20 produtos por página)
e deixa derrubar o token, trocar a unidade 8 de lugar ou tirar a chave, para provar o que a carga faz em cada falha.
"""
import asyncio
import io
import sys
import threading
import urllib.parse
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import alimentar_banco as ab  # noqa: E402
import coletor_vip as v  # noqa: E402
import coletor_vtex as c  # noqa: E402
import disjuntor  # noqa: E402
import historico  # noqa: E402

disjuntor.PAUSA_DA_SEGUNDA_RODADA = 0

UNIDADES = [{"id": 1, "nome": "ABC - Divinópolis (Goiás)", "nome_site": "ABC - Divinópolis (Goiás)", "ativo": True},
            {"id": 8, "nome": "ABC - Betim", "nome_site": "ABC - Betim", "ativo": True},
            {"id": 19, "nome": "ABC - Belo Horizonte (Horto)", "nome_site": "ABC - Belo Horizonte (Horto)", "ativo": True}]


def produto(produto_id, nome, preco="10.00", disponivel=True, sigla="UN", porcao=1, ean="7896006711155", **extra):
    base = {"produto_id": produto_id, "id": f"linha-{produto_id}", "descricao": nome, "preco": preco, "disponivel": disponivel, "unidade_sigla": sigla,
            "quantidade_unidade_diferente": porcao, "codigo_barras": ean, "em_oferta": False, "oferta": None, "preco_original": 0,
            "marca_id": 3491, "classificacao_mercadologica_id": 260, "unidade_fracao": None}
    base.update(extra)
    return base


class LojaFalsa:
    """O cliente HTTP do coletor, no lugar da rede. `catalogo`: {termo: [produtos]}."""

    def __init__(self, catalogo=None, unidades=None, chave_certa=True, sessao_ok=True):
        self.catalogo = catalogo or {}
        self.unidades = UNIDADES if unidades is None else unidades
        self.chave_certa, self.sessao_ok = chave_certa, sessao_ok
        self.logins, self.token_valido = 0, None
        self.registro, self.cabecalhos_das_buscas = [], []      # as chamadas feitas, e os cabeçalhos de cada busca
        self.chamadas, self.avisos = 0, []                      # o que o relatório da linha de comando lê do ClienteHttp de verdade
        self.derrubar_depois_da_pagina = None    # (termo, pagina): depois de servir essa página, a loja passa a recusar o token
        self.sempre_recusa = False
        self.barreira = None                     # threading.Barrier: as buscas recusadas esperam umas pelas outras, para esbarrarem juntas no token vencido
        self._trava = threading.Lock()

    def post_json(self, url, corpo, cabecalhos=None):
        with self._trava:
            self.registro.append(("POST", url))
            self.chamadas += 1
            assert url.endswith("/org/398/auth/loja/login")
            assert corpo == {"domain": "abcdelivery.com.br", "username": "loja", "key": v.CHAVE_DO_SITE}, corpo
            if not self.chave_certa:
                raise c.ErroDeColeta(f"HTTP 401 em {url}", status=401)
            self.logins += 1
            self.token_valido = f"token-{self.logins}"
            return {"success": True, "data": self.token_valido}

    def _autenticado(self, cabecalhos, url):
        if (self.sempre_recusa and "/buscas/" in url) or (cabecalhos or {}).get("Authorization") != f"Bearer {self.token_valido}":
            if self.barreira is not None and "/buscas/" in url:
                try:
                    self.barreira.wait(5)
                except threading.BrokenBarrierError:
                    pass
            raise c.ErroDeColeta(f"HTTP 401 em {url}", status=401)

    def get_json(self, url, cabecalhos=None):
        with self._trava:
            self.registro.append(("GET", url))
            self.chamadas += 1
        self._autenticado(cabecalhos, url)
        if url.endswith("/loja/sessao_cliente"):
            if not self.sessao_ok:
                raise c.ErroDeColeta(f"HTTP 500 em {url}", status=500)
            return {"success": True, "data": {"sessao_id": "sessao-1"}}
        if url.endswith("/loja/centros_distribuicoes/retiradas"):
            return {"success": True, "data": self.unidades}
        trecho = url.split("/loja/buscas/produtos/termo/")[1]
        termo, consulta = trecho.split("?page=")
        termo, pagina = urllib.parse.unquote(termo), int(consulta)
        with self._trava:
            self.cabecalhos_das_buscas.append(dict(cabecalhos))
        self._autenticado(cabecalhos, url)
        if self.derrubar_depois_da_pagina == (termo, pagina):
            self.derrubar_depois_da_pagina = None
            self.token_valido = "token-vencido"
        todos = self.catalogo.get(termo, [])
        paginas = -(-len(todos) // 20)
        return {"success": True, "data": {"busca_id": "1", "produtos": todos[(pagina - 1) * 20:pagina * 20], "digitado": termo, "termo": termo, "filtros": None},
                "paginator": {"page": pagina, "items_per_page": 20, "total_pages": paginas, "total_items": len(todos)}, "isRedirect": False}


def buscas(loja):
    return [u for metodo, u in loja.registro if metodo == "GET" and "/buscas/produtos/termo/" in u]


# ============================== a linha do produto ==============================

def teste_linha_de_um_produto_por_unidade():
    linha = v.linha_do_produto(produto(37832, "  Arroz Tipo 1  Camil 5 Kg ", "18.90"), "arroz")
    assert linha["id_origem"] == "37832"                                            # o produto_id, e não o `id` da linha da busca (que a loja renumera)
    assert linha == {"supermercado": "Super ABC", "id_origem": "37832", "nome": "Arroz Tipo 1 Camil 5 Kg", "marca": None, "ean": "7896006711155", "categoria": "",
                     "preco_varejo": 18.9, "preco_atacado": 18.9, "quantidade_atacado": 1, "uf_cobertura": "MG", "termo": "arroz",
                     "peso_variavel": False, "unidade": "un", "multiplicador": None}


def teste_item_a_peso_tem_o_preco_do_quilo_e_a_porcao_como_multiplicador():
    # a loja guarda o preço da PORÇÃO: 9,59 pela porção de 1,2 kg é R$ 7,99 o quilo (o item "Banana Prata Kg" custa R$ 7,99 na tela)
    banana = v.linha_do_produto(produto(1, "Banana Prata 1,2 Kg (5 A 6 Unidades))", "9.59", sigla="KG", porcao=1.2, ean=""), "banana")
    assert banana["preco_varejo"] == 7.99 and banana["multiplicador"] == 1.2 and banana["unidade"] == "kg" and banana["peso_variavel"] is True
    assert banana["preco_atacado"] == 7.99 and banana["quantidade_atacado"] == 1 and banana["ean"] is None
    presunto = v.linha_do_produto(produto(2, "Presunto Sadia Cozido Kg", "115.96", sigla="KG", porcao=4), "presunto")
    assert presunto["preco_varejo"] == 28.99 and presunto["multiplicador"] == 4
    por_quilo = v.linha_do_produto(produto(3, "Banana Prata Kg", "7.99", sigla="KG", porcao=1), "banana")
    assert por_quilo["preco_varejo"] == 7.99 and por_quilo["multiplicador"] == 1
    sem_porcao = v.linha_do_produto(produto(4, "Tomate Grape Amar Kg", "10.90", sigla="kg", porcao=None), "tomate")
    assert sem_porcao["preco_varejo"] == 10.9 and sem_porcao["multiplicador"] == 1 and sem_porcao["unidade"] == "kg"
    fracionado = v.linha_do_produto(produto(5, "Tomate Grape 300g (1 A 3 Unidades)", "4.47", sigla="KG", porcao=0.3), "tomate")
    assert fracionado["preco_varejo"] == 14.9 and fracionado["multiplicador"] == 0.3


def teste_outra_sigla_e_venda_por_unidade_ou_pacote():
    for sigla in ("UN", "BD", "CX", "PC", "DP", "", None):
        linha = v.linha_do_produto(produto(7, "Tomate Saladete Nectar 650g", "8.99", sigla=sigla, porcao=1), "tomate")
        assert linha["unidade"] == "un" and linha["peso_variavel"] is False and linha["multiplicador"] is None and linha["preco_varejo"] == 8.99, sigla
    pera = v.linha_do_produto(produto(8, "Pera Ercolini Unidade 1 Kg", "24.90", sigla="UN", porcao=1.5), "pera")
    assert pera["preco_varejo"] == 24.9, "só o item KG divide o preço pela porção"


def teste_sem_estoque_sem_preco_ou_sem_identidade_nao_entra():
    assert v.linha_do_produto(produto(1, "Arroz", disponivel=False), "arroz") is None
    for preco in ("0.00", "", None, "abc", "-3"):
        assert v.linha_do_produto(produto(1, "Arroz", preco), "arroz") is None, preco
    assert v.linha_do_produto(produto(None, "Arroz"), "arroz") is None
    assert v.linha_do_produto(produto(1, "   "), "arroz") is None
    assert v.linha_do_produto(produto(1, "Arroz", disponivel=None), "arroz") is None


def teste_oferta_e_preco_do_clube_nao_mudam_o_preco_do_site():
    oferta = {"oferta_id": 2820, "classe_oferta": "preco-vip", "preco_antigo": "5.69", "preco_oferta": "5.39"}
    linha = v.linha_do_produto(produto(9, "Leite Longa Vida Integral Itambé 1 Litro", "5.59", em_oferta=True, oferta=oferta, preco_original=5.69), "leite")
    assert linha["preco_varejo"] == 5.59 and linha["quantidade_atacado"] == 1


def teste_codigo_de_barras_interno_e_descartado():
    for codigo, esperado in (("7896006711155", "7896006711155"), ("8200", None), ("", None), (None, None), ("1111111111111", None), ("789-600-6711155", "7896006711155")):
        assert v.linha_do_produto(produto(1, "Arroz", ean=codigo), "arroz")["ean"] == esperado, codigo


# ============================== a unidade de uma cidade (levantar_entrega.py) ==============================

def unidade(id_, nome, cidade, estado="Minas Gerais", ativo=True):
    return {"id": id_, "nome": nome, "nome_site": nome, "ativo": ativo, "endereco": {"cep": "30000000", "cidade": cidade, "estado": estado}}


def teste_unidade_da_cidade():
    unidades = [unidade(1, "ABC - Divinópolis (Goiás)", "Divinópolis"), unidade(19, "ABC - Belo Horizonte (Horto)", "Belo Horizonte"),
                unidade(24, "ABC - Belo Horizonte (Barreiro)", "Belo Horizonte"), unidade(8, "ABC - Betim", "Betim"), unidade(40, "ABC - Pará de Minas", "Pará de Minas")]
    achar = lambda cidade, uf="MG": (v.unidade_da_cidade(unidades, cidade, uf) or {}).get("id")
    assert achar("Betim") == 8 and achar("Divinópolis") == 1
    assert achar("Belo Horizonte") == 19, "com duas unidades na cidade vale a primeira da lista"
    assert achar("belo horizonte") == 19 and achar("PARA DE MINAS") == 40 and achar("Pará de Minas") == 40      # sem acento e sem caixa
    assert achar("Contagem") is None and achar("Betim", "SP") is None and achar("Betim", "mg") == 8              # o estado entra na conta
    assert achar("Bet") is None and achar("Belo") is None and achar("Belo Horizonte Norte") is None             # o nome da cidade vale inteiro
    assert v.unidade_da_cidade([], "Betim", "MG") is None and v.unidade_da_cidade(None, "Betim", "MG") is None


def teste_unidade_da_cidade_ignora_inativa_e_trata_endereco_estranho():
    lista = [unidade(1, "ABC - Betim", "Betim", ativo=False), unidade(2, "ABC - Betim 2", "Betim")]
    assert v.unidade_da_cidade(lista, "Betim", "MG")["id"] == 2                                                   # a inativa não atende
    assert v.unidade_da_cidade([{"id": 1, "ativo": True}, {"id": 2, "endereco": None}, {"id": 3, "endereco": {"cidade": None, "estado": None}}], "Betim", "MG") is None
    assert v.unidade_da_cidade([unidade(1, "ABC - Santos", "Santos", "São Paulo")], "Santos", "SP")["id"] == 1    # fora de MG: o estado por extenso vira a sigla
    assert v.unidade_da_cidade([unidade(1, "ABC - Santos", "Santos", "Atlântida")], "Santos", "SP") is None       # estado que não conhece não casa por engano
    assert set(v.UF_DO_ESTADO.values()) == {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


# ============================== login, sessão e unidade ==============================

def teste_entra_uma_vez_e_manda_a_identificacao_da_loja_em_toda_busca():
    loja = LojaFalsa({"arroz": [produto(i, f"Arroz {i}") for i in range(45)], "feijão": [produto(100, "Feijão Preto")]})
    baixador = v.BaixadorSuperAbc()
    assert len(baixador(loja, "arroz")) == 45 and len(baixador(loja, "feijão")) == 1
    assert loja.logins == 1 and baixador.logins == 1
    assert len(buscas(loja)) == 4                                               # 3 páginas de arroz e 1 de feijão
    for cab in loja.cabecalhos_das_buscas:
        assert cab["Authorization"] == "Bearer token-1" and cab["sessao-id"] == "sessao-1"
        assert cab["domainkey"] == "abcdelivery.com.br" and cab["organizationid"] == "398" and cab["User-Agent"].startswith("Mozilla/5.0 (Windows")


def teste_so_busca_na_unidade_de_betim_e_codifica_o_termo():
    loja = LojaFalsa({"feijão": [produto(1, "Feijão")], "a/b c": [produto(2, "Coisa")]})
    baixador = v.BaixadorSuperAbc()
    baixador(loja, "feijão")
    baixador(loja, "a/b c")
    assert all("/centro_distribuicao/8/loja/buscas/produtos/termo/" in u for u in buscas(loja))
    assert any("/termo/feij%C3%A3o?page=1" in u for u in buscas(loja)) and any("/termo/a%2Fb%20c?page=1" in u for u in buscas(loja))


def teste_unidade_que_nao_e_mais_a_de_betim_para_a_coleta_sem_buscar_nada():
    renumerada = [{"id": 8, "nome": "ABC - Contagem", "nome_site": "ABC - Contagem", "ativo": True}]
    loja = LojaFalsa({"arroz": [produto(1, "Arroz")]}, unidades=renumerada)
    try:
        v.BaixadorSuperAbc()(loja, "arroz")
    except c.ErroDeColeta as erro:
        assert "unidade 8" in str(erro) and "Contagem" in str(erro) and "outra cidade" in str(erro)
    else:
        raise AssertionError("a unidade 8 virou Contagem: devia parar")
    assert buscas(loja) == []                                                    # nenhum preço foi lido

    for lista in ([], [{"id": 1, "nome": "ABC - Betim", "nome_site": "ABC - Betim", "ativo": True}], [{"id": 8, "nome": "ABC - Betim", "ativo": False}]):
        try:
            v.BaixadorSuperAbc()(LojaFalsa({"arroz": [produto(1, "Arroz")]}, unidades=lista), "arroz")
        except c.ErroDeColeta:
            pass
        else:
            raise AssertionError(f"unidade ausente, de outro número ou inativa devia parar: {lista}")


def teste_o_nome_da_unidade_vale_sem_acento_e_sem_caixa():
    for nome in ("ABC - Betim", "ABC - BETIM", "ABC Plus - Bétim"):
        loja = LojaFalsa({"arroz": [produto(1, "Arroz")]}, unidades=[{"id": 8, "nome": nome, "nome_site": nome, "ativo": True}])
        assert len(v.BaixadorSuperAbc()(loja, "arroz")) == 1, nome


def teste_chave_recusada_no_login_explica_o_que_conferir():
    loja = LojaFalsa({"arroz": [produto(1, "Arroz")]}, chave_certa=False)
    baixador = v.BaixadorSuperAbc()
    for _ in range(2):                                                            # o login é tentado de novo na busca seguinte
        try:
            baixador(loja, "arroz")
        except c.ErroDeColeta as erro:
            assert "login anônimo" in str(erro) and "chave pública" in str(erro) and "docs/coletor_por_api.md" in str(erro) and erro.status == 401
        else:
            raise AssertionError("sem login a busca não pode seguir")
    assert buscas(loja) == []


def teste_login_sem_token_levanta():
    loja = LojaFalsa({"arroz": [produto(1, "Arroz")]})
    loja.post_json = lambda url, corpo, cabecalhos=None: {"success": False, "error": "chave inválida"}
    try:
        v.BaixadorSuperAbc()(loja, "arroz")
    except c.ErroDeColeta as erro:
        assert "recusou o login anônimo" in str(erro) and "chave inválida" in str(erro)
    else:
        raise AssertionError("login sem sucesso devia levantar")
    loja.post_json = lambda url, corpo, cabecalhos=None: {"success": True, "data": None}
    try:
        v.BaixadorSuperAbc()(loja, "arroz")
    except c.ErroDeColeta as erro:
        assert "não devolveu o token" in str(erro)
    else:
        raise AssertionError("login sem token devia levantar")


def teste_sessao_que_falha_nao_derruba_a_busca():
    loja = LojaFalsa({"arroz": [produto(1, "Arroz")]}, sessao_ok=False)
    assert len(v.BaixadorSuperAbc()(loja, "arroz")) == 1
    assert loja.cabecalhos_das_buscas and all("sessao-id" not in cab for cab in loja.cabecalhos_das_buscas)
    assert len(loja.avisos) == 1 and "sem sessão da loja" in loja.avisos[0]


# ============================== a busca ==============================

def teste_pagina_ate_o_fim_na_ordem_da_loja():
    produtos = [produto(i, f"Arroz {i:03d}") for i in range(45)]
    loja = LojaFalsa({"arroz": produtos})
    linhas = v.BaixadorSuperAbc()(loja, "arroz")
    assert [l["id_origem"] for l in linhas] == [str(i) for i in range(45)]       # 20 + 20 + 5, na ordem da loja, mesmo com as páginas em paralelo
    assert sorted(int(u.rsplit("page=", 1)[1]) for u in buscas(loja)) == [1, 2, 3]


def teste_a_ordem_vale_mesmo_quando_as_paginas_chegam_fora_de_ordem():
    produtos = [produto(i, f"Arroz {i:03d}") for i in range(100)]
    loja = LojaFalsa({"arroz": produtos})
    original = loja.get_json

    def devagar_nas_primeiras(url, cabecalhos=None):
        pagina = int(url.rsplit("page=", 1)[1]) if "page=" in url else 0
        if pagina in (2, 3):
            threading.Event().wait(0.05 * (4 - pagina))                         # as páginas 2 e 3 terminam depois da 4
        return original(url, cabecalhos)

    loja.get_json = devagar_nas_primeiras
    assert [l["id_origem"] for l in v.BaixadorSuperAbc()(loja, "arroz")] == [str(i) for i in range(100)]


def teste_para_no_limite_de_paginas():
    loja = LojaFalsa({"sal": [produto(i, f"Sal {i}") for i in range(400)]})       # 20 páginas
    linhas = v.BaixadorSuperAbc()(loja, "sal")
    assert len(buscas(loja)) == v.MAX_PAGINAS == 15 and len(linhas) == 300
    menos = LojaFalsa({"sal": [produto(i, f"Sal {i}") for i in range(400)]})
    assert len(v.BaixadorSuperAbc(max_paginas=2)(menos, "sal")) == 40 and len(buscas(menos)) == 2


def paginas_pedidas(loja):
    return sorted(int(u.rsplit("page=", 1)[1]) for u in buscas(loja))


def teste_casa_com_a_busca():
    casa = v.casa_com_a_busca
    assert casa("Sal Refinado Globo 1 Kg", v.palavras("sal refinado")) and casa("Sal Ref Lebre 1kg", v.palavras("sal refinado"))   # abreviado
    assert casa("Ovos Brancos 12 un", v.palavras("ovo")) and casa("Ovo Branco", v.palavras("ovos"))                                  # plural
    assert casa("Feijão Preto Camil 1kg", v.palavras("FEIJÃO")) and casa("Leite Condensado Moça", v.palavras("leite condensado"))     # acento e caixa
    assert casa("Salame Italiano", v.palavras("sal"))                                                                                  # só ficam de fora os nomes sem a palavra
    assert not casa("Creme de Arroz", v.palavras("creme de leite")) and not casa("Esmalte Risqué", v.palavras("arroz"))
    assert not casa("Creme Leite Piracanjuba", v.palavras("creme de leite")), "palavra de 2 letras ('de') só vale inteira"
    assert casa("Qualquer coisa", []) and v.palavras("Óleo de Soja 900ml") == ["oleo", "de", "soja", "900ml"]


def teste_para_depois_de_duas_paginas_seguidas_sem_o_que_a_busca_pede():
    # como "creme de leite" na loja: o que serve está na página 1, e as outras 79 são ruído
    relevantes = [produto(i, f"Creme de Leite Marca {i}") for i in range(11)]
    ruido = [produto(100 + i, f"Esmalte Cor {i}") for i in range(189)]            # 200 produtos no total: 10 páginas
    loja = LojaFalsa({"creme de leite": relevantes + ruido})
    linhas = v.BaixadorSuperAbc()(loja, "creme de leite")
    pedidas = set(paginas_pedidas(loja))
    assert {1, 2, 3} <= pedidas <= {1, 2, 3, 4, 5}                                 # a 1ª e um lote de 4: a regra para na 3ª (as do lote que ainda não tinham começado são canceladas)
    assert len(linhas) == 60 and [l["id_origem"] for l in linhas[:11]] == [str(i) for i in range(11)]       # só as 3 primeiras páginas entram: 20 + 20 + 20
    assert "Esmalte Cor 60" not in [l["nome"] for l in linhas]                     # 4ª página em diante: ruído, descartada


def teste_sem_nenhum_achado_le_ate_o_limite_das_paginas():
    loja = LojaFalsa({"xablau": [produto(i, f"Esmalte Cor {i}") for i in range(100)]})                   # a busca da loja respondeu algo que não tem as palavras
    assert len(v.BaixadorSuperAbc()(loja, "xablau")) == 100 and paginas_pedidas(loja) == [1, 2, 3, 4, 5]


def teste_uma_pagina_ruim_no_meio_nao_para_a_busca_mas_duas_seguidas_sim():
    def pagina(letra, tem):
        return [produto(f"{letra}{i}", f"Arroz {letra}{i}" if tem else f"Esmalte {letra}{i}") for i in range(20)]

    loja = LojaFalsa({"arroz": pagina("a", True) + pagina("b", False) + pagina("c", True) + pagina("d", False) + pagina("e", False) + pagina("f", True)})
    linhas = v.BaixadorSuperAbc()(loja, "arroz")
    assert len(linhas) == 100 and not any(l["id_origem"].startswith("f") for l in linhas)                # a, b, c, d, e entram; f, depois de 2 páginas ruins, não
    # o limite conhecido: um achado depois de duas páginas seguidas sem nada fica de fora
    loja = LojaFalsa({"arroz": pagina("a", True) + pagina("b", False) + pagina("c", False) + pagina("d", True)})
    assert {l["id_origem"][0] for l in v.BaixadorSuperAbc()(loja, "arroz")} == {"a", "b", "c"}


def teste_so_o_disponivel_vira_linha_e_o_resto_da_pagina_segue():
    produtos = [produto(i, f"Arroz {i}", disponivel=(i % 4 == 0)) for i in range(45)]
    linhas = v.BaixadorSuperAbc()(LojaFalsa({"arroz": produtos}), "arroz")
    assert [l["id_origem"] for l in linhas] == [str(i) for i in range(0, 45, 4)]


def teste_busca_sem_resultado_nao_e_falha():
    assert v.BaixadorSuperAbc()(LojaFalsa({}), "abobrinha") == []                  # total_pages 0: a loja não vende isso


def teste_resposta_fora_do_formato_levanta():
    loja = LojaFalsa({"arroz": [produto(1, "Arroz")]})
    original = loja.get_json
    for quebrada in ({"success": False, "error": "x"}, {"success": True, "data": {"produtos": []}}, {"success": True, "data": {"produtos": []}, "paginator": {"page": 1}},
                      {"success": True, "data": {}, "paginator": {"total_pages": 1}},
                     {"success": True, "data": None, "paginator": {"total_pages": 1}}, ["lista"], None):
        loja.get_json = lambda url, cabecalhos=None, q=quebrada: q if "/buscas/" in url else original(url, cabecalhos)
        try:
            v.BaixadorSuperAbc()(loja, "arroz")
        except c.ErroDeColeta as erro:
            assert "Super ABC" in str(erro) and "arroz" in str(erro), quebrada
        else:
            raise AssertionError(f"resposta fora do formato devia levantar: {quebrada}")


def teste_falha_de_pagina_no_meio_derruba_o_termo_inteiro():
    loja = LojaFalsa({"arroz": [produto(i, f"Arroz {i}") for i in range(100)]})
    original = loja.get_json

    def quebra_a_3(url, cabecalhos=None):
        if url.endswith("?page=3"):
            raise c.ErroDeColeta("sem resposta depois de 4 tentativas")
        return original(url, cabecalhos)

    loja.get_json = quebra_a_3
    try:
        v.BaixadorSuperAbc()(loja, "arroz")
    except c.ErroDeColeta as erro:
        assert "4 tentativas" in str(erro)                                         # termo com página faltando seria dado pela metade: falha, não parcial
    else:
        raise AssertionError("uma página faltando devia falhar o termo")


# ============================== token recusado ==============================

def teste_token_recusado_entra_de_novo_e_repete_so_uma_vez():
    loja = LojaFalsa({"arroz": [produto(i, f"Arroz {i}") for i in range(100)]})   # 5 páginas
    loja.derrubar_depois_da_pagina = ("arroz", 1)                                  # a loja vence o token logo depois da 1ª página: as 4 seguintes esbarram juntas
    loja.barreira = threading.Barrier(4)                                           # (e esperam umas pelas outras, para esbarrarem de verdade ao mesmo tempo)
    baixador = v.BaixadorSuperAbc()
    linhas = baixador(loja, "arroz")
    assert len(linhas) == 100 and [l["id_origem"] for l in linhas] == [str(i) for i in range(100)]
    assert loja.logins == 2 and baixador.logins == 2                              # uma entrada nova, mesmo com várias páginas esbarrando juntas


def teste_token_recusado_de_novo_depois_do_login_desiste():
    loja = LojaFalsa({"arroz": [produto(1, "Arroz")]})
    loja.sempre_recusa = True
    try:
        v.BaixadorSuperAbc()(loja, "arroz")
    except c.ErroDeColeta as erro:
        assert erro.status == 401
    else:
        raise AssertionError("token sempre recusado devia desistir")
    assert loja.logins == 2                                                        # entrou, foi recusado, entrou de novo, foi recusado: acabou


def teste_erro_que_nao_e_de_token_nao_refaz_o_login():
    loja = LojaFalsa({"arroz": [produto(1, "Arroz")]})
    original = loja.get_json

    def cai(url, cabecalhos=None):
        if "/buscas/" in url:
            raise c.ErroDeColeta("HTTP 404", status=404)
        return original(url, cabecalhos)

    loja.get_json = cai
    try:
        v.BaixadorSuperAbc()(loja, "arroz")
    except c.ErroDeColeta as erro:
        assert erro.status == 404
    else:
        raise AssertionError("404 devia levantar")
    assert loja.logins == 1


def teste_o_cliente_http_guarda_o_codigo_da_resposta_no_erro():
    cliente = c.ClienteHttp(pausa=0, tentativas=3, espera=0)
    import urllib.error
    for codigo in (401, 403, 404):
        with mock.patch("urllib.request.urlopen", mock.Mock(side_effect=urllib.error.HTTPError("http://x", codigo, "erro", {}, io.BytesIO(b"")))):
            try:
                cliente.get_json("http://x/a")
            except c.ErroDeColeta as erro:
                assert erro.status == codigo
    with mock.patch("urllib.request.urlopen", mock.Mock(side_effect=urllib.error.HTTPError("http://x", 503, "erro", {}, io.BytesIO(b"")))):
        try:
            cliente.get_json("http://x/a")
        except c.ErroDeColeta as erro:
            assert erro.status == 503
    assert c.ErroDeColeta("sem código").status is None


# ============================== dentro da carga ==============================

def teste_a_carga_coleta_o_super_abc_pela_api_com_os_quatro_mercados():
    assert set(ab.MERCADOS_PELA_API) == set(ab.MERCADOS) and "Super ABC" in ab.MERCADOS_PELA_API
    assert ab.BAIXADORES_DA_CARGA["Super ABC"] is v.baixar_super_abc
    assert set(ab.BAIXADORES_DA_CARGA) == set(ab.MERCADOS)
    assert not hasattr(ab, "buscar_na_plataforma_regex")                          # o robô do Super ABC saiu da carga


def teste_a_coleta_do_super_abc_aplica_o_filtro_do_termo_pelo_nome():
    catalogo = {
        "arroz": [produto(1, "Arroz Tipo 1 Camil 5 Kg", "18.90"), produto(2, "Esmalte Risqué Grão Arroz", "7.99"), produto(3, "Arroz Codil 2 Kg", "7.98", disponivel=False),
                  produto(4, "Arroz Parboilizado Prato Fino 5kg", "26.90"), produto(1, "Arroz Tipo 1 Camil 5 Kg", "18.90"),
                  produto(5, "Arroz Agulhinha a Granel Kg", "6.00", sigla="KG", porcao=1.0, ean="")],
        "banana": [produto(10, "Banana Prata 1,2 Kg (5 A 6 Unidades)", "9.59", sigla="KG", porcao=1.2, ean=""), produto(11, "Chips de Banana 100g", "6.00"),
                   produto(12, "Banana Nanica 300g", "1.50", sigla="KG", porcao=0.3, ean="")],
        "queijo mussarela": [produto(20, "Queijo Mussarela Fatiado Itambé 150g", "9.90"), produto(21, "Queijo Mussarela Mutumilk Kg Ped", "43.90", sigla="KG")],
    }
    por_nome = {t["termo"]: t for t in c.carregar_lista_da_carga()[1]}
    termos = [por_nome["arroz"], por_nome["banana"], por_nome["queijo mussarela"]]
    for t in termos:
        t["consultas"] = [t["termo"]]
    coletas = ab.coletas_pela_api(["Super ABC"], termos, 100, http=LojaFalsa(catalogo), baixadores={"Super ABC": v.BaixadorSuperAbc()}, limite_de_falhas=None)
    coleta = coletas["Super ABC"]
    por_termo = {}
    for linha in coleta.produtos:
        por_termo.setdefault(linha["termo"], []).append(linha)
    assert sorted(l["id_origem"] for l in por_termo["arroz"]) == ["1", "4"]       # o esmalte (nome), o indisponível, o repetido e o a granel (por quilo) ficam de fora
    assert sorted(l["id_origem"] for l in por_termo["banana"]) == ["10", "12"]     # hortifrúti aceita o item a peso; o chips sai pelo nome
    assert sorted(l["id_origem"] for l in por_termo["queijo mussarela"]) == ["20", "21"]       # o queijo mussarela aceita o item a peso (etapa 5 dos cortes); o arroz, não
    assert coleta.termos_falhos == [] and ab.avaliar_coleta(coleta.produtos, coleta.termos_total, coleta.termos_falhos, coleta.tolerancia) == "ok"
    banana = {l["id_origem"]: l for l in por_termo["banana"]}
    assert banana["10"]["preco_varejo"] == 7.99 and banana["12"]["preco_varejo"] == 5.0 and banana["12"]["unidade"] == "kg"
    queijo = {l["id_origem"]: l for l in por_termo["queijo mussarela"]}
    assert queijo["21"]["unidade"] == "kg" and queijo["21"]["preco_varejo"] == 43.9 and queijo["20"]["unidade"] == "un"
    assert all(l["supermercado"] == "Super ABC" and l["uf_cobertura"] == "MG" for l in coleta.produtos)


def teste_mercado_do_super_abc_fora_do_ar_falha_a_coleta_sem_gravar_nada():
    loja = LojaFalsa({}, chave_certa=False)
    termos = [{"termo": f"t{i}", "consultas": [f"t{i}"]} for i in range(30)]
    coleta = ab.coletas_pela_api(["Super ABC"], termos, 100, http=loja, baixadores={"Super ABC": v.BaixadorSuperAbc()}, pausa=0, dormir=lambda s: None)["Super ABC"]
    assert coleta.produtos == [] and len(coleta.termos_falhos) == 30
    assert ab.avaliar_coleta(coleta.produtos, coleta.termos_total, coleta.termos_falhos, coleta.tolerancia) == "falhou"
    assert "chave pública" in coleta.motivos[0]
    tentativas_de_login = sum(1 for metodo, _ in loja.registro if metodo == "POST")
    assert loja.logins == 0 and buscas(loja) == [] and tentativas_de_login == 12  # o disjuntor parou nas 6 primeiras de cada rodada: ninguém martelou o login


def teste_o_historico_continua_de_onde_estava_quando_o_produto_ganha_id():
    # até 23/11 o Super ABC era guardado pelo nome ('n:…', do robô); agora chega com o id da loja ('v:…') e religa o que já existia
    antigo = {historico.chave_origem("Arroz Tipo 1 Camil 5 Kg"): {"id": 77, "nome": "Arroz Tipo 1 Camil 5 Kg", "ativo": True, "ultimo_dia": None},
              historico.chave_origem("Feijão Preto Camil 1kg"): {"id": 78, "nome": "Feijão Preto Camil 1kg", "ativo": True, "ultimo_dia": None}}
    novos = [v.linha_do_produto(produto(37832, "Arroz Tipo 1 Camil 5 Kg", "18.90"), "arroz"), v.linha_do_produto(produto(40000, "Arroz Novo 1kg", "6.00"), "arroz")]
    itens, _ = historico.preparar_itens(novos)
    assert set(itens) == {"v:37832", "v:40000"}
    pares = historico.a_religar(itens, antigo)
    assert [(i, chave) for i, chave, _ in pares] == [(77, "v:37832")] and "v:37832" in antigo      # o arroz do robô virou o produto 37832; o feijão ainda espera


def teste_no_modo_antigo_o_super_abc_tambem_vem_pela_api():
    chamadas = []

    def falso(http, consulta):
        chamadas.append(consulta)
        return [{"supermercado": "Super ABC", "id_origem": "1", "nome": "Arroz Camil 5kg", "preco_varejo": 18.9}]

    with mock.patch.object(v, "baixar_super_abc", falso):
        produtos = asyncio.run(ab.ROBOS["Super ABC"]("Arroz"))
    assert chamadas == ["Arroz"] and produtos[0]["nome"] == "Arroz Camil 5kg"


# ============================== linha de comando ==============================

def rodar_o_relatorio(loja, *argumentos):
    saida = io.StringIO()
    with mock.patch.object(c, "ClienteHttp", lambda: loja), mock.patch.object(v, "_BAIXADOR_DA_CARGA", v.BaixadorSuperAbc()),             mock.patch("sys.stdout", saida), mock.patch.object(c.sys.stdout, "reconfigure", create=True):
        codigo = v.principal(list(argumentos))
    return codigo, saida.getvalue()


def teste_relatorio_da_linha_de_comando():
    loja = LojaFalsa({"arroz": [produto(1, "Arroz Tipo 1 Camil 5 Kg", "18.90"), produto(2, "Arroz Codil 2 Kg", "7.98")]})
    codigo, texto = rodar_o_relatorio(loja, "--termos", "arroz")
    assert codigo == 0 and "unidade confirmada: ABC - Betim" in texto and "arroz" in texto and "2 itens" in texto and "0 erro(s)" in texto, texto


def teste_relatorio_da_linha_de_comando_mostra_o_erro_e_sai_com_1():
    codigo, texto = rodar_o_relatorio(LojaFalsa({}, chave_certa=False), "--termos", "arroz")
    assert codigo == 1 and "ERRO arroz" in texto and "chave pública" in texto, texto


if __name__ == "__main__":
    testes = [fn for nome, fn in sorted(globals().items()) if nome.startswith("teste_")]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
