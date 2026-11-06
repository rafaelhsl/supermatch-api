"""Testes da busca (busca.py) e do agrupamento por código de barras (Comparador_inteligente.py), sem rede e sem banco.

Rodar com:  python tests/test_busca_e_comparador.py   (precisa de thefuzz, do requirements.txt)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import busca  # noqa: E402
import Comparador_inteligente as comp  # noqa: E402


def produto(nome, termo=None, mercado="Apoio Entrega", preco=10.0, ean=None):
    return {"nome": nome, "termo": termo, "supermercado": mercado, "preco_varejo": preco, "ean": ean}


def nomes(produtos):
    return [p["nome"] for p in produtos]


# ============================== busca ==============================

def teste_principais_escondem_quem_so_cita():
    catalogo = busca.indexar([
        produto("Arroz Branco Camil 5kg", "arroz"), produto("ARROZ TIO JOAO 1KG", "arroz"), produto("Arroz Parboilizado Prato Fino", "arroz"),
        produto("Condicionador Seda com Arroz Preto 325ml", "condicionador"), produto("Macarrão Bifum de Arroz 200g", "macarrão"),
    ])
    achados, ocultos = busca.buscar(catalogo, "arroz")
    assert nomes(achados) == ["Arroz Branco Camil 5kg", "ARROZ TIO JOAO 1KG", "Arroz Parboilizado Prato Fino"] and ocultos == 2
    assert busca.filtrar(catalogo, "arroz") == achados


def teste_poucos_principais_devolve_tudo_com_os_principais_primeiro():
    catalogo = busca.indexar([
        produto("Condicionador com Arroz Preto", "condicionador"), produto("Arroz Camil 1kg", "arroz"), produto("Biscoito de Arroz Integral", "biscoito"),
        produto("Arroz Tio João 1kg", "arroz"),
    ])
    achados, ocultos = busca.buscar(catalogo, "arroz")      # só 2 principais (< 3): nada some, para a busca não ficar vazia
    assert nomes(achados)[:2] == ["Arroz Camil 1kg", "Arroz Tio João 1kg"] and len(achados) == 4 and ocultos == 0


def teste_marca_ou_produto_fora_da_lista_nao_fica_vazio():
    catalogo = busca.indexar([produto("Leite em Pó Ninho 380g", "leite em pó"), produto("Achocolatado Ninho Soleil", "achocolatado")])
    achados, ocultos = busca.buscar(catalogo, "ninho")
    assert len(achados) == 2 and ocultos == 0


def teste_palavra_curta_nao_vira_prefixo():
    catalogo = busca.indexar([produto("Sal Refinado Cisne 1kg", "sal"), produto("Sal Grosso Lebre 1kg", "sal"), produto("Sal Marinho Kitano", "sal"),
                              produto("Salsicha Hot Dog Sadia", "salsicha"), produto("Salame Italiano Seara", "presunto")])
    achados, ocultos = busca.buscar(catalogo, "sal")
    assert nomes(achados) == ["Sal Refinado Cisne 1kg", "Sal Grosso Lebre 1kg", "Sal Marinho Kitano"] and ocultos == 2


def teste_palavra_longa_vale_como_prefixo():
    catalogo = busca.indexar([produto(f"Arroz Marca {i}", "arroz") for i in range(3)] + [produto("Farinha de Arroz Tio João", "farinha de trigo")])
    assert len(busca.buscar(catalogo, "arro")[0]) == 3


def teste_sem_termo_o_inicio_do_nome_decide():
    # linhas da carga antiga (sem a coluna `termo`) ou de qualquer mercado que não a preencha
    catalogo = busca.indexar([produto(f"Café Marca {i} 500g") for i in range(3)] + [produto("Biscoito Sabor Café com Leite")])
    achados, ocultos = busca.buscar(catalogo, "cafe")
    assert len(achados) == 3 and ocultos == 1


def teste_varias_palavras_e_palavras_de_ligacao():
    catalogo = busca.indexar([produto("Óleo de Soja Liza 900ml", "óleo"), produto("Óleo de Soja Soya 900ml", "óleo"), produto("Óleo Soja Vitaliv 900ml", "óleo"),
                              produto("Óleo de Girassol Liza", "óleo"), produto("Molho de Soja Shoyu", "molho")])
    achados, ocultos = busca.buscar(catalogo, "óleo de soja")          # "de" é ignorado; o termo "óleo" não tem "soja", o nome começa por "óleo"
    assert len(achados) == 3 and ocultos == 0 and all("Soja" in n and n.startswith("Óleo") for n in nomes(achados))
    catalogo = busca.indexar([produto(f"Arroz Integral Marca {i}", "arroz") for i in range(3)] + [produto("Arroz Branco Camil", "arroz")])
    assert len(busca.buscar(catalogo, "arroz integral")[0]) == 3


def teste_termo_com_varias_palavras():
    catalogo = busca.indexar([produto(f"NINHO Leite em Pó {i}", "leite em pó") for i in range(3)] + [produto("Leite Condensado Moça", "leite condensado")])
    achados, ocultos = busca.buscar(catalogo, "leite")          # marca na frente: o termo da lista é que diz o que o produto é
    assert len(achados) == 4                                    # "leite em pó" e "leite condensado" têm a palavra "leite" no termo
    assert len(busca.buscar(catalogo, "leite em po")[0]) == 3                          # e "em" é ignorado na busca


def teste_limite_de_resultados():
    catalogo = busca.indexar([produto(f"Arroz Marca {i}", "arroz") for i in range(1000)])
    achados, ocultos = busca.buscar(catalogo, "arroz")
    assert len(achados) == busca.LIMITE_DE_RESULTADOS == 400 and ocultos == 600
    achados, ocultos = busca.buscar(catalogo, "arroz", limite=10)
    assert len(achados) == 10 and ocultos == 990
    catalogo = busca.indexar([produto(f"Arroz Marca {i}", "arroz") for i in range(3)] + [produto(f"Sopa com Arroz {i}", "sopa") for i in range(10)])
    assert busca.buscar(catalogo, "arroz", limite=5)[1] == 10        # os que só citam (10) + nenhum a mais


def teste_detalhe_dos_que_so_citam_por_mercado():
    catalogo = busca.indexar(
        [produto(f"Arroz Marca {i}", "arroz") for i in range(3)]
        + [produto("Condicionador com Arroz Preto", "condicionador", mercado="Supernosso"), produto("Sopa de Arroz", "sopa", mercado="Super ABC"),
           produto("Biscoito de Arroz", "biscoito", mercado="Supernosso")])
    b = busca.buscar_detalhado(catalogo, "arroz")
    assert len(b.produtos) == 3 and b.ocultos_so_citam == 3 and b.ocultos_pelo_limite == 0
    assert b.so_citam_por_mercado == {"Supernosso": 2, "Super ABC": 1}                      # para o site contar só os mercados que entregam na cidade
    assert busca.buscar(catalogo, "arroz") == (b.produtos, 3)                              # a forma antiga continua igual
    assert all("so_cita" not in p for p in b.produtos)


def teste_pedir_todos_traz_os_que_so_citam_marcados_sem_alterar_o_catalogo():
    catalogo = busca.indexar([produto(f"Arroz Marca {i}", "arroz") for i in range(3)] + [produto("Condicionador com Arroz Preto", "condicionador")])
    b = busca.buscar_detalhado(catalogo, "arroz", incluir_so_citam=True)
    assert nomes(b.produtos) == ["Arroz Marca 0", "Arroz Marca 1", "Arroz Marca 2", "Condicionador com Arroz Preto"]
    assert [p.get("so_cita") for p in b.produtos] == [None, None, None, True]               # só quem apenas cita vem marcado
    assert b.ocultos_so_citam == 0 and b.so_citam_por_mercado == {"Apoio Entrega": 1}
    assert all("so_cita" not in e.produto for e in catalogo)                               # o catálogo em memória não ganhou a marca


def teste_poucos_principais_mostra_tudo_e_ainda_conta_os_que_so_citam():
    catalogo = busca.indexar([produto("Arroz Camil", "arroz"), produto("Condicionador com Arroz Preto", "condicionador")])
    b = busca.buscar_detalhado(catalogo, "arroz")
    assert len(b.produtos) == 2 and b.ocultos_so_citam == 0 and b.so_citam_por_mercado == {"Apoio Entrega": 1}
    assert b.produtos[1].get("so_cita") is True


def teste_o_teto_conta_a_parte():
    catalogo = busca.indexar([produto(f"Arroz Marca {i}", "arroz") for i in range(10)] + [produto("Sopa com Arroz", "sopa")])
    b = busca.buscar_detalhado(catalogo, "arroz", limite=4)
    assert len(b.produtos) == 4 and b.ocultos_so_citam == 1 and b.ocultos_pelo_limite == 6
    assert busca.buscar(catalogo, "arroz", limite=4)[1] == 7
    b = busca.buscar_detalhado(catalogo, "arroz", limite=4, incluir_so_citam=True)
    assert b.ocultos_so_citam == 0 and b.ocultos_pelo_limite == 7


def teste_acento_caixa_e_busca_vazia():
    catalogo = busca.indexar([produto(f"FEIJÃO CARIOCA {i}", "feijão") for i in range(3)])
    assert len(busca.buscar(catalogo, "Feijao")[0]) == 3 and len(busca.buscar(catalogo, "FEIJÃO")[0]) == 3
    assert busca.buscar(catalogo, "   ") == ([], 0) and busca.buscar(catalogo, "") == ([], 0)
    assert busca.buscar(catalogo, "xyz")[0] == []


# ============================== agrupamento por EAN ==============================

def teste_mesmo_ean_junta_nomes_diferentes():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Arroz Branco Camil Tipo 1 5kg", mercado="Apoio Entrega", preco=24.99, ean="7896006711155"),
        produto("Arroz Camil Seleções 5 kg Pacote", mercado="Atacadao", preco=22.5, ean="7896006711155"),
        produto("ARROZ CAMIL T1 5KG", mercado="Supernosso", preco=24.99, ean="7896006711155"),
    ]])
    assert len(grupos) == 1 and grupos[0]["ean"] == "7896006711155"
    assert [o["supermercado"] for o in grupos[0]["opcoes_de_compra"]] == ["Atacadao", "Apoio Entrega", "Supernosso"]     # do mais barato
    assert grupos[0]["vencedor_preco_baixo"] == "Atacadao"


def teste_ean_com_zero_a_esquerda_e_o_mesmo():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Café em Pó Coffee++ Caparao 250g", mercado="Apoio Entrega", ean="0630941446201"),
        produto("Café em Pó Coffee++ Caparao 250g", mercado="Supernosso", ean="630941446201"),
    ]])
    assert len(grupos) == 1 and len(grupos[0]["opcoes_de_compra"]) == 2


def teste_mesmo_ean_com_medidas_diferentes_nao_junta():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Refrigerante Mate Couro 200ml", mercado="Apoio Entrega", ean="7896478801361"),
        produto("Refrigerante Mate Couro 1L", mercado="Atacadao", ean="7896478801361"),     # EAN repetido por engano no cadastro
    ]])
    assert len(grupos) == 2


def teste_ean_diferente_com_nome_so_parecido_nao_junta():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Cerveja Heineken Zero 250ml", mercado="Atacadao", ean="7896045507429"),
        produto("Cerveja Heineken Garrafa 250ml", mercado="Apoio Entrega", ean="7896045506132"),
        produto("Refrigerante Laranja Fanta Garrafa 200ml", mercado="Apoio Entrega", ean="78936478"),
        produto("Refrigerante Guaraná Antarctica 200ml", mercado="Supernosso", ean="7891991014908"),
    ]])
    assert len(grupos) == 4                                                                # antes, a similaridade de nome juntava esses pares


def teste_ean_diferente_com_nome_identico_em_mercados_diferentes_junta():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Refrigerante Pepsi Lata 350ml", mercado="Apoio Entrega", preco=3.09, ean="7892840800628"),
        produto("Refrigerante Pepsi Lata 350ml", mercado="Supernosso", preco=3.29, ean="7892840800079"),
    ]])
    assert len(grupos) == 1 and len(grupos[0]["opcoes_de_compra"]) == 2


def teste_nome_identico_no_mesmo_mercado_nao_junta():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Refrigerante Pepsi Lata 350ml", mercado="Apoio Entrega", ean="7892840800628"),
        produto("Refrigerante Pepsi Lata 350ml", mercado="Apoio Entrega", ean="7892840800079"),      # dois cadastros no mesmo mercado: produtos distintos ali
        produto("Refrigerante Pepsi Lata 350ml", mercado="Supernosso", ean="7892840800555"),
    ]])
    assert len(grupos) == 2                                                    # o Supernosso se junta a um dos dois do Apoio; o outro fica sozinho


def teste_sem_ean_entra_no_grupo_parecido_pelo_nome():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Arroz Branco Camil Tipo 1 5kg", mercado="Apoio Entrega", preco=24.99, ean="7896006711155"),
        produto("Arroz Camil Tipo 1 5kg", mercado="Super ABC", preco=26.0),                           # robô do Super ABC: sem EAN
        produto("Arroz Camil Tipo 1 1kg", mercado="Super ABC", preco=6.0),                            # outra medida: grupo próprio
    ]])
    assert len(grupos) == 2
    cinco = next(g for g in grupos if len(g["opcoes_de_compra"]) == 2)
    assert {o["supermercado"] for o in cinco["opcoes_de_compra"]} == {"Apoio Entrega", "Super ABC"} and cinco["ean"] == "7896006711155"


def teste_so_o_mais_barato_de_cada_mercado():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Feijão Carioca Camil 1kg", mercado="Apoio Entrega", preco=8.5, ean="7896006744115"),
        produto("Feijão Carioca Camil 1 kg", mercado="Apoio Entrega", preco=7.99, ean="7896006744115"),
        produto("Feijão Carioca Camil 1kg", mercado="Atacadao", preco=7.59, ean="7896006744115"),
    ]])
    assert len(grupos) == 1 and [o["preco_varejo"] for o in grupos[0]["opcoes_de_compra"]] == [7.59, 7.99]


def teste_sem_nenhum_ean_continua_como_antes():
    grupos = comp.cruzar_multiplos_produtos([[
        produto("Arroz Branco Camil Tipo 1 5kg", mercado="Apoio Entrega", preco=24.9),
        produto("Arroz Camil Tipo 1 5kg", mercado="Atacadao", preco=23.9),
        produto("Feijão Preto Camil 1kg", mercado="Apoio Entrega", preco=8.0),
    ]])
    assert len(grupos) == 2 and "ean" not in grupos[0] and grupos[0]["vencedor_preco_baixo"] == "Atacadao"
    assert comp.cruzar_multiplos_produtos([[]]) == [] and comp.cruzar_multiplos_produtos([]) == []


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
