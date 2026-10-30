# Site

O site é **um arquivo só**, `site/index.html`, com HTML, CSS e JavaScript juntos. Não tem etapa de montagem nem biblioteca; só carrega as fontes do Google Fonts. Para publicar, suba esse arquivo no Netlify (o repositório não está ligado a ele, então é manual).

## O que a pessoa faz

1. Informa o CEP. A cidade vem da BrasilAPI (com a ViaCEP de reserva) e precisa ser uma das cidades atendidas (veja abaixo).
2. Escolhe como comparar, **Produto exato** ou **Produto equivalente**, busca um produto e adiciona à **lista**. A lista é uma só: o site soma, para cada mercado, o preço de todos os itens.
3. Vê o total de cada mercado nas **barracas** e, no **cupom**, o detalhe do mercado escolhido. O mais barato leva o carimbo.

## Cidades atendidas

Belo Horizonte, Betim, Brumadinho, Contagem, Esmeraldas, Ibirité, Igarapé, Nova Lima, Ribeirão das Neves, Sabará, Santa Luzia, São Joaquim de Bicas, Sarzedo e Vespasiano (todas em MG). A lista é a constante `CIDADES_ATENDIDAS` em `site/index.html`.

- CEP de outra cidade ou de outro estado é recusado com "Não há dados para o CEP inserido", dizendo em qual cidade o CEP fica e mostrando a lista das cidades atendidas.
- Um CEP já guardado no navegador é conferido de novo ao abrir a página; se a cidade não é atendida (ou não está guardada), a pessoa informa o CEP outra vez.
- A regra vale só no site. A API continua respondendo para qualquer CEP de MG.

## Produto exato e produto equivalente

- **Exato** (padrão): cada resultado é um produto específico (marca e tamanho), como a API agrupa. Um mercado que não vende exatamente esse produto fica sem preço.
- **Equivalente**: cada resultado é um **tipo de produto num tamanho**, de qualquer marca (por exemplo, "Arroz branco tipo 1, 5 kg"). Em cada mercado entra o produto que sai mais barato, já considerando o preço de atacado da quantidade pedida. O cartão mostra qual produto entra em cada mercado, e o cupom diz "Qualquer marca. Leva: …".

A lista pode misturar itens exatos e equivalentes. Trocar de modo não consulta a API de novo: o site reagrupa o que a busca já trouxe. Como o agrupamento é feito sobre o resultado da busca, vale buscar pelo tipo ("arroz"), não pela marca.

### Como o site decide o que é equivalente

As regras ficam em `FAMILIAS`, no bloco `@equivalencia-inicio` / `@equivalencia-fim` de `site/index.html`. Cada família diz o que **diferencia** um produto do outro; marca, embalagem e perfume não contam. O tamanho (g, kg, ml, L) sempre conta.

| Família | O que diferencia |
|---|---|
| Arroz | variedade (branco/agulhinha, parboilizado, integral, arbório, japonês, para risoto, quebrado) e tipo (1, 2, fora de tipo; sem tipo no nome conta como tipo 1) |
| Feijão | variedade (carioca, preto, branco, fradinho, jalo, vermelho, roxo, rajado, de corda) e tipo |
| Óleo | soja, girassol, milho, canola, algodão ou composto de soja e oliva |
| Café | forma (em pó, solúvel, em grãos, com leite) e força (tradicional, extraforte, gourmet, descafeinado, liofilizado) |
| Manteiga | com sal ou sem sal (obrigatório no nome), e extra, de búfala ou sem lactose |
| Açúcar | cristal, refinado, demerara, mascavo ou de confeiteiro, e orgânico ou light |
| Macarrão | formato (espaguete, parafuso, penne, linguine, fettuccine…) e massa (com ovos, de sêmola) |
| Detergente | líquido, gel, em pó, em pó para lava-louças |
| Sabão | líquido, em pó, em barra, em pasta, e para roupas delicadas |
| Amaciante | concentrado ou não |
| Papel higiênico | folha (simples, dupla, tripla), metragem e número de rolos |

Princípios:

- **Na dúvida, não junta.** Um produto que não cabe em nenhuma regra só aparece no modo exato. Juntar de menos é seguro; juntar o que não é equivalente engana a pessoa.
- **Fora das regras** ficam cosméticos e outros "óleos", cápsulas de café, macarrão instantâneo, caixas e multipacotes (`24x40g`), açúcar em sachê, produtos de outra categoria que só citam o nome (tempero para feijão, biscoito de arroz) e produtos sem tamanho no nome.
- **Preço muito abaixo do normal sai do grupo.** Em grupos com 5 produtos ou mais, um preço abaixo de 45% da mediana é tratado como erro de coleta (já apareceu feijão de 1 kg a R$ 0,78). O modo equivalente escolhe o mais barato de cada mercado, então um erro desses falsearia a comparação inteira. No modo exato o preço continua aparecendo.
- Famílias novas: acrescente uma entrada em `FAMILIAS` e casos em `tests/test_equivalencia.js`.

Para conferir as regras: `node tests/test_equivalencia.js` (precisa do Node). Os casos vêm de nomes reais dos mercados.

## Regras da comparação

- Um mercado que não vende algum item da lista fica **incompleto**: seu total é parcial, aparece como "falta N itens" e ele nunca é apontado como o mais barato.
- Ranking: mercados completos primeiro, do menor para o maior total; depois os incompletos.
- O preço de atacado vale quando a quantidade na lista alcança `quantidade_atacado`.
- O cupom mostra 3 itens, mais os que o mercado aberto não vende, e o botão "Mostrar tudo".

## Como conversa com a API

- `GET /saude` ao abrir a página: acorda o servidor do Render, que dorme após 15 minutos. A primeira busca depois disso pode levar cerca de 1 minuto; a tela avisa depois de 8 segundos.
- `GET /comparar?cep=<8 dígitos>&item=<texto>`: devolve `carrinho_comparativo`, uma lista de `{ produto_base, opcoes_de_compra: [{ supermercado, nome, preco_varejo, preco_atacado, quantidade_atacado, atualizado_em, ... }] }`. A API usa o CEP só para descobrir a UF.
- Uma busca antiga que responde depois de uma nova é descartada. Resposta de erro do servidor aparece como "Não deu para consultar", e não como "Nada encontrado".

## O que fica no navegador

`localStorage`: `sm_cep`, `sm_cidade`, `sm_modo` (exato ou equivalente) e `sm_lista` (a lista com os preços do momento em que cada item foi adicionado). Na primeira visita, o site também lê `user_cep` e `user_cidade`, que eram da versão anterior; sem a cidade guardada, o CEP é pedido de novo.

## Limitações conhecidas

- **Preços da lista envelhecem.** Ficam salvos como estavam quando o item entrou na lista, e os robôs atualizam o banco uma vez por dia. O cupom informa a data do preço mais antigo dele, mas ainda não busca preços novos ao reabrir a página.
- **O CEP decide se a cidade é atendida, mas ainda não quais mercados entregam nela.** O site mostra os quatro mercados em todas as 14 cidades, e isso nem sempre é verdade: o Super ABC só tem unidade em BH e Betim, e o Atacadão atende só parte de várias cidades. O levantamento de quem entrega onde está em [`entrega_por_cidade.md`](entrega_por_cidade.md) (gerado por `levantar_entrega.py`); falta o site usá-lo. O Apoio também muda de catálogo conforme a região.
- **Equivalência é por regras.** Cobre as 11 famílias que o banco tem hoje. Para outros produtos, só o modo exato funciona.
- A busca por "óleo" ainda traz óleo capilar no modo exato; a sugestão da tela usa "óleo de soja".
