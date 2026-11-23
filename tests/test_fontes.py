"""Testes das fontes hospedadas no próprio site (site/fonts/, @font-face de site/index.html, netlify.toml), sem rede.

O site não pede mais as letras ao Google Fonts: o Google deixou de receber o endereço IP de quem visita, e o aviso de privacidade (site/index.html)
foi escrito sobre isso. Estes testes são o que mantém isso verdadeiro.

Rodar com:  python tests/test_fontes.py
"""
import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SITE = RAIZ / "site"
HTML = (SITE / "index.html").read_text(encoding="utf-8")
CSS = HTML[HTML.index("<style>"):HTML.index("</style>")]
FACES = re.findall(r"@font-face \{([^}]*)\}", CSS)
FAMILIAS = {"Hanken Grotesk": "--texto", "Martian Mono": "--mono", "Unbounded": "--titulo"}


def face(corpo):
    familia = re.search(r'font-family: "([^"]+)"', corpo).group(1)
    return {"familia": familia, "peso": int(re.search(r"font-weight: (\d+)", corpo).group(1)), "url": re.search(r"url\(([^)]+)\)", corpo).group(1),
            "exibicao": re.search(r"font-display: (\w+)", corpo).group(1), "faixa": re.search(r"unicode-range: ([^;]+);", corpo).group(1)}


def teste_o_site_nao_fala_mais_com_o_google_fonts():
    for arquivo in (SITE / "index.html", RAIZ / "docs" / "og" / "og.html"):
        texto = arquivo.read_text(encoding="utf-8")
        assert not re.search(r"googleapis|gstatic|fonts\.google", texto), f"{arquivo.name} ainda aponta para o Google Fonts"
    assert not re.search(r"Google", HTML[HTML.index('<dialog id="janelaPrivacidade"'):HTML.index("</dialog>", HTML.index('<dialog id="janelaPrivacidade"'))]), "o aviso não deve citar o Google"


def teste_cada_familia_do_site_tem_as_suas_declaracoes():
    faces = [face(f) for f in FACES]
    assert len(faces) == 10, len(faces)                                              # 5 pesos de Hanken Grotesk, 3 de Martian Mono, 2 de Unbounded
    por_familia = {}
    for f in faces:
        por_familia.setdefault(f["familia"], []).append(f["peso"])
    assert {k: sorted(v) for k, v in por_familia.items()} == {"Hanken Grotesk": [400, 500, 600, 700, 800], "Martian Mono": [400, 500, 600], "Unbounded": [600, 800]}
    for nome, variavel in FAMILIAS.items():
        usada = re.search(rf"{variavel}:\s*\"([^\"]+)\"", CSS)
        assert usada and usada.group(1) == nome, f"{variavel} deveria começar por {nome}: {usada and usada.group(1)}"
    assert all(f["exibicao"] == "swap" for f in faces), "font-display: swap (o texto aparece na hora, com a fonte do sistema, e troca quando a fonte chega)"
    assert len({f["faixa"] for f in faces}) == 1 and "U+0000-00FF" in faces[0]["faixa"], "o mesmo intervalo de caracteres do Google (o do português)"


def teste_todo_peso_pedido_pelo_css_esta_no_intervalo_declarado():
    """Peso fora dos declarados cairia no mais próximo (ou, pior, numa fonte sintetizada)."""
    faces = [face(f) for f in FACES]
    faixas = {n: (min(f["peso"] for f in faces if f["familia"] == n), max(f["peso"] for f in faces if f["familia"] == n)) for n in FAMILIAS}
    pedidos = {}
    for peso, variavel in re.findall(r"font:\s*(?:italic\s+)?(\d{3})\s+[^;]*?var\((--texto|--mono|--titulo)\)", CSS):
        pedidos.setdefault(variavel, set()).add(int(peso))
    for nome, variavel in FAMILIAS.items():
        for peso in pedidos.get(variavel, ()):
            assert faixas[nome][0] <= peso <= faixas[nome][1], f"{nome}: o CSS pede o peso {peso}, fora de {faixas[nome]}"
    assert sum(len(v) for v in pedidos.values()) >= 8, "a varredura do CSS achou poucos pedidos de peso: o padrão mudou?"


def teste_os_arquivos_existem_sao_woff2_e_leves():
    faces = [face(f) for f in FACES]
    arquivos = {f["url"] for f in faces}
    assert len(arquivos) == 3, arquivos                                              # fonte variável: um arquivo por família serve todos os pesos
    total = 0
    for url in arquivos:
        caminho = SITE / url
        assert caminho.is_file(), f"falta {caminho}"
        dados = caminho.read_bytes()
        assert dados[:4] == b"wOF2", f"{url} não é woff2"
        assert re.fullmatch(r"fonts/[a-z-]+-latin-v\d+\.woff2", url), f"{url}: o nome precisa levar o número da versão (o Netlify guarda por um ano)"
        assert 10_000 < len(dados) < 80_000, f"{url}: {len(dados)} bytes"
        total += len(dados)
    assert total < 130_000, f"as três fontes pesam {total / 1024:.0f} KB (eram 109 KB no Google Fonts)"
    por_arquivo = {f["url"]: f["familia"] for f in faces}
    assert len(set(por_arquivo.values())) == 3 and all(len({f["familia"] for f in faces if f["url"] == u}) == 1 for u in arquivos), "um arquivo por família"


def teste_cada_arquivo_traz_a_licenca_da_fonte():
    """As três são OFL: pode redistribuir, desde que a licença vá junto."""
    licencas = sorted((SITE / "fonts").glob("OFL-*.txt"))
    assert [l.name for l in licencas] == ["OFL-Hanken-Grotesk.txt", "OFL-Martian-Mono.txt", "OFL-Unbounded.txt"]
    for licenca in licencas:
        texto = licenca.read_text(encoding="utf-8")
        assert texto.startswith("Copyright") and "SIL OPEN FONT LICENSE Version 1.1" in texto and "Project Authors" in texto, licenca.name


def teste_so_as_duas_fontes_da_primeira_tela_sao_pre_carregadas():
    pre = re.findall(r"<link rel=\"preload\"([^>]*)>", HTML[:HTML.index("<style>")])
    assert len(pre) == 2, pre
    urls = {f["url"] for f in map(face, FACES)}
    for atributos in pre:
        href = re.search(r'href="([^"]+)"', atributos).group(1)
        assert href in urls and (SITE / href).is_file(), f"o preload {href} não é de nenhuma fonte declarada"
        assert 'as="font"' in atributos and 'type="font/woff2"' in atributos
        assert "crossorigin" in atributos, "fonte pré-carregada sem crossorigin é baixada duas vezes"
    assert {re.search(r'href="([^"]+)"', a).group(1) for a in pre} == {"fonts/unbounded-latin-v1.woff2", "fonts/hanken-grotesk-latin-v1.woff2"}


def teste_o_netlify_guarda_as_fontes_por_um_ano():
    config = tomllib.loads((RAIZ / "netlify.toml").read_text(encoding="utf-8"))
    assert config["build"]["publish"] == "site", "as fontes estão em site/fonts: a pasta publicada tem de ser site"
    cabecalhos = [h for h in config.get("headers", []) if h["for"] == "/fonts/*"]
    assert len(cabecalhos) == 1, config.get("headers")
    assert cabecalhos[0]["values"]["Cache-Control"] == "public, max-age=31536000, immutable"
    assert "site/" in config["build"]["ignore"], "uma mudança só em site/fonts/ precisa publicar (a regra de ignorar olha site/)"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
