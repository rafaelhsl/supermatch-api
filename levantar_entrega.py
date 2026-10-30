"""Levanta, cidade por cidade, quais mercados entregam: roda cada robô com CEPs de amostra e anota o que o site respondeu.

Os sites não têm uma lista pública de onde entregam; a única forma de saber é informar um CEP e ver se o site o
aceita. Por isso o levantamento usa os próprios robôs da carga (com a busca "arroz") em CEPs reais de bairros
diferentes de cada cidade, e guarda o resultado em `dados/entrega_resultados.json`. Dele saem a tabela agregada
`dados/entrega_por_cidade.json` e o documento `docs/entrega_por_cidade.md`.

Uso (a partir da pasta do projeto):
    python levantar_entrega.py                              # todas as cidades e mercados (leva cerca de uma hora)
    python levantar_entrega.py --cidades "Betim,Contagem"   # só algumas cidades
    python levantar_entrega.py --mercados "Atacadao"        # só um mercado
    python levantar_entrega.py --refazer                    # repete também o que já tinha resposta firme
    python levantar_entrega.py --relatorio                  # só refaz a tabela e o documento a partir do que já foi coletado

Rodar de novo repete só o que ficou duvidoso (o site não respondeu, ou o robô se perdeu). Nada disso grava no banco.
"""
import argparse
import asyncio
import contextlib
import io
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PASTA = Path(__file__).parent
AMOSTRAS = PASTA / "dados" / "entrega_amostras.json"
RESULTADOS = PASTA / "dados" / "entrega_resultados.json"
TABELA = PASTA / "dados" / "entrega_por_cidade.json"
DOCUMENTO = PASTA / "docs" / "entrega_por_cidade.md"

ITEM = "arroz"
MERCADOS = ["Apoio Entrega", "Atacadao", "Supernosso", "Super ABC"]
NOME_NA_TELA = {"Apoio Entrega": "Apoio Entrega", "Atacadao": "Atacadão", "Supernosso": "Supernosso", "Super ABC": "Super ABC"}
# O Super ABC não localiza por CEP: o robô escolhe a unidade da cidade do CEP. Basta uma sondagem por cidade.
SO_UMA_POR_CIDADE = {"Super ABC"}
CANAL_APOIO = "15"          # só para a busca depois da localização; a cobertura é decidida antes, pelo CEP
PRAZO_DA_SONDAGEM = 420     # segundos por CEP e mercado, com as repetições do robô


# ============================== a sondagem de um CEP em um mercado ==============================

def robo_do_mercado(mercado):
    """Função que recebe o CEP e roda o robô de verdade, com a repetição automática da carga."""
    from robos_comum import com_novas_tentativas
    if mercado == "Apoio Entrega":
        from Scraper_Apoio_v2 import buscar_no_apoio
        return lambda cep: com_novas_tentativas(buscar_no_apoio, cep_usuario=cep, item_usuario=ITEM, canal_de_vendas=CANAL_APOIO)
    if mercado == "Atacadao":
        from Scraper_Atacadao_v2 import buscar_no_atacadao
        return lambda cep: com_novas_tentativas(buscar_no_atacadao, cep_usuario=cep, item_usuario=ITEM)
    if mercado == "Supernosso":
        from Scraper_Supernosso import buscar_no_supernosso
        return lambda cep: com_novas_tentativas(buscar_no_supernosso, cep_usuario=cep, item_usuario=ITEM)
    if mercado == "Super ABC":
        from Scraper_SuperABC import buscar_na_plataforma_regex
        return lambda cep: com_novas_tentativas(buscar_na_plataforma_regex, "https://superabconline.com.br/", "Super ABC", ITEM, cep_usuario=cep)
    raise SystemExit(f"Mercado desconhecido: {mercado}. Opções: {MERCADOS}")


