# Entrega por cidade

Quais mercados entregam em cada uma das 14 cidades atendidas pelo Supermatch. Gerado por [`levantar_entrega.py`](../levantar_entrega.py), que informa CEPs reais de bairros diferentes em cada site e anota o que ele respondeu. Última sondagem: 2026-10-30. Os sites mudam: para atualizar, rode o script de novo.

## Resumo

| Cidade | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|
| Belo Horizonte | Entrega (9 de 9) | Entrega (9 de 9) | Entrega (9 de 9) | Entrega (9 de 9) |
| Betim | Entrega (3 de 3) | Entrega (3 de 3) | Entrega (3 de 3) | Entrega (3 de 3) |
| Contagem | Entrega (4 de 4) | Entrega (4 de 4) | Entrega (4 de 4) | Não entrega (0 de 4) |
| Ribeirão das Neves | Entrega (3 de 3) | Só em parte (2 de 3) | Entrega (3 de 3) | Não entrega (0 de 3) |
| Santa Luzia | Entrega (2 de 2) | Só em parte (1 de 2) | Entrega (2 de 2) | Não entrega (0 de 2) |
| Sabará | Entrega (2 de 2) | Só em parte (1 de 2) | Entrega (2 de 2) | Não entrega (0 de 2) |
| Vespasiano | Entrega (2 de 2) | Não entrega (0 de 2) | Entrega (2 de 2) | Não entrega (0 de 2) |
| Ibirité | Entrega (2 de 2) | Não entrega (0 de 2) | Entrega (2 de 2) | Não entrega (0 de 2) |
| Nova Lima | Entrega (3 de 3) | Não entrega (0 de 3) | Entrega (3 de 3) | Não entrega (0 de 3) |
| Esmeraldas | Entrega (2 de 2) | Não entrega (0 de 2) | Entrega (2 de 2) | Não entrega (0 de 2) |
| Igarapé | Não entrega (0 de 2) | Não entrega (0 de 2) | Não entrega (0 de 2) | Não entrega (0 de 2) |
| Brumadinho | Não entrega (0 de 2) | Só em parte (1 de 2) | Não entrega (0 de 2) | Não entrega (0 de 2) |
| São Joaquim de Bicas | Entrega (2 de 2) | Só em parte (1 de 2) | Não entrega (0 de 2) | Não entrega (0 de 2) |
| Sarzedo | Entrega (2 de 2) | Só em parte (1 de 2) | Não entrega (0 de 2) | Não entrega (0 de 2) |

Cada célula diz quantos dos CEPs sondados na cidade o site aceitou. **Entrega** é a cidade inteira; **Só em parte** é quando o site aceita uns bairros e outros não; **A confirmar** é quando a sondagem não chegou a uma resposta firme (o site não respondeu ou o robô se perdeu) e precisa ser repetida.

## Como foi feito

- Para cada CEP e cada mercado, o levantamento roda o **mesmo robô da carga diária** (busca de "arroz"). O robô informa o CEP e só segue se o site o assumir; é essa resposta que vira a tabela. Nada é gravado no banco.
- **Atacadão, Apoio e Supernosso** respondem por CEP. O Supernosso e o Atacadão dizem de forma explícita que não atendem ("Ainda não atendemos essa região"). O Apoio não diz nada: o painel fica girando sem responder. Por isso o "não" do Apoio (**não assumiu o CEP**) só vale depois de repetido; aqui foi repetido três vezes, e uma delas esperando 40 s.
- **Super ABC** não localiza por CEP: o robô escolhe a unidade da cidade do CEP. "Não entrega" quer dizer que **não há unidade do Super ABC naquela cidade**. Uma unidade vizinha pode entregar lá, mas o site não deixa conferir.
- Os CEPs são de ruas e bairros reais (veja abaixo). Cidades grandes têm mais CEPs, porque os sites decidem por CEP e a resposta pode mudar de bairro para bairro. Em São Joaquim de Bicas e Sarzedo, que têm CEP único, a amostra é o CEP geral e o do Centro.

## Limites desta tabela

- **"Entrega" quer dizer que o site aceitou o CEP e mostrou produtos com preço.** Não garante frete, horário nem pedido mínimo.
- **A amostra é pequena** (2 a 9 CEPs por cidade). Onde todos os CEPs deram o mesmo resultado, a cidade inteira é tratada igual; onde deram resultados diferentes (**Só em parte**), só uma amostra maior diria qual bairro entra.
- **O Atacadão decide por bairro, não por cidade.** Em Santa Luzia, Sabará e Ribeirão das Neves, por exemplo, ele atende um bairro e recusa outro. Ele entrega a partir de três origens: a loja Pampulha, a loja Betim e uma unidade "Contagem", que também atende partes de BH (Barreiro, Alto Barroca, Buritis) e de Betim (Granja Verde).
- Em São Joaquim de Bicas e Sarzedo, a cidade tem CEP único (`-000`), e o Centro tem um CEP de rua. Os resultados diferem entre os dois.
- Os sites mudam. Para conferir de novo, rode `python levantar_entrega.py` (repete só o que ficou duvidoso) ou `--refazer`.

