"""Coletor por API pública do Super ABC (a loja online dele roda na plataforma VIP Commerce).

Em novembro de 2026 o Super ABC trocou o site (superabconline.com.br -> www.abcdelivery.com.br) e o robô de navegador parou: o botão de
unidades que ele procurava não existe mais. Em vez de consertar o robô, este coletor pergunta direto à API que o site novo usa, como o
`coletor_vtex.py` faz com os outros três mercados (veja docs/coletor_por_api.md, seção "Super ABC").

Como a loja identifica quem pergunta (sondado em 25/11/2026), tudo sem navegador:
1. Login anônimo: POST `/auth/loja/login` com a chave pública da loja (`CHAVE_DO_SITE`, que está no JavaScript do próprio site, em
   `lojaAuthJWT`) devolve um token. O token não traz prazo de validade; se a loja o recusar (HTTP 401), o coletor entra de novo, uma vez.
2. Sessão: GET `/loja/sessao_cliente` devolve o `sessao-id` que o site manda junto. A busca funciona sem ele, então ele é um extra.
3. Unidade: cada unidade (22) tem o seu preço. O coletor usa a de Betim (`CENTRO_DE_BETIM`), a mesma região do CEP_BASE da carga, e CONFERE
   na lista de unidades da loja que o número ainda é o de Betim: se a loja renumerar, a coleta para em vez de gravar o preço de outra cidade.
4. Busca: GET `.../centro_distribuicao/<unidade>/loja/buscas/produtos/termo/<termo>?page=N`, 20 produtos por página e `paginator.total_pages`.

O que vem em cada produto (e o que este coletor faz com isso):
- `disponivel`: a busca devolve o catálogo inteiro da rede, e a maioria não tem estoque na unidade (188 de 222 "arroz"). Só entra o disponível.
- `preco`: o que o site mostra ao cliente. Oferta e preço do Cliente Plus (`oferta`, `preco_original`) não entram: o preço do site é `preco`.
- `unidade_sigla`: "KG" = vendido a peso, e então `preco` é o da PORÇÃO (`quantidade_unidade_diferente`, em quilos): "Banana Prata 1,2 Kg" a R$ 9,59
  é a porção de 1,2 kg, a R$ 7,99 o quilo (o item "Banana Prata Kg" custa R$ 7,99). A linha leva o preço do QUILO e o multiplicador (a porção),
  como a dos outros mercados. Qualquer outra sigla (UN, BD, CX, PC, DP...) é venda por unidade ou pacote.
- `codigo_barras`: o EAN. Código interno (balança, loja) é descartado pelas mesmas regras do coletor da VTEX.
- Não há marca (só `marca_id`) nem categoria por nome: o filtro do termo decide só pelo nome, como decidia com o robô.

Só leitura: nada aqui escreve em banco. Rodar o relatório:  python coletor_vip.py --termos arroz,feijão
"""
import argparse
import json
import re
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import coletor_vtex
from busca import sem_acento
from coletor_vtex import ErroDeColeta, _avisar, ean_valido, numero

API = "https://services.vipcommerce.com.br/api-admin/v1/org/398"
SITE = "https://www.abcdelivery.com.br"
DOMINIO = "abcdelivery.com.br"
ORGANIZACAO = "398"
USUARIO = "loja"
# A chave pública do login anônimo da loja: está no JavaScript do site (`lojaAuthJWT`), igual para todo visitante. Se o login passar a ser
# recusado (HTTP 401/403), a primeira coisa a conferir é se ela mudou: docs/coletor_por_api.md ("Se o login for recusado").
CHAVE_DO_SITE = "df072f85df9bf7dd71b6811c34bdbaa4f219d98775b56cff9dfa5f8ca1bf8469"
FILIAL = 1
CENTRO_DE_BETIM = 8            # "ABC - Betim" na lista de unidades da loja; os preços mudam de unidade para unidade
NOME_DA_UNIDADE = "betim"      # o que a lista de unidades precisa dizer sobre o número acima (sem acento, em minúsculas)
UF = "MG"
MAX_PAGINAS = 15               # até 300 produtos brutos por termo (o teto de 100 vale depois do filtro), como nos outros mercados
PAGINAS_EM_PARALELO = 4        # páginas de uma mesma busca pedidas ao mesmo tempo
# A loja põe primeiro os produtos que têm as palavras da busca no nome; o que vem depois é ruído (em "creme de leite", os 11 produtos que
# servem estão na página 1 de 80). Por isso a busca para quando, DEPOIS de achar o que procura, passam 2 páginas seguidas sem nenhum nome
# com as palavras da busca. Sem nenhum achado, lê até o limite de páginas: sem o sinal, não adivinha.
PAGINAS_SEM_ACHADO = 2
# O site barra User-Agent curto ("Mozilla/5.0") na página; a API aceita, mas com o do navegador não há o que discutir.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
STATUS_DE_TOKEN_RECUSADO = (401, 403)