async def sondar(mercado, cep):
    """Roda o robô e classifica a resposta do site.

    atende        o site aceitou o CEP (e, em geral, a busca trouxe produtos)
    nao_atende    o site disse que não atende, ou o Super ABC não tem unidade na cidade (resposta definitiva)
    nao_confirmou o site não assumiu o CEP depois das repetições (é assim que o Atacadão e o Apoio recusam, mas também
                  pode ser falha do robô: por isso este resultado é repetido numa nova rodada)
    inconclusivo  o robô se perdeu antes de a localização ser decidida
    """
    from robos_comum import BuscaNaoRealizada, FalhaNoRobo, LocalizacaoNaoConfirmada
    inicio = time.time()
    saida = io.StringIO()
    resultado = {"mercado": mercado, "cep": cep}
    try:
        with contextlib.redirect_stdout(saida):
            produtos = await robo_do_mercado(mercado)(cep)
        resultado.update(status="atende", produtos=len(produtos))
    except LocalizacaoNaoConfirmada as erro:
        resultado.update(status="nao_atende" if erro.definitiva else "nao_confirmou", motivo=erro.motivo[:300])
    except FalhaNoRobo as erro:
        # BuscaNaoRealizada e página sem produtos só acontecem depois de a localização ter sido aceita
        confirmou = "confirmada" in saida.getvalue()
        resultado.update(status="atende" if confirmou else "inconclusivo", motivo=erro.motivo[:300],
                         observacao="localização aceita, mas a busca não trouxe produtos" if confirmou else None)
    except Exception as erro:  # o robô quebrou por outro motivo
        resultado.update(status="inconclusivo", motivo=f"erro inesperado: {erro!r}"[:300])
    # Atacadão e Super ABC dizem qual loja/unidade assumiram; interessa guardar
    achou = re.search(r"(?:Localização|Unidade) confirmada:\s*(.+)", saida.getvalue())
    if achou:
        resultado["detalhe"] = achou.group(1).strip()
    resultado["segundos"] = round(time.time() - inicio)
    return resultado


# ============================== o levantamento ==============================

def ler_json(caminho, padrao):
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else padrao


def gravar_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


async def sondar_em_processo(mercado, cep):
    """Cada sondagem roda num processo próprio: um navegador que trava não derruba as outras e some sozinho."""
    processo = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__)), "--sondar", mercado, cep,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=str(PASTA),
    )
    try:
        saida, _ = await asyncio.wait_for(processo.communicate(), timeout=PRAZO_DA_SONDAGEM)
    except asyncio.TimeoutError:
        processo.kill()
        await processo.wait()
        return {"mercado": mercado, "cep": cep, "status": "inconclusivo", "motivo": f"passou de {PRAZO_DA_SONDAGEM} s sem resposta"}
    for linha in reversed(saida.decode("utf-8", "replace").splitlines()):
        if linha.startswith("RESULTADO "):
            return json.loads(linha[len("RESULTADO "):])
    return {"mercado": mercado, "cep": cep, "status": "inconclusivo", "motivo": "o processo terminou sem resposta: " + saida.decode("utf-8", "replace")[-200:]}


