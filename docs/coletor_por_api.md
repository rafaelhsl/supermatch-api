# Coletor por API

`coletor_vtex.py` (Apoio Entrega, Atacadão e Supernosso) e `coletor_vip.py` (Super ABC) buscam produtos nas **APIs públicas que os próprios sites usam**, em vez de abrir um navegador e ler a primeira página de cada busca. Cada busca traz até 100 produtos por termo e mercado (os robôs leem de 20 a 30), com **código de barras (EAN)** e, nos três mercados da VTEX, **marca e categoria**, que o robô não consegue ler.

> **Estado:** ligado à carga diária (`alimentar_banco.py`) para os quatro mercados (o Super ABC, desde 25/11/2026). Os coletores em si só leem; quem grava no banco é a carga (veja [`banco_de_dados.md`](banco_de_dados.md) e [`robos.md`](robos.md#a-carga-e-as-falhas)).

O Super ABC trocou de site em novembro de 2026 e é coletado por `coletor_vip.py` (veja [Super ABC](#super-abc-loja-vip-commerce)); ele já não tem robô na carga diária.

## Como rodar

```
python coletor_vtex.py                                  # os 138 termos da carga (100 de produtos + 28 de hortifrúti + 10 de carnes), os 3 mercados
python coletor_vtex.py --termos "arroz,óleo"            # só alguns termos
python coletor_vtex.py --mercados "Atacadao"            # só um mercado
python coletor_vtex.py --saida coleta.json              # guarda as linhas coletadas
python tests/test_coletor_vtex.py                       # testes, sem rede
python coletor_vip.py                                   # o Super ABC, nos mesmos 138 termos
python coletor_vip.py --termos "arroz,óleo"             # só alguns termos
python tests/test_coletor_vip.py                        # testes do Super ABC, sem rede
```

Não precisa instalar nada além do Python. No GitHub: o workflow **Coletor por API** (`coletor-api.yml`) roda os dois coletores sem segredo e sem banco, e guarda `coleta.json` e `relatorio.txt` (VTEX) e `coleta-super-abc.json` e `relatorio-super-abc.txt` (Super ABC) na execução.

## De onde vem cada dado

Sondado em 05/11/2026. Estas APIs não têm contrato: se um site mudar, o coletor falha em voz alta (`ErroDeColeta`) em vez de devolver dado errado.

| Mercado | Fonte | Observações |
|---|---|---|
| **Supernosso** | `/api/catalog_system/pub/products/search/?ft=termo` | 50 produtos por chamada. Só vale o que tem estoque (`AvailableQuantity > 0`). Não tem atacado. O cookie de região não muda nada. |
| **Apoio Entrega** | a mesma API, com `&sc=15` (canal de vendas de Betim) | O atacado é o campo `Quantidade para atacado` do produto, mais o preço dessa quantidade na simulação de carrinho (`POST /api/checkout/pub/orderForms/simulation?sc=15`), que aceita vários itens por chamada. Bate com o que o robô lê. |
| **Atacadão** | GraphQL do site: `/api/graphql?operationName=ProductsQuery`, com a loja de Betim (`atacadaobr167`) | A API de catálogo devolve preço 0 para mais da metade dos produtos (não sabe qual loja) e não traz o atacado. O GraphQL traz as faixas de preço (`offers[].minQuantity`), a marca e a categoria, só do que a loja de Betim vende (para "arroz": 33 itens, contra 647 do catálogo geral). O EAN vem da API de catálogo, ligado pelo `productId`, até 50 por chamada. O campo `gtin` do GraphQL **não** é EAN (é um código interno de 7 a 8 dígitos). |

A loja de Betim do Atacadão sai de `/api/checkout/pub/regions?country=BRA&postalCode=32607600` (vendedor com `name: "Betim"`). Os preços do GraphQL conferem com os do robô (por exemplo, óleo Liza 900 ml: R$ 7,89, e R$ 7,59 a partir de 6).

Regras comuns:

- **EAN** só vale com 8, 12, 13 ou 14 dígitos e sem repetição óbvia. Códigos internos de marca própria (como "8200") viram vazio.
- **Item por quilo do Atacadão (corrigido em 26/11/2026).** Num item por quilo com multiplicador menor que 1 (tomate de 150 g, queijo de 400 g), o `price` do GraphQL passou a ser o da **porção mínima** (R$ 2,68) e o `listPrice` o do quilo (R$ 17,90); até 24/11 o `price` era o do quilo. O banco chegou a guardar "tomate R$ 2,68 o quilo" (a carga de 25/11 gravou assim). `preco_do_quilo_do_atacadao` confere um contra o outro: `price` = `listPrice` × multiplicador vale o `listPrice`; abaixo disso (porção em promoção) vale `price` ÷ multiplicador; acima disso (o `price` já é o do quilo) ou sem `listPrice`, vale o `price`. Com multiplicador 1 ou maior os dois sempre foram o quilo.
- **Atacado**: guarda a primeira faixa acima de 1 unidade, se for mais barata que o varejo. Sem faixa, `preco_atacado = preco_varejo` e `quantidade_atacado = 1`, como no banco hoje.
- **Peso variável** (vendido por kg ou grama: queijo fatiado, carne, hortifruti) é descartado, a não ser no termo que diz `"aceita_peso_variavel": true`. Dizem isso os termos de [`dados/lista_hortifruti.json`](../dados/lista_hortifruti.json) ([`hortifruti.md`](hortifruti.md)), os de [`dados/lista_carnes_e_frios.json`](../dados/lista_carnes_e_frios.json) ([`carnes_e_frios.md`](carnes_e_frios.md)) e oito termos da lista de 100 que também vendem a peso (frango congelado, peito de frango, carne moída, linguiça, bacon, presunto, queijo mussarela e queijo prato). Cada linha traz `unidade` (`kg` quer dizer que o preço é por quilo) e `multiplicador`; o banco guarda a `unidade` (`docs/sql/coluna_unidade.sql`) e não guarda o `multiplicador`.
- Falha de rede ou erro 429/5xx: repete até 4 vezes (o 403, não: é bloqueio). Um termo que falha mesmo assim vira erro daquele termo e a coleta segue; depois de 6 termos seguidos com erro o mercado é dado como fora do ar e os que faltam não são tentados, e no fim há uma segunda rodada, depois de 60 s, com o que não deu certo ([`carga_diaria.md`](carga_diaria.md#quando-um-mercado-cai-no-meio-da-carga)). Erro do GraphQL do Atacadão (já apareceu "Cannot read properties of undefined (reading 'price')" e passou na chamada seguinte): repete até 3 vezes.
- Um termo que falha em um mercado vira erro daquele par; os outros termos continuam. O programa termina com código 1 se houve erro.

## Super ABC (loja VIP Commerce)

Em novembro de 2026 o Super ABC trocou de site: `superabconline.com.br` passou a redirecionar para `www.abcdelivery.com.br`, uma loja da plataforma **VIP Commerce**, e o robô de navegador (que procurava o botão de unidades do site antigo) deixou de achar a página. As cargas de 24 e 25/11 falharam todas no Super ABC e os dados dele ficaram parados no dia 23. Em vez de consertar o robô, o Super ABC passou a ser coletado pela API que o site novo usa, em [`coletor_vip.py`](../coletor_vip.py): sem navegador, sem clique e com código de barras, que o robô não lia. Sondado em 25/11/2026.

**Como a loja identifica quem pergunta** (tudo sem navegador, a partir do endereço `https://services.vipcommerce.com.br/api-admin/v1/org/398`):

| Etapa | O que o coletor faz |
|---|---|
| Login anônimo | `POST /auth/loja/login` com a **chave pública** do site (`CHAVE_DO_SITE`, a mesma para qualquer visitante). Devolve um token sem prazo de validade; se a loja o recusar (HTTP 401), o coletor entra de novo, uma vez, e repete. |
| Sessão | `GET /loja/sessao_cliente` devolve o `sessao-id` que o site manda junto. A busca funciona sem ele, então, se falhar, a coleta segue com um aviso. |
| Unidade | O preço muda de unidade para unidade (a rede tem 22). O coletor usa a de **Betim** (`centro_distribuicao` 8), a mesma região do CEP da carga, e **confere na lista de unidades da loja** que o 8 ainda se chama "Betim". Se a loja renumerar, a coleta para com erro em vez de gravar o preço de outra cidade (a mesma regra dos robôs: sem localização confirmada, sem dado). |
| Busca | `GET .../filial/1/centro_distribuicao/8/loja/buscas/produtos/termo/<termo>?page=N`: 20 produtos por página e `paginator.total_pages`. A primeira página vem sozinha e as outras, 4 por vez (cada chamada leva de 1 a 3 s). No máximo 15 páginas (300 produtos brutos) por consulta. |

**O que cada produto traz e o que o coletor faz com isso:**

- **`disponivel`**: a busca devolve o catálogo inteiro da rede, e a maior parte não tem estoque na unidade ("arroz": 188 de 222 sem estoque). Só entra o disponível, como nos outros mercados (só vale o que tem estoque).
- **`preco`**: o que o site mostra ao cliente. Oferta (`oferta`, `preco_original`) e preço do Cliente Plus (`classe_oferta: preco-vip`) não entram; o preço do site é `preco`. Conferido contra a tela do site (leite longa vida Itambé 1 L: R$ 5,59 nos dois).
- **`unidade_sigla`**: `KG` quer dizer vendido a peso, e então **`preco` é o da porção** (`quantidade_unidade_diferente`, em quilos), não o do quilo. "Banana Prata 1,2 Kg (5 a 6 unidades)" a R$ 9,59 é a porção de 1,2 kg, a R$ 7,99 o quilo, que é o preço de "Banana Prata Kg" na tela. A linha leva o **preço do quilo** (`preco ÷ porção`), `unidade = kg` e o `multiplicador` (a porção), como as dos outros mercados ([`hortifruti.md`](hortifruti.md)). Qualquer outra sigla (`UN`, `BD`, `CX`, `PC`, `DP`) é venda por unidade ou pacote. Item a peso é `peso_variavel`, então só entra nos termos do hortifrúti, como nos outros mercados.
- **`codigo_barras`** é o EAN, e passa pelas mesmas regras do coletor da VTEX (código interno de balança ou de loja é descartado).
- **`produto_id`** vira o `id_origem`: o Super ABC passa a ter identidade própria no histórico de preços (veja abaixo).
- **Marca e categoria não vêm** (só números, `marca_id` e `classificacao_mercadologica_id`): o filtro do termo decide só pelo nome, como decidia com o robô.

**Como a busca acha os produtos.** A loja põe primeiro os produtos que têm as palavras da busca no nome, e o que vem depois é ruído: em "creme de leite", os 11 produtos que servem estão na página 1 de 80. Por isso a busca para quando, **depois de achar o que procura**, passam 2 páginas seguidas sem nenhum nome com todas as palavras da busca (`PAGINAS_SEM_ACHADO`); sem nenhum achado, lê até o limite de páginas, porque sem o sinal não dá para adivinhar. O custo é que um achado depois de uma pausa de 2 páginas fica de fora. O buscador da loja entende as palavras de um jeito próprio ("sal" acha sal, mas "biscoito" acha todos os biscoitos), e por isso um termo pode ter `consultas_super_abc` (veja a lista de produtos abaixo). Medido em 25/11/2026 nos 128 termos, as consultas da lista (feitas para os mercados da VTEX) rendem no Super ABC o mesmo ou mais que o nome do termo ou que as antigas `consultas_robo` ("sal", "sabão em pó", "escova de dente"... deram o mesmo número de produtos); por isso hoje nenhum termo tem `consultas_super_abc` e o campo `consultas_robo` saiu da lista.

**O histórico.** Até 23/11 o Super ABC era guardado pelo nome (`n:…`). Agora cada produto chega com o `produto_id` da loja (`v:<produto_id>`), e a carga **religa pelo nome** o que já existia, como fez com os outros mercados ([`historico_de_precos.md`](historico_de_precos.md)): o produto que tem o mesmo nome no robô e na API continua com o mesmo histórico; o que o nome mudou entra como produto novo. **Na prática o histórico do Super ABC quase recomeça:** medido em 25/11/2026 com 6 buscas (151 produtos que o robô guardava), só 12% voltam com o mesmo nome, porque o site novo escreve os nomes de outro jeito ("Arroz Tipo 1 Codil 5 Kg Pacote" virou "Arroz Tipo 1 Codil 5 Kg"), e o robô não lia o código de barras que ligaria os dois. Os produtos antigos que não voltarem são dados como saídos depois de 3 cargas completas sem eles, e o selo "caiu X%" do Super ABC precisa de 7 dias de histórico novo.

**Primeira coleta completa** (25/11/2026, no GitHub, sem gravar: [run 45638485330](https://github.com/rafaelhsl/supermatch-api/actions/runs/45638485330)): 128 termos, **2.491 produtos** (o robô trazia uns mil), 0 termos com falha, **17 minutos** (do computador, com o Brasil mais perto, é mais rápido). 98% com código de barras e 36 itens por quilo. Nove termos vieram sem produto, e não é falha: alface, couve, brócolis, couve-flor, abacate, mandioca, morango e papinha estavam sem estoque na unidade, e "batata frita congelada" não casa com os nomes do Super ABC ("Batata Palito Mais Batata 1kg"; o filtro por nome é o dos outros mercados).

**Se o login for recusado** (a mensagem da carga diz "o login anônimo do Super ABC falhou"): a chave pública mudou. Para achar a nova, abra `https://www.abcdelivery.com.br` no navegador, aperte F12, vá em **Rede** (Network), recarregue a página e procure a chamada `auth/loja/login`: o campo `key` do corpo da chamada é a chave. Ela também está nos arquivos `.js` do site, no campo `lojaAuthJWT`. Troque `CHAVE_DO_SITE` em `coletor_vip.py`. Se a mensagem for "a unidade 8 do Super ABC agora é …", a loja renumerou as unidades: a lista está em `GET .../filial/1/loja/centros_distribuicoes/retiradas` (o `id` da unidade "ABC - Betim" é o `CENTRO_DE_BETIM`).

## A lista de produtos

`dados/lista_de_produtos.json`: os 100 termos aprovados (93 da Fase 1 e 7 opcionais), até 100 produtos por termo e mercado (`teto_por_termo`). Cada termo tem:

| Campo | Para quê |
|---|---|
| `termo`, `grupo` | O nome na lista e o grupo (Mercearia, Limpeza…). |
| `consultas` | O que é enviado à busca. Uma frase inteira como "óleo de soja" quase não acha nada no Apoio (3 produtos, nenhum com estoque), enquanto "óleo" acha 50. Por isso a consulta costuma ser a palavra principal, e o filtro faz o resto. |
| `consultas_<mercado>` | Opcional: o que **um mercado** busca no lugar de `consultas`, quando o buscador dele não entende a consulta da lista (`consultas_super_abc`; veja `coletor_vtex.consultas_do_termo`). O buscador de cada loja é um: "biscoito" acha todos os biscoitos do Super ABC, e só "biscoito maisena" põe os de maisena na primeira página. Sem este campo vale `consultas`. O filtro do termo vale igual. |
| `nome_inclui` | Expressão regular: o nome precisa casar. Nos alimentos, o nome precisa **começar** pelo tipo do produto ("Óleo de Soja Liza…"), o que tira "Shampoo com Óleo de Argan". |
| `nome_exclui` | Expressão regular: se o nome casar, o produto sai (óleo "capilar", gelatina "capilar", leite "fermentado"…). |
| `categorias_proibidas` | Se o caminho da categoria casar, o produto sai. Por grupo: um alimento não pode estar em "cuidado com os cabelos" nem em "limpeza". |
| `categorias` | Opcional: o caminho da categoria precisa casar. Quase sempre vazio hoje, porque cada mercado nomeia as categorias de um jeito (o Apoio guarda leite em pó em "aveias, cereais e matinais"). |

Todas as expressões valem para texto em minúsculas e sem acento. O caminho da categoria é como `mercearia > graos > arroz`.

### Como a lista foi montada

1. Baixei os resultados brutos de 170 consultas nos 3 mercados (cerca de 1.800 chamadas, 19 minutos, sem erro).
2. Para cada termo, aprendi quais categorias de cada mercado reúnem os produtos cujo nome começa pelo tipo.
3. Olhei uma amostra dos nomes escolhidos, termo a termo, e corrigi o ruído com `nome_inclui`/`nome_exclui` (por exemplo, "coloração" casava com "ração" e "gelatina capilar" entrava em "gelatina").

Para ajustar um termo: edite o JSON e rode `python coletor_vtex.py --termos "nome do termo"`. O relatório mostra, por mercado, quantos produtos foram baixados e quantos passaram no filtro, com quantos EAN e quantos atacados.

## Resultado da primeira coleta completa

Executada no GitHub em 05/11/2026 ([run 42007495508](https://github.com/rafaelhsl/supermatch-api/actions/runs/42007495508)): 100 termos, 3 mercados, **8 minutos**, 1.055 chamadas.

| Mercado | Produtos | Com EAN | Com preço de atacado | Termos com itens |
|---|---|---|---|---|
| Apoio Entrega | 1.844 | 100% | 1.277 (69%) | 96 de 100 |
| Atacadão | 2.354 | 100% | 1.787 (76%) | 95 de 100 |
| Supernosso | 2.428 | 98% | não tem | 100 de 100 |

- **6.626 produtos distintos**, contra cerca de 950 na carga atual.
- **4.929 códigos de barras distintos**; 1.037 aparecem em 2 mercados e 301 nos 3. Esse é o ganho para a comparação exata: o mesmo EAN é o mesmo produto, sem adivinhar pelo nome. Exemplo: o arroz Camil tipo 1 de 5 kg custa R$ 24,99 no Apoio, R$ 22,50 no Atacadão e R$ 24,99 no Supernosso, ligados pelo EAN 7896006711155.
- Só 48 produtos caem em mais de um termo (40 são kits xampu + condicionador).
- Termos com menos de 3 itens (provavelmente falta de estoque na região): Apoio 10 (farinha de mandioca, fubá, presunto, carne moída, bacon, filé de tilápia, hidratante, lenço umedecido, ração para gatos, papinha), Atacadão 7 (fubá, fermento em pó, ovos, sabão em barra, ração para cães e para gatos, papinha), Supernosso 3 (tempero completo, carne moída, desengordurante).
- Um erro: o catálogo do Atacadão devolveu 500 na busca de EAN do termo "azeite" (não se repete no computador). Por isso a busca de EAN foi mudada para dividir o lote e seguir sem o EAN do que falhar, com um aviso, em vez de derrubar o termo.

## Limites conhecidos

- **Filtro por nome é conservador.** Produto com a marca antes do tipo ("Camil Arroz…") não passa nos alimentos. Na dúvida, não entra.
- **Cobertura varia por mercado.** Algumas lojas simplesmente não têm o produto em estoque na região (por exemplo, ovos no Atacadão, papinha no Apoio e no Atacadão, ração no Atacadão). O relatório de cada execução mostra onde.
- **Termos que se sobrepõem**: o mesmo produto pode aparecer em dois termos (por exemplo, "Leite em Pó Integral" em "leite integral" e "leite em pó", embora o filtro tente separar). Na carga, a linha vale uma vez por mercado.
- **Hortifrúti** entra na carga diária desde 18/11/2026, com a própria lista (`dados/lista_hortifruti.json`, 28 termos) coletada **junto** com a de 100 (`carregar_lista_da_carga`): é preciso o campo `unidade`, a equivalência e o "/kg" no site, e as três existem. Os **cortes de carne e queijos a peso** entram desde 26/11/2026, com a própria lista (10 termos) e com o peso ligado em oito termos da lista de 100: veja [`carnes_e_frios.md`](carnes_e_frios.md).
- O catálogo do Apoio muda de região para região (canal de vendas); o coletor usa o de Betim, como a carga diária.
- **O levantamento de entrega por cidade** (`levantar_entrega.py`) também deixou o robô antigo: para o Super ABC ele descobre a cidade do CEP e procura, na lista de unidades da loja (`.../loja/centros_distribuicoes/retiradas`, com cidade e estado de cada uma), uma unidade ali; achando, busca "arroz" nela. Refeito em 25/11/2026, deu a mesma tabela de antes (só Belo Horizonte e Betim têm unidade entre as 14 cidades). O arquivo do robô (`Scraper_SuperABC.py`) foi apagado.

## Próximos passos

1. **SQL de migração**: [`sql/colunas_do_coletor.sql`](sql/colunas_do_coletor.sql) acrescenta a `produtos` as colunas `ean`, `marca`, `categoria`, `id_origem` e `termo` (todas vazias, sem risco para o que existe). A tabela `catalogo` do histórico já tem `ean`, `marca` e `categoria`.
2. **Carga diária** (feito): os quatro mercados pelos coletores por API (o Super ABC pelo robô até 24/11/2026 e, desde 25/11, por `coletor_vip.py`), com coleta parcial. O histórico de preços usa `id_origem` como chave e religa os produtos antigos pelo nome ([`historico_de_precos.md`](historico_de_precos.md)). Se a API de um mercado falhar, ficam os dados do dia anterior; `coleta = robos` no workflow volta ao modo antigo.
3. **Agrupar por EAN** na API e no site, e levar as regras de equivalência do navegador para a carga (ainda não feito).
