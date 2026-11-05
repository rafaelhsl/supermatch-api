"""Carga diária: coleta os mercados e grava o banco de produtos e o histórico de preços.

Apoio Entrega, Atacadão e Supernosso são coletados pela API pública (coletor_vtex.py, docs/coletor_por_api.md) e o Super ABC,
que não tem API aberta, pelo robô (Scraper_SuperABC.py), com os 100 termos de dados/lista_de_produtos.json.

Quando uma parte da coleta falha, a carga não perde tudo nem grava dado duvidoso:
- falharam poucos termos (até 10%): grava o que veio, mantém as linhas antigas dos termos que falharam e registra a coleta como
  "parcial" no histórico (produto que não apareceu não conta como "saiu");
- falharam muitos, ou nada veio: não grava, mantém os dados antigos do mercado e a execução fica vermelha.

COLETA_POR_API=0 volta ao modo antigo (robôs com os 11 itens de ITENS_PARA_BUSCAR em todos os mercados, tudo ou nada).
"""
import asyncio
import math
import sys
import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from supabase import create_client

# Importando o trio parada dura!
from Scraper_Apoio_v2 import buscar_no_apoio
from Scraper_Atacadao_v2 import buscar_no_atacadao
from Scraper_Supernosso import buscar_no_supernosso
from Scraper_SuperABC import buscar_na_plataforma_regex
from robos_comum import FalhaNoRobo, com_novas_tentativas
from historico import RepositorioSupabase, hoje_em_brasilia, normalizar_nome, registrar_falha, registrar_mercado
import coletor_vtex

# --- 1. CONFIGURAÇÃO DO SEU BANCO DE DADOS SUPABASE ---
# Usando a URL exata que você me passou
SUPABASE_URL = "https://gtdvgdfalpsrnefzyfgu.supabase.co"
# O Python vai puxar a chave secreta direto do GitHub Actions!
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
# SEM_GRAVAR=1 roda a coleta e mostra o resumo sem tocar no banco (e sem precisar da chave)
GRAVAR = os.environ.get("SEM_GRAVAR") != "1"
# COLETA_POR_API=0 volta ao modo antigo, só com robôs (ver o topo deste arquivo)
COLETA_POR_API = os.environ.get("COLETA_POR_API", "1") != "0"
# --------------------------------------------------------

# A lista antiga de 11 itens: só o modo antigo (COLETA_POR_API=0) a usa.
ITENS_PARA_BUSCAR = ["Arroz", "Feijao", "Oleo", "Cafe", "Manteiga", "Açucar", "Macarrao", "Detergente", "Sabao", "Amaciante", "Higienico"]
CEP_BASE = "32607600"
# Praça (região) do histórico de preços: a do CEP_BASE. Outra cidade pede outro CEP_BASE e outra praça.
PRACA_BASE = "betim"
# Canal de vendas do Apoio para o CEP_BASE (Betim). Verificado em 28/10/2026: no canal 15 os produtos têm preço e
# estoque; no canal 1 (o padrão, onde a sessão do GitHub às vezes fica presa) todos aparecem como indisponíveis.
# Para outro CEP o canal é outro (BH Centro apareceu como 8) e precisa ser descoberto antes de usar.
CANAL_APOIO_BASE = "15"

# Nome do mercado (como é gravado na coluna `supermercado`) -> UF que ele atende.
MERCADOS = {"Apoio Entrega": "MG", "Atacadao": "BR", "Supernosso": "MG", "Super ABC": "MG"}
MERCADOS_PELA_API = ("Apoio Entrega", "Atacadao", "Supernosso")
TAMANHO_LOTE = 200
# Quantos navegadores do Super ABC ao mesmo tempo na lista de 100 termos (com 4 de uma vez o site ficava instável).
ROBOS_PARALELOS = int(os.environ.get("ROBOS_PARALELOS", "3"))
# Até esta fração dos termos pode falhar e a carga ainda grava o que veio (coleta "parcial").
TOLERANCIA_DE_TERMOS_COM_FALHA = 0.10

