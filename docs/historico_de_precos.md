# Histórico de preços

A cada carga diária, o banco passa a guardar também **como o preço de cada produto varia ao longo do tempo**. A tabela `produtos` não muda: continua sendo a foto do dia que a API e o site leem. O histórico fica em três tabelas novas, criadas por [`sql/historico_precos.sql`](sql/historico_precos.sql) e gravadas por [`historico.py`](../historico.py).

## A ideia: registrar o preço só quando ele muda

Um registro por produto por dia estouraria o banco (cerca de 14 mil produtos × 365 dias, perto de 900 MB por ano; o plano gratuito do Supabase tem 500 MB). Em vez disso, cada linha de `precos` diz que **o preço valeu de um dia até outro**; um intervalo novo só abre quando o preço muda. O preço de qualquer dia sai do intervalo que o contém.

Medido em 03/11/2026, comparando a coleta de 29/10 com a de agora: 19% dos produtos em comum mudaram de preço em cerca de 5 dias (Super ABC 27%, Supernosso 25%, Atacadão 14%, Apoio 10%). Isso dá algo como 250 a 300 mil linhas por ano, perto de **60 MB por ano**.

## As tabelas

| Tabela | O que guarda |
|---|---|
| `catalogo` | O produto com **identidade estável**: mercado, `chave_origem`, nome, e (para depois) código de barras, marca e categoria. Guarda o primeiro e o último dia em que foi visto e se está `ativo`. |
| `precos` | O preço vigente em um intervalo: `desde`, `ate` (vazio = vale até hoje), varejo, atacado, quantidade do atacado, `praca` (a região da coleta). Só um preço vigente por produto e praça. |
| `coletas` | O que cada carga fez, por dia, mercado e praça: `ok`, `parcial` ou `falhou`, com o número de itens. |

`produtos` não serve de chave para o histórico porque a carga a recria todo dia e seus ids mudam. `chave_origem` tem dois formatos:

- `v:productId:itemId`: o id do produto no catálogo do mercado, quando o coletor por API o traz (Apoio, Atacadão e Supernosso);
- `n:…`: um resumo do nome normalizado (sem acento, sem pontuação, em minúsculas), para o produto que não tem id (Super ABC, que vem do robô).

**Religação.** Os produtos que o histórico já guardava pelo nome (`n:…`) e passam a chegar com o id do mercado são **religados**: a
mesma linha de `catalogo` troca a chave para `v:…` e ganha EAN, marca e categoria, e o histórico de preços continua de onde
estava (não nasce um produto novo). A ligação sai pelo nome normalizado. Se num dia só o robô trouxer um produto (sem id), ele é
reencontrado pelo nome e continua sendo o mesmo.

## Como cada carga grava

Quando um mercado é coletado por inteiro e gravado em `produtos`, `historico.registrar_mercado` compara os produtos com o que já está registrado:

1. **Produto novo:** entra em `catalogo` e abre um intervalo de preço.
2. **Mesmo preço** (varejo, atacado e quantidade do atacado): só atualiza o "visto em".
3. **Preço diferente:** fecha o intervalo anterior no **dia anterior** e abre outro hoje.
4. **Carga repetida no mesmo dia com outro preço:** corrige o intervalo de hoje, em vez de criar um de zero dia. Repetir a carga com os mesmos dados não muda nada.
5. **Produto que não apareceu** em 3 cargas completas seguidas do mercado: fica `ativo = false` e o intervalo aberto fecha no último dia em que foi visto. Se voltar, abre um intervalo novo (o buraco fica no histórico).

Regras que protegem o histórico:

- **O "dia" é o de Brasília**, não o de UTC.
- **Falha não vira ausência.** Se a coleta de um mercado falha, `coletas` registra `falhou` e nada mais acontece com os produtos dele. As "3 cargas" contam só as `ok`.
- **Coleta parcial** (faltaram alguns termos, mas até 10% deles): os produtos que vieram são registrados normalmente, `coletas` registra `parcial`, **nenhum produto é dado como saído** e o dia não conta entre as "3 cargas completas". Um `parcial` nunca sobrescreve um `ok` do mesmo dia.
- **Nunca se apaga** o preço de um dia passado. O histórico só cresce.
- **Se o histórico falhar** (por exemplo, as tabelas ainda não existem), a carga diária **não falha**: vira um aviso destacado, "Histórico de preços não gravado", na execução do GitHub.
- Nomes repetidos no mesmo mercado viram um produto só, com o menor preço.

