-- Medição de uso do Supermatch, SEM rastrear ninguém (desenho em docs/uso_do_site.md).
-- Rode o script inteiro no SQL Editor do Supabase. Pode rodar mais de uma vez: não apaga nem altera nada que já exista.
-- Nenhuma tabela existente é tocada. A API só passa a contar depois que este script rodar; até lá, a contagem falha em silêncio e a busca segue normal.

-- 1) Uma soma por dia, por tipo de ocorrência. São TRÊS colunas e não há onde guardar mais nada: nada de CEP, estado, termo buscado, IP, horário ou identificador.
create table if not exists uso_diario (
  dia     date   not null,                                                          -- dia de Brasília
  evento  text   not null check (evento in ('abertura', 'busca', 'busca_sem_resultado', 'atualizacao_da_lista', 'historico')),
  total   bigint not null default 0 check (total >= 0),
  primary key (dia, evento)
);

-- 2) Só a chave secreta (a API) acessa, como nas outras tabelas: RLS ligado e nenhuma política (a chave pública não lê nem escreve).
--    O `grant` à chave secreta é explícito de propósito: o Supabase está deixando de dar permissão automática em tabela nova, e sem ele
--    a função abaixo (que roda com os direitos de quem chama) falharia com "permission denied". Os três comandos são o que a soma usa.
alter table uso_diario enable row level security;
revoke all on uso_diario from anon, authenticated;
grant select, insert, update on uso_diario to service_role;

-- 3) A soma é uma conta só, feita no banco: dois pedidos ao mesmo tempo não perdem contagem. Quem grava (a API) manda o tipo e quantas vezes
--    aconteceu desde o último envio (a API junta o que chega ao mesmo tempo). Quantidade fora de 1 a 1.000.000 é ignorada.
--    (`set search_path = public` fixa onde a função procura a tabela: é o que o painel de segurança do Supabase pede.)
create or replace function registrar_uso(p_evento text, p_qtd bigint default 1)
returns void
language sql
set search_path = public
as $$
  insert into uso_diario (dia, evento, total)
  select (now() at time zone 'America/Sao_Paulo')::date, p_evento, p_qtd
  where p_qtd between 1 and 1000000
  on conflict (dia, evento) do update set total = uso_diario.total + excluded.total;
$$;
revoke all on function registrar_uso(text, bigint) from public, anon, authenticated;
grant execute on function registrar_uso(text, bigint) to service_role;

notify pgrst, 'reload schema';

-- ---------------------------------------------------------------------------------------------------
-- Para ler os números (rode à parte, no SQL Editor; também em "Table Editor > uso_diario"):
--
--   Por dia, os últimos 30:
--   select dia,
--          coalesce(sum(total) filter (where evento = 'abertura'), 0)             as aberturas_do_site,
--          coalesce(sum(total) filter (where evento = 'busca'), 0)                as buscas,
--          coalesce(sum(total) filter (where evento = 'busca_sem_resultado'), 0)  as buscas_sem_resultado,
--          coalesce(sum(total) filter (where evento = 'atualizacao_da_lista'), 0) as atualizacoes_da_lista,
--          coalesce(sum(total) filter (where evento = 'historico'), 0)            as historicos
--   from uso_diario
--   group by dia
--   order by dia desc
--   limit 30;
--
-- Conferências de que deu certo (cada uma deve responder "true"):
--   select has_table_privilege('service_role', 'uso_diario', 'select')
--      and has_table_privilege('service_role', 'uso_diario', 'insert')
--      and has_table_privilege('service_role', 'uso_diario', 'update') as chave_secreta_pode_somar;
--   select not has_function_privilege('anon', 'registrar_uso(text,bigint)', 'execute')
--      and not has_table_privilege('anon', 'uso_diario', 'select') as chave_publica_nao_chega;
-- ---------------------------------------------------------------------------------------------------
