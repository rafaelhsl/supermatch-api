# Carnes, aves, peixes, frios e queijos vendidos a peso

> **Estado (26/11/2026): reconhecimento feito nos quatro mercados e a etapa 1 pronta (lista e filtros dos cortes bovinos e dos queijos minas e parmesão); nada disso entra na carga.** **Decidido em 26/11:** o premium entra, **separado do comum**, e o congelado entra, **separado do fresco**. A carga diária continua descartando tudo o que é vendido por quilo fora do hortifrúti, e mantém só o que vem **embalado** (as listas de produtos têm termos como "carne moída", "queijo mussarela", "presunto", "bacon", mas só com pacote de peso fixo). Esta página registra o que os mercados vendem a peso e o plano para trazer isso, nos mesmos moldes do [hortifrúti](hortifruti.md). O Super ABC foi reconhecido em 26/11/2026, pela API da loja (veja a tabela).

## Por que isso é o próximo passo natural

O hortifrúti já ensinou o projeto a lidar com preço **por quilo**: a coluna `unidade` (`kg`), o "R$ x/kg" e a lista em quilos no site, a trava para o modo exato não juntar quilo com pacote e o nome do item sem o peso da porção. O açougue, os frios e os queijos usam exatamente a mesma mecânica (o `measurementUnit` do mercado diz `kg` e o preço é o do quilo), e são parte grande de uma compra de verdade.

## O que o reconhecimento mostrou

Foram 38 buscas (cortes bovinos, aves, suínos, peixes, frios e queijos) em cada um dos três mercados com API, em 24/11/2026: **2.011 itens distintos**, dos quais **353 são vendidos por quilo** em categorias de carne, frios e queijo (a carga de hoje descarta todos):

| Mercado | Por quilo (carnes, frios, queijos) | Como aparece |
|---|---|---|
| Apoio Entrega | 60 | "Açougue" e "Frios e Laticínios"; quase tudo em peça de 1 kg; inclui congelados baratos |
| Atacadão | 111 | "Carnes, aves e peixes" e "Frios e congelados"; o nome diz **"Preço por quilo na peça"** (110 dos 111); o múltiplo é o peso típico da peça (1,2 kg etc.) |
| Supernosso | 182 | "Aves, Carnes e Peixes" e "Frios e Laticínios > Queijos" (98 queijos por quilo); linhas premium (Angus, Reserva, Carapreta) e produtos temperados |
| Super ABC | 217 (de 532 itens distintos nas mesmas 38 buscas, só o que tem estoque em Betim) | **sem categoria**: só o nome diz o que é. Carne bovina e suína em porções de 0,4 a 1,6 kg ("Carne Suína Lombo Completo 500g"), com o preço do **quilo**; frios e queijos por quilo; muita linha "a pururuca" e "temperada". Traz **ruído** que só o nome tira (melão e repolho inteiros, pão de queijo e sanduíche "por quilo", patê) |

Dos 34 tipos de produto que o nome permite reconhecer (picanha, contra filé, fraldinha, acém, músculo, costela, bacon, linguiça, presunto, mussarela, queijo prato, queijo minas, parmesão, peito de peru, salame, frango inteiro, tilápia...), **31 aparecem em dois ou mais mercados, 22 em três ou mais e 13 nos quatro** (com o Super ABC; sem ele eram 25 de 33 em dois ou mais). Só coxão mole, coxão duro e tilápia aparecem em um mercado só. O terreno comparável existe.

## O cuidado que o hortifrúti não pedia: o "mesmo tipo" não é o mesmo produto

No hortifrúti, "banana prata" é banana prata. Aqui o mesmo nome esconde produtos muito diferentes, e o preço por quilo mostra isso:

| Tipo | Apoio | Atacadão | Supernosso |
|---|---|---|---|
| Picanha bovina | R$ 54,99 a 69,99 | R$ 49,90 a 99,90 | R$ 89,99 a **259,99** (Angus congelada) |
| Contra filé | R$ 54,99 | R$ 39,90 a 64,90 | R$ 59,99 a **116,99** (Carapreta congelado) |
| Queijo minas | R$ 36,99 a 75,99 | R$ 34,99 a 69,90 | R$ 39,99 a **149,90** (curado artesanal) |

A diferença vem de **qualidade/marca** (Angus, Wagyu, Maturatta, Reserva, Premium), **forma** (peça, porcionado, fatiado, bife, moído), **estado** (resfriado ou congelado), **tempero** (temperado ou não) e, nos queijos, **curadoria** (frescal, padrão, meia cura, curado). Um "produto equivalente: picanha" que juntasse tudo faria o site recomendar uma picanha Angus congelada contra uma fatiada comum como se fossem a mesma coisa, o erro que o projeto mais evita ("na dúvida, não junta"). A equivalência dessa família precisa, no mínimo, destas dimensões: **corte, forma, estado, tempero e faixa de qualidade** (comum ou premium), além do peso da porção, que **não** conta (é o do múltiplo de compra, como no hortifrúti).