A primeira carga com o histórico ligado é o **dia 1**; a carga sempre apagou os preços antigos, então não existe passado para recuperar.

## Como ligar

1. No Supabase, abra o **SQL Editor** e rode o conteúdo de [`sql/historico_precos.sql`](sql/historico_precos.sql). Pode rodar mais de uma vez.
2. A partir da próxima carga (a agendada, ou um disparo manual do workflow), o histórico é gravado. No log da execução, procure as linhas `🗂️  Histórico do ...` com a contagem de produtos novos, preços novos e produtos que saíram.
3. Conferência no SQL Editor (as consultas também estão no fim do script):

```sql
select supermercado, count(*) from catalogo group by 1;      -- produtos por mercado
select * from coletas order by dia desc, supermercado;        -- cargas registradas
select count(*) from precos where ate is null;                -- preços vigentes (≈ produtos ativos)
```

Consultas úteis depois de alguns dias:

```sql
-- preço de cada produto do Atacadão em 10/11/2026
select c.nome, p.preco_varejo
from precos p join catalogo c on c.id = p.catalogo_id
where c.supermercado = 'Atacadao' and p.desde <= '2026-11-10' and (p.ate is null or p.ate >= '2026-11-10');

-- maiores altas desde 05/11
select c.supermercado, c.nome, ant.preco_varejo as antes, atual.preco_varejo as agora,
       round(100 * (atual.preco_varejo - ant.preco_varejo) / ant.preco_varejo, 1) as variacao_pct
from precos atual
join precos ant on ant.catalogo_id = atual.catalogo_id and ant.praca = atual.praca and ant.ate = atual.desde - 1
join catalogo c on c.id = atual.catalogo_id
where atual.desde >= '2026-11-05' order by variacao_pct desc limit 20;
```

## Limites e próximos passos

- **Uma praça só (`betim`).** `ultimo_dia` e `ativo` ficam no produto e valem para o mercado todo; quando houver mais de uma praça (CEP de outra cidade na carga), eles passam a ser por praça. A coluna `praca` já existe em `precos` e `coletas` para isso.
- **Os robôs leem só a primeira página de cada busca**, e o que aparece nela muda de ordem. Nos testes, de 29/10 para 03/11, 190 produtos sumiram e 147 apareceram. Por isso o produto só é dado como saído depois de 3 cargas completas sem aparecer, e por isso o novo coletor (que lê o catálogo inteiro) deve diminuir esse ruído.
- **Preço absurdo** (como um feijão de 1 kg a R$ 0,78) é registrado como veio. Filtrar é tarefa de quem lê o histórico.
- **O site ainda só usa o histórico para o selo "caiu X% em 7 dias"** (próxima seção). Ficam para depois um endereço novo na API (`/historico`) para o gráfico de preço do produto, o menor preço dos últimos 90 dias e "sua lista ficou mais cara ou mais barata que na semana passada". O site nunca lê o Supabase direto.
- Testes: `python tests/test_historico.py` (7 testes, com um repositório em memória e um Supabase falso).

## O selo "caiu X% em 7 dias"

A API compara o preço de hoje de cada produto com o que ele tinha 7 dias antes e, quando a queda é de **5% a 70%**, marca a opção de compra com `queda_preco`, e o site mostra o selo no quadro do mercado e na linha do cupom. O código está em [`quedas.py`](../quedas.py) e é chamado por `baixar_catalogo` (`api_supabase.py`); não precisa de SQL novo, só lê as tabelas acima.

```json
"queda_preco": { "preco_antes": 14.99, "percentual": 47, "dias": 7 }
```

**Como o preço de 7 dias antes é encontrado.** O preço de um dia sai do intervalo de `precos` que o contém. Quem não mudou de preço desde então ainda tem esse intervalo aberto (`ate` vazio), e não há o que comparar. Por isso a consulta pede só os intervalos que contêm o dia de antes **e já fecharam** (`desde <= dia` e `ate >= dia`, o que deixa de fora os abertos): são os produtos que mudaram de preço depois, uns 25% do catálogo, algo como 3 mil linhas (cerca de 600 KB, estimado; não medido no banco de verdade), já com o mercado e a `chave_origem` do `catalogo` junto. O catálogo em memória (`produtos`) traz o preço de hoje; cada produto é ligado ao histórico pela mesma `chave_do_produto` que a carga usa para gravar (`v:` + `id_origem`, ou o resumo do nome no Super ABC).

