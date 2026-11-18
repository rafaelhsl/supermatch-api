# Hortifrúti (frutas, verduras e legumes)

> **Estado (18/11/2026): etapa 1 pronta; etapa 2 começou pelo SQL.** Existe uma lista de 28 produtos e o coletor sabe lê-los (só leitura), mas **nada de hortifrúti é gravado no banco nem aparece no site ainda**. O motivo está em "Por que ainda não vai para o site". O script que cria a coluna `unidade` está pronto em [`sql/coluna_unidade.sql`](sql/coluna_unidade.sql): quem administra o Supabase o roda no SQL Editor (é seguro e pode repetir); depois vêm o código que a grava e lê, a equivalência e o site.

## O que a etapa 1 entrega

- [`dados/lista_hortifruti.json`](../dados/lista_hortifruti.json): 28 termos de alto giro (banana, maçã, laranja, limão, mamão, melancia, abacaxi, manga, uva, morango, abacate, tomate, batata, cebola, cenoura, alho, pepino, abobrinha, abóbora, chuchu, mandioca, beterraba, pimentão, repolho, brócolis, alface, couve e couve-flor), com os filtros de cada um. **A carga diária não lê esta lista.** Ela lê só `dados/lista_de_produtos.json`, e testes garantem isso.
- O coletor ([`coletor_vtex.py`](../coletor_vtex.py)) aceita o produto de peso variável **só** nos termos que dizem `"aceita_peso_variavel": true`; nos 100 termos da carga diária ele continua descartando.
- Cada linha coletada ganhou dois campos, `unidade` e `multiplicador` (veja "Como o preço vem").

Para ver o que os mercados têm hoje (3 minutos, só leitura, sem segredo e sem banco):

```
python coletor_vtex.py --lista dados/lista_hortifruti.json --saida hortifruti.json
python coletor_vtex.py --lista dados/lista_hortifruti.json --termos "banana,tomate"      # só alguns
```

A última coluna do relatório diz quantos itens do termo têm preço **por quilo** ("5 por kg").

## O que o reconhecimento mostrou (17/11/2026)

Coleta final: **175 itens** em 130 s, 249 chamadas, 0 erros. Os 28 termos trouxeram algo.

| Mercado | Itens | Como vende |
|---|---|---|
| Supernosso | 121 | 50 por quilo, 50 em pacote com o peso no nome, 21 por unidade ou maço |
| Atacadão | 53 | 35 por quilo, 3 em pacote, 5 em saco de 10 a 24 kg, 10 por unidade ou maço |
| Apoio Entrega | 1 | praticamente não vende fresco online (a "batata" dele é salgadinho e congelado) |
| Super ABC | — | a API dele não é aberta; o robô achou tomate, cebola e alface (veja "Super ABC") |

Onde o produto mora: em todos os mercados com API, o fresco está na categoria **Hortifrúti**, e tudo o que está fora dela com nome parecido é processado (chips, molho, conserva, congelado, doce, tempero). Por isso o filtro exige essa categoria.

### Preço por quilo: dá para comparar

Em **20 tipos** a coleta tem preço por quilo nos dois mercados (o menor de cada um):

| Tipo | Atacadão | Supernosso |
|---|---|---|
| banana prata | R$ 3,79 | R$ 7,99 |
| laranja pera | R$ 2,79 | R$ 6,00 |
| manga palmer | R$ 3,99 | R$ 7,99 |
| cebola | R$ 6,99 | R$ 12,99 |
| batata doce | R$ 4,99 | R$ 9,99 |
| tomate italiano | R$ 17,90 | R$ 21,99 |
| limão siciliano | R$ 12,90 | R$ 22,99 |
| pimentão verde | R$ 4,99 | R$ 11,99 |

O Atacadão é quase sempre mais barato; a diferença chega a 2 vezes. Cuidado ao ler a lista completa: alguns "menores preços" do Supernosso são de itens **orgânicos** (a cenoura "R$ 23,98/kg" é orgânica), e orgânico tem de ser uma dimensão própria na equivalência.

## Como o preço vem

O preço publicado pelo mercado tem três significados, e o nome nem sempre diz qual:

| `unidade` | Significa | Exemplo |
|---|---|---|
| `kg` | **O preço é por quilo.** O `multiplicador` é de quanto em quanto se compra (0,5 = meio quilo) | "Tomate Italiano Supernosso 500g", R$ 18,99, `kg`, 0,5: são R$ 18,99 **o quilo**, e cada unidade vendida é meio quilo |
| `un` com peso no nome | O preço é do **pacote** | "Cebola Orgânico do Chico 400g", R$ 7,99 |
| `un` sem peso | Por unidade ou maço | "Alface Crespa Unidade", R$ 5,99 |
| `un` com 10 kg ou mais | Saco de atacado | "Cebola 19kg", R$ 170,80 |