async def levantar(args):
    amostras = ler_json(AMOSTRAS, [])
    if not amostras:
        raise SystemExit(f"Não achei as amostras de CEP em {AMOSTRAS}")
    cidades = [c.strip() for c in args.cidades.split(",") if c.strip()] if args.cidades else None
    mercados = [m.strip() for m in args.mercados.split(",") if m.strip()] if args.mercados else MERCADOS
    desconhecidos = [m for m in mercados if m not in MERCADOS]
    if desconhecidos:
        raise SystemExit(f"Mercado desconhecido: {desconhecidos}. Opções: {MERCADOS}")
    if cidades:
        faltando = [c for c in cidades if c not in {a["cidade"] for a in amostras}]
        if faltando:
            raise SystemExit(f"Cidade sem amostra: {faltando}")
        amostras = [a for a in amostras if a["cidade"] in cidades]

    feitos = {(r["mercado"], r["cep"]): r for r in ler_json(RESULTADOS, [])}
    trava = asyncio.Lock()

    async def fila(mercado):
        ja_vistas = set()
        for amostra in amostras:
            if mercado in SO_UMA_POR_CIDADE and amostra["cidade"] in ja_vistas:
                continue
            ja_vistas.add(amostra["cidade"])
            anterior = feitos.get((mercado, amostra["cep"]))
            if anterior and anterior["status"] in ("atende", "nao_atende") and not args.refazer:
                continue
            resultado = await sondar_em_processo(mercado, amostra["cep"])
            resultado.update(cidade=amostra["cidade"], bairro=amostra["bairro"], data=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            async with trava:
                feitos[(mercado, amostra["cep"])] = resultado
                gravar_json(RESULTADOS, sorted(feitos.values(), key=lambda r: (r["cidade"], r["cep"], r["mercado"])))
                print(f"{resultado['status']:<13} {mercado:<14} {amostra['cidade']:<22} {amostra['cep']} {amostra['bairro'][:24]:<24} {resultado['segundos'] if 'segundos' in resultado else '?'}s  "
                      f"{(resultado.get('detalhe') or resultado.get('motivo') or '')[:90]}", flush=True)

    await asyncio.gather(*(fila(m) for m in mercados))


# ============================== a tabela e o documento ==============================

def situacao_da_cidade(resultados):
    """Resume as sondagens de uma cidade em um mercado."""
    total = len(resultados)
    atendem = sum(1 for r in resultados if r["status"] == "atende")
    recusam = sum(1 for r in resultados if r["status"] in ("nao_atende", "nao_confirmou"))
    duvida = total - atendem - recusam
    if total == 0:
        situacao = "sem_dados"
    elif atendem == total:
        situacao = "atende"
    elif atendem == 0 and recusam == total:
        situacao = "nao_atende"
    elif atendem and recusam:
        situacao = "parcial"
    else:
        situacao = "duvidoso"
    return {"situacao": situacao, "ceps_que_atendem": atendem, "ceps_testados": total, "ceps_em_duvida": duvida}


def montar_tabela():
    resultados = ler_json(RESULTADOS, [])
    amostras = ler_json(AMOSTRAS, [])
    por_cidade = defaultdict(lambda: defaultdict(list))
    for r in resultados:
        por_cidade[r["cidade"]][r["mercado"]].append(r)
    tabela = {}
    for cidade in dict.fromkeys(a["cidade"] for a in amostras):
        tabela[cidade] = {}
        for mercado in MERCADOS:
            rs = por_cidade[cidade][mercado]
            if mercado in SO_UMA_POR_CIDADE and rs:
                # uma sondagem vale pela cidade inteira
                rs = [{"status": rs[0]["status"]} for _ in amostras if _["cidade"] == cidade]
            tabela[cidade][mercado] = situacao_da_cidade(rs)
    return tabela, resultados, amostras


TEXTO_DA_SITUACAO = {"atende": "Entrega", "nao_atende": "Não entrega", "parcial": "Só em parte", "duvidoso": "A confirmar", "sem_dados": "Sem dados"}


def celula(info):
    if info["situacao"] == "sem_dados":
        return "Sem dados"
    return f"{TEXTO_DA_SITUACAO[info['situacao']]} ({info['ceps_que_atendem']} de {info['ceps_testados']})"


def gerar_documento(tabela, resultados, amostras):
    datas = sorted(r["data"] for r in resultados if r.get("data"))
    periodo = datas[-1][:10] if datas else "sem dados"
    linhas = [
        "# Entrega por cidade",
        "",
        "Quais mercados entregam em cada uma das 14 cidades atendidas pelo Supermatch. Gerado por "
        "[`levantar_entrega.py`](../levantar_entrega.py), que informa CEPs reais de bairros diferentes em cada site "
        "e anota o que ele respondeu. Última sondagem: " + periodo + ". Os sites mudam: para atualizar, rode o script de novo.",
        "",
        "## Resumo",
        "",
        "| Cidade | " + " | ".join(NOME_NA_TELA[m] for m in MERCADOS) + " |",
        "|---|" + "---|" * len(MERCADOS),
    ]
    for cidade, por_mercado in tabela.items():
        linhas.append(f"| {cidade} | " + " | ".join(celula(por_mercado[m]) for m in MERCADOS) + " |")
    linhas += [
        "",
        "Cada célula diz quantos dos CEPs sondados na cidade o site aceitou. **Entrega** é a cidade inteira; "
        "**Só em parte** é quando o site aceita uns bairros e outros não; **A confirmar** é quando a sondagem não "
        "chegou a uma resposta firme (o site não respondeu ou o robô se perdeu) e precisa ser repetida.",
        "",
        "## Como foi feito",
        "",
        "- Para cada CEP e cada mercado, o levantamento roda o **mesmo robô da carga diária** (busca de \"arroz\"). "
        "O robô informa o CEP e só segue se o site o assumir; é essa resposta que vira a tabela. Nada é gravado no banco.",
        "- **Atacadão, Apoio e Supernosso** respondem por CEP. O Supernosso e o Atacadão dizem de forma explícita que não "
        "atendem (\"Ainda não atendemos essa região\"). O Apoio não diz nada: o painel fica girando sem responder. Por isso o "
        "\"não\" do Apoio (**não assumiu o CEP**) só vale depois de repetido; aqui foi repetido três vezes, e uma delas esperando 40 s.",
        "- **Super ABC** não localiza por CEP: o robô escolhe a unidade da cidade do CEP. \"Não entrega\" quer dizer "
        "que **não há unidade do Super ABC naquela cidade**. Uma unidade vizinha pode entregar lá, mas o site não deixa conferir.",
        "- Os CEPs são de ruas e bairros reais (veja abaixo). Cidades grandes têm mais CEPs, porque os sites decidem por CEP e "
        "a resposta pode mudar de bairro para bairro. Em São Joaquim de Bicas e Sarzedo, que têm CEP único, a amostra é o CEP geral e o do Centro.",
        "",
        "## Limites desta tabela",
        "",
        "- **\"Entrega\" quer dizer que o site aceitou o CEP e mostrou produtos com preço.** Não garante frete, horário nem pedido mínimo.",
        "- **A amostra é pequena** (2 a 9 CEPs por cidade). Onde todos os CEPs deram o mesmo resultado, a cidade inteira é tratada igual; "
        "onde deram resultados diferentes (**Só em parte**), só uma amostra maior diria qual bairro entra.",
        "- **O Atacadão decide por bairro, não por cidade.** Em Santa Luzia, Sabará e Ribeirão das Neves, por exemplo, ele atende um "
        "bairro e recusa outro. Ele entrega a partir de três origens: a loja Pampulha, a loja Betim e uma unidade \"Contagem\", que "
        "também atende partes de BH (Barreiro, Alto Barroca, Buritis) e de Betim (Granja Verde).",
        "- Em São Joaquim de Bicas e Sarzedo, a cidade tem CEP único (`-000`), e o Centro tem um CEP de rua. Os resultados diferem entre os dois.",
        "- Os sites mudam. Para conferir de novo, rode `python levantar_entrega.py` (repete só o que ficou duvidoso) ou `--refazer`.",
        "",
        "## Detalhe por CEP",
        "",
    ]
    por_chave = {(r["cep"], r["mercado"]): r for r in resultados}
    for cidade in tabela:
        linhas += [f"### {cidade}", "", "| CEP | Bairro | " + " | ".join(NOME_NA_TELA[m] for m in MERCADOS) + " |", "|---|---|" + "---|" * len(MERCADOS)]
        for a in (x for x in amostras if x["cidade"] == cidade):
            celulas = []
            for m in MERCADOS:
                r = por_chave.get((a["cep"], m))
                if m in SO_UMA_POR_CIDADE:
                    r = next((x for x in resultados if x["cidade"] == cidade and x["mercado"] == m), None)
                    texto = "mesma da cidade" if r and a["cep"] != r["cep"] else None
                else:
                    texto = None
                if texto:
                    celulas.append(texto)
                elif not r:
                    celulas.append("sem dados")
                else:
                    base = {"atende": "entrega", "nao_atende": "não entrega", "nao_confirmou": "não assumiu o CEP", "inconclusivo": "a confirmar"}[r["status"]]
                    extra = ""
                    if r.get("detalhe") and m in ("Atacadao", "Super ABC"):
                        unidade = r["detalhe"].split(", CEP")[0]
                        unidade = re.sub(r"^loja\s+|^ABC Atacado e Varejo\s+", "", unidade)   # Atacadão: "loja Pampulha"; Super ABC: "ABC Atacado e Varejo Betim - Betim / MG"
                        unidade = re.sub(r"\s*/\s*MG$", "", unidade)
                        extra = " (" + unidade[:50] + ")"
                    celulas.append(base + extra)
            cep_fmt = f"{a['cep'][:5]}-{a['cep'][5:]}"
            linhas.append(f"| {cep_fmt} | {a['bairro'] or '(sem bairro)'} | " + " | ".join(celulas) + " |")
        linhas.append("")
    return "\n".join(linhas) + "\n"


def gerar_relatorio():
    tabela, resultados, amostras = montar_tabela()
    gravar_json(TABELA, {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "observacao": "situacao: atende | nao_atende | parcial | duvidoso | sem_dados. Super ABC: unidade na cidade, não CEP.",
        "cidades": tabela,
    })
    DOCUMENTO.write_text(gerar_documento(tabela, resultados, amostras), encoding="utf-8")
    print(f"Tabela em {TABELA.relative_to(PASTA)} e documento em {DOCUMENTO.relative_to(PASTA)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cidades", help="nomes separados por vírgula; vazio = todas")
    parser.add_argument("--mercados", help="nomes separados por vírgula; vazio = todos")
    parser.add_argument("--refazer", action="store_true", help="repete também o que já tinha resposta firme")
    parser.add_argument("--relatorio", action="store_true", help="só refaz a tabela e o documento")
    parser.add_argument("--sondar", nargs=2, metavar=("MERCADO", "CEP"), help="uso interno: sonda um CEP em um mercado")
    args = parser.parse_args()
    if args.sondar:
        print("RESULTADO " + json.dumps(asyncio.run(sondar(*args.sondar)), ensure_ascii=False))
    elif args.relatorio:
        gerar_relatorio()
    else:
        asyncio.run(levantar(args))
        gerar_relatorio()
