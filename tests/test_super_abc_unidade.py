"""Testes de `abrir_lista_de_unidades` (Scraper_SuperABC.py), sem navegador e sem rede.

Rodar com:  python tests/test_super_abc_unidade.py

Uma página falsa imita o botão "trocar-loja" e o campo de busca da lista de unidades, para provar
as três situações que importam na carga: o clique funciona, o clique é ignorado (o site ainda não
estava pronto) e a lista abre atrasada (clicar de novo a fecharia).
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from Scraper_SuperABC import abrir_lista_de_unidades, resumo_do_erro  # noqa: E402


class LocalizadorFalso:
    def __init__(self, pagina, tipo):
        self.pagina, self.tipo = pagina, tipo

    @property
    def first(self):
        return self

    async def wait_for(self, state="visible", timeout=0):
        if self.tipo == "campo" and not self.pagina.campo_visivel:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    async def is_visible(self):
        return self.pagina.campo_visivel if self.tipo == "campo" else True

    async def click(self, timeout=0):
        self.pagina.cliques += 1
        n = self.pagina.cliques
        if self.pagina.campo_visivel:           # clicar com a lista aberta a fecha
            self.pagina.campo_visivel = False
        elif n in self.pagina.abre_no_clique:
            self.pagina.campo_visivel = True
        elif n in self.pagina.abre_atrasado_no_clique:
            self.pagina.abre_na_proxima_espera = True


class PaginaFalsa:
    def __init__(self, abre_no_clique=(), abre_atrasado_no_clique=()):
        self.abre_no_clique, self.abre_atrasado_no_clique = set(abre_no_clique), set(abre_atrasado_no_clique)
        self.cliques, self.campo_visivel, self.abre_na_proxima_espera = 0, False, False

    def locator(self, seletor):
        return LocalizadorFalso(self, "botao" if "trocar-loja" in seletor else "campo")

    async def wait_for_timeout(self, ms):
        if self.abre_na_proxima_espera:         # a lista terminou de abrir enquanto o robô esperava
            self.campo_visivel, self.abre_na_proxima_espera = True, False


def rodar(pagina):
    return asyncio.run(abrir_lista_de_unidades(pagina))


def teste_abre_no_primeiro_clique():
    pagina = PaginaFalsa(abre_no_clique=[1])
    rodar(pagina)
    assert pagina.cliques == 1 and pagina.campo_visivel


def teste_clique_ignorado_clica_de_novo():
    pagina = PaginaFalsa(abre_no_clique=[2])
    rodar(pagina)
    assert pagina.cliques == 2 and pagina.campo_visivel


def teste_lista_atrasada_nao_e_fechada():
    # a lista abre depois do tempo de espera do 1º clique: um 2º clique a fecharia
    pagina = PaginaFalsa(abre_atrasado_no_clique=[1])
    rodar(pagina)
    assert pagina.cliques == 1 and pagina.campo_visivel


def teste_desiste_depois_de_tres_cliques():
    pagina = PaginaFalsa()
    try:
        rodar(pagina)
    except TimeoutError as erro:
        assert "Timeout" in str(erro)
    else:
        raise AssertionError("devia falhar quando a lista nunca abre")
    assert pagina.cliques == 3


def teste_resumo_do_erro():
    erro = Exception('Locator.click: Timeout 15000ms exceeded.\nCall log:\n  - waiting for locator("div.trocar-loja").first\n    - element intercepts pointer events')
    texto = resumo_do_erro(erro)
    assert "\n" not in texto and "intercepts pointer events" in texto, texto   # o motivo real sobrevive (antes o log cortava em 90)
    assert len(resumo_do_erro(Exception("x" * 1000))) == 300


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_")]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
