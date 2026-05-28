import sys
import os
import re
import uvicorn
import urllib.request
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

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

@app.get("/comparar")
async def buscar_e_comparar(cep: str, item: str):
    print(f"\n📡 API Recebeu pedido ULTRA-RÁPIDO! Item: '{item}' | CEP: '{cep}'")
    
    uf_cliente = obter_uf_pelo_cep(cep)
    
    # --- O TRUQUE DO CORINGA PARA IGNORAR ACENTOS ---
    # Troca qualquer vogal (com ou sem acento) pelo coringa "_"
    item_limpo = item.lower()
    item_coringa = re.sub(r'[aáãâeéêiíoóõôuúç]', '_', item_limpo)
    
    print(f"🔍 Buscando no banco pelo padrão: {item_coringa}")
    
    resposta_banco = supabase.table('produtos') \
        .select('*') \
        .ilike('nome', f'%{item_coringa}%') \
        .in_('uf_cobertura', [uf_cliente, 'BR']) \
        .execute()
        
    produtos_encontrados = resposta_banco.data
    print(f"⚡ O banco retornou {len(produtos_encontrados)} produtos em milissegundos!")
    
    relatorio_final = cruzar_multiplos_produtos([produtos_encontrados])
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
