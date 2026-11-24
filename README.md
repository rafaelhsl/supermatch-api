# Supermatch

**Onde a sua compra sai mais barata?** O Supermatch compara a sua lista de compras em quatro supermercados com compra online e entrega em Belo Horizonte e região metropolitana: **Atacadão, Supernosso, Super ABC e Apoio Entrega**.

**Site:** <https://spontaneous-hamster-cd3133.netlify.app/> · [![Testes](https://github.com/rafaelhsl/supermatch-api/actions/workflows/testes.yml/badge.svg)](https://github.com/rafaelhsl/supermatch-api/actions/workflows/testes.yml)

A pessoa informa o CEP, busca os produtos, monta a lista e vê **o total em cada mercado**, quais itens cada um não tem e onde a compra fica mais barata.

## O que o site faz

- **Lista de compras com cupom por mercado:** o total em cada barraca, o mais barato destacado e o que falta em cada uma.
- **Produto exato ou equivalente:** o mesmo produto em mercados diferentes (pelo código de barras) ou "qualquer marca" do mesmo tipo e tamanho (58 famílias, como arroz, leite, óleo, fralda, banana), sempre na dúvida **não junta**.
- **Hortifrúti por quilo:** frutas, verduras e legumes com o preço do quilo ("R$ 3,79/kg") e a lista em quilos.
- **Selo "caiu X% em 7 dias"** a partir do histórico de preços, e **aviso de preço velho** quando uma coleta não veio.
- **Só os mercados que entregam na cidade** da pessoa; avisa quando entregam só em parte dela.
- **Privacidade:** sem cadastro, anúncios nem rastreadores; as fontes são hospedadas no próprio site. O uso é medido só em somas por dia, sem identificar ninguém ([`docs/uso_do_site.md`](docs/uso_do_site.md)). Veja [`docs/privacidade.md`](docs/privacidade.md).

## Como funciona

```
Apoio, Atacadão, Supernosso (API pública de catálogo)  ─┐
                                                         ├─►  carga diária  ─►  Supabase  ─►  API (FastAPI)  ─►  site
Super ABC (sem API: robô com navegador, Playwright)    ─┘   (GitHub Actions,   (produtos +    (Render)         (Netlify,
                                                             07:30 de Brasília)  histórico)                      1 arquivo HTML)
```

- **Coleta** ([`coletor_vtex.py`](coletor_vtex.py), [`Scraper_SuperABC.py`](Scraper_SuperABC.py)): 128 termos (100 de prateleira e 28 de hortifrúti), até 100 produtos por termo e mercado, cerca de 8 mil produtos por dia. Falha de um mercado não apaga os dados dele: ficam os do dia anterior ([`docs/carga_diaria.md`](docs/carga_diaria.md), [`docs/robos.md`](docs/robos.md)).
- **Banco** (Supabase): a foto do dia (`produtos`) e o histórico de preços desde 04/11/2026 ([`docs/banco_de_dados.md`](docs/banco_de_dados.md), [`docs/historico_de_precos.md`](docs/historico_de_precos.md)).
- **API** ([`api_supabase.py`](api_supabase.py)): busca no catálogo em memória, agrupa o mesmo produto de mercados diferentes ([`Comparador_inteligente.py`](Comparador_inteligente.py)) e calcula as famílias de equivalência ([`equivalencia.py`](equivalencia.py)). `GET /comparar?cep=&item=`, `GET /historico?chaves=` e `GET /saude`.
- **Site** ([`site/index.html`](site/index.html)): um arquivo só, sem biblioteca e sem etapa de montagem. As regras do navegador estão em blocos puros, testados em Node ([`docs/site.md`](docs/site.md)). A publicação no Netlify gasta créditos a cada mudança no site: [`docs/netlify.md`](docs/netlify.md).

## Rodando os testes

Os testes não usam rede, banco nem segredo: as APIs e os bancos são de mentira.

```
pip install -r requirements.txt
python tests/test_carga.py                 # um arquivo por vez (cada um se roda sozinho)
node tests/test_queda.js
playwright install chromium                # só para os testes de navegador
python tests/navegador/test_site_hortifruti.py
```

Todos de uma vez, o que o CI faz em cada PR, e como escrever um teste novo: [`docs/testes.md`](docs/testes.md). A `main` só recebe PR com as quatro verificações verdes (Python 3.11, Python do Render, Node 24 e Navegador).

## Pastas

| Pasta | O que tem |
|---|---|
| `site/` | o site publicado (`index.html`, `fonts/`, `og.png`) |
| `dados/` | as listas de produtos da carga, a tabela de entrega por cidade e os lembretes |
| `docs/` | a documentação de cada parte (comece por [`docs/site.md`](docs/site.md) e [`docs/carga_diaria.md`](docs/carga_diaria.md)) |
| `docs/sql/` | os scripts SQL do Supabase (só aditivos e que podem repetir) |
| `tests/` | os testes: Python, Node e `navegador/` (Playwright) |
| `.github/workflows/` | a carga diária, os testes e os lembretes por data |

## Mantido por

Rafael Lima. Dúvidas sobre os dados de quem usa o site: o contato está no aviso de privacidade, no rodapé do próprio site.