# Colunas da tabela `produtos`. As novas vêm de docs/sql/colunas_do_coletor.sql.
COLUNAS_BASE = ("supermercado", "nome", "preco_varejo", "preco_atacado", "quantidade_atacado", "uf_cobertura", "texto_original")
COLUNAS_NOVAS = ("ean", "marca", "categoria", "id_origem", "termo")

# Um robô por mercado, já com repetição automática para falha passageira (site lento).
ROBOS = {
    "Apoio Entrega": lambda item: com_novas_tentativas(buscar_no_apoio, cep_usuario=CEP_BASE, item_usuario=item, canal_de_vendas=CANAL_APOIO_BASE),
    "Atacadao": lambda item: com_novas_tentativas(buscar_no_atacadao, cep_usuario=CEP_BASE, item_usuario=item),
    "Supernosso": lambda item: com_novas_tentativas(buscar_no_supernosso, cep_usuario=CEP_BASE, item_usuario=item),
    "Super ABC": lambda item: com_novas_tentativas(buscar_na_plataforma_regex, "https://superabconline.com.br/", "Super ABC", item, cep_usuario=CEP_BASE, tentativas=3),
}

# SO_MERCADOS="Apoio Entrega" (vários, separados por vírgula) roda a carga só desses mercados; vazio = todos.
# Serve para refazer um mercado que falhou sem mexer nos outros.
ESCOLHIDOS = [nome.strip() for nome in os.environ.get("SO_MERCADOS", "").split(",") if nome.strip()]


def mercados_da_carga():
    desconhecidos = [nome for nome in ESCOLHIDOS if nome not in MERCADOS]
    if desconhecidos:
        sys.exit(f"SO_MERCADOS tem mercado desconhecido: {desconhecidos}. Opções: {list(MERCADOS)}")
    return {mercado: uf for mercado, uf in MERCADOS.items() if not ESCOLHIDOS or mercado in ESCOLHIDOS}


# ============================== o que cada mercado coletou ==============================

@dataclass
class Coleta:
    """O resultado da coleta de um mercado: as linhas e quais termos falharam (termo sem resultado legítimo não é falha)."""
    mercado: str
    produtos: list = field(default_factory=list)
    termos_total: int = 0
    termos_falhos: list = field(default_factory=list)      # nomes dos termos
    motivos: list = field(default_factory=list)            # "'termo': motivo"
    tolerancia: float = TOLERANCIA_DE_TERMOS_COM_FALHA     # 0 = tudo ou nada
    status: str = ""


def avaliar_coleta(produtos, termos_total, termos_falhos, tolerancia=TOLERANCIA_DE_TERMOS_COM_FALHA):
    """"ok", "parcial" (grava o que veio) ou "falhou" (não grava).

    Nada coletado é sempre "falhou". Com tolerância, aceita falhar até essa fração dos termos (e sempre pelo menos 1).
    """
    if not produtos:
        return "falhou"
    if not termos_falhos:
        return "ok"
    if not tolerancia:
        return "falhou"
    return "parcial" if len(termos_falhos) <= max(1, math.floor(tolerancia * termos_total)) else "falhou"


def coletas_pela_api(mercados, termos, teto, http=None, baixadores=None):
    """Coleta os mercados pela API pública. -> {mercado: Coleta}. Bloqueante (rodar numa linha de execução à parte)."""
    http = http or coletor_vtex.ClienteHttp()

    def progresso(mercado, termo, brutos, escolhidas):
        print(f"   ✅ {mercado} '{termo['termo']}': {len(escolhidas)} itens ({brutos} lidos)", flush=True)

    resultado, erros = coletor_vtex.coletar(http, list(mercados), termos, teto, progresso, baixadores)
    coletas = {}
    for mercado in mercados:
        coleta = Coleta(mercado, termos_total=len(termos))
        vistos = set()
        for linhas in resultado[mercado].values():
            for linha in linhas:
                if linha["id_origem"] not in vistos:       # o mesmo produto pode aparecer em dois termos
                    vistos.add(linha["id_origem"])
                    coleta.produtos.append(linha)
        for m, termo, erro in erros:
            if m == mercado:
                print(f"   ⛔ {mercado} '{termo}': {erro}", flush=True)
                coleta.termos_falhos.append(termo)
                coleta.motivos.append(f"'{termo}': {erro}")
        coletas[mercado] = coleta
    return coletas


