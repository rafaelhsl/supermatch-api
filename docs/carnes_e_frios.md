# Carnes, aves, peixes, frios e queijos vendidos a peso

> **Estado (26/11/2026): reconhecimento feito nos quatro mercados (só leitura); nada disso entra na carga.** **Decidido em 26/11:** o premium entra, **separado do comum**, e o congelado entra, **separado do fresco**. A carga diária continua descartando tudo o que é vendido por quilo fora do hortifrúti, e mantém só o que vem **embalado** (as listas de produtos têm termos como "carne moída", "queijo mussarela", "presunto", "bacon", mas só com pacote de peso fixo). Esta página registra o que os mercados vendem a peso e o plano para trazer isso, nos mesmos moldes do [hortifrúti](hortifruti.md). O Super ABC foi reconhecido em 26/11/2026, pela API da loja (veja a tabela).

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

1. **Lista e filtros (fora da carga).** Um arquivo próprio (`dados/lista_carnes_e_frios.json`) com cerca de 30 termos por tipo de produto, filtro por categoria do mercado ("Açougue", "Carnes, aves e peixes", "Frios e Laticínios > Queijos"...) e por nome, casos reais de "entra" e "sai" e testes, como a [lista do hortifrúti](hortifruti.md). O coletor já sabe ler (`aceita_peso_variavel`).
2. **Equivalência** (uma família, como a do hortifrúti) por **corte, forma, estado, tempero e faixa de qualidade**, com o preço por quilo valendo "1 kg". Itens que o nome não deixa classificar ficam sem chave (só no modo exato).
3. **Site:** quase nada: já mostra "/kg", conta a lista em quilos e esconde o peso da porção. Talvez um rótulo de estado ("congelado") quando for útil.
4. **Super ABC (reconhecido em 26/11):** tem corte a peso, e entra como os outros. Sem categoria, o filtro dele é só por nome, e o nome precisa tirar o ruído (melão, repolho, pão de queijo, sanduíche, patê). A API da loja já traz `unidade = kg` e o preço do quilo (`coletor_vip.py`).
5. **Ligar na carga**, com a mesma cautela (OK explícito; uma coleta só com as outras listas, porque a gravação apaga o resto do mercado). Custo estimado: ~30 termos a mais na coleta por API (poucos segundos) e, se o Super ABC participar, ~30 buscas a mais do robô (as 28 do hortifrúti somaram uns 2 minutos à carga).

## O que foi decidido

- **Escopo da primeira rodada.** Sugestão: frango (inteiro, peito, coxa e sobrecoxa), carne moída, os cortes populares (patinho, acém, coxão mole, músculo, alcatra, fraldinha, picanha, contra filé), linguiça, bacon, presunto, mussarela, queijo prato, queijo minas e parmesão. Peixe, cordeiro, cortes premium e salame ficam para depois.
- **O premium entra? Sim (decidido em 26/11/2026), separado do comum** por chave (faixa "premium"), para nunca disputar o "mais barato" com o comum.
- **Congelado entra? Sim (decidido em 26/11/2026), separado do fresco**, também por chave.
- **Escopo da primeira rodada:** a sugestão acima segue como ponto de partida (o usuário respondeu só sobre premium e congelado), e cresce depois.

## Limites do reconhecimento

- Foi **uma coleta de um dia** e a classificação por tipo foi feita por expressões no nome, só para dimensionar; a regra de verdade nasce na etapa 2, com casos reais.
- **Super ABC:** o reconhecimento de 26/11 foi pela API da loja (unidade de Betim, só o que tem estoque), com as mesmas 38 buscas; o robô antigo, que falhou em todas as tentativas de 24/11, saiu da carga em 25/11. Como os outros, é uma coleta de um dia.
