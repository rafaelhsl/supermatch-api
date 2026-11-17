"""Selo "caiu X% em 7 dias": compara o preço de hoje com o que cada produto tinha 7 dias antes, a partir do histórico de preços.

Como funciona (docs/historico_de_precos.md explica as tabelas):

- O histórico guarda o preço por intervalo (`precos.desde` até `precos.ate`; `ate` vazio = vale até hoje). O preço de 7 dias atrás
  é o do intervalo que contém aquele dia. Quem não mudou de preço desde então tem esse intervalo ainda aberto: não há nada a
  comparar. Por isso a consulta traz só os intervalos que contêm o dia de antes e JÁ FECHARAM, ou seja, só os produtos cujo preço
  mudou depois (uns 25% do catálogo): cerca de 3 mil linhas, não as 14 mil.
- A consulta roda uma vez por carga de preços (não a cada recarga do catálogo, que é de hora em hora): o resultado fica em memória,
  para não gastar a cota de saída de dados do Supabase. Leitura feita logo depois da carga é provisória (veja ESPERA_DEPOIS_DA_CARGA).
- Cada produto do catálogo é ligado ao histórico pela mesma chave que o histórico usa para gravar (`historico.chave_do_produto`).
- Se o histórico falhar (tabela fora do ar, rede), o catálogo carrega do mesmo jeito, só que sem selos.

O produto ganha `queda_preco = {"preco_antes": 14.99, "percentual": 47, "dias": 7}` quando o preço do varejo caiu pelo menos
LIMITE_QUEDA_PCT e no máximo TETO_QUEDA_PCT por cento em relação ao de JANELA_DIAS dias antes. Não têm selo: subida, queda pequena,
preço que voltou ao mesmo valor, queda grande demais (quase sempre erro de coleta) e a linha que não é da carga mais nova.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

from historico import BRASILIA, chave_do_produto

JANELA_DIAS = 7            # compara com o preço de 7 dias antes
LIMITE_QUEDA_PCT = 5.0     # só vira selo a queda de 5% ou mais (em 3 a 7 dias, quedas entre 1% e 5% são raras: o limite pouco muda a quantidade)
TETO_QUEDA_PCT = 70.0      # queda maior que isso quase sempre é erro de coleta (um feijão de 1 kg a R$ 0,78): melhor não afirmar nada
PRACA = "betim"            # a praça da coleta (a mesma de alimentar_banco.PRACA_BASE; um teste confere)
TAMANHO_PAGINA = 1000      # limite de linhas por consulta do Supabase
# A carga grava um mercado de cada vez: primeiro os produtos dele, segundos ou minutos depois o histórico dele. Uma leitura feita
# enquanto a carga ainda corre (ou logo depois) pode não ver o fechamento dos intervalos de quem mudou de preço HOJE, e esses
# produtos ficariam sem selo. Por isso a leitura feita menos de 15 minutos depois da gravação mais nova é provisória e se repete
# na recarga seguinte do catálogo.
ESPERA_DEPOIS_DA_CARGA = timedelta(minutes=15)


def _agora():
    return datetime.now(timezone.utc)


def _momento(texto):
    """'2026-11-15T10:44:50.134498+00:00' -> datetime com fuso (sem fuso, vale como UTC); None se não der para ler."""
    if not texto:
        return None
    try:
        momento = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _dia(momento):
    return momento.astimezone(BRASILIA).date()


def momento_dos_dados(produtos):
    """A gravação mais nova do catálogo (quando a carga mais recente escreveu um produto). None se nenhum produto traz a data."""
    momentos = [m for m in (_momento(p.get("atualizado_em")) for p in produtos) if m]
    return max(momentos) if momentos else None


def dia_dos_dados(produtos):
    """O dia (de Brasília) da carga mais nova do catálogo: é o 'hoje' dos preços, mesmo se a API for consultada de manhã cedo,
    antes da carga do dia. None se nenhum produto traz a data."""
    momento = momento_dos_dados(produtos)
    return _dia(momento) if momento else None


def ler_precos_de_antes(banco, dia_de_antes):
    """{(mercado, chave_origem): preço do varejo} que valia em `dia_de_antes`, só dos produtos cujo preço mudou depois desse dia."""
    dia = dia_de_antes.isoformat()
    antes, inicio = {}, 0
    while True:
        pagina = (banco.table("precos")
                  .select("catalogo_id,preco_varejo,catalogo(supermercado,chave_origem)")
                  .eq("praca", PRACA).lte("desde", dia).gte("ate", dia)       # `ate >= dia` deixa de fora o intervalo ainda aberto
                  .order("catalogo_id")                                       # sem ordem fixa, a paginação repete e perde linhas
                  .range(inicio, inicio + TAMANHO_PAGINA - 1)
                  .execute().data)
        for linha in pagina:
            produto = linha.get("catalogo") or {}
            if produto.get("supermercado") and produto.get("chave_origem") and linha.get("preco_varejo") is not None:
                antes[(produto["supermercado"], produto["chave_origem"])] = float(linha["preco_varejo"])
        if len(pagina) < TAMANHO_PAGINA:
            return antes
        inicio += TAMANHO_PAGINA


def marcar_quedas(produtos, antes, limite_pct=LIMITE_QUEDA_PCT, dias=JANELA_DIAS, teto_pct=TETO_QUEDA_PCT, dia=None):
    """Põe `queda_preco` nos produtos cujo varejo caiu entre `limite_pct`% e `teto_pct`% em relação a `antes`. Devolve quantos marcou.

    Com `dia`, só conta a linha gravada nesse dia: a que a carga mais nova deixou para trás (um mercado que falhou, ou os termos que
    falharam numa coleta parcial) tem preço de outro dia e não pode ganhar um selo que afirma o preço de hoje.
    """
    marcados = 0
    for produto in produtos:
        try:
            if dia is not None:
                gravado = _momento(produto.get("atualizado_em"))
                if gravado is None or _dia(gravado) != dia:
                    continue
            anterior = antes.get((produto["supermercado"], chave_do_produto(produto)))
            atual = float(produto["preco_varejo"])
        except (KeyError, TypeError, ValueError):
            continue
        if not anterior or anterior <= 0 or atual <= 0 or atual >= anterior:
            continue
        percentual = (anterior - atual) / anterior * 100
        if limite_pct <= percentual + 1e-9 and percentual <= teto_pct + 1e-9:
            produto["queda_preco"] = {"preco_antes": round(anterior, 2), "percentual": round(percentual), "dias": dias}
            marcados += 1
    return marcados


class QuedasDoHistorico:
    """Guarda em memória os preços de antes e os aplica ao catálogo de cada carga. A consulta ao banco só se repete quando há uma
    carga nova de preços (ou enquanto a leitura é provisória, ou depois de uma falha); recarregar o catálogo sem carga nova
    reaproveita o que já foi lido."""

    def __init__(self):
        self._guardados = {}        # momento da gravação mais nova -> (preços de antes, definitivo?); só os 2 mais novos (UFs diferentes podem divergir)
        self._trava = threading.Lock()

    def anotar(self, banco, produtos):
        """Marca as quedas em `produtos`. NUNCA levanta erro: se o histórico falhar, o catálogo segue sem selos e a próxima carga tenta de novo."""
        try:
            momento = momento_dos_dados(produtos)
            if momento is None:
                return 0
            dia = _dia(momento)
            with self._trava:
                guardado = self._guardados.get(momento)
                if guardado is None or not guardado[1]:
                    inicio = time.monotonic()
                    de_antes = dia - timedelta(days=JANELA_DIAS)
                    antes = ler_precos_de_antes(banco, de_antes)
                    definitivo = _agora() - momento >= ESPERA_DEPOIS_DA_CARGA
                    guardado = (antes, definitivo)
                    self._guardados[momento] = guardado
                    for velho in sorted(self._guardados)[:-2]:
                        del self._guardados[velho]
                    print(f"📉 Histórico lido em {time.monotonic() - inicio:.1f} s: {len(antes)} produtos com preço diferente do de {de_antes:%d/%m} "
                          f"(dados de {dia:%d/%m})" + ("" if definitivo else "; leitura provisória, a carga acabou de gravar: lê de novo na próxima recarga"))
                antes = guardado[0]
            marcados = marcar_quedas(produtos, antes, dia=dia)
            print(f"📉 {marcados} de {len(produtos)} produtos com queda de {LIMITE_QUEDA_PCT:g}% a {TETO_QUEDA_PCT:g}% em {JANELA_DIAS} dias")
            return marcados
        except Exception as erro:
            print(f"⚠️ Selo de queda de preço: histórico indisponível ({erro!r}); o catálogo segue sem selos.")
            return 0
