# Banco de dados (Supabase)

> **Fonte do esquema:** script de criação da tabela fornecido pelo dono do projeto (seção
> [Script de criação](#script-de-criação)). Colunas, tipos, restrições e índice abaixo vêm dele.
> Continuam **[CONFIRMAR]** no painel do Supabase: se o banco ainda é igual ao script (alguma
> alteração manual posterior), se existem outras tabelas e como está o RLS. As consultas estão em
> [Como confirmar no Supabase](#como-confirmar-no-supabase).

- Projeto Supabase: `gtdvgdfalpsrnefzyfgu` (`https://gtdvgdfalpsrnefzyfgu.supabase.co`)
- Tabelas conhecidas: apenas **`produtos`** (o código não usa nenhuma outra).
- Quem acessa: o robô de carga ([`alimentar_banco.py`](../alimentar_banco.py)) escreve; a API
  ([`api_supabase.py`](../api_supabase.py)) lê. Ambos usam a variável de ambiente `SUPABASE_KEY`.

## Tabela `produtos`

Cada linha é **um produto de um supermercado na última coleta**. Não há histórico: a cada carga a
tabela inteira é apagada e regravada.

| Coluna | Tipo | Obrigatória | Preenchida por | Descrição |
|---|---|---|---|---|
| `id` | `uuid` (chave primária) | sim, automática | banco (`gen_random_uuid()`) | Identificador da linha. Muda a cada carga, pois a tabela é regravada |
| `supermercado` | `text` | sim | scrapers | Nome do mercado: `Apoio Entrega`, `Atacadao`, `Supernosso`, `Super ABC` |
| `nome` | `text` | sim | scrapers | Nome do produto como aparece no site do mercado |
| `preco_varejo` | `decimal(10,2)` | sim | scrapers | Preço unitário normal. Nos mercados com regra de atacado, é o **maior** dos preços lidos |
| `preco_atacado` | `decimal(10,2)` | sim | scrapers | Preço unitário a partir de `quantidade_atacado`. Sem atacado, é igual a `preco_varejo` |
| `quantidade_atacado` | `integer` | sim | scrapers | A partir de quantas unidades vale `preco_atacado`. Sem atacado, vale `1` |
| `uf_cobertura` | `text` | sim | `alimentar_banco.py` | UF atendida pelo mercado: `MG` (Apoio, Supernosso, Super ABC) ou `BR` (Atacadão) |
| `texto_original` | `text` | não | scrapers | Texto bruto do card do produto, guardado para depuração |
| `atualizado_em` | `timestamptz` | sim, automática | banco (`now()` em UTC) | Momento em que a linha foi inserida, ou seja, a hora da coleta |

### Regras que o banco garante e as que só o código assume

- **Garantido pelo banco:** `supermercado`, `nome`, os três campos de preço/quantidade e
  `uf_cobertura` nunca são nulos. Isso casa com os scrapers, que descartam produtos sem preço, e
  protege o comparador ([`Comparador_inteligente.py`](../Comparador_inteligente.py)), que ordena
  por `preco_varejo`.
- **Só no código:** `supermercado` identifica o mercado apenas pelo **texto**. Não existe tabela de
  mercados; um erro de digitação no nome cria um "mercado novo".
- **Só no código:** `uf_cobertura` é fixada em `alimentar_banco.py`, não é lida do site do mercado.
- **Só no código:** um produto é reconhecido só por `supermercado` + `nome`. Não há código de
  barras nem SKU, e nada impede linhas repetidas.
- `atualizado_em` já registra a hora da coleta, mas a API **não a devolve**, então o site não mostra
  quão recentes são os preços.

## Script de criação

```sql
-- Criando a tabela para armazenar nossos produtos
CREATE TABLE produtos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    supermercado TEXT NOT NULL,
    nome TEXT NOT NULL,
    preco_varejo DECIMAL(10, 2) NOT NULL,
    preco_atacado DECIMAL(10, 2) NOT NULL,
    quantidade_atacado INTEGER NOT NULL,
    uf_cobertura TEXT NOT NULL, -- Para sabermos se é de MG, SP, ou BR (Brasil todo)
    texto_original TEXT,
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Criando um índice para deixar a busca por nome super rápida!
CREATE INDEX idx_nome_produto ON produtos USING GIN (to_tsvector('portuguese', nome));
```

### O índice de nome não é usado pela API

O índice `idx_nome_produto` é de **busca textual** (`to_tsvector`). Ele só acelera consultas escritas
com `to_tsvector('portuguese', nome) @@ ...`. A API busca com `nome ilike '%...%'` (veja
[Como os dados saem](#como-os-dados-saem)), e o PostgreSQL **não usa esse índice** para `ilike`.
Na prática, hoje a busca varre a tabela inteira e o índice só custa tempo extra a cada inserção.
Com poucos milhares de linhas isso passa despercebido, mas deve ser resolvido quando o modelo de
dados for redesenhado (por exemplo, com `pg_trgm` + `unaccent`, ou passando a consulta a usar a
busca textual).

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

## Como confirmar no Supabase

No painel do Supabase, abra **SQL Editor** e rode as consultas abaixo. As mais importantes são as
de número **2**, **4** e **5**; a 1 e a 3 só confirmam que o banco continua igual ao script.
Cole os resultados na conversa para atualizarmos este documento.

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
select supermercado, uf_cobertura, count(*) as itens, max(atualizado_em) as ultima_coleta
from produtos
group by supermercado, uf_cobertura
order by supermercado;
```
