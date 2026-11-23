# Site

O site é **um arquivo só**, `site/index.html`, com HTML, CSS e JavaScript juntos (mais a pasta `site/fonts/`, com as letras, e a imagem `site/og.png`). Não tem etapa de montagem nem biblioteca, e não pede nada ao Google: as fontes são daqui. Para publicar, suba esse arquivo no Netlify (o repositório não está ligado a ele, então é manual).

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
- **O site não adivinha pelo nome.** Se a API não manda as chaves (resposta sem `equivalencia_familias`), o modo equivalente não junta nada e a mensagem diz que a comparação por equivalência não está disponível agora; o modo exato segue normal. A chave das 11 primeiras famílias é a mesma que o site calculava antes de a regra ir para a API, então as listas guardadas no navegador continuam valendo.
- **Preço muito abaixo do normal sai do grupo.** Em grupos com 5 produtos ou mais, um preço abaixo de 45% da mediana é tratado como erro de coleta (já apareceu feijão de 1 kg a R$ 0,78). O modo equivalente escolhe o mais barato de cada mercado, então um erro desses falsearia a comparação inteira. No modo exato o preço continua aparecendo.

Para conferir: `python tests/test_equivalencia.py` (as regras, precisa de Python) e `node tests/test_agrupamento.js` (o agrupamento por chave no site, precisa do Node). Os casos vêm de nomes dos mercados.

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

## Selo "caiu X% em 7 dias"

