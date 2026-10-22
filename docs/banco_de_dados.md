# Banco de dados (Supabase)

> **Conferido no Supabase em 22/10/2026** com a consulta da seção
> [Diagnóstico rápido](#diagnóstico-rápido-reexecutável): colunas, tipos, restrições, índices, RLS,
> lista de tabelas e volume. O banco está **igual ao script de criação**.

- Projeto Supabase: `gtdvgdfalpsrnefzyfgu` (`https://gtdvgdfalpsrnefzyfgu.supabase.co`)
- Tabelas no schema `public`: apenas **`produtos`** (confirmado).
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
| `preco_varejo` | `numeric` (`decimal(10,2)`) | sim | scrapers | Preço unitário normal. Nos mercados com regra de atacado, é o **maior** dos preços lidos |
| `preco_atacado` | `numeric` (`decimal(10,2)`) | sim | scrapers | Preço unitário a partir de `quantidade_atacado`. Sem atacado, é igual a `preco_varejo` |
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

## Segurança (RLS)

O RLS está **ligado** em `produtos` e **não há nenhuma política** (confirmado).

- As chaves públicas do Supabase (`anon` e `authenticated`) **não conseguem ler nem gravar** nessa
  tabela. Só a chave secreta (`service_role`) acessa, e ela ignora o RLS.
- A API e o robô funcionam, então o `SUPABASE_KEY` do Render e do GitHub Actions é uma chave desse
  tipo (deduzido do comportamento; não foi verificado nos painéis).
- Para o estado atual isso é seguro: o site fala só com a API, nunca direto com o Supabase.
- Pontos de atenção para o redesenho: a API só precisa **ler**, mas roda com poder total de
  escrita; e, se o site um dia falar direto com o Supabase, será preciso criar políticas.

## Estado da coleta em 21/10/2026

Última carga completa (GitHub Actions, 21/10/2026 por volta das 12:30 UTC):

| Mercado | UF | Itens | Última coleta (UTC) |
|---|---|---|---|
| Apoio Entrega | MG | 254 | 2026-10-21 12:37 |
| Atacadao | BR | 230 | 2026-10-21 12:37 |
| Supernosso | MG | 229 | 2026-10-21 12:37 |
| **Super ABC** | MG | **0** | nunca aparece |

Cada busca devolve em média 20 a 26 produtos por mercado (a primeira página da prateleira).

### Problema: o Super ABC não está entrando no banco

- Nas **10 últimas execuções** (13 a 21/10/2026), as 11 buscas do Super ABC terminaram com
  `Erro na barra de busca: Locator.wait_for: Timeout 10000ms exceeded` e **0 itens**.
- O workflow aparece como `success` mesmo assim, porque o scraper captura o erro e devolve lista
  vazia. Ninguém é avisado.
- Consequência: a API nunca devolve preços do Super ABC, embora o resto do sistema o trate como um
  dos mercados.
- `alimentar_banco.py` chama `https://www.superabc.com.br/` (a página responde com título
  "Home | Super ABC"), mas o teste local do próprio scraper usa `https://superabconline.com.br/`.
  Em 22/10/2026 esse segundo endereço respondeu `403` (bloqueio do CloudFront) a uma requisição
  simples.
- **[A INVESTIGAR]** Hipóteses ainda não confirmadas: (1) a loja online é a `superabconline.com.br`
  e o robô está abrindo o site institucional, que não tem a barra de busca de produtos; (2) o site
  da loja bloqueia os IPs do GitHub Actions. Falta abrir os dois endereços num navegador e rodar o
  scraper isolado.

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

### Índices existentes e o índice de nome não usado

Confirmado: só existem dois índices, `produtos_pkey` (em `id`) e `idx_nome_produto`. Não há índice
em `uf_cobertura` nem em `supermercado`.

O `idx_nome_produto` é de **busca textual** (`to_tsvector`). Ele só acelera consultas escritas
com `to_tsvector('portuguese', nome) @@ ...`. A API busca com `nome ilike '%...%'` (veja
[Como os dados saem](#como-os-dados-saem)), e o PostgreSQL **não usa esse índice** para `ilike`.
Na prática, hoje a busca varre a tabela inteira e o índice só custa tempo extra a cada inserção.
Com algumas centenas de linhas isso passa despercebido, mas deve ser resolvido quando o modelo de
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
- **Falhas silenciosas:** o workflow termina como `success` mesmo quando um mercado inteiro volta
  com 0 itens (caso do Super ABC, veja acima). Falta uma verificação que avise ou até impeça de
  apagar os dados antigos quando uma coleta vier vazia.
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

## Diagnóstico rápido (reexecutável)

Consulta somente de leitura. Cole no **SQL Editor** do Supabase para ver, de uma vez, as colunas,
as tabelas, os índices, o RLS, as políticas e o volume por mercado. Foi assim que a seção
"Estado da coleta" foi levantada.

```sql
select jsonb_build_object(
  'colunas', (
    select jsonb_agg(jsonb_build_object(
      'coluna', column_name::text, 'tipo', data_type::text,
      'nulo', is_nullable::text, 'padrao', column_default::text
    ) order by ordinal_position)
    from information_schema.columns
    where table_schema = 'public' and table_name = 'produtos'
  ),
  'tabelas_public', (
    select jsonb_agg(table_name::text order by table_name)
    from information_schema.tables
    where table_schema = 'public'
  ),
  'indices', (
    select jsonb_agg(indexdef)
    from pg_indexes
    where schemaname = 'public' and tablename = 'produtos'
  ),
  'rls_ligado', (
    select relrowsecurity from pg_class where oid = 'public.produtos'::regclass
  ),
  'politicas', (
    select coalesce(jsonb_agg(jsonb_build_object(
      'nome', policyname, 'comando', cmd, 'papeis', roles, 'regra', qual
    )), '[]'::jsonb)
    from pg_policies
    where schemaname = 'public' and tablename = 'produtos'
  ),
  'volume', (
    select jsonb_agg(jsonb_build_object(
      'supermercado', supermercado, 'uf', uf_cobertura,
      'itens', itens, 'ultima_coleta', ultima
    ))
    from (
      select supermercado, uf_cobertura, count(*) as itens, max(atualizado_em) as ultima
      from public.produtos
      group by supermercado, uf_cobertura
      order by supermercado
    ) t
  )
) as diagnostico;
```
