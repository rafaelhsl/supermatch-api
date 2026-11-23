"""Testes das tags de pré-visualização do link (Open Graph) de site/index.html e da imagem site/og.png, sem rede.

Quem compartilha o link (WhatsApp, Instagram, Facebook, X, Telegram) mostra o que estas tags dizem; elas precisam de endereços ABSOLUTOS e de uma imagem de verdade.

Rodar com:  python tests/test_og.py
"""
import re
import struct
import sys
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent.parent
HTML = (RAIZ / "site" / "index.html").read_text(encoding="utf-8")
CABECA = HTML[:HTML.index("<style>")]


def meta(propriedade):
    achados = re.findall(r'<meta\s+(?:property|name)="%s"\s+content="([^"]*)"' % re.escape(propriedade), CABECA)
    return achados[0] if len(achados) == 1 else None


def canonico():
    achados = re.findall(r'<link\s+rel="canonical"\s+href="([^"]*)"', CABECA)
    return achados[0] if len(achados) == 1 else None


def tamanho_do_png(caminho):
    dados = caminho.read_bytes()
    assert dados[:8] == b"\x89PNG\r\n\x1a\n", f"{caminho.name} não é um PNG"
    return struct.unpack(">II", dados[16:24])                    # largura e altura, no bloco IHDR


def teste_todas_as_tags_estao_la_uma_vez_so():
    for propriedade in ("og:type", "og:locale", "og:site_name", "og:title", "og:description", "og:url", "og:image", "og:image:type", "og:image:width", "og:image:height",
                        "og:image:alt", "twitter:card"):
        assert meta(propriedade), f"falta (ou repete) a tag {propriedade}"
    assert canonico(), "falta (ou repete) o link canonical"
    assert meta("og:type") == "website" and meta("og:locale") == "pt_BR" and meta("og:site_name") == "Supermatch"
    assert meta("twitter:card") == "summary_large_image"
    assert meta("og:image:type") == "image/png"


def teste_o_titulo_e_a_descricao_dizem_o_mesmo_que_a_pagina():
    titulo = re.search(r"<title>([^<]*)</title>", CABECA).group(1)
    assert meta("og:title") == titulo
    assert 20 <= len(meta("og:title")) <= 70, "título de prévia entre 20 e 70 caracteres (as redes cortam)"
    assert 60 <= len(meta("og:description")) <= 200, "descrição de prévia entre 60 e 200 caracteres"
    assert 20 <= len(meta("og:image:alt")) <= 420 and "Mais barato" in meta("og:image:alt")
    descricao = re.search(r'<meta name="description" content="([^"]*)"', CABECA).group(1)
    assert descricao and "mais barata" in descricao


def teste_os_enderecos_sao_absolutos_e_de_um_endereco_so():
    urls = {"canonical": canonico(), "og:url": meta("og:url"), "og:image": meta("og:image")}
    for nome, url in urls.items():
        partes = urlparse(url)
        assert partes.scheme == "https" and partes.netloc, f"{nome} tem de ser um endereço absoluto (https): {url!r}"
    origens = {urlparse(u).scheme + "://" + urlparse(u).netloc for u in urls.values()}
    assert len(origens) == 1, f"canonical, og:url e og:image têm de ser do mesmo endereço: {origens}"
    assert urls["canonical"] == urls["og:url"] and urlparse(urls["og:url"]).path in ("", "/")
    assert not re.search(r"localhost|127\.0\.0\.1|file:", " ".join(urls.values()))


def teste_a_imagem_existe_no_endereco_publicado_e_tem_o_tamanho_declarado():
    caminho_publicado = urlparse(meta("og:image")).path.lstrip("/")           # o Netlify publica a pasta site/ na raiz (netlify.toml: publish = "site")
    assert 'publish = "site"' in (RAIZ / "netlify.toml").read_text(encoding="utf-8")
    arquivo = RAIZ / "site" / caminho_publicado
    assert arquivo.is_file(), f"a imagem {arquivo} não existe"
    largura, altura = tamanho_do_png(arquivo)
    assert (largura, altura) == (int(meta("og:image:width")), int(meta("og:image:height"))) == (1200, 630), (largura, altura)
    assert arquivo.stat().st_size <= 300 * 1024, f"imagem pesada demais para a prévia do WhatsApp: {arquivo.stat().st_size / 1024:.0f} KB"
    assert arquivo.stat().st_size >= 5 * 1024, "imagem pequena demais: parece vazia"


def teste_a_fonte_da_imagem_esta_no_repositorio():
    """A imagem não é um arquivo solto: dá para refazê-la (docs/og/og.html + docs/og/gerar_og.py)."""
    fonte = (RAIZ / "docs" / "og" / "og.html").read_text(encoding="utf-8")
    assert "Onde a sua compra sai mais barata?" in fonte and "Mais barato" in fonte
    assert not re.search(r"R\$\s*\d", fonte), "a imagem de divulgação não pode ter preço: o site não o confirma"
    assert (RAIZ / "docs" / "og" / "gerar_og.py").is_file()
    for cor in re.findall(r'"(#[0-9a-f]{6})"', re.search(r"const CORES = \[(.*?)\];", fonte, re.S).group(1)):     # as cores dos mercados são as do site
        assert cor in HTML, f"a cor {cor} da imagem não é de nenhum mercado do site"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_") and callable(v)]
    for t in testes:
        t()
    print(f"ok: {len(testes)} testes passaram")