async def coletar_por_robo(mercado, alvos, paralelo=1, tolerancia=TOLERANCIA_DE_TERMOS_COM_FALHA):
    """Coleta um mercado pelo robô. alvos: [(termo, texto da busca, regras do termo ou None)].

    Com regras (a lista de 100 termos), o resultado passa pelo mesmo filtro do coletor por API (nome e categorias proibidas).
    Busca que o site responde sem nenhum produto devolve [] e não é falha; só o robô que levanta erro conta como termo falho.
    """
    uf = MERCADOS[mercado]
    semaforo = asyncio.Semaphore(paralelo)
    coleta = Coleta(mercado, termos_total=len(alvos), tolerancia=tolerancia)

    async def um(termo, texto, regras):
        async with semaforo:
            try:
                return termo, regras, await ROBOS[mercado](texto), None
            except Exception as erro:
                motivo = erro.motivo if isinstance(erro, FalhaNoRobo) else f"erro inesperado: {erro!r}"
                print(f"   ⛔ {mercado} '{texto}': {motivo}", flush=True)
                return termo, regras, None, motivo

    vistos = set()
    for termo, regras, produtos, motivo in await asyncio.gather(*(um(*alvo) for alvo in alvos)):
        if produtos is None:
            coleta.termos_falhos.append(termo)
            coleta.motivos.append(f"'{termo}': {motivo}")
            continue
        aproveitados = 0
        for produto in produtos:
            nome = normalizar_nome(produto.get("nome", ""))
            if nome in vistos or (regras is not None and not coletor_vtex.passa_no_filtro(produto, regras)):
                continue
            vistos.add(nome)
            linha = dict(produto)
            linha["supermercado"] = mercado
            linha["uf_cobertura"] = uf
            linha["termo"] = termo if regras is not None else None
            coleta.produtos.append(linha)
            aproveitados += 1
        print(f"   ✅ {mercado} '{termo}': {aproveitados} itens ({len(produtos)} lidos)", flush=True)
    return coleta


# ============================== o banco ==============================

def colunas_novas_existem(banco):
    """A tabela `produtos` já tem as colunas de docs/sql/colunas_do_coletor.sql? Outro erro (rede, chave) não é resposta: sobe."""
    try:
        banco.table("produtos").select(",".join(COLUNAS_NOVAS)).limit(1).execute()
        return True
    except Exception as erro:
        if "does not exist" in str(erro) or getattr(erro, "code", "") in ("42703", "PGRST204"):
            return False
        raise


def para_o_banco(produto, com_colunas_novas=True):
    """A linha de `produtos`: só as colunas que existem, com os valores que o banco exige (NOT NULL)."""
    linha = {coluna: produto.get(coluna) for coluna in COLUNAS_BASE}
    linha["preco_atacado"] = produto.get("preco_atacado") if produto.get("preco_atacado") is not None else produto.get("preco_varejo")
    linha["quantidade_atacado"] = int(produto.get("quantidade_atacado") or 1)
    if com_colunas_novas:
        linha.update({coluna: produto.get(coluna) for coluna in COLUNAS_NOVAS})
    return linha


def filtro_termos_mantidos(termos):
    """Filtro do PostgREST: linhas sem termo (da carga antiga) ou de qualquer termo fora dos que falharam."""
    lista = ",".join('"' + str(t).replace('"', "") + '"' for t in termos)
    return f"termo.is.null,termo.not.in.({lista})"


