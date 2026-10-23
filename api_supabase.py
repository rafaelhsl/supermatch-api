import sys
import os
import time
import uvicorn
import urllib.request
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

from busca import filtrar, indexar, sem_acento
from Comparador_inteligente import cruzar_multiplos_produtos

# --- 1. CONFIGURAÇÃO SEGURA DO BANCO ---
SUPABASE_URL = "https://gtdvgdfalpsrnefzyfgu.supabase.co"

# A MÁGICA: O Python vai procurar a senha escondida no Servidor da Nuvem!
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") 

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Motor de Comparação de Supermercados API")

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
# Os preços só mudam na carga diária. Por isso o catálogo de cada UF fica em memória por alguns
# minutos e a busca é feita aqui, ignorando acentos. Antes, a busca trocava cada vogal por um
# curinga SQL ("óleo" virava "_l__") e trazia produtos sem relação, como arroz.
CATALOGO_VALIDADE_SEGUNDOS = 600
TAMANHO_PAGINA = 1000  # limite de linhas por consulta do Supabase
_catalogos = {}  # uf -> (momento em que foi carregado, catálogo indexado)

def carregar_catalogo(uf: str):
    agora = time.monotonic()
    guardado = _catalogos.get(uf)
    if guardado and agora - guardado[0] < CATALOGO_VALIDADE_SEGUNDOS:
        return guardado[1]

    produtos, inicio = [], 0
    while True:
        pagina = supabase.table('produtos') \
            .select('*') \
            .in_('uf_cobertura', [uf, 'BR']) \
            .order('id') \
            .range(inicio, inicio + TAMANHO_PAGINA - 1) \
            .execute().data
        produtos.extend(pagina)
        if len(pagina) < TAMANHO_PAGINA:
            break
        inicio += TAMANHO_PAGINA

    catalogo = indexar(produtos)
    _catalogos[uf] = (agora, catalogo)
    print(f"📦 Catálogo de {uf}+BR carregado do banco: {len(produtos)} produtos")
    return catalogo

@app.get("/saude")
def saude():
    # Resposta leve, sem banco. Serve para acordar o servidor: o plano gratuito do Render
    # "dorme" após 15 minutos sem uso e a primeira chamada depois disso leva cerca de 1 minuto.
    return {"status": "ok"}

@app.get("/comparar")
def buscar_e_comparar(cep: str, item: str):
    print(f"\n📡 API Recebeu pedido ULTRA-RÁPIDO! Item: '{item}' | CEP: '{cep}'")

    uf_cliente = obter_uf_pelo_cep(cep)

    produtos_encontrados = filtrar(carregar_catalogo(uf_cliente), item)
    print(f"🔍 '{item}': {len(produtos_encontrados)} produtos encontrados")

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
        "carrinho_comparativo": relatorio_final
    }

if __name__ == "__main__":
    print("🚀 API de Alta Velocidade Iniciada!")
    uvicorn.run(app, host="127.0.0.1", port=8000)
