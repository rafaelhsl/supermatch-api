# Coletor por API

`coletor_vtex.py` busca produtos nas **APIs públicas que os próprios sites usam**, em vez de abrir um navegador e ler a primeira página de cada busca. Cada busca traz até 100 produtos por termo e mercado (os robôs leem de 20 a 30), com **marca, categoria e código de barras (EAN)**, que o robô não consegue ler.

> **Estado:** só lê. Ainda não está ligado à carga diária, não grava em banco e não mexe em `produtos`. O próximo passo é ligá-lo à carga (ver o fim deste texto).

O Super ABC não tem API aberta (responde 403) e continua pelo robô (`Scraper_SuperABC.py`).

## Como rodar

```
python coletor_vtex.py                                  # os 100 termos, os 3 mercados
python coletor_vtex.py --termos "arroz,óleo"            # só alguns termos
python coletor_vtex.py --mercados "Atacadao"            # só um mercado
python coletor_vtex.py --saida coleta.json              # guarda as linhas coletadas
python tests/test_coletor_vtex.py                       # testes, sem rede
```

Não precisa instalar nada além do Python. No GitHub: o workflow **Coletor por API** (`coletor-api.yml`) roda tudo sem segredo e sem banco, e guarda `coleta.json` e `relatorio.txt` na execução.

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
- **Atacado**: guarda a primeira faixa acima de 1 unidade, se for mais barata que o varejo. Sem faixa, `preco_atacado = preco_varejo` e `quantidade_atacado = 1`, como no banco hoje.
- **Peso variável** (vendido por kg ou grama: queijo fatiado, carne, hortifruti) é descartado. É a Fase 2.
- Falha de rede ou erro 429/5xx: repete até 4 vezes. Erro do GraphQL do Atacadão (já apareceu "Cannot read properties of undefined (reading 'price')" e passou na chamada seguinte): repete até 3 vezes.
- Um termo que falha em um mercado vira erro daquele par; os outros termos continuam. O programa termina com código 1 se houve erro.

## A lista de produtos

`dados/lista_de_produtos.json`: os 100 termos aprovados (93 da Fase 1 e 7 opcionais), até 100 produtos por termo e mercado (`teto_por_termo`). Cada termo tem:

| Campo | Para quê |
|---|---|
| `termo`, `grupo` | O nome na lista e o grupo (Mercearia, Limpeza…). |
| `consultas` | O que é enviado à busca. Uma frase inteira como "óleo de soja" quase não acha nada no Apoio (3 produtos, nenhum com estoque), enquanto "óleo" acha 50. Por isso a consulta costuma ser a palavra principal, e o filtro faz o resto. |
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
- **Fase 2** (hortifruti e peso variável) fica de fora, de propósito.
- O catálogo do Apoio muda de região para região (canal de vendas); o coletor usa o de Betim, como a carga diária.

## Próximos passos

1. **SQL de migração**: [`sql/colunas_do_coletor.sql`](sql/colunas_do_coletor.sql) acrescenta a `produtos` as colunas `ean`, `marca`, `categoria`, `id_origem` e `termo` (todas vazias, sem risco para o que existe). A tabela `catalogo` do histórico já tem `ean`, `marca` e `categoria`.
2. **Ligar à carga diária**: Apoio, Atacadão e Supernosso pelo coletor (o robô fica de reserva se a API falhar), Super ABC pelo robô nos 100 termos. O histórico de preços passa a usar `id_origem` como chave, ligando os produtos antigos pelo nome.
3. **Agrupar por EAN** na API e no site, e levar as regras de equivalência do navegador para a carga.