def gravar_mercado(banco, mercado, produtos, inicio, com_colunas_novas=True, termos_mantidos=()):
    """Grava os produtos novos do mercado e só depois apaga os antigos dele.

    As linhas antigas dos `termos_mantidos` (os que falharam nesta carga) ficam. Sem as colunas novas não há como saber o termo
    de uma linha antiga, então nada é mantido por termo (a carga parcial nem chega aqui nesse caso).
    Se a gravação falhar no meio, os dados antigos continuam lá (pode haver duplicados até a próxima carga).
    """
    linhas = [para_o_banco(p, com_colunas_novas) for p in produtos]
    for i in range(0, len(linhas), TAMANHO_LOTE):
        banco.table('produtos').insert(linhas[i:i + TAMANHO_LOTE]).execute()
    apagar = banco.table('produtos').delete().eq('supermercado', mercado).lt('atualizado_em', inicio)
    if termos_mantidos and com_colunas_novas:
        apagar = apagar.or_(filtro_termos_mantidos(termos_mantidos))
    apagar.execute()


def anotar_historico(banco, mercado, dia, produtos=None, falha=None, status="ok"):
    """Grava a coleta no histórico de preços (docs/historico_de_precos.md). Nunca derruba a carga: se der erro, vira aviso.

    Com `produtos`, registra a coleta do mercado (status "ok" ou "parcial"). Com `falha`, só anota que a coleta daquele dia falhou.
    """
    try:
        repositorio = RepositorioSupabase(banco)
        if falha is None:
            resumo = registrar_mercado(repositorio, mercado, produtos, dia, PRACA_BASE, status)
            print(f"   🗂️  Histórico do {mercado}: {resumo.linha()}")
        else:
            registrar_falha(repositorio, mercado, falha, dia, PRACA_BASE)
    except Exception as erro:
        print(f"::warning title=Histórico de preços não gravado ({mercado})::{erro!r}")


def gravar_coletas(banco, coletas, inicio, dia):
    """Grava cada mercado conforme o status da coleta. -> {mercado: situação}, com situação em "atualizado", "parcial",
    "falhou" ou "nao_gravado" (SEM_GRAVAR)."""
    situacoes = {}
    com_colunas_novas = colunas_novas_existem(banco) if banco is not None else True
    if banco is not None and not com_colunas_novas:
        print("::warning title=Colunas novas ausentes em produtos::rode docs/sql/colunas_do_coletor.sql no Supabase; "
              "enquanto isso a carga grava só as colunas antigas e não aceita coleta parcial.")
    for mercado, coleta in coletas.items():
        status = avaliar_coleta(coleta.produtos, coleta.termos_total, coleta.termos_falhos, coleta.tolerancia)
        if status == "parcial" and banco is not None and not com_colunas_novas:
            status = "falhou"
            coleta.motivos.append("coleta parcial exige as colunas novas de produtos (docs/sql/colunas_do_coletor.sql)")
        coleta.status = status
        if status == "falhou":
            if not coleta.produtos and not coleta.motivos:
                coleta.motivos.append("nenhum produto coletado")
            print(f"⚠️  {mercado}: coleta incompleta, os dados antigos desse mercado foram mantidos.")
            if banco is not None:
                anotar_historico(banco, mercado, dia, falha=coleta.motivos[0] if coleta.motivos else "coleta incompleta")
            situacoes[mercado] = "falhou"
            continue
        if banco is None:
            print(f"   (SEM_GRAVAR) {mercado}: {len(coleta.produtos)} itens não foram gravados.")
            situacoes[mercado] = "nao_gravado"
            continue
        try:
            gravar_mercado(banco, mercado, coleta.produtos, inicio, com_colunas_novas, coleta.termos_falhos)
        except Exception as erro:
            coleta.status = "falhou"
            coleta.motivos.insert(0, f"erro ao gravar no banco: {erro!r}")
            print(f"⛔ {mercado}: {coleta.motivos[0]}")
            anotar_historico(banco, mercado, dia, falha=coleta.motivos[0])
            situacoes[mercado] = "falhou"
            continue
        anotar_historico(banco, mercado, dia, produtos=coleta.produtos, status=status)
        situacoes[mercado] = "parcial" if status == "parcial" else "atualizado"
    return situacoes