MERCADO = "Super ABC"


def cabecalhos_basicos():
    return {"User-Agent": USER_AGENT, "domainkey": DOMINIO, "organizationid": ORGANIZACAO, "Referer": SITE + "/", "Origin": SITE}


def _dado(resposta, o_que):
    """O `data` de uma resposta da loja. Resposta sem `success` é erro de coleta, com o que a loja disse."""
    if not isinstance(resposta, dict) or not resposta.get("success"):
        raise ErroDeColeta(f"a loja do Super ABC recusou {o_que}: {str(resposta)[:160]}")
    return resposta.get("data")


def unidade_da_lista(unidades, centro=CENTRO_DE_BETIM, nome=NOME_DA_UNIDADE):
    """O nome da unidade `centro` na lista da loja, se ela ainda é a de `nome`. Senão, erro: preço de outra cidade seria dado errado."""
    for unidade in unidades or []:
        if str(unidade.get("id")) == str(centro):
            achado = str(unidade.get("nome_site") or unidade.get("nome") or "")
            if nome in sem_acento(achado).lower() and unidade.get("ativo") is not False:
                return achado
            raise ErroDeColeta(f"a unidade {centro} do Super ABC agora é '{achado}' (ativa: {unidade.get('ativo')}), e não a de {nome.title()}: "
                               f"nenhum preço foi coletado para não gravar os de outra cidade")
    raise ErroDeColeta(f"a unidade {centro} do Super ABC (Betim) não está mais na lista de unidades da loja: nenhum preço foi coletado")


def entrar_sem_unidade(http):
    """Login anônimo + sessão, sem escolher unidade. -> cabeçalhos das chamadas da loja."""
    base = cabecalhos_basicos()
    try:
        token = _dado(http.post_json(f"{API}/auth/loja/login", {"domain": DOMINIO, "username": USUARIO, "key": CHAVE_DO_SITE}, base), "o login anônimo")
    except ErroDeColeta as erro:
        raise ErroDeColeta(f"o login anônimo do Super ABC falhou ({erro}); se a chave pública do site mudou, veja docs/coletor_por_api.md",
                           status=erro.status) from erro
    if not isinstance(token, str) or not token:
        raise ErroDeColeta("o login anônimo do Super ABC não devolveu o token")
    cabecalhos = {**base, "Authorization": "Bearer " + token}
    try:
        cabecalhos["sessao-id"] = _dado(http.get_json(f"{API}/loja/sessao_cliente", cabecalhos), "a sessão")["sessao_id"]
    except (ErroDeColeta, KeyError, TypeError) as erro:
        _avisar(http, f"Super ABC: sem sessão da loja ({str(erro)[:100]}); as buscas seguem sem ela")
    return cabecalhos


def lista_de_unidades(http, cabecalhos):
    """As unidades da loja (22 em 25/11/2026), cada uma com `id`, `nome_site`, `ativo` e `endereco` (`cidade` e `estado` por extenso)."""
    return _dado(http.get_json(f"{API}/filial/{FILIAL}/loja/centros_distribuicoes/retiradas", cabecalhos), "a lista de unidades")


def entrar(http, centro=CENTRO_DE_BETIM, nome=NOME_DA_UNIDADE):
    """Login anônimo + sessão + conferência da unidade. -> cabeçalhos das buscas."""
    cabecalhos = entrar_sem_unidade(http)
    print(f"📍 Super ABC: unidade confirmada: {unidade_da_lista(lista_de_unidades(http, cabecalhos), centro, nome)}", flush=True)
    return cabecalhos


UF_DO_ESTADO = {"acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE", "distrito federal": "DF", "espirito santo": "ES",
                "goias": "GO", "maranhao": "MA", "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
                "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
                "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO"}