## Detalhe por CEP

### Belo Horizonte

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 30130-010 | Centro | entrega | entrega (Pampulha) | entrega | entrega (Barreiro - BH Belo Horizonte) |
| 30140-008 | Savassi | entrega | entrega (Pampulha) | entrega | mesma da cidade |
| 31340-505 | Bandeirantes (Pampulha) | entrega | entrega (Pampulha) | entrega | mesma da cidade |
| 31610-070 | Venda Nova | entrega | entrega (Pampulha) | entrega | mesma da cidade |
| 30640-070 | Barreiro | entrega | entrega (Contagem) | entrega | mesma da cidade |
| 31260-500 | Suzana | entrega | entrega (Pampulha) | entrega | mesma da cidade |
| 30431-025 | Alto Barroca | entrega | entrega (Contagem) | entrega | mesma da cidade |
| 30575-180 | Buritis | entrega | entrega (Contagem) | entrega | mesma da cidade |
| 30285-255 | Vera Cruz | entrega | entrega (Pampulha) | entrega | mesma da cidade |

### Betim

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 32600-055 | Centro | entrega | entrega (Betim) | entrega | entrega (Betim Betim) |
| 32607-600 | Teixeirinha | entrega | entrega (Betim) | entrega | mesma da cidade |
| 32678-166 | Granja Verde | entrega | entrega (Contagem) | entrega | mesma da cidade |

### Contagem

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 32041-000 | Três Barras | entrega | entrega (Contagem) | entrega | não entrega |
| 32040-030 | Centro | entrega | entrega (Contagem) | entrega | mesma da cidade |
| 32315-010 | Eldorado | entrega | entrega (Contagem) | entrega | mesma da cidade |
| 32210-110 | Cidade Industrial | entrega | entrega (Contagem) | entrega | mesma da cidade |

### Ribeirão das Neves

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 33805-276 | Tânia | entrega | não entrega | entrega | não entrega |
| 33900-240 | São José (Justinópolis) | entrega | entrega (Pampulha) | entrega | mesma da cidade |
| 33913-480 | Menezes (Justinópolis) | entrega | entrega (Pampulha) | entrega | mesma da cidade |

### Santa Luzia

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 33010-000 | Centro | entrega | não entrega | entrega | não entrega |
| 33120-563 | São Benedito | entrega | entrega (Pampulha) | entrega | mesma da cidade |

### Sabará

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 34505-000 | Centro | entrega | não entrega | entrega | não entrega |
| 34590-050 | Nações Unidas | entrega | entrega (Pampulha) | entrega | mesma da cidade |

### Vespasiano

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 33200-356 | Centro | entrega | não entrega | entrega | não entrega |
| 33200-700 | Nova Granja | entrega | não entrega | entrega | mesma da cidade |

### Ibirité

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 32405-113 | Morada da Serra | entrega | não entrega | entrega | não entrega |
| 32415-138 | São Pedro | entrega | não entrega | entrega | mesma da cidade |

### Nova Lima

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 34000-132 | Centro | entrega | não entrega | entrega | não entrega |
| 34006-031 | Vale do Sereno | entrega | não entrega | entrega | mesma da cidade |
| 34018-010 | Alphaville - Lagoa dos Ingleses | entrega | não entrega | entrega | mesma da cidade |

### Esmeraldas

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 32800-060 | Centro | entrega | não entrega | entrega | não entrega |
| 32809-472 | São Francisco de Assis | entrega | não entrega | entrega | mesma da cidade |

### Igarapé

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 32510-050 | Centro | não assumiu o CEP | não entrega | não entrega | não entrega |
| 32516-002 | Padre Eustáquio | não assumiu o CEP | não entrega | não entrega | mesma da cidade |

### Brumadinho

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 32481-000 | Do Carmo | não assumiu o CEP | não entrega | não entrega | não entrega |
| 32480-172 | Santa Cruz | não assumiu o CEP | entrega (Contagem) | não entrega | mesma da cidade |

### São Joaquim de Bicas

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 32920-000 | (sem bairro) | entrega | entrega (Betim) | não entrega | não entrega |
| 32920-971 | Centro | entrega | não entrega | não entrega | mesma da cidade |

### Sarzedo

| CEP | Bairro | Apoio Entrega | Atacadão | Supernosso | Super ABC |
|---|---|---|---|---|---|
| 32450-000 | (sem bairro) | entrega | entrega (Betim) | não entrega | não entrega |
| 32450-971 | Centro | entrega | não entrega | não entrega | mesma da cidade |