# ============================== a carga ==============================

def alvos_da_lista(termos):
    """O robô busca pelo nome do termo; o filtro do termo tira o ruído do resultado."""
    return [(t["termo"], t["termo"], t) for t in termos]


async def coletar_tudo(mercados):
    """{mercado: Coleta}. Pela API, os três mercados com API ao mesmo tempo e o Super ABC por robô; no modo antigo, só robôs."""
    if not COLETA_POR_API:
        print(f"ℹ️  COLETA_POR_API=0: modo antigo, robôs com {len(ITENS_PARA_BUSCAR)} itens, tudo ou nada.")
        alvos = [(item, item, None) for item in ITENS_PARA_BUSCAR]
        feitas = await asyncio.gather(*(coletar_por_robo(m, alvos, paralelo=1, tolerancia=0) for m in mercados))
        return dict(zip(mercados, feitas))

    teto, termos = coletor_vtex.carregar_lista()
    pela_api = [m for m in mercados if m in MERCADOS_PELA_API]
    por_robo = [m for m in mercados if m not in MERCADOS_PELA_API]
    print(f"📋 Lista de {len(termos)} produtos (até {teto} por termo). API: {', '.join(pela_api) or '-'}. Robô: {', '.join(por_robo) or '-'}.")

    tarefas = []
    if pela_api:
        tarefas.append(asyncio.to_thread(coletas_pela_api, pela_api, termos, teto))
    for mercado in por_robo:
        tarefas.append(coletar_por_robo(mercado, alvos_da_lista(termos), paralelo=ROBOS_PARALELOS))
    coletas = {}
    for resultado in await asyncio.gather(*tarefas):
        coletas.update(resultado if isinstance(resultado, dict) else {resultado.mercado: resultado})
    return {m: coletas[m] for m in mercados}


async def popular_banco():
    mercados = mercados_da_carga()
    print(f"🚀 INICIANDO A CARGA ({len(mercados)} MERCADO(S): {', '.join(mercados)})...")
    inicio = datetime.now(timezone.utc).isoformat()
    dia = hoje_em_brasilia()   # o "dia" do histórico de preços

    coletas = await coletar_tudo(mercados)

    # --- GRAVAÇÃO: um mercado por vez ---
    banco = create_client(SUPABASE_URL, SUPABASE_KEY) if GRAVAR else None
    situacoes = gravar_coletas(banco, coletas, inicio, dia)

    print("\n📊 RESUMO DA CARGA")
    texto_da_situacao = {"atualizado": "banco atualizado", "parcial": "banco atualizado (PARCIAL: dados antigos dos termos que falharam mantidos)",
                         "falhou": "NÃO atualizado (dados antigos mantidos)", "nao_gravado": "não gravado (SEM_GRAVAR)"}
    for mercado, coleta in coletas.items():
        print(f"   {mercado}: {len(coleta.produtos)} itens coletados, {len(coleta.termos_falhos)} termo(s) com falha de {coleta.termos_total} - {texto_da_situacao[situacoes[mercado]]}")

    falhou = False
    for mercado, coleta in coletas.items():
        if coleta.status == "falhou":
            falhou = True
            # Aparece em destaque na tela da execução no GitHub
            print(f"::error title=Falha na coleta do {mercado}::{len(coleta.termos_falhos)} termo(s) com falha. Primeira: {(coleta.motivos or ['?'])[0]}")
        elif coleta.status == "parcial":
            print(f"::warning title=Coleta parcial do {mercado}::{len(coleta.termos_falhos)} de {coleta.termos_total} termos falharam ({', '.join(coleta.termos_falhos[:8])}). Primeira falha: {coleta.motivos[0]}")
    if falhou:
        print("\n❌ CARGA INCOMPLETA: veja as falhas acima.")
        return 1

    print(f"\n🎉 MISSÃO CUMPRIDA! {len(mercados)} MERCADO(S) COLETADO(S): {', '.join(mercados)}.")
    return 0

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    sys.exit(asyncio.run(popular_banco()))
