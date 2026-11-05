"""Histórico de preços: a cada carga, registra só o que mudou.

Três tabelas (script em docs/sql/historico_precos.sql; desenho em docs/historico_de_precos.md):

- `catalogo`: o produto, com identidade estável. A tabela `produtos` é apagada e recriada a cada carga e seus ids
  mudam todo dia, então não serve de chave para o histórico.
- `precos`: o preço vigente em um intervalo de datas (desde/ate). Um intervalo novo só abre quando o preço muda.
- `coletas`: o que cada carga fez por dia e mercado. É o que separa "não coletei" de "o produto sumiu".

Este módulo tem três partes: funções puras que decidem o que gravar (`preparar_itens`, `planejar`, `escolher_inativos`),
o orquestrador `registrar_mercado`, que conversa com um repositório, e o `RepositorioSupabase`, que é esse repositório.
Os testes (tests/test_historico.py) usam um repositório em memória e um falso Supabase.
"""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from busca import sem_acento

# O Brasil não tem horário de verão desde 2019, então Brasília é UTC-3 o ano todo. O "dia" do histórico é o de Brasília.
BRASILIA = timezone(timedelta(hours=-3))
CARGAS_SEM_APARECER = 3     # o produto só é dado como saído depois de sumir de 3 cargas completas seguidas
LOTE = 300                  # linhas (ou ids) por chamada ao Supabase


def hoje_em_brasilia():
    return datetime.now(BRASILIA).date()


# ============================== o que gravar (funções puras) ==============================

