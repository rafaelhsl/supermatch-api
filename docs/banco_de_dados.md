# Banco de dados (Supabase)

> **Status: INFERIDO DO CÓDIGO, ainda não conferido no Supabase.**
> Este documento descreve o que o código espera do banco. Os pontos marcados com
> **[CONFIRMAR]** precisam ser verificados no painel do Supabase com as consultas
> da seção [Como confirmar no Supabase](#como-confirmar-no-supabase).
> Depois de conferir, remova este aviso e ajuste o que estiver diferente.

- Projeto Supabase: `gtdvgdfalpsrnefzyfgu` (`https://gtdvgdfalpsrnefzyfgu.supabase.co`)
- Tabelas conhecidas: apenas **`produtos`** (o código não usa nenhuma outra).
- Quem acessa: o robô de carga ([`alimentar_banco.py`](../alimentar_banco.py)) escreve; a API
  ([`api_supabase.py`](../api_supabase.py)) lê. Ambos usam a variável de ambiente `SUPABASE_KEY`.

## Tabela `produtos`

Cada linha é **um produto de um supermercado na última coleta**. Não há histórico: a cada carga a
tabela inteira é apagada e regravada.

| Coluna | Tipo provável | Origem | Descrição |
|---|---|---|---|
| `supermercado` | texto | scrapers | Nome do mercado: `Apoio Entrega`, `Atacadao`, `Supernosso`, `Super ABC` |
| `nome` | texto | scrapers | Nome do produto como aparece no site do mercado |
| `preco_varejo` | numérico | scrapers | Preço unitário normal. Nos mercados com regra de atacado, é o **maior** dos preços lidos |
| `preco_atacado` | numérico | scrapers | Preço unitário a partir de `quantidade_atacado`. Sem atacado, é igual a `preco_varejo` |
| `quantidade_atacado` | inteiro | scrapers | A partir de quantas unidades vale `preco_atacado`. Sem atacado, vale `1` |
| `texto_original` | texto | scrapers | Texto bruto do card do produto, guardado para depuração |
| `uf_cobertura` | texto | `alimentar_banco.py` | UF atendida pelo mercado: `MG` (Apoio, Supernosso, Super ABC) ou `BR` (Atacadão) |

Colunas que provavelmente existem mas o código não menciona **[CONFIRMAR]**: `id` (chave primária
gerada pelo Supabase) e `created_at`.

### Regras que o código assume (hoje não garantidas pelo banco)

- `preco_varejo` e `preco_atacado` **nunca são nulos**: os scrapers descartam produtos sem preço
  (`return None`). Mas o comparador ([`Comparador_inteligente.py`](../Comparador_inteligente.py))
  faz `preco_varejo < ...` e ordena por esse campo, então um valor nulo quebraria a resposta da API.
  **[CONFIRMAR]** se as colunas têm `NOT NULL`.
- `supermercado` identifica o mercado só pelo **texto**. Não existe tabela de mercados; um erro de
  digitação no nome cria um "mercado novo".
- `uf_cobertura` é fixada **no código** (`alimentar_banco.py`), não é lida do site do mercado.
- Um produto é identificado só por `supermercado` + `nome`. Não há código de barras nem SKU.

## Como os dados entram

[`alimentar_banco.py`](../alimentar_banco.py), disparado diariamente pelo workflow
[`.github/workflows/main.yml`](../.github/workflows/main.yml):

1. Apaga **todas** as linhas: `delete().neq('supermercado', 'nada')`.
2. Para cada um dos 11 itens da lista (`Arroz`, `Feijao`, `Oleo`, `Cafe`, `Manteiga`, `Açucar`,
   `Macarrao`, `Detergente`, `Sabao`, `Amaciante`, `Higienico`), roda os 4 scrapers em paralelo
   com o CEP fixo `32607600`.
3. Define `uf_cobertura` e insere os produtos **um a um** (`insert` por linha).

Riscos conhecidos desse fluxo:

- Se o robô falhar depois do passo 1, o banco fica **vazio ou incompleto** até a próxima execução.
- Os preços são os de um único CEP, mas a API os devolve para qualquer CEP da mesma UF.
- Um `insert` por produto gera muitas requisições; não há tratamento de erro por linha.

## Como os dados saem

Endpoint `GET /comparar?cep=...&item=...` em [`api_supabase.py`](../api_supabase.py):

1. Descobre a UF do CEP pelo ViaCEP (se falhar, usa `BR`).
2. Troca todas as vogais (e o `ç`) do termo por `_`, o curinga de um caractere do SQL, para ignorar
   acentos. Por exemplo, `feijão` vira `f__j__` e passa a casar com `Feijao` e `Feijão`.
3. Consulta equivalente a:

```sql
select *
from produtos
where nome ilike '%<termo com vogais trocadas por _>%'
  and uf_cobertura in ('<UF do CEP>', 'BR');
```

4. Passa o resultado para `cruzar_multiplos_produtos`, que agrupa produtos equivalentes de mercados
   diferentes (nome parecido, mesma medida, mesmas tags) e aponta o mais barato de cada grupo.

Observações de desempenho: `ilike '%...%'` não usa índice comum, então a busca varre a tabela
inteira. Com poucos milhares de linhas isso é aceitável; com mais dados, vale um índice `pg_trgm`.

## Como confirmar no Supabase

No painel do Supabase, abra **SQL Editor** e rode as consultas abaixo. Cole os resultados na
conversa para atualizarmos este documento.

**1. Colunas, tipos e obrigatoriedade**

```sql
select column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public' and table_name = 'produtos'
order by ordinal_position;
```

**2. Outras tabelas existentes**

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;
```

**3. Índices e chave primária**

```sql
select indexname, indexdef
from pg_indexes
where schemaname = 'public' and tablename = 'produtos';
```

**4. Row Level Security (RLS) e políticas**

```sql
select relname, relrowsecurity
from pg_class
where oid = 'public.produtos'::regclass;

select policyname, cmd, roles, qual
from pg_policies
where tablename = 'produtos';
```

**5. Volume e cobertura atuais**

```sql
select supermercado, uf_cobertura, count(*) as itens
from produtos
group by supermercado, uf_cobertura
order by supermercado;
```
