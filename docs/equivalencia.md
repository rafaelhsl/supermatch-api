# Produto equivalente

No modo **Produto equivalente** do site, cada resultado é um **tipo de produto num tamanho**, de qualquer marca ("Leite integral, 1 L"). Em cada mercado entra o produto que sai mais barato. Esta página explica como a API decide o que é equivalente e como acrescentar um tipo novo. Como o site mostra isso à pessoa, veja [`site.md`](site.md).

## Onde fica

O motor é [`equivalencia.py`](../equivalencia.py). A API ([`api_supabase.py`](../api_supabase.py)) calcula a chave de **cada produto** ao carregar o catálogo (menos de 1 s para os ~8 mil produtos) e a devolve junto com o produto, em `/comparar`:

| Campo | Onde | O que é |
|---|---|---|
| `chave_equivalencia` | em cada opção de compra | Texto que identifica "tipo + tamanho" (por exemplo, `sal\|refinado\|1000g`). Produtos com a mesma chave são equivalentes. |
| `rotulo_equivalencia` | em cada opção de compra | O nome do grupo para a pessoa ("Leite integral, 1 L"). |
| `equivalencia_familias` | na resposta | Os tipos de produto que o motor conhece, na ordem em que foram declarados. O site os lista na mensagem "Nenhum produto equivalente para …". |

Produto que não cabe em nenhuma família **não leva** os dois primeiros campos. O site só agrupa o que tem chave; esses produtos aparecem no modo exato.

Nada disso mexe no banco: a chave é calculada na API, a cada recarga do catálogo (a cada hora, em segundo plano). Uma regra nova vale assim que a API é publicada, sem recarregar os dados.

O site **não tem regra própria**: só junta os produtos que chegam com a mesma chave (bloco `@equivalencia-inicio` de `site/index.html`). Sem as chaves, o modo equivalente avisa que não está disponível. Até o PR #32 o site tinha um motor próprio, com as 11 primeiras famílias; foi removido depois que a API passou a decidir.

## Como decide

Cada família diz o que **diferencia** um produto do outro (leite desnatado não é integral; vinagre de maçã não é de álcool) e o que não importa (marca, embalagem, "caixa com tampa"). O **tamanho** (g, kg, ml, L) sempre conta. A primeira família que casa com o nome decide; por isso as mais específicas vêm antes ("leite condensado" antes de "leite").

- **Na dúvida, não junta.** O que não cabe em nenhuma regra fica sem chave. Juntar de menos é seguro; juntar o que não é equivalente engana a pessoa.
- Vira "fora" o produto sem tamanho no nome, a caixa ou o multipacote (`24x40g`, `kit`, `2 unidades`, `leve 3`) e o produto de outra categoria que só cita o nome (tempero para feijão, biscoito de arroz).
- Uma dimensão **obrigatória** sem resposta no nome também deixa o produto de fora. Exemplo: margarina sem "com sal" ou "sem sal" no nome não é comparável, porque não dá para saber.
- O que não aparece no nome não conta: dois leites iguais, um deles com "Zero Lactose" só na embalagem, ficam juntos.

## Famílias

As 11 primeiras vieram do site e foram traduzidas sem mudar o resultado: nos 7.836 produtos do catálogo de 09/11/2026, o motor em JavaScript (hoje removido do site) e o de Python deram a **mesma chave e o mesmo rótulo** em todos os 981 que o JavaScript cobria. Por isso as listas de compras já guardadas no navegador continuam valendo.

