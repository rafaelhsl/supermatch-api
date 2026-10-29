# Site

O site é **um arquivo só**, `site/index.html`, com HTML, CSS e JavaScript juntos. Não tem etapa de montagem nem biblioteca; só carrega as fontes do Google Fonts. Para publicar, suba esse arquivo no Netlify (o repositório não está ligado a ele, então é manual).

## O que a pessoa faz

1. Informa o CEP. A cidade vem da BrasilAPI (com a ViaCEP de reserva) e serve só para mostrar "Betim/MG" no topo.
2. Busca um produto e adiciona à **lista**. A lista é uma só: o site soma, para cada mercado, o preço de todos os itens.
3. Vê o total de cada mercado nas **barracas** e, no **cupom**, o detalhe do mercado escolhido. O mais barato leva o carimbo.

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

`localStorage`: `sm_cep`, `sm_cidade` e `sm_lista` (a lista com os preços do momento em que cada item foi adicionado). Na primeira visita, o site também lê `user_cep` e `user_cidade`, que eram da versão anterior.

## Limitações conhecidas

- **Preços da lista envelhecem.** Ficam salvos como estavam quando o item entrou na lista, e os robôs atualizam o banco uma vez por dia. O cupom informa a data do preço mais antigo dele, mas ainda não busca preços novos ao reabrir a página.
- **O CEP ainda não define quais mercados entregam.** Só serve para escolher a UF. O texto do site foi escrito para não prometer isso.
- **Produtos específicos demais** (marcas diferentes) deixam poucos mercados com a lista completa. Falta aceitar produtos equivalentes.
- A busca por "óleo" ainda traz óleo capilar; a sugestão da tela já usa "óleo de soja".