def normalizar_nome(nome):
    """'Arroz Branco Camil Tipo 1 5Kg' e 'arroz  branco camil tipo 1 5kg' dão o mesmo texto."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sem_acento(str(nome)))).strip()


def chave_origem(nome):
    """Identidade pelo nome ('n:…'), para o produto que não tem id do mercado (o que vem do robô)."""
    return "n:" + hashlib.sha1(normalizar_nome(nome).encode("utf-8")).hexdigest()[:20]


def chave_do_produto(produto):
    """Identidade do produto dentro do mercado: o id do catálogo do mercado ('v:productId:itemId') quando o coletor por API o traz; senão, o nome."""
    id_origem = str(produto.get("id_origem") or "").strip()
    return ("v:" + id_origem) if id_origem else chave_origem(produto["nome"])


def preparar_itens(produtos):
    """Produtos coletados -> ({chave: item}, duplicados). Descarta o que não tem preço; se a mesma chave aparece duas vezes, fica o mais barato."""
    itens, duplicados = {}, 0
    for p in produtos:
        try:
            varejo = round(float(p["preco_varejo"]), 2)
        except (KeyError, TypeError, ValueError):
            continue
        if varejo <= 0 or not str(p.get("nome", "")).strip():
            continue
        atacado = p.get("preco_atacado")
        item = {
            "chave": chave_do_produto(p),
            "legado": chave_origem(p["nome"]),          # a chave que o histórico antigo (por nome) usava para este produto
            "nome": str(p["nome"]).strip(),
            "ean": p.get("ean") or None,
            "marca": p.get("marca") or None,
            "categoria": p.get("categoria") or None,
            "preco_varejo": varejo,
            "preco_atacado": round(float(atacado), 2) if atacado not in (None, "") else None,
            "quantidade_atacado": int(p.get("quantidade_atacado") or 1),
        }
        antigo = itens.get(item["chave"])
        if antigo is not None:
            duplicados += 1
            if antigo["preco_varejo"] <= varejo:
                continue
        itens[item["chave"]] = item
    return itens, duplicados


def alinhar_chaves(itens, catalogo):
    """Item sem id do mercado (vem do robô) cujo nome o catálogo já guarda sob outra chave: usa a chave que já existe.

    Acontece depois que um produto foi religado ao id do mercado: no dia em que só o robô o traz, ele continua sendo o mesmo produto.
    """
    por_nome = {}
    for chave, entrada in catalogo.items():
        if entrada.get("nome"):
            por_nome.setdefault(chave_origem(entrada["nome"]), chave)
    alinhados = {}
    for chave, item in itens.items():
        destino = chave
        if chave.startswith("n:") and chave not in catalogo and por_nome.get(chave) not in (None, *itens):
            destino = por_nome[chave]
        if destino not in alinhados:
            alinhados[destino] = {**item, "chave": destino}
    return alinhados


def a_religar(itens, catalogo):
    """Produtos que o catálogo guardava pelo nome ('n:…') e agora chegam com o id do mercado ('v:…'): passam a usar o id.

    Troca a chave no `catalogo` (em memória) e devolve [(id do catálogo, chave nova, item)] para o banco, para o histórico de
    preços continuar de onde estava em vez de recomeçar com um produto novo.
    """
    pares = []
    for chave, item in itens.items():
        legado = item.get("legado")
        if chave.startswith("v:") and chave not in catalogo and legado in catalogo and legado not in itens:
            entrada = catalogo.pop(legado)
            catalogo[chave] = entrada
            pares.append((entrada["id"], chave, item))
    return pares


def mesmo_preco(aberto, item):
    """O intervalo aberto já registra este preço (varejo, atacado e quantidade do atacado)?"""
    def igual(a, b):
        return (a is None and b is None) or (a is not None and b is not None and abs(float(a) - float(b)) < 0.005)
    return (igual(aberto["preco_varejo"], item["preco_varejo"]) and igual(aberto["preco_atacado"], item["preco_atacado"])
            and int(aberto["quantidade_atacado"] or 1) == int(item["quantidade_atacado"] or 1))


@dataclass
class Plano:
    vistos: list = field(default_factory=list)      # ids do catálogo para marcar como vistos hoje (e ativos)
    abrir: list = field(default_factory=list)       # (id, item): abre um intervalo de preço a partir de hoje
    fechar: list = field(default_factory=list)      # ids cujo intervalo aberto termina ontem (o preço mudou)
    corrigir: list = field(default_factory=list)    # (id, item): o intervalo aberto começou hoje e o preço mudou de novo no mesmo dia


def separar_novos(itens, catalogo):
    """Itens que ainda não estão no catálogo do mercado."""
    return [item for chave, item in itens.items() if chave not in catalogo]


def planejar(dia, itens, catalogo, abertos):
    """Decide o que gravar para cada item visto hoje.

    catalogo: {chave: {"id", "ativo", "ultimo_dia"}}, já com os produtos novos. abertos: {id do catálogo: intervalo aberto}.
    """
    plano = Plano()
    for chave, item in itens.items():
        entrada = catalogo[chave]
        if not entrada["ativo"] or entrada["ultimo_dia"] != dia:
            plano.vistos.append(entrada["id"])
        aberto = abertos.get(entrada["id"])
        if aberto is None:
            plano.abrir.append((entrada["id"], item))            # produto novo, ou voltou depois de dado como saído
        elif mesmo_preco(aberto, item):
            continue                                              # nada mudou: só o "visto hoje" acima
        elif aberto["desde"] == dia:
            plano.corrigir.append((entrada["id"], item))          # carga repetida no mesmo dia com outro preço
        else:
            plano.fechar.append(entrada["id"])
            plano.abrir.append((entrada["id"], item))
    return plano


def escolher_inativos(catalogo, dias_ok, minimo=CARGAS_SEM_APARECER):
    """Produtos ativos que não apareceram em nenhuma das últimas `minimo` cargas completas do mercado. -> [(id, ultimo_dia)]."""
    if len(dias_ok) < minimo:
        return []
    limite = min(dias_ok[:minimo])
    return [(e["id"], e["ultimo_dia"]) for e in catalogo.values() if e["ativo"] and e["ultimo_dia"] < limite]


# ============================== o orquestrador ==============================

@dataclass
class Resumo:
    itens: int = 0
    novos: int = 0
    mudaram: int = 0
    reabertos: int = 0
    inativados: int = 0
    duplicados: int = 0
    religados: int = 0
    status: str = "ok"

    def linha(self):
        texto = (f"{self.itens} itens: {self.novos} novos, {self.mudaram} com preço novo, {self.reabertos} que voltaram, "
                 f"{self.inativados} que saíram, {self.duplicados} repetidos")
        if self.religados:
            texto += f", {self.religados} religados ao id do mercado"
        if self.status != "ok":
            texto += f" [coleta {self.status}: quem não apareceu não conta como saído]"
        return texto


def registrar_mercado(repo, mercado, produtos, dia, praca="betim", status="ok"):
    """Registra no histórico a coleta de um mercado. Pode ser repetida no mesmo dia sem duplicar nada.

    status "ok": coleta completa. "parcial": faltou parte (alguns termos falharam); registra o que veio, mas o produto que não
    apareceu não conta como "sumiu" e o dia não entra na contagem das 3 cargas completas.
    """
    if status not in ("ok", "parcial"):
        raise ValueError(f"status inválido: {status}")
    itens, duplicados = preparar_itens(produtos)
    if not itens:
        raise ValueError("nenhum produto com nome e preço para registrar")
    catalogo = repo.carregar_catalogo(mercado)
    itens = alinhar_chaves(itens, catalogo)
    religados = a_religar(itens, catalogo)
    if religados:
        repo.religar(religados)
    abertos = repo.carregar_precos_abertos(mercado, praca)

    novos = separar_novos(itens, catalogo)
    criados = repo.inserir_catalogo(mercado, novos, dia)
    catalogo.update(criados)
    ids_novos = {e["id"] for e in criados.values()}

    plano = planejar(dia, itens, catalogo, abertos)
    repo.atualizar_visto(plano.vistos, dia)
    repo.fechar_precos(plano.fechar, dia - timedelta(days=1), praca)
    repo.abrir_precos(plano.abrir, dia, praca)
    repo.corrigir_precos(plano.corrigir, dia, praca)

    vistos = set(plano.vistos)
    for entrada in catalogo.values():           # mantém o catálogo em memória igual ao do banco para a etapa seguinte
        if entrada["id"] in vistos:
            entrada["ultimo_dia"], entrada["ativo"] = dia, True

    repo.registrar_coleta(dia, mercado, praca, status, len(itens))
    inativos = []
    if status == "ok":
        inativos = escolher_inativos(catalogo, repo.ultimos_dias_ok(mercado, praca, CARGAS_SEM_APARECER))
        repo.inativar(inativos, praca)

    ids_fechar = set(plano.fechar)
    return Resumo(
        itens=len(itens), novos=len(ids_novos), mudaram=len(plano.fechar) + len(plano.corrigir),
        reabertos=sum(1 for i, _ in plano.abrir if i not in ids_fechar and i not in ids_novos),
        inativados=len(inativos), duplicados=duplicados, religados=len(religados), status=status,
    )


def registrar_falha(repo, mercado, motivo, dia, praca="betim"):
    """Anota que a carga do mercado falhou. Dia sem coleta é lacuna no histórico, nunca produto que saiu. Não apaga um 'ok' do mesmo dia."""
    repo.registrar_coleta(dia, mercado, praca, "falhou", 0, motivo)


# ============================== o repositório do Supabase ==============================

def _data(valor):
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def _em_lotes(lista, tamanho=LOTE):
    for i in range(0, len(lista), tamanho):
        yield lista[i:i + tamanho]


class RepositorioSupabase:
    """As gravações do histórico no Supabase (cliente da biblioteca `supabase`)."""

    def __init__(self, banco):
        self.banco = banco

    def _paginado(self, montar):
        """Lê todas as linhas, 1000 por vez (o limite de cada consulta do Supabase)."""
        linhas, inicio = [], 0
        while True:
            pagina = montar().range(inicio, inicio + 999).execute().data
            linhas.extend(pagina)
            if len(pagina) < 1000:
                return linhas
            inicio += 1000

    def carregar_catalogo(self, mercado):
        linhas = self._paginado(lambda: self.banco.table("catalogo").select("id,chave_origem,nome,ativo,ultimo_dia")
                                .eq("supermercado", mercado).order("id"))
        return {l["chave_origem"]: {"id": l["id"], "nome": l["nome"], "ativo": l["ativo"], "ultimo_dia": _data(l["ultimo_dia"])} for l in linhas}

    def carregar_precos_abertos(self, mercado, praca):
        linhas = self._paginado(lambda: self.banco.table("precos")
                                .select("catalogo_id,desde,preco_varejo,preco_atacado,quantidade_atacado,catalogo!inner(supermercado)")
                                .eq("praca", praca).is_("ate", "null").eq("catalogo.supermercado", mercado).order("catalogo_id"))
        return {l["catalogo_id"]: {"desde": _data(l["desde"]), "preco_varejo": l["preco_varejo"], "preco_atacado": l["preco_atacado"],
                                   "quantidade_atacado": l["quantidade_atacado"]} for l in linhas}

    def inserir_catalogo(self, mercado, itens, dia):
        """Insere os produtos novos e devolve {chave: entrada} com os ids gerados."""
        criados = {}
        for lote in _em_lotes(itens):
            linhas = [{"supermercado": mercado, "chave_origem": i["chave"], "nome": i["nome"], "ean": i.get("ean"), "marca": i.get("marca"),
                       "categoria": i.get("categoria"), "primeiro_dia": dia.isoformat(), "ultimo_dia": dia.isoformat(), "ativo": True} for i in lote]
            for l in self.banco.table("catalogo").insert(linhas).execute().data:
                criados[l["chave_origem"]] = {"id": l["id"], "nome": l["nome"], "ativo": True, "ultimo_dia": dia}
        return criados

    def religar(self, pares):
        """Produtos que eram guardados pelo nome passam a ser guardados pelo id do mercado (e ganham EAN, marca e categoria)."""
        for i, chave, item in pares:
            self.banco.table("catalogo").update({"chave_origem": chave, "ean": item.get("ean"), "marca": item.get("marca"),
                                                 "categoria": item.get("categoria")}).eq("id", i).execute()

    def atualizar_visto(self, ids, dia):
        for lote in _em_lotes(ids):
            self.banco.table("catalogo").update({"ultimo_dia": dia.isoformat(), "ativo": True}).in_("id", lote).execute()

    def fechar_precos(self, ids, ate, praca):
        for lote in _em_lotes(ids):
            self.banco.table("precos").update({"ate": ate.isoformat()}).in_("catalogo_id", lote).eq("praca", praca).is_("ate", "null").execute()

    def abrir_precos(self, pares, dia, praca):
        for lote in _em_lotes(pares):
            linhas = [{"catalogo_id": i, "praca": praca, "desde": dia.isoformat(), "preco_varejo": item["preco_varejo"],
                       "preco_atacado": item["preco_atacado"], "quantidade_atacado": item["quantidade_atacado"]} for i, item in lote]
            self.banco.table("precos").upsert(linhas, on_conflict="catalogo_id,praca,desde").execute()

    def corrigir_precos(self, pares, dia, praca):
        for i, item in pares:
            self.banco.table("precos").update({"preco_varejo": item["preco_varejo"], "preco_atacado": item["preco_atacado"],
                                               "quantidade_atacado": item["quantidade_atacado"]}) \
                .eq("catalogo_id", i).eq("praca", praca).eq("desde", dia.isoformat()).execute()

    def registrar_coleta(self, dia, mercado, praca, status, itens, erro=None):
        linha = {"dia": dia.isoformat(), "supermercado": mercado, "praca": praca, "status": status, "itens": itens, "erro": erro[:500] if erro else None}
        # uma falha nunca sobrescreve uma coleta 'ok' do mesmo dia (carga repetida à mão)
        self.banco.table("coletas").upsert(linha, on_conflict="dia,supermercado,praca", ignore_duplicates=(status != "ok")).execute()

    def ultimos_dias_ok(self, mercado, praca, quantos):
        linhas = (self.banco.table("coletas").select("dia").eq("supermercado", mercado).eq("praca", praca).eq("status", "ok")
                  .order("dia", desc=True).limit(quantos).execute().data)
        return [_data(l["dia"]) for l in linhas]

    def inativar(self, inativos, praca):
        """Marca como saídos e fecha o intervalo de preço aberto no último dia em que foram vistos."""
        por_dia = {}
        for i, ultimo in inativos:
            por_dia.setdefault(ultimo, []).append(i)
        for ultimo, ids in por_dia.items():
            for lote in _em_lotes(ids):
                self.banco.table("precos").update({"ate": ultimo.isoformat()}).in_("catalogo_id", lote).eq("praca", praca).is_("ate", "null").execute()
        for lote in _em_lotes([i for i, _ in inativos]):
            self.banco.table("catalogo").update({"ativo": False}).in_("id", lote).execute()
