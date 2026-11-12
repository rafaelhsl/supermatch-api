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

### Quais mercados aparecem em cada cidade

Os mercados nem sempre entregam na cidade toda. O site usa a tabela de [`entrega_por_cidade.md`](entrega_por_cidade.md) (levantada com os robôs, em CEPs reais) e mostra só o que entrega na cidade do CEP:

- **Entrega:** o mercado aparece normalmente.
- **Só em parte** (a entrega depende do bairro): o mercado aparece, com a marca "Só em parte da cidade" na barraca, um aviso fixo sob as barracas, um aviso no cupom dele e, quando é o mais barato, um aviso no painel principal. O site não tem como saber o bairro, então manda a pessoa conferir no site do mercado.
- **Não entrega:** o mercado some da tela (barracas, resultados, comparação). Produto vendido só por mercados que não entregam ali também some.
- **Nenhum mercado entrega** (hoje, Igarapé): o CEP é recusado com "Não há dados para o CEP inserido. Nenhum dos mercados que acompanhamos entrega em Igarapé/MG por enquanto."
- Antes de informar o CEP, as quatro barracas aparecem. Ao trocar de cidade, tudo se refaz sem recarregar.

A tabela mora dentro de `site/index.html` (bloco `ENTREGA_POR_CIDADE`, entre `@entrega-inicio` e `@entrega-fim`) e **não se edita à mão**: `python levantar_entrega.py --relatorio` reescreve o bloco a partir de `dados/entrega_por_cidade.json`. `node tests/test_entrega.js` falha se o site ficar desatualizado em relação ao levantamento.

## Produto exato e produto equivalente

- **Exato** (padrão): cada resultado é um produto específico (marca e tamanho), como a API agrupa. Um mercado que não vende exatamente esse produto fica sem preço.
- **Equivalente**: cada resultado é um **tipo de produto num tamanho**, de qualquer marca (por exemplo, "Arroz branco tipo 1, 5 kg"). Em cada mercado entra o produto que sai mais barato, já considerando o preço de atacado da quantidade pedida. O cartão mostra qual produto entra em cada mercado, e o cupom diz "Qualquer marca. Leva: …".

A lista pode misturar itens exatos e equivalentes. Trocar de modo não consulta a API de novo: o site reagrupa o que a busca já trouxe. Como o agrupamento é feito sobre o resultado da busca, vale buscar pelo tipo ("arroz"), não pela marca.

### Como se decide o que é equivalente

A regra mora na **API** ([`equivalencia.py`](../equivalencia.py)), não no site: cada produto de `/comparar` já vem com `chave_equivalencia` e `rotulo_equivalencia`, e o site só junta os que têm a mesma chave. Cada família diz o que **diferencia** um produto do outro (leite desnatado não é integral; vinagre de maçã não é de álcool); marca e embalagem não contam. O tamanho (g, kg, ml, L) sempre conta. A tabela das famílias, como acrescentar uma e como conferir estão em [`equivalencia.md`](equivalencia.md).

No site:

- **Sem chave, sem equivalente.** O produto que a API não marcou só aparece no modo exato. Juntar de menos é seguro; juntar o que não é equivalente engana a pessoa.
- **A mensagem "Nenhum produto equivalente para …"** lista as famílias que a API mandou em `equivalencia_familias`.
- **API antiga.** Se a resposta não traz `equivalencia_familias`, o site usa o motor reserva que ainda tem (bloco `@equivalencia-inicio` / `@equivalencia-fim`, só com arroz, feijão, óleo, café, manteiga, açúcar, macarrão, detergente, sabão, amaciante e papel higiênico) e a mensagem volta a citar essas 11. A chave dos dois motores é a mesma nessas 11, então a lista guardada no navegador vale nos dois casos.
- **Preço muito abaixo do normal sai do grupo.** Em grupos com 5 produtos ou mais, um preço abaixo de 45% da mediana é tratado como erro de coleta (já apareceu feijão de 1 kg a R$ 0,78). O modo equivalente escolhe o mais barato de cada mercado, então um erro desses falsearia a comparação inteira. No modo exato o preço continua aparecendo.

Para conferir: `python tests/test_equivalencia.py` (regras, precisa de Python) e `node tests/test_equivalencia.js` (agrupamento no site, precisa do Node). Os casos vêm de nomes reais dos mercados.

## Resultados que só citam a palavra

