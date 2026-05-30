import asyncio
import sys
import os
import warnings
from supabase import create_client, Client

# Importando os robôs que você já criou
from Scraper_Apoio_v2 import buscar_no_apoio
from Scraper_Atacadao_v2 import buscar_no_atacadao

# --- 1. CONFIGURAÇÃO DO SEU BANCO DE DADOS SUPABASE ---
# Usando a URL exata que você me passou
SUPABASE_URL = "https://gtdvgdfalpsrnefzyfgu.supabase.co"
# O Python vai puxar a chave secreta direto do GitHub Actions!
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") 

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) 

# Conectando ao Banco...
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# --------------------------------------------------------

# Lista de categorias básicas para o nosso teste de "Carga Inicial"
ITENS_PARA_BUSCAR =["Arroz", "Feijao", "Oleo", "Cafe", "Manteiga"]
CEP_BASE = "32607600" # O CEP de Betim que atende o Apoio

async def popular_banco():
    print("🚀 INICIANDO O ROBÔ DE MADRUGADA (ALIMENTADOR DO BANCO)...")
    print("🧹 Limpando o banco de dados antigo para não duplicar...")
    try:
        # Apaga os dados antigos para termos apenas preços de hoje
        supabase.table('produtos').delete().neq('supermercado', 'nada').execute()
    except Exception as e:
        print("Nota: O banco já estava vazio ou erro ao limpar.")

    for item in ITENS_PARA_BUSCAR:
        print(f"\n🛒 Extraindo '{item}' dos supermercados...")
        
        # Liga os dois robôs ao mesmo tempo para esse item
        resultados_apoio, resultados_atacadao = await asyncio.gather(
            buscar_no_apoio(cep_usuario=CEP_BASE, item_usuario=item),
            buscar_no_atacadao(cep_usuario=CEP_BASE, item_usuario=item)
        )
        
        # --- INSERINDO OS DADOS DO APOIO NO BANCO ---
        if resultados_apoio:
            for produto in resultados_apoio:
                # Nosso SQL exige saber a região. Apoio é MG.
                produto['uf_cobertura'] = 'MG' 
                supabase.table('produtos').insert(produto).execute()
            print(f"   ✅ Salvos {len(resultados_apoio)} itens do Apoio.")
            
        # --- INSERINDO OS DADOS DO ATACADÃO NO BANCO ---
        if resultados_atacadao:
            for produto in resultados_atacadao:
                # Atacadão atende o Brasil todo, então marcamos como BR
                produto['uf_cobertura'] = 'BR'
                supabase.table('produtos').insert(produto).execute()
            print(f"   ✅ Salvos {len(resultados_atacadao)} itens do Atacadão.")

    print("\n🎉 MISSÃO CUMPRIDA! BANCO DE DADOS ATUALIZADO COM OS PREÇOS DE HOJE!")

# Blindagem do Windows para o Playwright
if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    asyncio.run(popular_banco())