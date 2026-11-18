# Hortifrúti (frutas, verduras e legumes)

> **Estado (18/11/2026): pronto e ligado à carga diária.** Os 28 produtos de [`dados/lista_hortifruti.json`](../dados/lista_hortifruti.json) são coletados **junto** com os 100 de [`dados/lista_de_produtos.json`](../dados/lista_de_produtos.json), nos 4 mercados, e gravados com a coluna `unidade` (`kg` = o preço é por quilo). A equivalência por variedade e orgânico ([`equivalencia.md`](equivalencia.md)), o "/kg" no site ([`site.md`](site.md#preço-por-quilo-hortifrúti)) e a trava do modo exato (quilo não junta com pacote, [`banco_de_dados.md`](banco_de_dados.md)) vieram antes, de propósito: ligar a coleta sem eles faria o site mostrar "Tomate Italiano 500g: R$ 18,99" quando esse preço é de 1 kg.

## O que entrou na carga

- [`dados/lista_hortifruti.json`](../dados/lista_hortifruti.json): 28 termos de alto giro (banana, maçã, laranja, limão, mamão, melancia, abacaxi, manga, uva, morango, abacate, tomate, batata, cebola, cenoura, alho, pepino, abobrinha, abóbora, chuchu, mandioca, beterraba, pimentão, repolho, brócolis, alface, couve e couve-flor), com os filtros de cada um.
- **Uma coleta só.** `coletor_vtex.carregar_lista_da_carga()` soma as duas listas (128 termos) e é o único caminho que a carga usa. Tem de ser assim: a gravação **apaga os produtos antigos do mercado** e grava os novos, então uma carga que usasse só a lista de hortifrúti apagaria os outros ~2.000 produtos de cada mercado, e uma que usasse só a de produtos apagaria o hortifrúti. Testes travam isso (a carga e a API não leem arquivo de lista; os nomes dos termos não se repetem entre as listas; o teto por termo é o mesmo).
- O coletor ([`coletor_vtex.py`](../coletor_vtex.py)) aceita o produto de peso variável **só** nos termos que dizem `"aceita_peso_variavel": true`; nos 100 termos de prateleira ele continua descartando.
- Cada linha coletada tem `unidade` e `multiplicador` (veja "Como o preço vem"). **Item por quilo não leva faixa de atacado**: a quantidade mínima da faixa seria em quilos ou em múltiplos da compra, e a lista do site conta em quilos; vale o preço do varejo (nos dados de 17/11, nenhum item por quilo tinha faixa).
- Os termos têm tolerância como os outros: até 10% de falha dos 128 termos (12) é coleta "parcial" ([`robos.md`](robos.md#a-carga-e-as-falhas)). Termo sem resultado (o Apoio quase não vende fresco; abobrinha não existe no Super ABC) **não** é falha.

Para ver o que os mercados têm hoje (só leitura, sem segredo e sem banco):

```
python coletor_vtex.py --termos "banana,tomate"                                   # a lista da carga (produtos + hortifrúti), só estes termos
python coletor_vtex.py --lista dados/lista_hortifruti.json --saida hortifruti.json  # só o hortifrúti
```

A última coluna do relatório diz quantos itens do termo têm preço **por quilo** ("5 por kg").

## O que o reconhecimento mostrou (17/11/2026)

Coleta final: **175 itens** em 130 s, 249 chamadas, 0 erros. Os 28 termos trouxeram algo.

| Mercado | Itens | Como vende |
|---|---|---|
| Supernosso | 121 | 50 por quilo, 50 em pacote com o peso no nome, 21 por unidade ou maço |
| Atacadão | 53 | 35 por quilo, 3 em pacote, 5 em saco de 10 a 24 kg, 10 por unidade ou maço |
| Apoio Entrega | 1 | praticamente não vende fresco online (a "batata" dele é salgadinho e congelado) |
| Super ABC | 51 (robô, 18/11) | só em pacote de peso aproximado ou por unidade (veja "Super ABC") |

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

O Atacadão é quase sempre mais barato; a diferença chega a 2 vezes. Cuidado ao ler a lista completa: alguns "menores preços" do Supernosso são de itens **orgânicos** (a cenoura "R$ 23,98/kg" é orgânica), e orgânico é uma dimensão própria na equivalência.

## Como o preço vem

O preço publicado pelo mercado tem três significados, e o nome nem sempre diz qual:

| `unidade` | Significa | Exemplo |
|---|---|---|
| `kg` | **O preço é por quilo.** O `multiplicador` é de quanto em quanto se compra (0,5 = meio quilo) | "Tomate Italiano Supernosso 500g", R$ 18,99, `kg`, 0,5: são R$ 18,99 **o quilo**, e cada unidade vendida é meio quilo |
| `un` com peso no nome | O preço é do **pacote** | "Cebola Orgânico do Chico 400g", R$ 7,99 |
| `un` sem peso | Por unidade ou maço | "Alface Crespa Unidade", R$ 5,99 |
| `un` com 10 kg ou mais | Saco de atacado | "Cebola 19kg", R$ 170,80 |

Conferido pelos preços: o tomate italiano do Atacadão sai a R$ 17,90 o quilo, e o do Supernosso, "500g, `kg`, 0,5", a R$ 18,99: o mesmo patamar. Se R$ 18,99 fosse o preço de 500 g, o quilo sairia a R$ 38.

## Super ABC

O Super ABC não tem API aberta: entra pelo robô, com a mesma lista (o termo é a busca) e o mesmo filtro de nome. O robô **não traz categoria nem `unidade`**, e o peso do nome é aproximado ("400 G (1 A 2 Unidades)"). Rodado em 18/11/2026 (CEP de Betim), os 28 termos devolveram **51 produtos de 26 termos** (sem resultado: abobrinha, que o site avisa que não tem, e mandioca e morango, que só acham processados):

- **Entra** o que é fresco, em pacote de peso aproximado (tomate longa vida 500 g, cebola roxa 400 g, banana prata 1,2 kg), por unidade ("Alface Und", "Couve Unidade") ou pelo quilo no nome ("Maca Pink Lady Kg"). Os nomes reais estão em `tests/casos_hortifruti.py` (`SUPER_ABC`).
- **Sai pelo nome**, já que a categoria não existe: tomate pelado em lata, batata ondulada congelada e "Maca Peito Bovina" (um corte de carne que o robô achava na busca de maçã). Por isso a lista tem exclusões por nome a mais (`lata`, `pelado`, `ondulad`, `palito`, `bem brasil`, `mccain`, `bovin`, `peito`), que valem para todos os mercados e não derrubaram nenhum dos 175 itens da coleta de 17/11.
- Como ele não informa `unidade`, **nunca é "por quilo"**: o preço do pacote dele só se compara com um pacote do mesmo peso (modo exato) ou com a chave do mesmo peso (modo equivalente). "Banana Prata 1,2 Kg" não é o preço do quilo do Atacadão, e o site não o mostra com "/kg".
- Custo na carga: o robô passa de 100 para 128 buscas (cerca de 4 minutos a mais, com 3 navegadores).

## Filtros da lista

- **Categoria:** `Hortifrúti` (qualquer nível). Fora ficam chips, molhos, conservas, congelados e tempero. A exceção é a **couve-flor**: o Supernosso a guarda em "Visualizar Mais Produtos", e só esse termo aceita essa categoria. O robô do Super ABC não tem categoria: só o nome decide.
- **Nome:** começa pelo termo (`Banana Prata Quilo`). A abobrinha também aceita "abóbora italiana" (como o Atacadão a chama) e a mandioca, "aipim".
- **Saem pelo nome:** fruta seca (passas), produto picado, ralado, higienizado, descascado ou "processado", cozido no vapor ou a vácuo, frito, em conserva, em lata ou em calda, congelado, suco, polpa, molho, flocos, corte de carne.
- **Entram de propósito:** orgânico, bandeja, baby e o saco de atacado ("Cebola 19kg"). O produto sem estoque não entra: o coletor só traz o que tem estoque, como sempre.

Outras verduras e ervas ficam para depois (cebolinha, salsinha, coentro, rúcula, agrião, espinafre).

A lista é **gerada** por um script (as regras repetidas ficam num lugar só); para mudar uma regra, mude a do script e confira `tests/casos_hortifruti.py`.

## Como chegou aqui

1. ~~O campo `unidade` no banco.~~ Coluna criada por [`sql/coluna_unidade.sql`](sql/coluna_unidade.sql) (`text`, sem restrição, para a carga não quebrar se um mercado mandar uma unidade que não conhecemos). `coletor_vtex.unidade_normalizada` deixa só `kg`, `un` ou vazio; a carga detecta a coluna e a grava; a API a pede (e segue sem ela se o banco não a tiver). O histórico de preços não precisa dela: o preço de um produto vendido por quilo continua sendo comparável com o dele mesmo.
2. ~~Equivalência por variedade e forma de venda.~~ Uma família só, guiada por uma tabela de 28 produtos: o preço por quilo vira "1 kg" na chave; o pacote vale o peso do nome; sem peso, "unidade". Dimensões: variedade, importada, **orgânico**; sinônimos (caturra = nanica, aipim = mandioca, "abóbora italiana" = abobrinha, "Limão Tahiti" = "Limão-taiti"). Nos 175 itens da coleta de 17/11: todos com chave, 132 grupos, **30 comparáveis**. Veja [`equivalencia.md`](equivalencia.md).
3. ~~O site.~~ "R$ 3,79**/kg**" no quadro do mercado, "2 kg na lista" no cartão e "2 kg × R$ 3,79/kg" no cupom, só onde `unidade = kg` (veja [`site.md`](site.md#preço-por-quilo-hortifrúti)). Ficam de fora, por ora, "/maço" e o aviso de peso aproximado: o produto sem `unidade kg` aparece como qualquer outro, com o nome dizendo o que é ("Alface Crespa Unidade").
4. ~~Modo exato.~~ Quilo não junta com pacote (veja abaixo).
5. ~~Super ABC e a carga.~~ Os 28 termos entram na carga dos 4 mercados.

Conferido antes de ligar (offline, com o catálogo de 7.836 produtos de 12/11 somado a 226 linhas de hortifrúti: 175 dos 3 mercados com API e 51 do Super ABC, pela função real da API): **as chaves de equivalência dos 7.836 produtos que já existiam não mudam**; nenhum produto do dia a dia cai na família de hortifrúti; todo hortifrúti ganha chave; nenhum grupo do modo exato mistura quilo com pacote; as buscas do dia a dia (arroz, leite, óleo, café, açúcar, sal, ovos, fralda, queijo...) devolvem o mesmo número de grupos.

## Limites conhecidos

- Perde uns poucos itens frescos que o Supernosso guarda em categoria genérica (um tomate grape orgânico, o alho-poró "Unidade"): a regra por categoria prefere perder 4 itens a deixar entrar tempero e conserva.
- Sem estoque, não há linha: o Supernosso não tinha mamão nem morango fresco no dia (0 itens), e o Atacadão só tinha brócolis congelado. O estoque muda de um dia para o outro: um termo pode ter 0 itens num mercado e 20 no seguinte.
- Frutas e verduras com o nome começando por outra palavra ("Aipim", "Cheiro-verde") dependem de sinônimos, só feitos para a mandioca e a abobrinha.
- "Alho-poró" entra no termo "alho" (o nome começa por "alho"); a equivalência os separa por variedade.
- A diferença de preço pode refletir uma variedade que o nome não diz (abacate Hass e comum, "Tomate Italiano" de qualidade diferente): a equivalência junta pelo que está escrito.
- Os preços do Super ABC são do pacote, com peso aproximado: servem para comparar pacotes de peso igual, não para calcular o quilo.
- **Modo exato: quilo não junta com pacote (resolvido).** O agrupamento por nome (`Comparador_inteligente.py`) foi feito para produto de prateleira e, nos dados de 17/11, juntou 2 dos 10 grupos com mais de um mercado um preço **por quilo** com o de um **pacote** ("Repolho Branco Quilo" do Atacadão, R$ 3,49/kg, com "Repolho Misto 200g" do Supernosso, R$ 11,99; "Cebola Roxa Quilo" com "Cebola Roxa Org 400g", que ainda é orgânica). Agora um item `kg` só entra em grupo de itens `kg`, e um que não é `kg` (inclusive o do Super ABC, sem a informação) só em grupo dos que não são (veja [`banco_de_dados.md`](banco_de_dados.md)). Nos mesmos dados: 0 grupos misturados; no catálogo de 7.814 produtos de 12/11, os 5.357 grupos saem idênticos. O custo: o mesmo produto vendido por quilo num mercado e em bandeja no outro fica em dois cartões no modo exato; o modo equivalente os junta (a bandeja de 1 kg vale o preço do quilo).

## Testes

`python tests/test_coletor_vtex.py` confere: que o termo comum continua descartando o peso variável e o de hortifrúti o aceita; que a linha traz `unidade` e `multiplicador` (Supernosso, Apoio e Atacadão); 28 termos com 114 nomes reais que entram e 74 que saem em `tests/casos_hortifruti.py`, mais 52 nomes reais do robô do Super ABC (46 que entram e 6 que saem); que a carga junta as duas listas numa coleta só e que nada mais lê um arquivo de lista; que listas com termo repetido ou teto diferente são recusadas; que item por quilo não leva atacado; e o relatório de itens por quilo.
