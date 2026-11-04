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

`produtos` não serve de chave para o histórico porque a carga a recria todo dia e seus ids mudam. `chave_origem` é, **por enquanto**, um resumo do nome normalizado (sem acento, sem pontuação, em minúsculas); quando o coletor por API entrar, vira o id do produto no catálogo do mercado, e a ligação entre as duas chaves sai pelo nome.

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
- **Ainda não há como ler o histórico pelo site.** O próximo passo é um endereço novo na API (`/historico`) para o gráfico de preço do produto, o menor preço dos últimos 90 dias e "sua lista ficou mais cara ou mais barata que na semana passada". O site nunca lê o Supabase direto.
- Testes: `python tests/test_historico.py` (7 testes, com um repositório em memória e um Supabase falso).