def unidade_da_cidade(unidades, cidade, uf):
    """A primeira unidade ativa da loja na cidade `cidade`/`uf` (o endereço dela traz a cidade e o estado por extenso), ou None se não há.

    Serve ao levantamento de onde o Super ABC entrega (levantar_entrega.py): o site não localiza por CEP, e quem atende uma cidade é a unidade
    que fica nela. Compara sem acento e sem diferença de caixa; o estado entra na conta porque há cidades com o mesmo nome em estados diferentes.
    """
    for unidade in unidades or []:
        endereco = unidade.get("endereco") or {}
        estado = sem_acento(str(endereco.get("estado") or ""))
        uf_da_unidade = UF_DO_ESTADO.get(estado, estado.upper())
        if (unidade.get("ativo") is not False and sem_acento(str(endereco.get("cidade") or "")) == sem_acento(str(cidade))
                and uf_da_unidade == str(uf).upper()):
            return unidade
    return None


def _limpar_nome(texto):
    return " ".join(str(texto or "").split())


def palavras(texto):
    """As palavras de um texto, em minúsculas e sem acento: 'Óleo de Soja 900ml' -> ['oleo', 'de', 'soja', '900ml']."""
    return re.findall(r"[a-z0-9]+", sem_acento(str(texto or "")))


def casa_com_a_busca(nome, palavras_da_busca):
    """O nome tem todas as palavras da busca? Vale a palavra inteira, ou abreviada/no plural (de 3 letras para cima): "Sal Ref" casa com
    "sal refinado" e "Ovo" com "ovos"."""
    do_nome = palavras(nome)
    return all(any(p == n or (min(len(p), len(n)) >= 3 and (p.startswith(n) or n.startswith(p))) for n in do_nome) for p in palavras_da_busca)


def linha_do_produto(produto, termo):
    """A linha do produto no formato da carga, ou None se ele não pode ser vendido agora (sem estoque na unidade ou sem preço)."""
    if not produto.get("disponivel"):
        return None
    preco = numero(produto.get("preco"))
    nome = _limpar_nome(produto.get("descricao"))
    if preco <= 0 or not nome or produto.get("produto_id") in (None, ""):
        return None
    por_quilo = str(produto.get("unidade_sigla") or "").strip().upper() == "KG"
    # Por quilo, `preco` é o da porção (quantidade_unidade_diferente, em kg): o preço do quilo é a divisão, e a porção é o multiplicador.
    porcao = (numero(produto.get("quantidade_unidade_diferente")) or 1.0) if por_quilo else None
    preco_final = round(preco / porcao, 2) if por_quilo else round(preco, 2)
    return {
        "supermercado": MERCADO,
        "id_origem": str(produto["produto_id"]),
        "nome": nome,
        "marca": None,
        "ean": ean_valido(produto.get("codigo_barras")),
        "categoria": "",
        "preco_varejo": preco_final,
        "preco_atacado": preco_final,
        "quantidade_atacado": 1,
        "uf_cobertura": UF,
        "termo": termo,
        "peso_variavel": por_quilo,
        "unidade": "kg" if por_quilo else "un",
        "multiplicador": porcao,
    }


