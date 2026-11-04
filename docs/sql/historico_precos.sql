-- Histórico de preços do Supermatch (desenho em docs/historico_de_precos.md).
-- Rode o script inteiro no SQL Editor do Supabase. Pode rodar mais de uma vez: não apaga nem altera nada que já exista.
-- A tabela `produtos` não é tocada: ela continua sendo a foto do dia que a API e o site leem.

-- 1) O produto, com identidade estável. (`produtos` é recriada a cada carga e seus ids mudam todo dia.)
create table if not exists catalogo (
  id            bigint generated always as identity primary key,
  supermercado  text    not null,
  chave_origem  text    not null,           -- identidade dentro do mercado: hoje um resumo do nome; depois, o id do catálogo do mercado
  nome          text    not null,
  ean           text,                       -- código de barras (preenchido quando o coletor por API entrar)
  marca         text,
  categoria     text,
  primeiro_dia  date    not null,           -- 1º dia em que foi visto (data de Brasília)
  ultimo_dia    date    not null,           -- último dia em que foi visto
  ativo         boolean not null default true,   -- false: sumiu de 3 cargas completas seguidas
  unique (supermercado, chave_origem)
);
create index if not exists catalogo_ean on catalogo (ean) where ean is not null;

-- 2) O preço, só quando muda: cada linha vale do dia `desde` até o dia `ate` (vazio = vale até hoje).
--    `praca` é a região da coleta (hoje só 'betim'; o Apoio muda de catálogo e de preço conforme a região).
create table if not exists precos (
  catalogo_id         bigint        not null references catalogo(id) on delete cascade,
  praca               text          not null default 'betim',
  desde               date          not null,
  ate                 date,
  preco_varejo        numeric(10,2) not null check (preco_varejo > 0),
  preco_atacado       numeric(10,2),
  quantidade_atacado  int,
  disponivel          boolean       not null default true,
  primary key (catalogo_id, praca, desde),
  check (ate is null or ate >= desde)
);
create unique index if not exists precos_aberto on precos (catalogo_id, praca) where ate is null;   -- um só preço vigente por produto e praça
create index if not exists precos_desde on precos (desde);                                         -- "o que mudou no dia X"

-- 3) O que cada carga fez. Dia sem linha 'ok' é lacuna: não vira queda de preço nem produto que saiu.
create table if not exists coletas (
  dia           date not null,
  supermercado  text not null,
  praca         text not null default 'betim',
  status        text not null check (status in ('ok', 'parcial', 'falhou')),
  itens         int,
  erro          text,
  primary key (dia, supermercado, praca)
);

-- Só a chave secreta (a carga e a API) acessa, como na tabela `produtos`: RLS ligado e nenhuma política.
alter table catalogo enable row level security;
alter table precos   enable row level security;
alter table coletas  enable row level security;

-- ---------------------------------------------------------------------------------------------------
-- Conferências (rode à parte, depois da primeira carga com o histórico ligado):
--
--   select supermercado, count(*) from catalogo group by 1;                               -- produtos por mercado
--   select status, count(*) from coletas group by 1;                                      -- cargas registradas
--   select count(*) from precos where ate is null;                                        -- preços vigentes (deve ser ~ produtos ativos)
--
-- Preço de cada produto do Atacadão em 10/11/2026:
--   select c.nome, p.preco_varejo
--   from precos p join catalogo c on c.id = p.catalogo_id
--   where c.supermercado = 'Atacadao' and p.desde <= '2026-11-10' and (p.ate is null or p.ate >= '2026-11-10');
--
-- Série de preços de um produto:
--   select p.desde, p.ate, p.preco_varejo from precos p
--   where p.catalogo_id = 123 order by p.desde;
-- ---------------------------------------------------------------------------------------------------
