import asyncio
import sys
import os
import warnings
from datetime import datetime, timezone
from supabase import create_client

# Importando o trio parada dura!
from Scraper_Apoio_v2 import buscar_no_apoio
from Scraper_Atacadao_v2 import buscar_no_atacadao
from Scraper_Supernosso import buscar_no_supernosso
from Scraper_SuperABC import buscar_na_plataforma_regex
from robos_comum import FalhaNoRobo, com_novas_tentativas

# --- 1. CONFIGURAÇÃO DO SEU BANCO DE DADOS SUPABASE ---
# Usando a URL exata que você me passou
SUPABASE_URL = "https://gtdvgdfalpsrnefzyfgu.supabase.co"
# O Python vai puxar a chave secreta direto do GitHub Actions!
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
# SEM_GRAVAR=1 roda os robôs e mostra o resumo sem tocar no banco (e sem precisar da chave)
GRAVAR = os.environ.get("SEM_GRAVAR") != "1"
# --------------------------------------------------------

# Lista de categorias básicas para o nosso teste de "Carga Inicial"
ITENS_PARA_BUSCAR = ["Arroz", "Feijao", "Oleo", "Cafe", "Manteiga", "Açucar", "Macarrao", "Detergente", "Sabao", "Amaciante", "Higienico"]
CEP_BASE = "32607600"

# Nome do mercado (como é gravado na coluna `supermercado`) -> UF que ele atende.
MERCADOS = {"Apoio Entrega": "MG", "Atacadao": "BR", "Supernosso": "MG", "Super ABC": "MG"}
TAMANHO_LOTE = 200

# Um robô por mercado, já com repetição automática para falha passageira (site lento).
ROBOS = {
    "Apoio Entrega": lambda item: com_novas_tentativas(buscar_no_apoio, cep_usuario=CEP_BASE, item_usuario=item),
    "Atacadao": lambda item: com_novas_tentativas(buscar_no_atacadao, cep_usuario=CEP_BASE, item_usuario=item),
    "Supernosso": lambda item: com_novas_tentativas(buscar_no_supernosso, cep_usuario=CEP_BASE, item_usuario=item),
    "Super ABC": lambda item: com_novas_tentativas(buscar_na_plataforma_regex, "https://superabconline.com.br/", "Super ABC", item, cep_usuario=CEP_BASE),
}

# SO_MERCADOS="Apoio Entrega" (vários, separados por vírgula) roda a carga só desses mercados; vazio = todos.
# Serve para refazer um mercado que falhou sem mexer nos outros.
ESCOLHIDOS = [nome.strip() for nome in os.environ.get("SO_MERCADOS", "").split(",") if nome.strip()]


def mercados_da_carga():
    desconhecidos = [nome for nome in ESCOLHIDOS if nome not in MERCADOS]
    if desconhecidos:
        sys.exit(f"SO_MERCADOS tem mercado desconhecido: {desconhecidos}. Opções: {list(MERCADOS)}")
    return {mercado: uf for mercado, uf in MERCADOS.items() if not ESCOLHIDOS or mercado in ESCOLHIDOS}


def aproveitar(mercado, item, resultado, falhas):
    """Devolve os produtos do robô, ou [] anotando o motivo se ele falhou."""
    if isinstance(resultado, BaseException):
        motivo = resultado.motivo if isinstance(resultado, FalhaNoRobo) else f"erro inesperado: {resultado!r}"
        falhas.setdefault(mercado, []).append(f"'{item}': {motivo}")
        print(f"   ⛔ {mercado}: {motivo}")
        return []
    return resultado


def gravar_mercado(banco, mercado, produtos, inicio):
    """Grava os produtos novos do mercado e só depois apaga os antigos dele.

    Se a gravação falhar no meio, os dados antigos continuam lá (pode haver duplicados até a próxima carga).
    """
    for i in range(0, len(produtos), TAMANHO_LOTE):
        banco.table('produtos').insert(produtos[i:i + TAMANHO_LOTE]).execute()
    banco.table('produtos').delete().eq('supermercado', mercado).lt('atualizado_em', inicio).execute()


async def popular_banco():
    mercados = mercados_da_carga()
    print(f"🚀 INICIANDO O ROBÔ ({len(mercados)} MERCADO(S): {', '.join(mercados)})...")
    inicio = datetime.now(timezone.utc).isoformat()
    coletado = {mercado: [] for mercado in mercados}
    falhas = {}

    for item in ITENS_PARA_BUSCAR:
        print(f"\n🛒 Extraindo '{item}' dos supermercados...")

        # ⚡ LIGA OS ROBÔS DOS MERCADOS ESCOLHIDOS AO MESMO TEMPO ⚡
        # return_exceptions: se um robô falhar, os outros continuam e a falha vai para o resumo.
        resultados = await asyncio.gather(*(ROBOS[mercado](item) for mercado in mercados), return_exceptions=True)

        for (mercado, uf), resultado in zip(mercados.items(), resultados):
            produtos = aproveitar(mercado, item, resultado, falhas)
            for produto in produtos:
                produto['uf_cobertura'] = uf
            coletado[mercado].extend(produtos)
            if produtos:
                print(f"   ✅ Coletados {len(produtos)} itens do {mercado}.")

    # --- GRAVAÇÃO: um mercado por vez, e só os que foram coletados por inteiro ---
    banco = create_client(SUPABASE_URL, SUPABASE_KEY) if GRAVAR else None
    atualizados = []
    for mercado, produtos in coletado.items():
        if not produtos and mercado not in falhas:
            falhas[mercado] = ["nenhum produto coletado"]
        if mercado in falhas:
            print(f"⚠️  {mercado}: coleta incompleta, os dados antigos desse mercado foram mantidos.")
            continue
        if not GRAVAR:
            print(f"   (SEM_GRAVAR) {mercado}: {len(produtos)} itens não foram gravados.")
            continue
        try:
            gravar_mercado(banco, mercado, produtos, inicio)
            atualizados.append(mercado)
        except Exception as erro:
            falhas[mercado] = [f"erro ao gravar no banco: {erro!r}"]
            print(f"⛔ {mercado}: {falhas[mercado][0]}")

    print("\n📊 RESUMO DA CARGA")
    for mercado, produtos in coletado.items():
        if mercado in atualizados:
            situacao = "banco atualizado"
        elif mercado in falhas:
            situacao = "NÃO atualizado (dados antigos mantidos)"
        else:
            situacao = "não gravado (SEM_GRAVAR)"
        print(f"   {mercado}: {len(produtos)} itens coletados, {len(falhas.get(mercado, []))} falha(s) - {situacao}")

    if falhas:
        for mercado, motivos in falhas.items():
            # Aparece em destaque na tela da execução no GitHub
            print(f"::error title=Falha no robô do {mercado}::{len(motivos)} falha(s). Primeira: {motivos[0]}")
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
