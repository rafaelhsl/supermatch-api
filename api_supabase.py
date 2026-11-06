import sys
import os
import time
import threading
import uvicorn
import urllib.request
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

from busca import buscar_detalhado, indexar, sem_acento
from Comparador_inteligente import cruzar_multiplos_produtos

# --- 1. CONFIGURAÇÃO SEGURA DO BANCO ---
SUPABASE_URL = "https://gtdvgdfalpsrnefzyfgu.supabase.co"

# A MÁGICA: O Python vai procurar a senha escondida no Servidor da Nuvem!
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") 

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@asynccontextmanager
async def ciclo_de_vida(_app):
    aquecer_catalogo(UF_DA_REGIAO)           # o servidor acabou de acordar: já começa a carregar o catálogo
    yield


app = FastAPI(title="Motor de Comparação de Supermercados API", lifespan=ciclo_de_vida)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def obter_uf_pelo_cep(cep: str):
    try:
        url = f"https://viacep.com.br/ws/{cep}/json/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            dados = json.loads(response.read().decode())
            return dados.get("uf", "BR")
    except:
        return "BR"

# --- 2. CATÁLOGO EM MEMÓRIA ---
# Os preços só mudam na carga diária. Por isso o catálogo de cada UF fica em memória e a busca é feita aqui, ignorando
# acentos. Antes, a busca trocava cada vogal por um curinga SQL ("óleo" virava "_l__") e trazia produtos sem relação.
#
# Com cerca de 8 mil produtos, baixar o catálogo leva uns 6 s. Por isso:
# - depois de CATALOGO_VALIDADE_SEGUNDOS a busca responde NA HORA com o catálogo que tem e a atualização roda em segundo
#   plano (só a primeira busca depois de o servidor acordar, sem catálogo nenhum, precisa esperar);
# - só uma atualização por UF acontece por vez, mesmo com várias buscas chegando juntas;
# - se a atualização falhar, o catálogo anterior continua valendo;
# - o servidor carrega o catálogo ao iniciar e quando o site chama /saude, então a primeira busca já o encontra pronto.
CATALOGO_VALIDADE_SEGUNDOS = 600
TAMANHO_PAGINA = 1000  # limite de linhas por consulta do Supabase
UF_DA_REGIAO = "MG"    # Belo Horizonte e região metropolitana
# Só as colunas que a API devolve ou usa na busca e no agrupamento (fica de fora `texto_original`, o texto bruto do robô).
COLUNAS_DO_CATALOGO = ("id,supermercado,nome,marca,ean,categoria,id_origem,termo,"
                       "preco_varejo,preco_atacado,quantidade_atacado,uf_cobertura,atualizado_em")
_catalogos = {}   # uf -> (momento em que foi carregado, catálogo indexado)
_travas = {}      # uf -> trava: uma atualização por vez
_travas_das_travas = threading.Lock()


def _trava_da_uf(uf: str):
    with _travas_das_travas:
        return _travas.setdefault(uf, threading.Lock())


def _vencido(guardado) -> bool:
    return time.monotonic() - guardado[0] >= CATALOGO_VALIDADE_SEGUNDOS


def baixar_catalogo(uf: str):
    """Lê do banco todos os produtos da UF (e do Brasil todo), de 1000 em 1000, e devolve o catálogo indexado."""
    produtos, inicio = [], 0
    while True:
        pagina = supabase.table('produtos') \
            .select(COLUNAS_DO_CATALOGO) \
            .in_('uf_cobertura', [uf, 'BR']) \
            .order('id') \
            .range(inicio, inicio + TAMANHO_PAGINA - 1) \
            .execute().data
        produtos.extend(pagina)
        if len(pagina) < TAMANHO_PAGINA:
            break
        inicio += TAMANHO_PAGINA
    print(f"📦 Catálogo de {uf}+BR carregado do banco: {len(produtos)} produtos")
    return indexar(produtos)


def atualizar_catalogo(uf: str):
    """Baixa e guarda o catálogo. Quem chega durante uma atualização espera por ela e usa o resultado, em vez de baixar de novo."""
    with _trava_da_uf(uf):
        guardado = _catalogos.get(uf)
        if guardado and not _vencido(guardado):
            return guardado[1]
        catalogo = baixar_catalogo(uf)
        _catalogos[uf] = (time.monotonic(), catalogo)
        return catalogo


def atualizar_em_segundo_plano(uf: str):
    if _trava_da_uf(uf).locked():     # já há uma atualização em andamento
        return

    def trabalho():
        try:
            atualizar_catalogo(uf)
        except Exception as erro:
            print(f"⚠️ Não consegui atualizar o catálogo de {uf}: {erro!r}. Sigo com o catálogo anterior.")

    threading.Thread(target=trabalho, daemon=True).start()


def carregar_catalogo(uf: str):
    guardado = _catalogos.get(uf)
    if guardado is None:
        return atualizar_catalogo(uf)         # primeira vez: não há o que mostrar, então espera
    if _vencido(guardado):
        atualizar_em_segundo_plano(uf)        # responde já com o catálogo que tem
    return guardado[1]


def aquecer_catalogo(uf: str):
    """Deixa o catálogo carregando em segundo plano, se ainda não existe ou já venceu."""
    guardado = _catalogos.get(uf)
    if guardado is None or _vencido(guardado):
        atualizar_em_segundo_plano(uf)


@app.get("/saude")
def saude():
    # Resposta leve, sem esperar o banco. Serve para acordar o servidor: o plano gratuito do Render "dorme" após
    # 15 minutos sem uso e a primeira chamada depois disso leva cerca de 1 minuto. Aproveita para já deixar o catálogo
    # carregando, assim a primeira busca depois de abrir o site não paga o download.
    aquecer_catalogo(UF_DA_REGIAO)
    return {"status": "ok"}

@app.get("/comparar")
def buscar_e_comparar(cep: str, item: str, todos: bool = False):
    print(f"\n📡 API Recebeu pedido ULTRA-RÁPIDO! Item: '{item}' | CEP: '{cep}'")

    uf_cliente = obter_uf_pelo_cep(cep)

    # Produtos "principais" da busca; os que só citam a palavra no meio do nome ficam de fora quando há principais
    # suficientes (ver busca.py), a menos que se peça `todos=1`.
    busca = buscar_detalhado(carregar_catalogo(uf_cliente), item, incluir_so_citam=todos)
    produtos_encontrados = busca.produtos
    ocultos = busca.ocultos_so_citam + busca.ocultos_pelo_limite
    print(f"🔍 '{item}': {len(produtos_encontrados)} produtos encontrados ({ocultos} ficaram de fora)")

    relatorio_final = cruzar_multiplos_produtos([produtos_encontrados])
    # Grupos vendidos em mais mercados primeiro (são os que permitem comparar), depois ordem alfabética
    relatorio_final.sort(key=lambda g: (-len(g['opcoes_de_compra']), sem_acento(g['produto_base'])))
    mercados_acionados = list(set([p['supermercado'] for p in produtos_encontrados]))
    
    return {
        "status": "sucesso",
        "cep": cep,
        "uf": uf_cliente,
        "item": item,
        "mercados_consultados": mercados_acionados,
        "ocultos": ocultos,
        "ocultos_so_citam": busca.ocultos_so_citam,
        "ocultos_pelo_limite": busca.ocultos_pelo_limite,
        "so_citam_por_mercado": busca.so_citam_por_mercado,
        "carrinho_comparativo": relatorio_final
    }

if __name__ == "__main__":
    print("🚀 API de Alta Velocidade Iniciada!")
    uvicorn.run(app, host="127.0.0.1", port=8000)