**Custo.** A consulta roda **uma vez por carga de preços** (e uma vez quando o servidor acorda), não a cada recarga do catálogo, que é de hora em hora: o resultado fica em memória até haver uma carga nova. O "hoje" é o dia (de Brasília) da carga mais nova do catálogo, então de manhã cedo, antes da carga do dia, a conta ainda usa o dia anterior e fica certa.

**Leitura provisória.** A carga grava um mercado de cada vez: primeiro os produtos dele e, segundos depois, o histórico dele. Uma leitura feita enquanto a carga corre (ou nos 15 minutos seguintes à última gravação) pode não ver o fechamento do intervalo de quem mudou de preço **hoje**, e essas quedas mais novas ficariam sem selo. Por isso essa leitura é marcada como provisória (`ESPERA_DEPOIS_DA_CARGA`) e se repete na próxima recarga do catálogo, uma hora depois; só a leitura feita depois da espera é guardada até a carga seguinte.

**O que conta como queda.**

| Situação | Selo? |
|---|---|
| 14,99 → 7,99 (-47%) | sim |
| a partir de 5% de queda (20,00 → 19,00) | sim |
| queda de menos de 5% (20,00 → 19,02) | não |
| o preço subiu, ou não mudou | não |
| caiu e voltou ao mesmo preço (10 → 8 → 10) | não: a conta é só o preço de hoje contra o de 7 dias atrás |
| o produto não existia há 7 dias (novo) ou voltou depois de sumir | não: sem preço para comparar |
| queda de mais de 70% | não: quase sempre é erro de coleta (o feijão de 1 kg a R$ 0,78); melhor não afirmar nada |
| a linha do produto não é da carga mais nova (o mercado falhou, ou o termo falhou numa coleta parcial e a linha de ontem foi mantida) | não: o selo afirma o preço de hoje, e esse preço é de outro dia |
| preço de atacado | não conta: só o preço do varejo |

Em dados reais (fotos do catálogo de 5 a 12/11/2026, 3 a 7 dias de distância, 6 mil produtos que dá para ligar), o limite de 5% marca uns **9% dos produtos**. Quedas entre 1% e 5% são raras: com limite de 1% teriam selo 9,5% dos produtos, e com 5%, 8,7%. Então o limite pouco muda a quantidade; ele existe para não gritar "caiu 2%" por centavos. O Super ABC ficou de fora dessa medida, porque a foto não trazia código para ligar os produtos dele.

**Se o histórico falhar** (tabelas fora do ar, rede), o catálogo carrega do mesmo jeito, sem selos, e o log do Render diz `⚠️ Selo de queda de preço: histórico indisponível`. A próxima carga do catálogo (em até 1 hora) tenta de novo. No log, uma leitura boa aparece como `📉 Histórico lido em X s: N produtos com preço diferente do de DD/MM` e, a cada carga do catálogo, `📉 N de M produtos com queda de 5% a 70% em 7 dias`. Uma leitura feita logo depois da carga acrescenta "leitura provisória".

**Mudar as regras:** `LIMITE_QUEDA_PCT`, `TETO_QUEDA_PCT` e `JANELA_DIAS`, no começo de `quedas.py`. O selo precisa de pelo menos `JANELA_DIAS` dias de histórico (o histórico começou em 04/11/2026, então vale desde 11/11).

**Limites conhecidos.**

- **"Em 7 dias" é a conta de hoje contra o preço registrado para o dia de 7 dias antes.** Se o mercado ficou dias sem uma coleta boa (a tabela `coletas` registra `falhou`), o intervalo antigo só fecha na primeira carga que volta, e a queda pode ter acontecido antes dos 7 dias. O preço mostrado e o de antes são verdadeiros; só o prazo é aproximado. A consulta não olha `coletas`.
- **Um mercado com carga atrasada** (dados de 1 a 3 dias antes dos outros) é comparado com o mesmo "7 dias antes" do dia mais novo do catálogo. A linha dele, por ser de outro dia, fica sem selo (regra da tabela acima).
- **O histórico de um mercado que falhou** na gravação (vira só um aviso na execução do GitHub) deixa as quedas de hoje dele sem selo até a carga seguinte.

Testes: `python tests/test_quedas.py` (as regras, a leitura paginada, a falha do histórico e a resposta da API), `node tests/test_queda.js` (a validação no site) e `python tests/navegador/test_site_queda.py` (a tela).