| Família | O que diferencia |
|---|---|
| Arroz | variedade (branco, parboilizado, integral, arbório, japonês, para risoto, quebrado) e tipo (1, 2, fora de tipo; sem tipo no nome conta como tipo 1) |
| Feijão | variedade (carioca, preto, branco, fradinho, jalo, vermelho, roxo, rajado, de corda) e tipo |
| Óleo | soja, girassol, milho, canola, algodão ou composto de soja e oliva |
| Café | forma (em pó, solúvel, em grãos, com leite) e força (tradicional, extraforte, gourmet, descafeinado, liofilizado) |
| Manteiga | com sal ou sem sal (obrigatório no nome), e extra, de búfala ou sem lactose |
| Açúcar | cristal, refinado, demerara, mascavo ou de confeiteiro, e orgânico ou light |
| Macarrão | formato (espaguete, parafuso, penne, linguine, fettuccine…) e massa (com ovos, de sêmola). O instantâneo é outra família |
| Detergente | líquido, gel, em pó, em pó para lava-louças |
| Sabão | líquido, em pó, em barra, em pasta, e para roupas delicadas |
| Amaciante | concentrado ou não |
| Papel higiênico | folha (simples, dupla, tripla), metragem e número de rolos |
| Leite | integral, semidesnatado ou desnatado (obrigatório); sem lactose, A2, orgânico, pasteurizado. Fora: em pó, condensado, achocolatado, sabores, vegetais, fórmulas infantis, com proteína |
| Leite em pó | integral, semidesnatado ou desnatado (obrigatório); sem lactose. Fora: fórmulas e leites infantis, achocolatados, sabores |
| Leite condensado | tradicional, semidesnatado, desnatado ou sem lactose |
| Creme de leite | tradicional, leve, fresco, para bater ou sem lactose |
| Queijo ralado | parmesão, grana ou mix |
| Margarina | com sal ou sem sal (obrigatório); light, vegetal, sem lactose |
| Requeijão | cremoso, cheddar, 4 queijos, culinário, parmesão; light e sem lactose |
| Pão de forma | tradicional, integral, grãos, sem casca, de leite, doce, com sementes e castanhas, sem glúten; zero açúcar e sem lactose |
| Iogurte | forma (colher, grego, líquido), **todos** os sabores ("morango e banana" não é "morango"), gordura, zero açúcar e sem lactose |
| Saco de lixo | litros e quantidade de sacos no pacote; cor e perfume |
| Sal | refinado, grosso, marinho, rosa do Himalaia ou light (obrigatório) |
| Vinagre | de álcool, maçã, vinho tinto, vinho branco, arroz, cereais, balsâmico ou de fruta (obrigatório); colorido, orgânico, concentrado |
| Farinha de trigo | tipo 1, 2, 00 ou integral; com fermento; para pastel, pizza, pães, bolos ou salgados |
| Farinha de mandioca | torrada, crua, temperada ou biju; amarela ou branca; fina ou grossa |
| Fubá | mimoso (fino) ou comum |
| Molho de tomate | tradicional ou sabor (bolonhesa, manjericão, pizza, passata, refogado, napolitana, com ervas…); sem açúcar |
| Extrato de tomate | tradicional, com alho e cebola, strogonoff, picante, com ervas |
| Milho verde, Ervilha | em conserva ou congelado |
| Atum | ralado, sólido, em pedaços ou desfiado, **e** em óleo, ao natural, ao molho ou no azeite (ambos obrigatórios); light |
| Sardinha | ao molho de tomate, em óleo ou ao natural (obrigatório); filé; picante |
| Maionese | tradicional, light, vegana, sem glúten e sabores (alho, ervas, bacon, queijo…) |
| Ketchup | tradicional, picante, light e sabores |
| Azeite de oliva | extra virgem, virgem ou tipo único (obrigatório); intensidade; país de origem |
| Aveia | farelo, farinha, flocos finos ou flocos (obrigatório); sem glúten |
| Fermento em pó | químico em pó (biológico, fresco e instantâneo ficam de fora) |
| Água sanitária | só o volume |
| Água mineral | sem gás ou com gás (obrigatório); alcalina |
| Gelatina | sabor (obrigatório; "sem sabor" e incolor contam como um sabor) e zero açúcar. Fora: gelatina pronta e as balas Fini |
| Chá | **sachê ou folhas**: todas as ervas do nome ("camomila e maracujá") e o peso; **bebida pronta**: sabor, versão (natural, original), zero açúcar e volume. Fora: misturas ("misto"), solúvel, cápsula |
| Salsicha | hot dog, viena, de frango, de peru, defumada, light; peso. Fora: em conserva |
| Linguiça | tipo (toscana, calabresa, mista, de frango, de pernil, costela, paio, portuguesa…, obrigatório), defumada ou cozida, fina, e sabores (bacon, apimentada, alho, queijo); peso |
| Hambúrguer | bovino, de frango, suíno ou misto (obrigatório), e angus, picanha, costela, bacon, queijo, fit, defumado; peso. Fora: vegetal |
| Papel toalha | rolo ou interfolhas, folha simples ou dupla, rolos e folhas (ver "Limites") |
| Fralda | tamanho (RN a XXXG), calça ou comum, linha premium e quantidade de fraldas. Fora: geriátrica, de pano e sem tamanho ou quantidade no nome |
| Absorvente | externo, interno ou protetor diário; com ou sem abas; suave, seca ou em gel; noturno ou dia e noite; tamanho; plus, ultrafino, longo, premium; quantidade. Fora: pacote com "grátis N" |
| Macarrão instantâneo | formato (lámen em pacote, copo "Cup Noodles", yakissoba, talharim), **sabor** (obrigatório: galinha, galinha caipira, frango assado, carne, carne defumada, bacon, calabresa, picanha, costela, tomate, cheddar, nacho, parmegiana, bolonhesa, tradicional…), picante ou suave; peso do pacote. Fora: espaguete instantâneo sem tempero |
| Achocolatado | em pó, granulado ou flocos crocantes; light, menos açúcar, 60% cacau, proteína, com malte, Alpino, sem lactose, vegano; peso. Fora: cápsulas e os líquidos (em ml) |
| Geleia | **sabor** (obrigatório: morango, amora, frutas vermelhas, damasco, goiaba, uva, pimenta…), zero açúcar, gourmet, polonesa, agridoce; peso. Fora: geleia de mocotó e a sem sabor no nome |
| Pipoca | de micro-ondas, pronta ou **milho para pipoca** (o grão). Micro-ondas e pronta pedem o sabor no nome (manteiga, manteiga de cinema, manteiga light, natural, bacon, cheddar, queijo, doce, temperada); o grão separa o premium; peso. Fora: saco de pipoca de festa, pipoqueira |
| Caldo | sabor (obrigatório: galinha, galinha caipira, carne, legumes, costela, camarão, peixe, bacon) e menos sal; o peso separa os cubos (57 a 152 g) do pó profissional (1 kg), e "12 cubos" não é multipacote. Fora: Sazón (é tempero) e caldo líquido |