class BaixadorSuperAbc:
    """O baixador do Super ABC: chamado como os de `coletor_vtex.BAIXADORES` (`baixador(http, consulta)` -> linhas).

    Guarda o login (cabeçalhos) entre as buscas. A primeira página da busca diz quantas há; as outras vêm `paginas_em_paralelo` por vez
    (cada chamada leva cerca de 1 s, e um termo grande tem 15 páginas), sempre devolvidas na ordem da loja (a mais relevante primeiro).
    """

    def __init__(self, centro=CENTRO_DE_BETIM, nome=NOME_DA_UNIDADE, max_paginas=MAX_PAGINAS, paginas_em_paralelo=PAGINAS_EM_PARALELO):
        self.centro, self.nome, self.max_paginas, self.paginas_em_paralelo = centro, nome, max_paginas, paginas_em_paralelo
        self.cabecalhos = None
        self.logins = 0
        self._trava = threading.Lock()

    def _login(self, http, recusado=None):
        """Os cabeçalhos do login atual; entra se ainda não entrou, ou se o login atual é o `recusado` pela loja (e só um dos que esbarraram nisso entra)."""
        with self._trava:
            if self.cabecalhos is None or self.cabecalhos is recusado:
                self.cabecalhos = None
                self.cabecalhos = entrar(http, self.centro, self.nome)
                self.logins += 1
            return self.cabecalhos

    def _pedir(self, http, url):
        """GET com o login da loja. Se ela recusar o token, entra de novo e repete, uma vez."""
        cabecalhos = self._login(http)
        try:
            return http.get_json(url, cabecalhos)
        except ErroDeColeta as erro:
            if erro.status not in STATUS_DE_TOKEN_RECUSADO:
                raise
        return http.get_json(url, self._login(http, recusado=cabecalhos))

    def _pagina(self, http, consulta, pagina):
        """(produtos, total de páginas) de uma página da busca."""
        url = (f"{API}/filial/{FILIAL}/centro_distribuicao/{self.centro}/loja/buscas/produtos/termo/"
               f"{urllib.parse.quote(consulta, safe='')}?page={pagina}")
        resposta = self._pedir(http, url)
        produtos = (_dado(resposta, f"a busca por '{consulta}'") or {}).get("produtos")
        paginador = resposta.get("paginator")
        if not isinstance(produtos, list) or not isinstance(paginador, dict) or "total_pages" not in paginador:
            raise ErroDeColeta(f"a busca por '{consulta}' no Super ABC veio sem a lista de produtos ou sem a paginação: {str(resposta)[:160]}")
        return produtos, int(numero(paginador["total_pages"]))

    def produtos_da_busca(self, http, consulta):
        """Os produtos brutos da busca, do mais relevante para o menos, página a página (20 por página), até a regra de `PAGINAS_SEM_ACHADO`."""
        buscadas = palavras(consulta)
        estado = {"achou": False, "sem_achado": 0}

        def parar_depois_desta(produtos):
            if any(casa_com_a_busca(p.get("descricao"), buscadas) for p in produtos):
                estado["achou"], estado["sem_achado"] = True, 0
            else:
                estado["sem_achado"] += 1
            return estado["achou"] and estado["sem_achado"] >= PAGINAS_SEM_ACHADO

        produtos, total = self._pagina(http, consulta, 1)
        yield from produtos
        if parar_depois_desta(produtos):
            return
        restantes = list(range(2, min(total, self.max_paginas) + 1))
        with ThreadPoolExecutor(max_workers=max(1, self.paginas_em_paralelo)) as pool:
            for inicio in range(0, len(restantes), self.paginas_em_paralelo):
                lote = restantes[inicio:inicio + self.paginas_em_paralelo]
                for produtos_da_pagina in pool.map(lambda numero_da_pagina: self._pagina(http, consulta, numero_da_pagina)[0], lote):
                    yield from produtos_da_pagina
                    if parar_depois_desta(produtos_da_pagina):
                        return

    def __call__(self, http, consulta):
        return [linha for linha in (linha_do_produto(p, consulta) for p in self.produtos_da_busca(http, consulta)) if linha]


_BAIXADOR_DA_CARGA = BaixadorSuperAbc()


def baixar_super_abc(http, consulta):
    """O baixador da carga: um login por execução, guardado em `_BAIXADOR_DA_CARGA`."""
    return _BAIXADOR_DA_CARGA(http, consulta)


BAIXADORES = {MERCADO: baixar_super_abc}


# ============================== linha de comando ==============================

def principal(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Relatório do coletor do Super ABC (só leitura, não grava em banco).")
    parser.add_argument("--termos", help="só estes termos da lista, separados por vírgula (padrão: todos)")
    parser.add_argument("--lista", help="um arquivo de lista só (padrão: o que a carga diária coleta, a lista de produtos mais a de hortifrúti)")
    parser.add_argument("--saida", help="grava as linhas coletadas neste arquivo JSON")
    args = parser.parse_args(argv)

    teto, termos = coletor_vtex.carregar_lista(args.lista) if args.lista else coletor_vtex.carregar_lista_da_carga()
    if args.termos:
        pedidos = {sem_acento(t.strip()) for t in args.termos.split(",")}
        termos = [t for t in termos if sem_acento(t["termo"]) in pedidos]

    http = coletor_vtex.ClienteHttp()
    inicio = time.time()

    def ao_terminar(mercado, termo, brutas, escolhidas):
        print(f"{termo['termo']:<24} {brutas:>4} brutos -> {coletor_vtex.resumo_de_termo(escolhidas)}", flush=True)

    resultado, erros = coletor_vtex.coletar(http, [MERCADO], termos, teto, ao_terminar, BAIXADORES)
    total = sum(len(linhas) for linhas in resultado[MERCADO].values())
    print(f"\n{total} linhas em {time.time() - inicio:.0f}s, {http.chamadas} chamadas, {len(erros)} erro(s), {len(http.avisos)} aviso(s)")
    for _, termo, erro in erros:
        print(f"  ERRO {termo}: {erro}")
    if args.saida:
        Path(args.saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(principal())
