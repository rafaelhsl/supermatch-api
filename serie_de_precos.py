"""Série de preços de produtos, para o gráfico "histórico de preços" do site (docs/historico_de_precos.md, "O gráfico").

O histórico guarda o preço por intervalo (`precos.desde` até `precos.ate`; `ate` vazio = vale até hoje). Aqui só se LÊ: dado um
conjunto de produtos (mercado + chave do histórico), devolve os intervalos de preço de cada um. A chave é a mesma que o histórico usa
para gravar (`historico.chave_do_produto`) e que a API põe em cada produto do catálogo (`chave_historico`).

Cada leitura vai ao Supabase (uma consulta de produtos por mercado e uma de preços), então o resultado fica uns minutos em memória: o
gráfico de um mesmo produto aberto por várias pessoas não repete a consulta, e a cota de saída de dados do plano gratuito não sofre.
"""
import re
import threading
import time

from quedas import PRACA

MERCADOS = ("Apoio Entrega", "Atacadao", "Supernosso", "Super ABC")
MAXIMO_DE_PRODUTOS = 8             # um cartão do site tem no máximo 4 mercados; folga para o dobro
VALIDADE_SEGUNDOS = 1800           # 30 min: a carga grava às 07:30-08:00 e o gráfico de um produto que mudou hoje se corrige sozinho logo depois
LIMITE_DO_CACHE = 2000             # produtos guardados; passou disso, os mais antigos saem
_CHAVE = re.compile(r"[vn]:[A-Za-z0-9:_.\-]{1,100}")      # v:productId:itemId (mercados com API) ou n:<20 hex> (o nome, no Super ABC)


class PedidoInvalido(ValueError):
    """O que veio na consulta não é uma lista de "Mercado|chave" que a API entenda."""


def interpretar(texto):
    """'Atacadao|v:1:2,Supernosso|n:ab12' -> [('Atacadao', 'v:1:2'), ('Supernosso', 'n:ab12')], sem repetidos e na ordem pedida."""
    if not texto or not str(texto).strip():
        raise PedidoInvalido("informe os produtos: chaves=Mercado|chave,Mercado|chave")
    pares = []
    for pedaco in str(texto).split(","):
        mercado, separador, chave = pedaco.strip().partition("|")
        if not separador or mercado not in MERCADOS:
            raise PedidoInvalido(f"mercado desconhecido ou pedido mal formado: {pedaco[:60]!r}")
        if not _CHAVE.fullmatch(chave):
            raise PedidoInvalido(f"chave do histórico mal formada: {chave[:60]!r}")
        if (mercado, chave) not in pares:
            pares.append((mercado, chave))
    if len(pares) > MAXIMO_DE_PRODUTOS:
        raise PedidoInvalido(f"no máximo {MAXIMO_DE_PRODUTOS} produtos por consulta")
    return pares


def ler_series(banco, pares):
    """{(mercado, chave): [{'desde': 'AAAA-MM-DD', 'ate': 'AAAA-MM-DD' ou None, 'preco': 7.99}, ...]} em ordem de data.
    Produto sem histórico (ou que nunca entrou no catálogo do histórico) fica com a lista vazia."""
    resultado = {par: [] for par in pares}
    por_mercado = {}
    for mercado, chave in pares:
        por_mercado.setdefault(mercado, []).append(chave)
    for mercado, chaves in por_mercado.items():
        produtos = banco.table("catalogo").select("id,chave_origem").eq("supermercado", mercado).in_("chave_origem", chaves).execute().data
        chave_do_id = {linha["id"]: linha["chave_origem"] for linha in produtos}
        if not chave_do_id:
            continue
        precos = (banco.table("precos").select("catalogo_id,desde,ate,preco_varejo")
                  .eq("praca", PRACA).in_("catalogo_id", list(chave_do_id))
                  .order("catalogo_id").order("desde").execute().data)
        for linha in precos:
            chave = chave_do_id.get(linha["catalogo_id"])
            if chave is not None:
                resultado[(mercado, chave)].append({"desde": str(linha["desde"])[:10], "ate": str(linha["ate"])[:10] if linha.get("ate") else None, "preco": round(float(linha["preco_varejo"]), 2)})
    return resultado


class CacheDeSeries:
    """Guarda as séries por alguns minutos. `obter` só consulta o banco para o que falta ou venceu, e numa consulta só."""

    def __init__(self, validade=VALIDADE_SEGUNDOS, limite=LIMITE_DO_CACHE, relogio=time.monotonic):
        self._guardado = {}                 # (mercado, chave) -> (quando, intervalos)
        self._trava = threading.Lock()
        self.validade, self.limite, self._relogio = validade, limite, relogio

    def obter(self, banco, pares):
        with self._trava:
            agora = self._relogio()
            faltam = [p for p in pares if p not in self._guardado or agora - self._guardado[p][0] >= self.validade]
            if faltam:
                for par, intervalos in ler_series(banco, faltam).items():       # se o banco falhar, o erro sobe e nada é guardado pela metade
                    self._guardado[par] = (agora, intervalos)
                while len(self._guardado) > self.limite:
                    del self._guardado[min(self._guardado, key=lambda p: self._guardado[p][0])]
            return {par: self._guardado[par][1] for par in pares}