## Como acrescentar uma família

1. Em `equivalencia.py`, dentro de `FAMILIAS += [...]`, acrescente uma chamada a `declarar(id, título, casa=..., exclui=..., dims=[...])`. `casa` diz quando o nome é dessa família; `exclui` tira o que parece mas não é; cada `dim(...)` é uma coisa que diferencia o produto (a primeira regra que casa vale). Se a regra é especial demais, escreva uma função própria, como `_iogurte` e `_saco_de_lixo`.
2. **Ordem importa:** a família mais específica vem antes da geral. Não reordene as 11 primeiras: o teste de paridade depende delas.
3. Escreva os casos em `tests/casos_equivalencia_novos.py`, com **nomes reais** de produtos dos mercados: `juntam` (marcas e embalagens diferentes que são o mesmo produto), `separam` (parecidos, mas diferentes) e `fora`. Toda família nova precisa de pelo menos um caso `juntam`; o teste reclama se faltar.
4. Meça nos dados reais antes de publicar: baixe o catálogo (`/comparar?...&todos=1` por termo, ou direto do banco) e olhe cada grupo comparável. O erro que importa é **juntar o que não é igual** (um "light" com um tradicional); procure nos grupos as palavras que mudam o produto (light, zero, integral, picante, sem lactose, orgânico).

## Testes

- `python tests/test_equivalencia.py`: confere os mesmos casos do teste em JavaScript contra as 11 primeiras famílias (paridade), os casos novos, a lista de famílias e `com_equivalencia`.
- `python tests/test_api_catalogo.py`: a API calcula as chaves ao carregar o catálogo e as devolve na resposta.
- `node tests/test_agrupamento.js`: o agrupamento no site a partir das chaves da API (produto repetido, preço de erro de coleta, ordem).

## Cobertura

No catálogo de 05 a 09/11/2026 (7.836 produtos, 4 mercados):

| | 11 famílias (as do site) | 39 famílias | 47 famílias | 52 famílias |
|---|---|---|---|---|
| Produtos com chave | 981 (12,5%) | 2.606 (33,3%) | 3.161 (40,3%) | 3.458 (44,1%) |
| Grupos | — | 800 | 1.115 | 1.254 |
| Grupos comparáveis (2 mercados ou mais) | 114 | 396 | 521 | 588 |

Iogurte fragmenta de propósito (cada combinação de sabores é um grupo), por isso a cobertura dele é alta e a comparação, menor.

## Limites conhecidos

- A equivalência é por **regras sobre o nome**. Se o mercado omite no nome algo que muda o produto, o motor não tem como saber.
- Produto sem tamanho no nome (ou com medida em unidade não reconhecida) não tem chave.
- **Quantidade de unidades.** Fralda, absorvente e papel toalha pesam em unidades, não em gramas. "Leve 28 Pague 26" vale 28 (o que vem no pacote); "Leve 3 Pague 2" (poucas unidades) são vários pacotes e o produto fica de fora. Nome com "grátis N" também fica de fora, porque não diz quanto vem. No papel toalha, "2 rolos de 120 folhas" e "2 unidades com 60 folhas cada" são folhas por rolo; "2 rolos com 100 folhas" pode ser o total ou por rolo, então só junta com quem escreve do mesmo jeito.
- **Marca e linha.** Em fralda, a linha premium (Premium Care, Supreme Care, Premium Protection) não junta com a comum, mas Pampers, Huggies e Personal da mesma linha juntam. Quem não quer trocar de marca usa o modo exato.
- Fora das famílias declaradas nada é equivalente.
- **Decidido: higiene pessoal e bebidas ficam sem equivalência**, só no modo exato. Shampoo, condicionador, sabonete, desodorante, creme dental, vinho, cerveja, suco, refrigerante e energético somam mais de 2 mil produtos, mas são diversos demais: cheiro, sabor e marca pesam na escolha, e "qualquer marca" enganaria. `tests/casos_equivalencia_novos.py` guarda a decisão (esses nomes têm de ficar em "fora"), para que uma regra futura mais ampla não os junte sem querer. Se a decisão mudar, comece por uma família estreita (por exemplo, creme dental de uma só variante e peso), não pela categoria inteira.
- Candidatos que ainda faltam, em ordem do que há no catálogo: cereal matinal, farofa, biscoito cream cracker e de maisena, ovos. Os que vendem a peso variável (queijo, presunto, frango, carne moída) não cabem: o preço por quilo mudaria a regra.
