# Carnes, aves, peixes, frios e queijos vendidos a peso

> **Estado (24/11/2026): reconhecimento feito (só leitura); nada disso entra na carga.** A carga diária continua descartando tudo o que é vendido por quilo fora do hortifrúti, e mantém só o que vem **embalado** (as listas de produtos têm termos como "carne moída", "queijo mussarela", "presunto", "bacon", mas só com pacote de peso fixo). Esta página registra o que os mercados vendem a peso e o plano para trazer isso, nos mesmos moldes do [hortifrúti](hortifruti.md). **O Super ABC (robô) ainda não foi reconhecido**: o site dele não abriu a lista de unidades durante o reconhecimento (veja o fim).

## Por que isso é o próximo passo natural

O hortifrúti já ensinou o projeto a lidar com preço **por quilo**: a coluna `unidade` (`kg`), o "R$ x/kg" e a lista em quilos no site, a trava para o modo exato não juntar quilo com pacote e o nome do item sem o peso da porção. O açougue, os frios e os queijos usam exatamente a mesma mecânica (o `measurementUnit` do mercado diz `kg` e o preço é o do quilo), e são parte grande de uma compra de verdade.

## O que o reconhecimento mostrou

Foram 38 buscas (cortes bovinos, aves, suínos, peixes, frios e queijos) em cada um dos três mercados com API, em 24/11/2026: **2.011 itens distintos**, dos quais **353 são vendidos por quilo** em categorias de carne, frios e queijo (a carga de hoje descarta todos):

| Mercado | Por quilo (carnes, frios, queijos) | Como aparece |
|---|---|---|
| Apoio Entrega | 60 | "Açougue" e "Frios e Laticínios"; quase tudo em peça de 1 kg; inclui congelados baratos |
| Atacadão | 111 | "Carnes, aves e peixes" e "Frios e congelados"; o nome diz **"Preço por quilo na peça"** (110 dos 111); o múltiplo é o peso típico da peça (1,2 kg etc.) |
| Supernosso | 182 | "Aves, Carnes e Peixes" e "Frios e Laticínios > Queijos" (98 queijos por quilo); linhas premium (Angus, Reserva, Carapreta) e produtos temperados |

Dos 33 tipos de produto que o nome permite reconhecer (picanha, contra filé, fraldinha, acém, músculo, costela, bacon, linguiça, presunto, mussarela, queijo prato, queijo minas, parmesão, peito de peru, salame, frango inteiro, tilápia...), **25 aparecem em dois ou mais mercados**. O terreno comparável existe.

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
4. **Super ABC:** reconhecer pela API da loja (`coletor_vip.py`: o robô saiu em 25/11/2026; só embalado? há corte a peso?) e decidir se entra.
5. **Ligar na carga**, com a mesma cautela (OK explícito; uma coleta só com as outras listas, porque a gravação apaga o resto do mercado). Custo estimado: ~30 termos a mais na coleta por API (poucos segundos) e, se o Super ABC participar, ~30 buscas a mais do robô (as 28 do hortifrúti somaram uns 2 minutos à carga).

## O que precisa ser decidido

- **Escopo da primeira rodada.** Sugestão: frango (inteiro, peito, coxa e sobrecoxa), carne moída, os cortes populares (patinho, acém, coxão mole, músculo, alcatra, fraldinha, picanha, contra filé), linguiça, bacon, presunto, mussarela, queijo prato, queijo minas e parmesão. Peixe, cordeiro, cortes premium e salame ficam para depois.
- **O premium entra?** Sugestão: entra, mas **separado por chave** (faixa "premium"), para nunca disputar o "mais barato" com o comum.
- **Congelado entra?** Sugestão: entra, também separado por chave.

## Limites do reconhecimento

- Foi **uma coleta de um dia** e a classificação por tipo foi feita por expressões no nome, só para dimensionar; a regra de verdade nasce na etapa 2, com casos reais.
- **Super ABC:** o robô falhou em todas as tentativas de abrir a lista de unidades durante o reconhecimento (as 6 primeiras buscas, de manhã cedo; o site respondia, mas o botão de unidades não ficou visível). É o mesmo erro intermitente de sempre (veja [`robos.md`](robos.md)); o reconhecimento do ABC fica para repetir em outro horário.