Quando a API marca uma opção de compra com `queda_preco` (o preço do varejo caiu 5% ou mais em relação ao de 7 dias antes; veja [`historico_de_precos.md`](historico_de_precos.md#o-selo-caiu-x-em-7-dias)), o site mostra:

- **no quadro do mercado** (a "pílula" de cada cartão de produto), um selo verde "↓ Caiu 47% em 7 dias" e, embaixo, "Era R$ 14,99". Aparece em qualquer mercado que tenha caído, não só no mais barato. O quadro amarelo do mais barato continua amarelo;
- **na linha do cupom**, "↓ Caiu 47% em 7 dias (era R$ 14,99)" embaixo do nome. Quando o cupom cobra o **preço de atacado** (a quantidade alcançou o mínimo), o selo não aparece, porque a queda era do preço do varejo.

O site **não confia cegamente na marca**: `quedaDaOpcao` (bloco `@queda-inicio` / `@queda-fim`) refaz o percentual com o preço de antes e o preço que ele mesmo mostra, e some com o selo se o preço mostrado não for mais menor que o de antes (um item velho da lista guardada no navegador, por exemplo). Resposta de uma API sem o campo não gera selo. O verde (`--queda`) tem contraste de 5,8:1 a 6,1:1 sobre o fundo do selo, e a seta é só enfeite (`aria-hidden`): o leitor de tela ouve "Caiu 47% em 7 dias" e "Era R$ 14,99". Em tela estreita (320 px) o selo quebra em duas linhas, "Caiu 47%" e "em 7 dias".

`node tests/test_queda.js` confere a regra do site e `python tests/navegador/test_site_queda.py` confere a tela (celular, celular estreito e computador).

## Aviso de preço velho

Os preços vêm da carga diária (07:30 de Brasília; a de reserva do GitHub às vezes atrasa umas horas). Um preço com **até 36 horas** de idade é normal. Passou disso, a coleta de um dia não veio e o site avisa, na busca ("Atenção: Estes preços são de 16/11 (há 3 dias): a atualização mais recente ainda não chegou. Confira no site do mercado antes de comprar.") e no cupom, com a data de Brasília. Vale o preço **mais antigo da tela**: um mercado em dia e outro atrasado avisam, com a data do atrasado. Data ilegível ou no futuro (relógio errado) não avisa.

O limite (`PRECO_VELHO_HORAS = 36`) e a regra (`avisoDePrecoVelho`) estão no bloco `@preco-velho-inicio` / `@preco-velho-fim`. `node tests/test_preco_velho.js` confere a regra e `python tests/navegador/test_site_preco_velho.py` confere a tela (datas calculadas a partir de agora: 3, 24 e 35 h não avisam; 37 h e 3 dias avisam). Para o dono, a falha de uma carga continua chegando por e-mail do GitHub; este aviso é o que a **pessoa que usa o site** vê. Os preços de uma lista guardada também passam por aqui: o cupom usa a data mais antiga da lista.

## Fontes

As três fontes (**Unbounded** nos títulos, **Hanken Grotesk** no texto e **Martian Mono** no cupom) ficam em `site/fonts/` e são declaradas por `@font-face` no começo do CSS de `site/index.html`. Até 23/11/2026 vinham do Google Fonts, que recebia o endereço IP de cada visitante; hoje o site não pede nada ao Google.

- **Os arquivos** (`hanken-grotesk-latin-v1.woff2`, `martian-mono-latin-v1.woff2`, `unbounded-latin-v1.woff2`, 109 KB no total, o mesmo peso de antes) são **exatamente os que o Google entregava a um navegador**: fontes variáveis, só o subconjunto "latin" (o português inteiro cabe nele: todo caractere do site está lá). Antes de trocar, comparei o site com as fontes do Google e com estas, pixel a pixel, em 3 larguras de tela e 4 estados (primeira visita, aviso de privacidade, resultados, cupom): **0 pixels de diferença**. As declarações são as mesmas que o Google mandava: um bloco por peso e o mesmo intervalo de caracteres.
- **Licença:** as três são **OFL 1.1** (podem ser redistribuídas desde que a licença vá junto): o texto de cada uma está ao lado, em `site/fonts/OFL-*.txt`.
- **As duas da primeira tela** (Unbounded e Hanken Grotesk) são pré-carregadas (`<link rel="preload">`); a Martian Mono, só do cupom, carrega quando precisa. `font-display: swap`: o texto aparece na hora com a fonte do sistema e troca quando a fonte chega.
- **Cache de um ano** (`netlify.toml`, cabeçalho para `/fonts/*`): por isso **o nome do arquivo leva a versão** (`-v1`). **Para trocar uma fonte, grave o arquivo novo com `-v2` no nome e mude o `@font-face` e o `preload`**; com o mesmo nome, quem já visitou continuaria vendo a antiga por um ano. `tests/test_fontes.py` confere o padrão do nome.
- **Atenção ao baixar fonte do Google no futuro:** o mesmo endereço entrega arquivos diferentes conforme quem pede (uma versão com os pesos cortados, mais leve e com serrilhado um pouco diferente, e a versão inteira que o navegador recebe). As que estão aqui são as do navegador, por serem as que dão 0 pixels de diferença.
- **A imagem de divulgação** (`docs/og/og.html`) usa os mesmos arquivos, então refazê-la não precisa de internet.
- `python tests/test_fontes.py` confere os arquivos, as licenças, que cada peso pedido pelo CSS existe, o preload e o cache; `python tests/navegador/test_site_fontes.py` abre o site **com o Google bloqueado** e confere que as três famílias carregam, cada arquivo uma vez só, sem nenhum pedido ao Google.

## Pré-visualização do link (tags OG)

Quando o link é compartilhado (WhatsApp, Instagram, Facebook, X, Telegram), quem monta a prévia lê as tags `og:*` do `<head>` e a imagem `site/og.png` (1200 x 630, ~70 KB): o título, a descrição e um toldo listrado com as cores dos quatro mercados, o título do site e a placa amarela "Mais barato", **sem preço nenhum** (a imagem não promete um valor que o site não confirma).

- **O endereço é um só e absoluto**, nas três tags `canonical`, `og:url` e `og:image` (`https://spontaneous-hamster-cd3133.netlify.app`). Quem monta a prévia não roda o site, então não dá para calcular isso por JavaScript. **Se o site ganhar um domínio próprio, troque os três** (e o `tests/test_og.py` confere que continuam iguais).
- **Refazer a imagem:** edite `docs/og/og.html` (a fonte: cores e letras do site) e rode `python docs/og/gerar_og.py`. Confira o resultado antes de publicar.
- **Depois de publicar,** as redes guardam a prévia antiga por um tempo. Para forçar a atualização: no Facebook, o [Depurador de Compartilhamento](https://developers.facebook.com/tools/debug/) ("Buscar novas informações"); no WhatsApp, compartilhar o link com um parâmetro novo (`?v=2`) mostra a prévia nova.
- `python tests/test_og.py` confere as tags, que a imagem existe, tem 1200 x 630 e menos de 300 KB, e que os endereços batem.

## Privacidade do CEP

O rodapé tem o link "Privacidade e seus dados", e a janela do CEP diz para que ele serve e leva ao mesmo aviso ("Como tratamos seus dados"). A janela diz o que fica no aparelho, para onde o CEP vai (BrasilAPI, ViaCEP e a nossa API) e o que os serviços de hospedagem veem, e tem o botão "Apagar meus dados deste aparelho" (`esquecerTudo`: apaga as chaves `sm_...` e as da versão anterior). O que cada frase afirma, o que a garante (a API só escreve os 5 primeiros dígitos do CEP no log), quem responde (nome e e-mail para dúvidas) e o que ainda falta decidir (fontes do Google, retenção) estão em [`privacidade.md`](privacidade.md). `node tests/test_privacidade.js` trava os endereços externos do site contra o aviso, e `python tests/navegador/test_site_privacidade.py` confere a tela.

## Preço por quilo (hortifrúti)

A API manda `unidade: "kg"` na opção de compra quando **o preço é por quilo** (frutas, verduras e legumes vendidos a peso; veja [`hortifruti.md`](hortifruti.md)). Sem avisar, "Tomate Italiano 500g: R$ 18,99" seria lido como o preço da bandeja, e é o do quilo. Só a unidade exatamente `kg` conta; `un`, vazio, ausente (API antiga, item guardado antes, robô do Super ABC, que não a informa) ou qualquer outro valor é um produto comum, **exatamente como era**.

- **no quadro do mercado**, "R$ 7,99/kg": o "/kg" vem em corpo menor ao lado do preço (`.por`), na cor do texto secundário (e no quadro amarelo do mais barato, no marrom escuro do selo de atacado). O leitor de tela lê "R$ 7,99/kg";
- **o nome do item não mostra o peso da porção.** Em item por quilo, o "500g" do nome ("Batata Doce Roxa 500g") é o da porção que o mercado vende por vez, não a base do preço: o Supernosso mostra "R$ 7,99 /kg" e, ao lado, "R$ 4,00" pela porção, e avisa que o peso varia e o preço final sai da pesagem. Mostrar "500g" junto de "/kg" parecia contradição (e a pessoa podia ler o preço como o do pacote); por isso o título, os botões e o cupom dizem "Batata Doce Roxa". Em todos os 50 itens por quilo com peso no nome da coleta de 17/11, o peso é o do múltiplo de compra do mercado. Pacote (`un`) e produto comum mantêm o peso, que aí é do pacote (`semPesoDaPorcao`, `nomeDaOpcao`);
- **no cartão**, "1 kg na lista" no lugar de "1 na lista", e os botões dizem "Tirar 1 kg de…" e "Colocar mais 1 kg de…". Num item por quilo, cada passo da lista é **1 kg**;
- **no cupom**, o controle mostra "2 kg" e a linha diz sempre "2 kg × R$ 7,99/kg" (também com 1 kg), porque o nome do produto cita a bandeja ("500g") e o preço é do quilo. O subtotal é quilos × preço do quilo. No mercado que não vende o item, a linha "sem preço" também fala em quilos. Com item por quilo na lista, o cupom avisa: "Itens por quilo: o valor final sai da pesagem no [mercado], então pode variar um pouco." O **cabeçalho do cupom** conta quilos e unidades à parte, porque não se somam: "2 itens, 3 unidades e 2 kg"; só quilos, "1 item, 1 kg"; só produtos comuns, "2 itens, 3 unidades", como sempre.

A decisão do quadro é **da opção** (cada mercado diz o seu), a do cartão e a do cupom é **do grupo**: basta uma opção por quilo. No modo equivalente, a bandeja de 1 kg de um mercado (`un`) divide o cartão "Banana prata, 1 kg" com o preço por quilo de outro, porque a chave de equivalência as trata como o mesmo quilo ([`equivalencia.md`](equivalencia.md)); o quadro da bandeja não ganha "/kg" (é o preço do pacote), mas a lista conta em quilos e o cupom escreve "1 kg × R$ 6,49/kg", que é a mesma conta.

O código fica no bloco `@unidade-inicio` / `@unidade-fim` (`porQuilo`, `grupoPorQuilo`, `passoDaLista`, `quantidadeNaLista`, `quantidadesDaLista`, `textoDasQuantidades`). `node tests/test_unidade.js` confere a regra e `python tests/navegador/test_site_hortifruti.py` confere a tela (celular, celular estreito e computador): o "/kg" só onde o preço é por quilo, o contraste (mínimo 4,5:1), a conta do cupom (2 kg × R$ 7,99 = R$ 15,98), o mercado que não vende o item, o modo equivalente e a API antiga, sem o campo.

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
