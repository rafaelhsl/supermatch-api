-- Colunas novas em `produtos` para o coletor por API (docs/coletor_por_api.md).
-- Rode o script inteiro no SQL Editor do Supabase. Pode rodar mais de uma vez e não muda nem apaga nenhum dado:
-- só acrescenta colunas vazias e um índice. A API e o site atuais continuam funcionando como estão.

alter table produtos
  add column if not exists ean        text,   -- código de barras (8, 12, 13 ou 14 dígitos); o mesmo EAN é o mesmo produto em qualquer mercado
  add column if not exists marca      text,
  add column if not exists categoria  text,   -- como o mercado classifica, ex.: 'Mercearia > Grãos > Arroz'
  add column if not exists id_origem  text,   -- identidade do produto no mercado (productId:itemId do catálogo); chave do histórico de preços
  add column if not exists termo      text;   -- termo da lista de produtos que trouxe o item, ex.: 'arroz'

create index if not exists produtos_ean on produtos (ean) where ean is not null;

-- Conferência (lista as colunas de `produtos`; as 5 novas aparecem no fim e ficam vazias até a primeira carga com o coletor):
--   select column_name, data_type from information_schema.columns
--   where table_schema = 'public' and table_name = 'produtos' order by ordinal_position;
