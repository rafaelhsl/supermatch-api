# Banco de dados (Supabase)

> **Conferido no Supabase em 22/10/2026** com a consulta da seção
> [Diagnóstico rápido](#diagnóstico-rápido-reexecutável): colunas, tipos, restrições, índices, RLS,
> lista de tabelas e volume. O banco está **igual ao script de criação**.

- Projeto Supabase: `gtdvgdfalpsrnefzyfgu` (`https://gtdvgdfalpsrnefzyfgu.supabase.co`)
- Tabelas no schema `public`: apenas **`produtos`** (confirmado em 22/10/2026). O [histórico de preços](historico_de_precos.md)
  acrescenta `catalogo`, `precos` e `coletas` (script em [`sql/historico_precos.sql`](sql/historico_precos.sql));
  `produtos` continua sendo a foto do dia que a API e o site leem.
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
| `texto_original` | `text` | não | scrapers | Texto bruto do card do produto, guardado para depuração (só o robô do Super ABC preenche) |
| `ean` | `text` | não | coletor por API | Código de barras. O mesmo EAN é o mesmo produto em qualquer mercado. O robô do Super ABC não lê |
| `marca` | `text` | não | coletor por API | Marca do produto |
| `categoria` | `text` | não | coletor por API | Como o mercado classifica, ex.: `Mercearia > Grãos > Arroz` |
| `id_origem` | `text` | não | coletor por API | Identidade do produto no mercado (`productId:itemId`); é a chave do histórico de preços |
| `termo` | `text` | não | coletor por API e robô da lista | Termo da [lista de produtos](../dados/lista_de_produtos.json) que trouxe o item, ex.: `arroz`. Vazio nas linhas do modo antigo |

As cinco últimas colunas vêm de [`sql/colunas_do_coletor.sql`](sql/colunas_do_coletor.sql). Sem elas a carga grava só as colunas
antigas (e não aceita coleta parcial); a API e o site não usam as colunas novas.
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

> Este quadro é o de 21/10. As correções de 26 e 27/10 (CEP confirmado em cada robô e Super ABC na
> unidade de Betim) estão descritas em [Como os dados entram](#como-os-dados-entram). Vale rodar de
> novo o [diagnóstico rápido](#diagnóstico-rápido-reexecutável) depois da primeira carga nova.

Última carga completa (GitHub Actions, 21/10/2026 por volta das 12:30 UTC):

| Mercado | UF | Itens | Última coleta (UTC) |
|---|---|---|---|
| Apoio Entrega | MG | 254 | 2026-10-21 12:37 |
| Atacadao | BR | 230 | 2026-10-21 12:37 |
| Supernosso | MG | 229 | 2026-10-21 12:37 |
| **Super ABC** | MG | **0** | nunca aparece |

Cada busca devolve em média 20 a 26 produtos por mercado (a primeira página da prateleira).

### Super ABC: causa encontrada e corrigida

- Nas **10 últimas execuções** (13 a 21/10/2026), as 11 buscas do Super ABC terminaram com
  `Erro na barra de busca: Locator.wait_for: Timeout 10000ms exceeded` e **0 itens**.
- **Causa confirmada em 22/10/2026:** `alimentar_banco.py` abria `https://www.superabc.com.br/`, que
  é o site **institucional** (título "Home | Super ABC") e não tem busca de produtos. A loja online
  é `https://superabconline.com.br/` (título "Super ABC - Loja Online"), que já abre com a loja
  "Hiper ABC Centro - Divinópolis / MG" selecionada.
- Testes com o scraper real, busca por "Cafe": a loja online devolve **30 itens** tanto de uma rede
  residencial em MG quanto do servidor do GitHub Actions (EUA, Microsoft). O site institucional
  devolve 0 nos dois lugares, com o mesmo erro do log.
- Hipóteses descartadas: geobloqueio ou bloqueio de datacenter (o GitHub Actions acessa a loja
  normalmente) e lentidão de renderização no servidor.
- O workflow aparecia como `success` mesmo assim, porque o scraper captura o erro e devolve lista
  vazia. Ninguém era avisado.
- **Correção:** a URL em `alimentar_banco.py` passou para `https://superabconline.com.br/`. A tabela
  acima só passa a incluir o Super ABC na próxima carga completa.
- Para o modelo de cobertura por CEP: a loja online abre com **uma unidade selecionada por padrão**
  (Hiper ABC Centro, Divinópolis/MG), então os preços coletados provavelmente são os dessa unidade
  **[CONFIRMAR]**.

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
com `to_tsvector('portuguese', nome) @@ ...`. A API **não faz busca por nome no banco**: ela carrega
o catálogo da UF e filtra em memória (veja [Como os dados saem](#como-os-dados-saem)). Portanto
esse índice não é usado por ninguém e só custa tempo extra a cada inserção. Pode ser removido, ou
aproveitado quando o modelo de dados for redesenhado (por exemplo, com `pg_trgm` + `unaccent`, se o
catálogo crescer a ponto de não caber em memória).

## Como os dados entram

[`alimentar_banco.py`](../alimentar_banco.py), disparado diariamente pelo workflow
[`.github/workflows/main.yml`](../.github/workflows/main.yml):

1. Lê a lista de 100 produtos ([`dados/lista_de_produtos.json`](../dados/lista_de_produtos.json), até 100 por termo e
   mercado). **Apoio Entrega, Atacadão e Supernosso** são coletados pela API pública
   ([`coletor_por_api.md`](coletor_por_api.md)), em paralelo, no CEP fixo `32607600` (Betim). O **Super ABC**, que não
   tem API aberta, é coletado pelo robô nos mesmos 100 termos (3 navegadores por vez), com o mesmo filtro de nome.
   Cada robô informa o CEP **antes** de buscar e só segue se o site confirmar a localização (veja [`robos.md`](robos.md)).
2. Define `uf_cobertura` e guarda tudo em memória, por mercado.
3. Grava **um mercado por vez**, conforme o resultado da coleta (veja [A carga e as falhas](robos.md#a-carga-e-as-falhas)):
   insere os produtos novos (em lotes de 200) e só então apaga os antigos do mesmo mercado (`atualizado_em` anterior ao
   início da carga). Em coleta parcial, as linhas antigas dos termos que falharam ficam.
4. Registra o [histórico de preços](historico_de_precos.md) e imprime o resumo por mercado. Se algum mercado falhou, termina
   com erro: o GitHub marca a execução como falha e envia o e-mail de aviso.

`SEM_GRAVAR=1` roda tudo sem escrever no banco e sem precisar da chave. `COLETA_POR_API=0` (ou a entrada `coleta = robos` do
workflow, ao disparar à mão) volta ao modo antigo: os 4 robôs com os 11 itens `Arroz`, `Feijao`, `Oleo`, `Cafe`,
`Manteiga`, `Açucar`, `Macarrao`, `Detergente`, `Sabao`, `Amaciante` e `Higienico`, tudo ou nada.

No modo antigo (27/10/2026) a carga tinha cerca de 1.007 itens (Apoio 256, Atacadão 223, Supernosso 224, Super ABC 304). Com a
lista de 100 produtos a tabela passa de 8 mil linhas. **Passa de 1.000 linhas**, o limite de uma consulta do Supabase; a API
já pagina o catálogo (veja [Como os dados saem](#como-os-dados-saem)).

Riscos conhecidos desse fluxo:

- **Dados antigos podem ficar:** se um mercado falhar, o preço dele continua o do último dia em que
  deu certo. A API não devolve `atualizado_em`, então o site não mostra a idade do preço.
- Os preços são os de um único CEP (Betim), mas a API os devolve para qualquer CEP da mesma UF. O
  modelo de cobertura por CEP ainda não existe.
- O Super ABC é coletado na unidade de Betim; o Atacadão, na loja de Betim.

## Como os dados saem

Endpoint `GET /comparar?cep=...&item=...` em [`api_supabase.py`](../api_supabase.py):

1. Descobre a UF do CEP pelo ViaCEP (se falhar, usa `BR`).
2. Pega o **catálogo** da UF, ou seja, todos os produtos com `uf_cobertura` igual à UF do CEP ou
   a `BR`, **em memória** (os preços só mudam na carga diária). Baixá-lo do banco leva uns 6 s com 8 mil
   produtos, por isso:
   - Passados 10 minutos, a busca **responde na hora com o catálogo que tem** e a atualização roda em
     segundo plano; a busca seguinte já vê o novo. Só a primeira busca depois de o servidor acordar, sem
     catálogo nenhum, espera o download.
   - Só uma atualização por UF acontece por vez, mesmo com várias buscas chegando juntas.
   - Se a atualização falhar (banco fora do ar), a API segue com o catálogo anterior e avisa no log.
   - O servidor começa a carregar o catálogo ao ligar e quando o site chama `/saude`, então a primeira
     busca depois de abrir o site já o encontra pronto.

   A consulta ao banco é paginada de 1000 em 1000 linhas, o limite do Supabase por requisição, e pede só
   as colunas que a API devolve ou usa (fica de fora `texto_original`, o texto bruto do robô):

```sql
select id, supermercado, nome, marca, ean, categoria, id_origem, termo,
       preco_varejo, preco_atacado, quantidade_atacado, uf_cobertura, atualizado_em
from produtos
where uf_cobertura in ('<UF do CEP>', 'BR')
order by id
limit 1000 offset <0, 1000, 2000, ...>;
```

3. Filtra o catálogo em memória ([`busca.py`](../busca.py)): ignora maiúsculas e acentos e exige que
   o nome contenha **todas** as palavras digitadas, em qualquer ordem. Palavras de ligação (`de`,
   `da`, `do`, `e`, `com`, `para`, `em`) são ignoradas, então `óleo de soja` também acha
   `Óleo Soja Liza`. Os resultados têm duas faixas:
   - **principais**: o `termo` do produto (coluna `termo`, ex.: `arroz`) tem as palavras digitadas, ou o
     nome **começa** por elas (`Arroz Branco Camil…`). Palavras de até 3 letras valem inteiras (`sal` não
     acha `salsicha`); as de 4 ou mais valem como começo (`arro` acha `arroz`);
   - **só citam**: a palavra aparece no meio do nome (`Condicionador… Arroz Preto`, `Sardinha em Óleo`).

   Havendo 3 ou mais principais, só eles voltam; o resto vira `ocultos` na resposta. Com menos de 3
   (uma marca como `ninho`, um produto fora da lista), voltam todos, principais primeiro, e `ocultos` é 0.
   A resposta traz no máximo 400 produtos (a busca de uma letra casava 6,6 mil e o agrupamento levava
   24 s); os que passam disso também entram em `ocultos`.
4. Passa o resultado para `cruzar_multiplos_produtos` ([`Comparador_inteligente.py`](../Comparador_inteligente.py)),
   que agrupa o mesmo produto de mercados diferentes e aponta o mais barato de cada grupo:
   1. **Mesmo código de barras (`ean`) = mesmo produto**, sem adivinhar pelo nome. O EAN é comparado sem os zeros
      à esquerda (`0630941446201` = `630941446201`). Só não junta se as medidas do nome discordarem.
   2. **EAN diferente, nome praticamente idêntico** (pontuação de similaridade 95 ou mais), mesma medida e
      mesmas tags, **em mercados diferentes**: junta. O mesmo produto às vezes tem um EAN em cada mercado (o do
      Apoio costuma diferir nos últimos dígitos). `Heineken Zero` e `Heineken` (pontuação ~86) ficam separados.
   3. **Sem EAN** (o robô do Super ABC não o lê): entra no grupo mais parecido pelo nome, como sempre foi
      (mesma medida, mesmas tags, similaridade a partir de 75).
   O grupo traz `ean` quando tem um. Em dados reais de 05/11/2026 (6,7 mil produtos), o número de grupos
   comparáveis (com 2 ou mais mercados) nas 15 buscas mais comuns subiu de 321 para 475, e os grupos que
   misturavam EANs diferentes por nome parecido (Skol com Kaiser, Fanta com Guaraná, Coca Zero com Coca) deixaram de existir.
5. Ordena os grupos: primeiro os vendidos em mais mercados (os que permitem comparar), depois por
   ordem alfabética.

Antes de 23/10/2026 a busca era feita no banco com `nome ilike '%...%'`, trocando **todas as
vogais do termo por `_`** para ignorar acentos. Em palavras curtas isso virava um padrão que casa
com quase tudo: `óleo` virava `_l__` e devolvia 583 produtos, só 83 deles com óleo, com o arroz no
topo. O comparador também fazia a conta de nome, medida e tags de cada grupo a cada produto, o que
levava 15 s no Render para essa resposta.

A resposta de `/comparar` tem os campos `status`, `cep`, `uf`, `item`, `mercados_consultados` e `carrinho_comparativo`, mais
o que a busca deixou de fora (passo 3):

| Campo | O que é |
|---|---|
| `ocultos` | Total que ficou de fora: os que só citam a palavra mais os que passaram do teto de 400. |
| `ocultos_so_citam` | Quantos produtos que só citam a palavra foram escondidos. Vale 0 quando havia menos de 3 principais (voltaram todos) ou quando se pediu `todos=1`. |
| `ocultos_pelo_limite` | Quantos passaram do teto de 400 resultados. |
| `so_citam_por_mercado` | `{mercado: quantos}` dos produtos que só citam a palavra, escondidos ou não. O site soma só os mercados que entregam na cidade da pessoa. |

A resposta traz ainda `equivalencia_familias`, a lista dos tipos de produto para os quais o modo "Produto equivalente" funciona
(arroz, feijão, leite…). Cada opção de compra de uma família traz `chave_equivalencia` e `rotulo_equivalencia`; produto fora de
qualquer família vem sem esses dois campos. A chave é calculada pela API ao carregar o catálogo (`equivalencia.py`), não fica
no banco. Veja [`equivalencia.md`](equivalencia.md).

O parâmetro opcional `todos=1` (`/comparar?cep=...&item=...&todos=1`) devolve também os que só citam a palavra. Cada opção
desses vem marcada com `"so_cita": true`. É o que o botão "Mostrar também" do site pede.

O endpoint `GET /saude` responde `{"status": "ok"}` sem esperar o banco (só dispara o carregamento do catálogo
em segundo plano, se preciso). O site o chama ao abrir a página para acordar o servidor, que no plano gratuito do
Render dorme após 15 minutos sem uso; o acordar do servidor (cerca de 30 a 60 s) continua sendo o maior tempo de
espera da primeira busca do dia.

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