Outros pontos que a coleta mostrou:

- **O peso do nome não é a base do preço** (de novo): "Contra Filé Noix Peça 1.4Kg, R$ 54,99" é R$ 54,99 **o quilo**, e a peça tem ~1,4 kg. O site já tira o peso da porção do nome do item por quilo e já avisa que o valor final sai da pesagem.
- **O "preço por quilo" do Atacadão vem escrito no nome** ("Preço por quilo na peça", "no pacote"); o filtro por nome tem de ignorar essa frase.
- **Frango congelado a R$ 6,99 e R$ 8,99 o quilo** (fígado e coxa com sobrecoxa do Apoio) ao lado de "frango caipira" a R$ 23,99 (Supernosso): tipos e estados diferentes, que também não podem se juntar.
- Boa parte dessas categorias é **embalado de peso fixo** (99 itens no Apoio, 338 no Atacadão e 309 no Supernosso nesse reconhecimento), que os termos de hoje só recolhem em parte e que não é problema desta família.

## Plano (nos moldes do hortifrúti; nada entra na carga antes da decisão final)

1. **Lista e filtros (fora da carga). Feito em 26/11/2026** ([veja a etapa 1](#etapa-1-a-lista-e-os-filtros-feita-em-26112026-fora-da-carga)). Um arquivo próprio (`dados/lista_carnes_e_frios.json`) com os termos novos, filtro por categoria do mercado e por nome, casos reais de "entra" e "sai" e testes, como a [lista do hortifrúti](hortifruti.md). O coletor já sabe ler (`aceita_peso_variavel`). Os tipos que já têm termo na lista de 100 não repetem aqui.
2. **Equivalência** (uma família, como a do hortifrúti) por **corte, forma, estado, tempero e faixa de qualidade**, com o preço por quilo valendo "1 kg". Itens que o nome não deixa classificar ficam sem chave (só no modo exato).
3. **Site:** quase nada: já mostra "/kg", conta a lista em quilos e esconde o peso da porção. Talvez um rótulo de estado ("congelado") quando for útil.
4. **Super ABC (reconhecido em 26/11):** tem corte a peso, e entra como os outros. Sem categoria, o filtro dele é só por nome, e o nome precisa tirar o ruído (melão, repolho, pão de queijo, sanduíche, patê). A API da loja já traz `unidade = kg` e o preço do quilo (`coletor_vip.py`).
5. **Ligar na carga**, com a mesma cautela (OK explícito; uma coleta só com as outras listas, porque a gravação apaga o resto do mercado). Custo estimado: ~30 termos a mais na coleta por API (poucos segundos) e, se o Super ABC participar, ~30 buscas a mais do robô (as 28 do hortifrúti somaram uns 2 minutos à carga).

## Etapa 1: a lista e os filtros (feita em 26/11/2026, fora da carga)

[`dados/lista_carnes_e_frios.json`](../dados/lista_carnes_e_frios.json) tem os **10 termos novos** do escopo da primeira rodada: oito cortes bovinos (patinho, acém, coxão mole, músculo, alcatra, fraldinha, picanha, contra filé) e dois queijos (minas e parmesão). **Ninguém a lê**: a carga diária continua com os 128 termos de antes, e um teste trava isso (`teste_a_lista_de_carnes_e_frios_ainda_nao_entra_na_carga`). Para ver o que ela traz hoje: `python coletor_vtex.py --lista dados/lista_carnes_e_frios.json` (os três mercados da VTEX) e `python coletor_vip.py --lista dados/lista_carnes_e_frios.json` (o Super ABC).

**Como o filtro decide.** Todos os termos aceitam peso variável (`aceita_peso_variavel`), e o **embalado de peso fixo também entra** (o "Queijo Parmesão Président 180g" ao lado da peça de 1 kg). Premium e congelado entram: a faixa e o estado são da chave de equivalência (etapa 2), não da lista.
- **Carne:** a categoria tem de ser a de carne do mercado (`Açougue`, `Carnes, aves e peixes`, `Aves, Carnes e Peixes`) e o nome tem de **começar** pelo corte, com `carne`, `bovina` ou `bov`, `bife de` ou `steak` na frente ("Carne Bovina Picanha ...", "Carne Bov Músculo ...", "Steak Picanha ..."). Por começar pelo corte, saem sozinhos o hambúrguer e o salgadinho "sabor picanha", a carne de sol, o limpador "Mr Músculo" e a "Capa de Contra Filé" (outro corte, bem mais barato). A única exclusão por nome é `suin`: "Alcatra Suína" e "Patinho Suíno" são outra peça. Em alcatra, entram também "miolo", "bombom" e "coração" de alcatra, e em acém, "miolo de acém" (partes do mesmo corte, que a chave de equivalência separa). O Super ABC não traz categoria: só o nome decide.
- **Queijo:** a categoria é `Queijos` (e a genérica "Visualizar Mais Produtos", onde o Supernosso põe alguns), e o nome começa por "Queijo Minas" (ou "Queijo Supernosso Minas") ou por "Queijo Parmesão". O parmesão ralado (que já tem o termo "queijo ralado"), o "Ral" abreviado do Super ABC e o parmesão vegano saem.
- Os casos reais estão em `tests/casos_carnes.py` (nomes e categorias dos mercados em 26/11, e os do Super ABC só com o nome), e `teste_lista_de_carnes_e_frios_do_repositorio` confere cada um. 15 mutações das regras, todas pegas pelos testes.

**O que a lista traz hoje** (itens de 26/11/2026; entre parênteses, os vendidos por quilo):

| Termo | Apoio | Atacadão | Supernosso | Super ABC | Total |
|---|---|---|---|---|---|
| patinho | 0 | 0 | 2 | 4 | 6 (5) |
| acém | 0 | 2 | 1 | 2 | 5 (5) |
| coxão mole | 0 | 1 | 0 | 0 | 1 (1) |
| músculo | 2 | 0 | 4 | 2 | 8 (7) |
| alcatra | 0 | 0 | 4 | 10 | 14 (14) |
| fraldinha | 1 | 2 | 3 | 2 | 8 (8) |
| picanha | 2 | 7 | 9 | 5 | 23 (23) |
| contra filé | 2 | 3 | 7 | 9 | 21 (21) |
| queijo minas | 11 | 9 | 39 | 14 | 73 (64) |
| queijo parmesão | 4 | 3 | 24 | 2 | 33 (12) |
| **Total** | 22 | 27 | 93 | 50 | **192 (160)** |

Os números baixos (coxão mole, patinho, acém) são o que as lojas têm em estoque no dia, não falha do filtro: nos nomes que casam com a palavra e saem, só há hambúrguer, carne de porco, carne de sol e limpador. O estoque muda de um dia para o outro.

**Os oito tipos que já têm termo na lista de 100** (frango congelado, peito de frango, carne moída, linguiça, bacon, presunto, queijo mussarela e queijo prato) **não estão nesta lista**: ao ligar na carga, esses termos passam a aceitar peso variável. Testei os nomes por quilo reais de 24/11 e do Super ABC contra os filtros de hoje, com o peso variável ligado, e **três coisas precisam de ajuste nessa hora** (afetam também o embalado de hoje):
1. **Bacon do Apoio:** o termo `bacon` não tem a categoria do Apoio (`Açougue > Salsichas e Linguiças`), então o bacon do Apoio, por quilo ou embalado, nunca entra.
2. **Muçarela:** o termo `queijo mussarela` procura "mussarela" e perde a grafia "Muçarela" ("Queijo Muçarela Supernosso Peça 1Kg", e as seis do Super ABC).
3. **Frango caipira cortado** ("Frango Caipira Nhô Bento Cortado 2Kg") não casa com `frango congelado`, que só aceita "frango inteiro", "a passarinho", "em pedaços" e "congelado" no começo do nome.
O "apresuntado" fica de fora do `presunto` (é outro produto), e o "peito de peru" do `peito de frango`, de propósito.

## O que foi decidido

- **Escopo da primeira rodada.** Sugestão: frango (inteiro, peito, coxa e sobrecoxa), carne moída, os cortes populares (patinho, acém, coxão mole, músculo, alcatra, fraldinha, picanha, contra filé), linguiça, bacon, presunto, mussarela, queijo prato, queijo minas e parmesão. Peixe, cordeiro, cortes premium e salame ficam para depois.
- **O premium entra? Sim (decidido em 26/11/2026), separado do comum** por chave (faixa "premium"), para nunca disputar o "mais barato" com o comum.
- **Congelado entra? Sim (decidido em 26/11/2026), separado do fresco**, também por chave.
- **Escopo da primeira rodada:** a sugestão acima segue como ponto de partida (o usuário respondeu só sobre premium e congelado), e cresce depois.

## Limites do reconhecimento

- Foi **uma coleta de um dia** e a classificação por tipo foi feita por expressões no nome, só para dimensionar; a regra de verdade nasce na etapa 2, com casos reais.
- **Super ABC:** o reconhecimento de 26/11 foi pela API da loja (unidade de Betim, só o que tem estoque), com as mesmas 38 buscas; o robô antigo, que falhou em todas as tentativas de 24/11, saiu da carga em 25/11. Como os outros, é uma coleta de um dia.
