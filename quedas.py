"""Selo "caiu X% em 7 dias": compara o preço de hoje com o que cada produto tinha 7 dias antes, a partir do histórico de preços.

Como funciona (docs/historico_de_precos.md explica as tabelas):

- O histórico guarda o preço por intervalo (`precos.desde` até `precos.ate`; `ate` vazio = vale até hoje). O preço de 7 dias atrás
  é o do intervalo que contém aquele dia. Quem não mudou de preço desde então tem esse intervalo ainda aberto: não há nada a
  comparar. Por isso a consulta traz só os intervalos que contêm o dia de antes e JÁ FECHARAM, ou seja, só os produtos cujo preço
  mudou depois (uns 25% do catálogo): cerca de 3 mil linhas, não as 14 mil.
- A consulta roda uma vez por dia de carga (não a cada recarga do catálogo, que é de hora em hora): o resultado fica em memória,
  para não gastar a cota de saída de dados do Supabase.
- Cada produto do catálogo é ligado ao histórico pela mesma chave que o histórico usa para gravar (`historico.chave_do_produto`).
- Se o histórico falhar (tabela fora do ar, rede), o catálogo carrega do mesmo jeito, só que sem selos.

O produto ganha `queda_preco = {"preco_antes": 14.99, "percentual": 47, "dias": 7}` quando o preço do varejo caiu pelo menos
LIMITE_QUEDA_PCT por cento em relação ao de JANELA_DIAS dias antes. Subida, queda pequena e preço que voltou ao mesmo valor não têm selo.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

from historico import BRASILIA, chave_do_produto

JANELA_DIAS = 7            # compara com o preço de 7 dias antes
LIMITE_QUEDA_PCT = 5.0     # só vira selo a queda de 5% ou mais (em 3 a 7 dias, quedas entre 1% e 5% são raras: o limite pouco muda a quantidade)
PRACA = "betim"            # a praça da coleta (a mesma de alimentar_banco.PRACA_BASE; um teste confere)
TAMANHO_PAGINA = 1000      # limite de linhas por consulta do Supabase


def _momento(texto):
    """'2026-11-15T10:44:50.134498+00:00' -> datetime com fuso (sem fuso, vale como UTC); None se não der para ler."""
    if not texto:
        return None
    try:
        momento = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def dia_dos_dados(produtos):
    """O dia (de Brasília) da carga mais nova do catálogo: é o 'hoje' dos preços, mesmo se a API for consultada de manhã cedo,
    antes da carga do dia. None se nenhum produto traz a data."""
    momentos = [m for m in (_momento(p.get("atualizado_em")) for p in produtos) if m]
    return max(momentos).astimezone(BRASILIA).date() if momentos else None


def ler_precos_de_antes(banco, dia_de_antes):
    """{(mercado, chave_origem): preço do varejo} que valia em `dia_de_antes`, só dos produtos cujo preço mudou depois desse dia."""
    dia = dia_de_antes.isoformat()
    antes, inicio = {}, 0
    while True:
        pagina = (banco.table("precos")
                  .select("catalogo_id,preco_varejo,catalogo(supermercado,chave_origem)")
                  .eq("praca", PRACA).lte("desde", dia).gte("ate", dia)       # `ate >= dia` deixa de fora o intervalo ainda aberto
                  .order("catalogo_id")
                  .range(inicio, inicio + TAMANHO_PAGINA - 1)
                  .execute().data)
        for linha in pagina:
            produto = linha.get("catalogo") or {}
            if produto.get("supermercado") and produto.get("chave_origem") and linha.get("preco_varejo") is not None:
                antes[(produto["supermercado"], produto["chave_origem"])] = float(linha["preco_varejo"])
        if len(pagina) < TAMANHO_PAGINA:
            return antes
        inicio += TAMANHO_PAGINA


def marcar_quedas(produtos, antes, limite_pct=LIMITE_QUEDA_PCT, dias=JANELA_DIAS):
    """Põe `queda_preco` nos produtos cujo varejo caiu `limite_pct`% ou mais em relação a `antes`. Devolve quantos marcou."""
    marcados = 0
    for produto in produtos:
        try:
            anterior = antes.get((produto["supermercado"], chave_do_produto(produto)))
            atual = float(produto["preco_varejo"])
        except (KeyError, TypeError, ValueError):
            continue
        if not anterior or anterior <= 0 or atual <= 0 or atual >= anterior:
            continue
        percentual = (anterior - atual) / anterior * 100
        if percentual + 1e-9 >= limite_pct:
            produto["queda_preco"] = {"preco_antes": round(anterior, 2), "percentual": round(percentual), "dias": dias}
            marcados += 1
    return marcados


class QuedasDoHistorico:
    """Guarda em memória os preços de antes e os aplica ao catálogo de cada carga. A consulta ao banco só se repete quando o dia
    dos dados muda (ou depois de uma falha); recarregar o catálogo no mesmo dia reaproveita o que já foi lido."""

    def __init__(self):
        self._por_dia = {}          # dia dos dados -> preços de antes (guarda só os 2 dias mais novos: catálogos de UFs diferentes podem estar em dias diferentes)
        self._trava = threading.Lock()

    def anotar(self, banco, produtos):
        """Marca as quedas em `produtos`. NUNCA levanta erro: se o histórico falhar, o catálogo segue sem selos e a próxima carga tenta de novo."""
        try:
            dia = dia_dos_dados(produtos)
            if dia is None:
                return 0
            with self._trava:
                if dia not in self._por_dia:
                    inicio = time.monotonic()
                    de_antes = dia - timedelta(days=JANELA_DIAS)
                    antes = ler_precos_de_antes(banco, de_antes)
                    self._por_dia = {d: a for d, a in sorted(self._por_dia.items())[-1:]}      # descarta os mais antigos
                    self._por_dia[dia] = antes
                    print(f"📉 Histórico lido em {time.monotonic() - inicio:.1f} s: {len(antes)} produtos com preço diferente do de {de_antes:%d/%m} (dados de {dia:%d/%m})")
                antes = self._por_dia[dia]
            marcados = marcar_quedas(produtos, antes)
            print(f"📉 {marcados} de {len(produtos)} produtos com queda de {LIMITE_QUEDA_PCT:g}% ou mais em {JANELA_DIAS} dias")
            return marcados
        except Exception as erro:
            print(f"⚠️ Selo de queda de preço: histórico indisponível ({erro!r}); o catálogo segue sem selos.")
            return 0