Conferido pelos preços: o tomate italiano do Atacadão sai a R$ 17,90 o quilo, e o do Supernosso, "500g, `kg`, 0,5", a R$ 18,99: o mesmo patamar. Se R$ 18,99 fosse o preço de 500 g, o quilo sairia a R$ 38.

## Por que ainda não vai para o site

Hoje o site mostra o preço como se fosse do produto inteiro. Gravando o hortifrúti agora, ele mostraria **"Tomate Italiano 500g: R$ 18,99" quando esse preço é de 1 kg**: a pessoa leria o dobro do que vai pagar. Antes de gravar, as etapas 2 e 3 precisam existir.

Cuidado ao rodar a carga: `alimentar_banco.py` apaga os produtos antigos do mercado e grava os novos. Uma carga que usasse só a lista de hortifrúti **apagaria os outros produtos** do mercado. Por isso nenhum caminho da carga lê esta lista.

## Filtros da lista

- **Categoria:** `Hortifrúti` (qualquer nível). Fora ficam chips, molhos, conservas, congelados e tempero. A exceção é a **couve-flor**: o Supernosso a guarda em "Visualizar Mais Produtos", e só esse termo aceita essa categoria.
- **Nome:** começa pelo termo (`Banana Prata Quilo`). A abobrinha também aceita "abóbora italiana" (como o Atacadão a chama) e a mandioca, "aipim".
- **Saem pelo nome:** fruta seca (passas), produto picado, ralado, higienizado, descascado ou "processado", cozido no vapor ou a vácuo, frito, em conserva ou em calda, suco, polpa, molho, flocos.
- **Entram de propósito:** orgânico, bandeja, baby e o saco de atacado ("Cebola 19kg"). O produto sem estoque não entra: o coletor só traz o que tem estoque, como sempre.

Outras verduras e ervas ficam para depois (cebolinha, salsinha, coentro, rúcula, agrião, espinafre).

## O que falta (etapas seguintes)

1. **O campo `unidade` no banco.** Script pronto em [`sql/coluna_unidade.sql`](sql/coluna_unidade.sql) (uma coluna vazia, `text`, sem restrição, para a carga não quebrar se um mercado mandar uma unidade que não conhecemos). **Falta rodá-lo no Supabase**; depois, o código que normaliza a unidade (`kg`, `un` ou vazio), a grava e a API a devolve. O histórico de preços não precisa dela: o preço de um produto vendido por quilo continua sendo comparável com o dele mesmo.
2. **Equivalência por variedade e forma de venda.** O preço por quilo vira "1 kg" na chave; o pacote de 400 g continua sendo 400 g. As dimensões que importam: variedade (banana prata, nanica, da terra; tomate italiano, salada, uva; maçã fuji, gala), **orgânico**, tipo de embalagem (a granel, bandeja, pacote), e o nome escrito de dois jeitos ("Limão Tahiti" e "Limão-taiti"). O mapa de entrega por mercado também importa: só Supernosso e Atacadão vendem fresco online.
3. **O site.** Rótulo "R$ 3,79 **/kg**" (e "/maço", "/un"), quantidade da lista em quilos para o que é vendido por quilo, e o aviso quando o preço é por peso aproximado.
4. **Super ABC.** Sem API; o robô achou tomate (longa vida, italiano, grape), cebola (roxa e branca) e alface, em pacotes de peso aproximado ("400 G, 1 a 2 unidades"), então o preço por quilo dele é uma estimativa. Banana fresca não apareceu. Falta ligar o robô a esta lista.

## Limites conhecidos desta etapa

- Perde uns poucos itens frescos que o Supernosso guarda em categoria genérica (um tomate grape orgânico, o alho-poró "Unidade"): a regra por categoria prefere perder 4 itens a deixar entrar tempero e conserva.
- Sem estoque, não há linha: o Supernosso não tinha mamão nem morango fresco no dia (0 itens), e o Atacadão só tinha brócolis congelado.
- Frutas e verduras com o nome começando por outra palavra ("Aipim", "Cheiro-verde") dependem de sinônimos, só feitos para a mandioca e a abobrinha.
- "Alho-poró" entra no termo "alho" (o nome começa por "alho"); a etapa 2 os separa por variedade.

## Testes

`python tests/test_coletor_vtex.py` confere: que o termo comum continua descartando o peso variável e o de hortifrúti o aceita, que a linha traz `unidade` e `multiplicador` (Supernosso, Apoio e Atacadão), 28 termos com 114 nomes reais que entram e 74 que saem (`tests/casos_hortifruti.py`), que a carga diária não lê a lista, e o relatório de itens por quilo.
