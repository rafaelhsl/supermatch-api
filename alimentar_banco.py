import asyncio
import sys
import os
import warnings
from supabase import create_client, Client

# Importando o trio parada dura!
from Scraper_Apoio_v2 import buscar_no_apoio
from Scraper_Atacadao_v2 import buscar_no_atacadao
from Scraper_Supernosso import buscar_no_supernosso
from Scraper_SuperABC import buscar_na_plataforma_regex

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
ITENS_PARA_BUSCAR = ["Arroz", "Feijao", "Oleo", "Cafe", "Manteiga", "Açucar", "Macarrao", "Detergente", "Sabao", "Amaciante", "Higienico"]
CEP_BASE = "32607600" 

async def popular_banco():
    print("🚀 INICIANDO O ROBÔ DE MADRUGADA (AGORA COM 3 MERCADOS!)...")
    print("🧹 Limpando o banco de dados antigo para não duplicar...")
    try:
        supabase.table('produtos').delete().neq('supermercado', 'nada').execute()
    except Exception as e:
        print("Nota: O banco já estava vazio ou erro ao limpar.")

    for item in ITENS_PARA_BUSCAR:
        print(f"\n🛒 Extraindo '{item}' dos supermercados...")
        
        # ⚡ LIGA OS TRÊS ROBÔS AO MESMO TEMPO ⚡
        resultados_apoio, resultados_atacadao, resultados_supernosso, resultados_abc = await asyncio.gather(
            buscar_no_apoio(cep_usuario=CEP_BASE, item_usuario=item),
            buscar_no_atacadao(cep_usuario=CEP_BASE, item_usuario=item),
            buscar_no_supernosso(cep_usuario=CEP_BASE, item_usuario=item),
            buscar_na_plataforma_regex("https://www.superabc.com.br/", "Super ABC", item)
        )
        
        # --- SALVANDO APOIO ---
        if resultados_apoio:
            for produto in resultados_apoio:
                produto['uf_cobertura'] = 'MG' 
                supabase.table('produtos').insert(produto).execute()
            print(f"   ✅ Salvos {len(resultados_apoio)} itens do Apoio.")
            
        # --- SALVANDO ATACADÃO ---
        if resultados_atacadao:
            for produto in resultados_atacadao:
                produto['uf_cobertura'] = 'BR'
                supabase.table('produtos').insert(produto).execute()
            print(f"   ✅ Salvos {len(resultados_atacadao)} itens do Atacadão.")

        # --- SALVANDO SUPERNOSSO ---
        if resultados_supernosso:
            for produto in resultados_supernosso:
                produto['uf_cobertura'] = 'MG' # O Supernosso também é fortíssimo em MG
                supabase.table('produtos').insert(produto).execute()
            print(f"   ✅ Salvos {len(resultados_supernosso)} itens do Supernosso.")

        # --- SALVANDO SUPER ABC ---
        if resultados_abc:
            for produto in resultados_abc:
                produto['uf_cobertura'] = 'MG' 
                supabase.table('produtos').insert(produto).execute()
            print(f"   ✅ Salvos {len(resultados_abc)} itens do Super ABC.")

    print("\n🎉 MISSÃO CUMPRIDA! BANCO DE DADOS ATUALIZADO COM OS 3 MERCADOS!")

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    asyncio.run(popular_banco())