A API esconde o produto que apenas cita a palavra buscada ("Condicionador com Arroz Preto" ao buscar "arroz") quando há
produtos suficientes que são do que foi buscado (veja [`banco_de_dados.md`](banco_de_dados.md#como-os-dados-saem)). O site
conta isso numa nota tracejada logo abaixo do título dos resultados:

- **"13 produtos que apenas citam “arroz” foram ocultados."**, com o botão **Mostrar também**. O botão refaz a busca com
  `todos=1`; a nota passa a **"Mostrando também 13 produtos que apenas citam “arroz”."**, com o botão **Ocultar de novo**.
  Uma busca nova volta a esconder. O foco do teclado vai para o botão novo.
- O número **só conta os mercados que entregam na cidade** do CEP (o Super ABC, por exemplo, não entrega fora de BH e Betim),
  para bater com o que a tela pode mostrar. Se tudo o que foi escondido é de mercado que não entrega ali, não há nota.
- Quando a busca passa do teto de 400 resultados: **"Há mais N produtos além dos mostrados. Digite mais palavras para refinar a busca."**,
  sem botão.
- Com uma API sem esses campos (antiga), não aparece nota nenhuma.
- O texto da nota é escapado: um termo digitado com HTML aparece como texto.

O texto e as contas ficam em `notasDaBusca` (bloco `@ocultos-inicio` / `@ocultos-fim` de `site/index.html`), testado por
`node tests/test_ocultos.js`.

## Preços da lista

A lista fica salva no navegador, e os preços mudam todo dia (os robôs atualizam o banco uma vez por dia). Por isso o site **busca os preços de hoje** dos itens da lista:

- **Quando:** ao abrir a página e ao voltar a ela (a aba que estava em segundo plano), para os itens cuja consulta tem mais de 3 horas. Itens salvos antes dessa versão não têm a hora `em` e são atualizados na primeira abertura. O item que acabou de ser adicionado já tem preço de agora e não é consultado.
- **Como:** uma consulta à API por termo (o campo `termo` que cada produto traz; num item antigo, a primeira palavra do nome), no máximo 3 ao mesmo tempo. Itens do mesmo termo dividem a consulta.
- **O que muda:** só as opções de compra, com os preços. O nome, a quantidade e a escolha exato/equivalente do item não mudam, então a lista não "troca" o produto por outro nem duplica itens. O item exato é achado pelo código de barras (o nome do grupo pode mudar de um dia para o outro) e, sem ele, pelo nome; o equivalente é achado pela chave de equivalência.
- **Quando não dá:** se o produto não aparece mais, ou a API não responde, o item mantém o último preço. O cupom diz "Atualizando os preços…" enquanto consulta, e depois "N itens sem preço novo: ficou o último que a lista tinha" ou "Não deu para atualizar os preços agora".
- Dá para mexer na lista (mudar quantidades, remover) enquanto a atualização acontece.

- **Identidade do item.** Cada produto exato é identificado pelo `id_do_grupo` que a API manda (o código de barras; com o tamanho quando dois grupos dividem o código). O nome do grupo é o do primeiro produto que entrou nele e muda de um dia para o outro, então por nome o mesmo produto podia aparecer fora da lista ("Adicionar" de novo) e entrar duas vezes. Sem código de barras (cerca de 11% dos grupos, os do Super ABC), o id continua sendo o nome. Um item guardado antes recebe o id na primeira atualização; se isso fizer dois itens virarem o mesmo produto, o site os junta somando as quantidades.

O código fica nos blocos `@lista-inicio` / `@lista-fim` (decisões puras: o id do grupo, quais itens estão velhos, qual termo consultar, qual grupo da resposta é o mesmo item, juntar repetidos) e em `atualizarPrecosDaLista`. `node tests/test_lista.js` confere a atualização dos preços e `node tests/test_id_do_grupo.js` confere o identificador e a junção de repetidos.

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

`localStorage`: `sm_cep`, `sm_cidade`, `sm_modo` (exato ou equivalente) e `sm_lista` (a lista: cada item guarda o grupo com os preços da última vez que foi consultado, a quantidade e a hora `em` dessa consulta). Na primeira visita, o site também lê `user_cep` e `user_cidade`, que eram da versão anterior; sem a cidade guardada, o CEP é pedido de novo.

## Limitações conhecidas

- **Preços da lista são atualizados ao abrir a página.** Veja "Preços da lista" abaixo. Quando a API está fora do ar, ou o produto saiu do catálogo, o item fica com o último preço que a lista tinha e o cupom avisa; a data dele, "Preços de …", é a do preço mais antigo.
- **A entrega é decidida por cidade, mas o Atacadão (e talvez os outros) decide por bairro.** Onde o levantamento deu resultados diferentes dentro da cidade, o site só avisa ("Só em parte da cidade"). Uma amostra mais densa de CEPs (um por faixa de CEP) diria o bairro exato. A amostra atual tem de 2 a 9 CEPs por cidade.
- **O Super ABC aparece só em BH e Betim**, porque só tem unidade lá; uma unidade vizinha pode entregar em outras cidades, mas o site dele não deixa conferir.
- **O Apoio muda de catálogo conforme a região** (canal de vendas); a carga diária usa o canal de Betim.
- **Equivalência é por regras sobre o nome.** Cobre 52 tipos de produto (arroz, feijão, leites, iogurte, farinhas, enlatados, azeite, água, carnes processadas, fralda, absorvente, pipoca, caldo…; lista em [`equivalencia.md`](equivalencia.md)), 44% do catálogo. Higiene pessoal e bebidas ficam de fora de propósito. Para os outros produtos, só o modo exato funciona.
- A busca prioriza o que é do produto digitado: "óleo" não traz mais óleo capilar nem sardinha em óleo quando há óleos de cozinha suficientes (ver [`banco_de_dados.md`](banco_de_dados.md#como-os-dados-saem)). O site conta quantos resultados ficaram de fora e deixa mostrá-los (veja "Resultados que só citam a palavra").
