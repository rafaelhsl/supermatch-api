-- Coluna nova em `produtos` para o hortifrúti (docs/hortifruti.md, etapa 2).
-- Rode o script inteiro no SQL Editor do Supabase. Pode rodar mais de uma vez e não muda nem apaga nenhum dado: só acrescenta uma coluna
-- vazia (operação instantânea, mesmo com a tabela cheia). A carga e a API de hoje continuam funcionando como estão: nenhuma delas
-- conhece a coluna ainda. O código que a grava e a lê vem num PR seguinte, depois que você rodar este script.

alter table produtos
  add column if not exists unidade text;     -- como o mercado vende: 'kg' = o PREÇO É POR QUILO; 'un' = por unidade ou pacote; vazio = não informado

-- Faz a API do Supabase enxergar a coluna na hora (ele costuma fazer isso sozinho depois de um alter table; não custa nada).
notify pgrst, 'reload schema';

-- Conferência (rode à parte, depois):
--   select column_name, data_type from information_schema.columns
--   where table_schema = 'public' and table_name = 'produtos' and column_name = 'unidade';      -- deve listar 1 linha: unidade | text
--   select count(*) as com_unidade, count(*) filter (where unidade is not null) as preenchidas from produtos;      -- preenchidas = 0 até o código novo gravar
