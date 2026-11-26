# Carnes, aves, peixes, frios e queijos vendidos a peso

> **Estado (26/11/2026): feito e na carga diária.** Reconhecimento nos quatro mercados, lista e filtros (etapa 1), equivalência (etapa 2) e a ligação na carga (etapa 5) para os cortes bovinos e os queijos minas e parmesão; os oito tipos que já tinham termo na lista de 100 (frango congelado, peito de frango, carne moída, linguiça, bacon, presunto, queijo mussarela, queijo prato) passaram a aceitar também o item por quilo. **Decidido em 26/11:** o premium entra, **separado do comum**, e o congelado entra, **separado do fresco**. Até 26/11 a carga descartava tudo o que é vendido por quilo fora do hortifrúti e mantinha só o que vem **embalado**. Esta página registra o que os mercados vendem a peso, o plano e o que foi feito, nos mesmos moldes do [hortifrúti](hortifruti.md). O Super ABC foi reconhecido em 26/11/2026, pela API da loja (veja a tabela).

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

## Plano (nos moldes do hortifrúti)

1. **Lista e filtros (fora da carga). Feito em 26/11/2026** ([veja a etapa 1](#etapa-1-a-lista-e-os-filtros-feita-em-26112026-fora-da-carga)). Um arquivo próprio (`dados/lista_carnes_e_frios.json`) com os termos novos, filtro por categoria do mercado e por nome, casos reais de "entra" e "sai" e testes, como a [lista do hortifrúti](hortifruti.md). O coletor já sabe ler (`aceita_peso_variavel`). Os tipos que já têm termo na lista de 100 não repetem aqui.
2. **Equivalência. Feito em 26/11/2026** ([veja a etapa 2](#etapa-2-a-equivalência-feita-em-26112026-fora-da-carga)). Uma família, como a do hortifrúti, por **corte, forma, estado, tempero e faixa de qualidade**, com o preço por quilo valendo "1 kg". Itens que o nome não deixa classificar ficam sem chave (só no modo exato).
3. **Site:** quase nada: já mostra "/kg", conta a lista em quilos e esconde o peso da porção. Talvez um rótulo de estado ("congelado") quando for útil.
4. **Super ABC (reconhecido em 26/11):** tem corte a peso, e entra como os outros. Sem categoria, o filtro dele é só por nome, e o nome precisa tirar o ruído (melão, repolho, pão de queijo, sanduíche, patê). A API da loja já traz `unidade = kg` e o preço do quilo (`coletor_vip.py`).
5. **Ligar na carga. Feito em 26/11/2026** ([veja a etapa 5](#etapa-5-ligar-na-carga-feita-em-26112026)), com a mesma cautela (OK explícito; uma coleta só com as outras listas, porque a gravação apaga o resto do mercado).

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

**Os oito tipos que já têm termo na lista de 100** (frango congelado, peito de frango, carne moída, linguiça, bacon, presunto, queijo mussarela e queijo prato) **não estão nesta lista**: ao ligar na carga, esses termos passam a aceitar peso variável. Testei os nomes por quilo reais de 24/11 e do Super ABC contra os filtros de hoje, com o peso variável ligado, e achei **três lacunas, que afetavam também o embalado de hoje e foram corrigidas em 26/11/2026** (lista de 100, `teste_bacon_muçarela_e_frango_caipira_da_lista_de_100`):
1. **Bacon do Apoio:** o termo `bacon` não tinha a categoria do Apoio (`Açougue > Salsichas e Linguiças`), então o bacon do Apoio, por quilo ou embalado, nunca entrava. Agora o embalado entra (4 itens); o por quilo (5) entra quando o peso variável for ligado.
2. **Muçarela:** o termo `queijo mussarela` procurava e aceitava só "mussarela" e perdia a grafia "Muçarela" (35 nomes distintos contra 68 de "mussarela"). Agora ele busca as duas grafias (cada loja acha uma coisa para cada: no Super ABC, "mussarela" traz 4 produtos e "muçarela", 16) e o filtro aceita as duas, e a busca do site trata as duas como a mesma palavra (`GRAFIAS_IGUAIS`). O parmesão e a muçarela **vegana** ("Queijo Muçarela Vegano de Castanha de Caju") ficam de fora. O embalado passa de 39 para 59 itens nos quatro mercados (Apoio 9 para 14, Supernosso 10 para 17, Super ABC 3 para 11, Atacadão 17).
3. **Frango caipira cortado** ("Frango Caipira Nhô Bento Cortado 2Kg") não casava com `frango congelado`, que só aceitava "frango inteiro", "a passarinho", "em pedaços" e "congelado" no começo do nome. Agora aceita também "frango caipira" (os dois itens são por quilo e entram com o peso variável).
O "apresuntado" fica de fora do `presunto` (é outro produto), e o "peito de peru" do `peito de frango`, de propósito.

## Etapa 2: a equivalência (feita em 26/11/2026, fora da carga)

A família `carnes_a_peso` ("cortes de carne e queijos a peso") de [`equivalencia.py`](../equivalencia.py) dá uma **chave de equivalência** a cada item dos dez termos da lista. É a etapa que faz valer a decisão do dono: **premium e congelado nunca disputam o "mais barato" com o comum e o fresco**. Detalhes das regras em [`equivalencia.md`](equivalencia.md).

- **O que a chave junta:** o corte (e a parte dele), a **forma** (peça, fatiada, bifes, cubos, moída), o **estado** (congelado), o **tempero** e a **faixa** (premium). No queijo minas, o tipo (frescal, padrão, meia cura, curado) e o que o nome diz de especial (zero lactose, light, artesanal, de búfala, defumado, temperado); no parmesão, fatiado, maturado e importado.
- **O preço por quilo vale "1 kg"**, qualquer que seja o peso do nome (que é o da porção); o embalado de peso fixo vale o peso do nome, e os dois nunca se juntam (um é preço do quilo, o outro do pacote).
- **Premium é o que o nome diz.** Os marcadores são Angus, Wagyu, Kobe, Carapreta, Reserva, Maturatta e maturada, Premium, Gourmet, Prime, Bassi e dry aged; a lista é uma constante (`_PREMIUM_DE_CORTE`) e cresce quando aparecer uma linha nova. Uma marca premium que o nome não revela fica entre os comuns, e o corte congelado que não diz "congelado" fica entre os frescos: são os limites desta etapa.
- **O agrupamento exato também só junta com a mesma chave** (`Comparador_inteligente.py`, a mesma trava do hortifrúti): "Picanha Bassi Resfriada 1Kg" e "Picanha A Resfriada 1Kg" têm nome parecido e preços de duas faixas; sem a trava, o nome os juntaria.
- **Item por quilo só entra numa família que lê a unidade.** Isso protege a etapa 5: quando o peso variável for ligado nos termos que já existem (linguiça, bacon, presunto...), o item por quilo deles não pode ser chaveado pelo peso do nome. Até lá eles ficam sem chave (só no modo exato).
- **Resultado na lista de hoje:** os 192 itens ganham chave, em 68 chaves; 20 delas têm dois mercados ou mais. Entre os 2.620 itens reais que usei de teste, só 194 mudaram de chave (de "sem chave" para uma chave nova); as de todos os outros ficaram iguais.
- **Testes:** `tests/test_equivalencia_carnes.py` (111 verificações, com nomes reais e a unidade de cada um: o quilo, o embalado, o premium, o congelado, a forma, cada dimensão do queijo, o rótulo e o que fica sem chave), `tests/test_busca_e_comparador.py` (a trava do agrupamento exato) e os casos de cobertura em `tests/casos_equivalencia_novos.py`. mais de 30 mutações das regras, todas pegas.

## Etapa 5: ligar na carga (feita em 26/11/2026)

Com o OK do dono ("teste a gravação e, se tudo funcionar, pode dar a carga real"), a carga diária passou a coletar **três listas numa coleta só**: os 100 termos de prateleira, os 28 de hortifrúti e os **10 de carnes e queijos a peso** (`coletor_vtex.carregar_lista_da_carga`, 138 termos). Duas mudanças:

1. **A lista de carnes entra na carga** (`LISTA_CARNES`, no fim da coleta). Termo repetido ou teto por termo diferente entre quaisquer duas das três listas continua sendo recusado, e um teste trava que só o coletor abre o arquivo.
2. **Os oito termos da lista de 100 que também vendem a peso passam a aceitar peso variável** (`aceita_peso_variavel`): frango congelado, peito de frango, carne moída, linguiça, bacon, presunto, queijo mussarela e queijo prato. O item **embalado** deles segue igual, com a chave de sempre. O item **por quilo** entra sem chave de equivalência (a regra da etapa 2: item por quilo só vira chave numa família que lê a unidade), e por isso só aparece no modo "produto exato"; nunca se junta ao embalado (o agrupamento separa "por quilo" de "por pacote").

**Como foi testado, antes de gravar:**

- Leitura (só leitura, sem banco) dos 18 termos afetados nos quatro mercados: 657 linhas, 283 por quilo, 0 erros. O preço do quilo ficou plausível em todos os termos (mínimo, mediana e máximo conferidos termo a termo e mercado a mercado; os únicos abaixo de R$ 8 são o fígado e a coxa com sobrecoxa de frango congelados). Nenhum item por quilo dos oito termos antigos ganhou chave; os dez termos novos ficaram 100% com chave (194 itens, 67 chaves, 19 delas em dois mercados ou mais, e nenhum produto em dois termos).
- Carga completa **sem gravar** no GitHub ([run 45827747085](https://github.com/rafaelhsl/supermatch-api/actions/runs/45827747085)): sucesso, **0 termos com falha de 138** nos quatro mercados, 0 repetições do coletor e 0 avisos. Itens: Apoio 1.940 (+43 sobre a carga das 07:30 do mesmo dia, 1.897), Atacadão 2.327 (+48), Supernosso 2.743 (+139) e Super ABC 2.581 (+96): **+326 itens**, como estimado. Tempo: 20 minutos, quase todos do Super ABC (a loja dele limita o ritmo; a de 25/11 levou 17).
- Os testes do repositório (Python 3.11, Python do Render, Node e navegador) passaram no PR.

**O que os mercados não vendem não é falha:** o Apoio não tem patinho, acém, coxão mole nem alcatra (0 itens), o Supernosso não tem coxão mole, o Atacadão não tem patinho, alcatra nem músculo (as buscas dele trazem carne suína, carne moída e desinfetante "Pinho", que o filtro descarta) e o Super ABC não tem coxão mole. O coxão mole só existe no Atacadão (1 item), então não compara.

**Limites que seguem:** o item por quilo dos oito termos antigos (presunto, queijo mussarela e prato, frango, bacon, carne moída) só compara no modo exato, por nome; uma família de equivalência para eles é um passo à parte. As duas pontas da lista de carnes continuam as da etapa 2 (premium e congelado só pelo que o nome diz).

## O que foi decidido

- **Escopo da primeira rodada.** Sugestão: frango (inteiro, peito, coxa e sobrecoxa), carne moída, os cortes populares (patinho, acém, coxão mole, músculo, alcatra, fraldinha, picanha, contra filé), linguiça, bacon, presunto, mussarela, queijo prato, queijo minas e parmesão. Peixe, cordeiro, cortes premium e salame ficam para depois.
- **O premium entra? Sim (decidido em 26/11/2026), separado do comum** por chave (faixa "premium"), para nunca disputar o "mais barato" com o comum.
- **Congelado entra? Sim (decidido em 26/11/2026), separado do fresco**, também por chave.
- **Escopo da primeira rodada:** a sugestão acima segue como ponto de partida (o usuário respondeu só sobre premium e congelado), e cresce depois.

## Limites do reconhecimento

- Foi **uma coleta de um dia** e a classificação por tipo foi feita por expressões no nome, só para dimensionar; a regra de verdade nasce na etapa 2, com casos reais.
- **Super ABC:** o reconhecimento de 26/11 foi pela API da loja (unidade de Betim, só o que tem estoque), com as mesmas 38 buscas; o robô antigo, que falhou em todas as tentativas de 24/11, saiu da carga em 25/11. Como os outros, é uma coleta de um dia.
