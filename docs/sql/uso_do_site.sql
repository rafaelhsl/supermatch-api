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
alter table uso_diario enable row level security;
revoke all on uso_diario from anon, authenticated;

-- 3) A soma é uma conta só, feita no banco: dois pedidos ao mesmo tempo não perdem contagem. Quem grava (a API) manda apenas o tipo.
--    (`set search_path = public` fixa onde a função procura a tabela: é o que o painel de segurança do Supabase pede.)
create or replace function registrar_uso(p_evento text)
returns void
language sql
set search_path = public
as $$
  insert into uso_diario (dia, evento, total)
  values ((now() at time zone 'America/Sao_Paulo')::date, p_evento, 1)
  on conflict (dia, evento) do update set total = uso_diario.total + 1;
$$;
revoke all on function registrar_uso(text) from public, anon, authenticated;
grant execute on function registrar_uso(text) to service_role;

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
-- Conferência de que a função está liberada só para a chave secreta (deve listar apenas service_role e postgres):
--   select grantee from information_schema.routine_privileges where routine_name = 'registrar_uso' order by 1;
-- ---------------------------------------------------------------------------------------------------
