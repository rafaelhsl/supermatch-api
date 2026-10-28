"""Pedaços compartilhados pelos robôs: confirmação de localização, CEP e etiquetas de promoção."""
import json
import re
import urllib.request
from urllib.parse import unquote

from busca import sem_acento


class FalhaNoRobo(Exception):
    """Base dos erros em que o robô prefere parar a devolver dados duvidosos."""

    descricao = "falha"

    def __init__(self, mercado, motivo, definitiva=False):
        super().__init__(f"[{mercado}] {self.descricao}: {motivo}")
        self.mercado = mercado
        self.motivo = motivo
        # definitiva=True: repetir não adianta (ex.: o site informa que não atende a região)
        self.definitiva = definitiva


class LocalizacaoNaoConfirmada(FalhaNoRobo):
    """O site não assumiu o CEP pedido: não atende a região ou o robô não conseguiu informá-lo.

    Preços lidos nessa situação seriam de outro lugar. Por isso o robô para e levanta este erro
    em vez de devolver dados de uma localização desconhecida.
    """

    descricao = "localização não confirmada"


class BuscaNaoRealizada(FalhaNoRobo):
    """A busca não abriu a página de resultados: o que está na tela não é o resultado da busca."""

    descricao = "busca não realizada"


async def abortar(browser, mercado, motivo, erro=LocalizacaoNaoConfirmada, definitiva=False):
    """Fecha o navegador e levanta o erro pedido (por padrão, LocalizacaoNaoConfirmada)."""
    print(f"⛔ [{mercado}] {erro.descricao.capitalize()}: {motivo}")
    await browser.close()
    raise erro(mercado, motivo, definitiva=definitiva)


async def exigir_produtos(browser, mercado, produtos, page=None):
    """Uma página de resultados sem nenhum produto com preço quase sempre é página lida cedo demais.

    Trata como falha (passageira, então a carga repete o robô) em vez de devolver uma lista vazia que
    passaria despercebida. Com `page`, a mensagem de falha traz o título, a URL e o início do texto da
    página, para o log do GitHub mostrar o que o robô estava vendo (e salva uma captura de tela).
    """
    if produtos:
        return
    detalhe = ""
    if page is not None:
        try:
            titulo = await page.title()
            texto = await page.evaluate(
                "() => (document.body ? document.body.innerText : '').split(String.fromCharCode(10)).join(' | ').slice(0, 220)"
            )
            await page.screenshot(path=f"debug_sem_produtos_{mercado.replace(' ', '')}.png")
            detalhe = f" [título: {titulo!r}; URL: {page.url[:90]}; texto da página: {texto}]"
        except Exception:
            pass  # o diagnóstico é um extra: nunca pode atrapalhar a falha em si
    await abortar(browser, mercado, "a página de resultados não trouxe nenhum produto com preço" + detalhe, erro=BuscaNaoRealizada)


async def com_novas_tentativas(robo, *args, tentativas=2, **kwargs):
    """Roda o robô e, se falhar por um motivo passageiro, repete com um navegador novo.

    Os sites às vezes ficam lentos (principalmente com vários robôs ao mesmo tempo) e uma etapa se perde.
    Falhas definitivas, como "o site não atende essa região", não são repetidas.
    """
    for numero in range(1, tentativas + 1):
        try:
            return await robo(*args, **kwargs)
        except FalhaNoRobo as erro:
            if erro.definitiva or numero == tentativas:
                raise
            print(f"🔁 [{erro.mercado}] Tentando de novo ({numero + 1}/{tentativas}) depois de: {erro.motivo[:90]}")


def url_mostra_busca(url, item):
    """A URL da página atual contém o termo buscado? (páginas de resultado trazem o termo na URL)"""
    def normalizar(texto):
        # Alguns sites codificam a URL duas vezes ("Açucar" vira "A%25C3%25A7ucar"): decodifica até estabilizar
        for _ in range(3):
            decodificado = unquote(texto)
            if decodificado == texto:
                break
            texto = decodificado
        return re.sub(r"[^a-z0-9]", "", sem_acento(texto))
    return normalizar(item) in normalizar(url)


async def esperar_na_pagina(page, expressao_js, arg=None, segundos=15):
    """Espera `expressao_js(arg)` ficar verdadeira, mesmo que a página recarregue no meio."""
    for _ in range(int(segundos)):
        try:
            if await page.evaluate(expressao_js, arg):
                return True
        except Exception:
            pass  # a página estava recarregando: tenta de novo
        await page.wait_for_timeout(1000)
    return False


async def esperar_recarregamento(page, segundos=10):
    """Espera a página recarregar. Deixa uma marca nela e espera a marca sumir (sinal de que recarregou).

    Alguns sites recarregam a página logo depois de aceitar o CEP; uma busca feita antes disso é apagada.
    Se nada recarregar dentro de `segundos`, segue em frente.
    """
    try:
        await page.evaluate("() => { window.__antes_do_recarregamento = true; }")
    except Exception:
        pass  # a página já estava recarregando
    for _ in range(int(segundos)):
        try:
            if not await page.evaluate("() => window.__antes_do_recarregamento === true"):
                break
        except Exception:
            break  # a página está recarregando
        await page.wait_for_timeout(1000)
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(2000)


def so_digitos(cep):
    return re.sub(r"\D", "", cep or "")


def cep_com_hifen(cep):
    """'32607600' -> '32607-600' (formato do Atacadão e do Apoio)."""
    d = so_digitos(cep)
    return f"{d[:5]}-{d[5:]}"


def cep_com_ponto_e_hifen(cep):
    """'32607600' -> '32.607-600' (formato do Supernosso)."""
    d = so_digitos(cep)
    return f"{d[:2]}.{d[2:5]}-{d[5:]}"


def cidade_do_cep(cep, timeout=5):
    """(cidade, uf) do CEP, pelo ViaCEP com a BrasilAPI de reserva. None se nenhum responder."""
    d = so_digitos(cep)
    fontes = (
        (f"https://viacep.com.br/ws/{d}/json/", "localidade", "uf"),
        (f"https://brasilapi.com.br/api/cep/v1/{d}", "city", "state"),
    )
    for url, campo_cidade, campo_uf in fontes:
        try:
            pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
                dados = json.loads(resposta.read().decode())
            if dados.get(campo_cidade):
                return dados[campo_cidade], dados.get(campo_uf, "")
        except Exception:
            continue
    return None


# Etiquetas que os sites colocam no card do produto antes do nome ("Patrocinado | Leve 4 Pague 3 | café ...").
# Se o robô pegar uma delas como nome, o produto fica com o nome errado.
_ETIQUETA_PROMOCIONAL = re.compile(
    r"^(patrocinado|oferta|promo[cç][aã]o|termina em breve|ver tudo|frete gr[aá]tis"
    r"|leve\s+\d+.*|compre\s+\d+.*|pague\s+\d+.*|\d+\s*%.*|.*\b\d+\s*%\s*off\b.*)$",
    re.IGNORECASE,
)


def eh_etiqueta_promocional(texto):
    return bool(_ETIQUETA_PROMOCIONAL.match((texto or "").strip()))
