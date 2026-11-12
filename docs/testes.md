# Testes

Os testes ficam em [`tests/`](../tests). Todos são locais: usam bancos e APIs de mentira, não precisam de segredo, de rede nem de navegador.

| Arquivos | O que conferem | Precisa de |
|---|---|---|
| `tests/test_*.py` | a API, a busca, o agrupamento, a equivalência (`equivalencia.py`), a carga, o histórico, o coletor, o Super ABC, a entrega por cidade e os arquivos de bibliotecas | Python e as bibliotecas do `requirements.txt` |
| `tests/test_*.js` | trechos de `site/index.html`: agrupamento por equivalência, lista de compras, identificador dos itens, aviso dos ocultados e entrega por cidade | Node |

## Rodar na sua máquina

Um arquivo de cada vez (o nome diz o assunto):

```
python tests/test_equivalencia.py
node tests/test_lista.js
```

Todos de uma vez, no PowerShell:

```
Get-ChildItem tests/test_*.py | ForEach-Object { python $_.FullName }
Get-ChildItem tests/test_*.js | ForEach-Object { node $_.FullName }
```

Cada arquivo termina com `ok: N …` ou `N verificações passaram` quando tudo passa; se algo falha, mostra onde e sai com erro.

## Rodar no GitHub

O workflow [`testes.yml`](../.github/workflows/testes.yml) roda a suíte inteira **em cada PR e a cada merge na `main`**, e aparece no PR como "Testes". São três rodadas em paralelo:

- **Python 3.11**, a versão da carga diária (`main.yml`);
- **Python do Render**: lê a série do arquivo `.python-version` (hoje 3.14.3, então a série 3.14) e roda na correção mais nova que o GitHub oferece (hoje a 3.14.10, porque ele não tem mais a 3.14.3). Assim o teste acompanha a série de produção quando ela muda, e só difere na correção, não na versão;
- **Node 24**, para os testes do site.

Uma rodada vermelha mostra, na aba do PR, qual arquivo falhou (o log de cada um fica numa seção que se abre). Cada uma é independente: se a 3.11 falhar, a do Render continua e mostra se também falha nela. Um commit novo no mesmo PR cancela a rodada anterior.

## Regras da `main`

Desde 12/11/2026 a `main` tem uma regra de proteção (Settings → Branches), e ela vale **também para o dono do repositório**:

- **Só entra por PR.** Não dá para fazer `git push` direto na `main` (nem editar um arquivo e gravar direto nela pelo site do GitHub), nem forçar o histórico, nem apagá-la.
- **Os três "Testes" precisam estar verdes** (`Python (3.11, a da carga diária)`, `Python (a do Render, lida do .python-version)` e `Node (24)`). Enquanto algum estiver vermelho ou ainda rodando, o botão de merge fica bloqueado.
- **Não exige aprovação de outra pessoa** (o repositório tem um só dono) **nem que o PR esteja atualizado com a `main`**. Isso último é de propósito: com vários PRs abertos ao mesmo tempo, exigir a atualização obrigaria a refazer a rodada a cada merge. Para pegar o problema de juntar tudo, o workflow também roda a cada merge na própria `main`.
- As verificações do Netlify e do Supabase Preview **não** são exigidas: não testam o código.

Duas consequências práticas:

- **Mudou o nome de um job em `testes.yml`?** Atualize também a regra (Settings → Branches → editar a regra da `main` → "Require status checks"). Com o nome antigo ela espera uma verificação que nunca chega, e todo PR fica travado.
- **Emergência** (por exemplo, um teste vermelho que não tem a ver com o que você quer publicar): em Settings → Branches, edite a regra e desmarque "Do not allow bypassing the above settings"; faça o que precisa e **volte a marcar**. Apagar a regra inteira também funciona, mas perde a configuração.

## O que os testes não cobrem

- **O site no navegador.** A tela (clicar, buscar, adicionar à lista, o cupom) é conferida à mão e por scripts de navegador que ainda não estão no repositório. Os testes em Node só cobrem as decisões de `site/index.html` que não dependem da tela.
- **As APIs e o banco de verdade.** Tudo é simulado. Quem prova que a carga funciona é a própria carga diária (e o modo de teste do `main.yml`, que não grava: `gravar=nao`).
- **Os robôs de navegador** (`Scraper_*.py`).

## Acrescentar um teste

Crie `tests/test_alguma_coisa.py` (ou `.js`) seguindo o modelo dos vizinhos: um cabeçalho que diz o que confere e como rodar, e um final que imprime o resultado e sai com erro se algo falhar. O workflow encontra o arquivo sozinho pelo nome (`test_*.py` ou `test_*.js`); não precisa mexer nele.
