// Roda docs/sql/uso_do_site.sql num Postgres de verdade (PGlite = Postgres em WebAssembly, sem instalar nada) imitando o Supabase: os papéis
// anon, authenticated e service_role, em DOIS cenários de permissão padrão:
//   - o ANTIGO: todo objeto novo em public nasce acessível a anon, authenticated e service_role;
//   - o NOVO: o Supabase deixa de dar permissão automática em tabela e função novas (por isso o script dá o `grant` à chave secreta).
// Confere: restrições, a soma (de um em um e em lote), a quantidade fora de 1 a 1.000.000, o dia de Brasília, quem pode o quê, "rodar duas vezes"
// e as consultas de leitura e de conferência que estão no próprio script e em docs/uso_do_site.md.
//
// É feito à mão (o CI não roda: precisa de `npm install`). Quando mexer em docs/sql/uso_do_site.sql, rode:
//   cd tests/postgres_de_verdade && npm install && node testa_uso_do_site.mjs
// (opcional: outro arquivo .sql como argumento, para provar que o teste pega o defeito de um script quebrado)
import { readFileSync } from "node:fs";
import { PGlite } from "@electric-sql/pglite";

const ARQUIVO = process.argv[2] || new URL("../../docs/sql/uso_do_site.sql", import.meta.url);
const sql = readFileSync(ARQUIVO, "utf8");
let ok = 0;
const falhas = [];

async function cenario(nome, padraoAntigo) {
  const db = new PGlite();
  const confere = (cond, texto) => { if (cond) ok++; else falhas.push(`[${nome}] ${texto}`); console.log((cond ? "OK    " : "FALHA ") + `[${nome}] ${texto}`); };
  const falha = async (texto, consulta) => {
    try { await db.query(consulta); confere(false, `${texto} (devia dar erro)`); }
    catch (e) { confere(true, `${texto}  -> ${String(e.message).split("\n")[0].slice(0, 100)}`); }
  };
  const prv = async (consulta) => (await db.query(consulta)).rows[0].v;

  await db.exec(`
    create role anon nologin;
    create role authenticated nologin;
    create role service_role nologin bypassrls;
    grant usage on schema public to anon, authenticated, service_role;
  `);
  if (padraoAntigo) {
    await db.exec(`
      alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
      alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
      alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;
    `);
  } else {
    await db.exec(`
      alter default privileges in schema public revoke all on tables from anon, authenticated, service_role;
      alter default privileges in schema public revoke execute on functions from anon, authenticated, service_role;
    `);
  }

  // 1. o script roda, e roda de novo
  await db.exec(sql);
  confere(true, "o script rodou inteiro");
  await db.exec(sql);
  confere(true, "o script roda de novo sem erro");

  // 2. a tabela
  const colunas = (await db.query("select column_name from information_schema.columns where table_schema='public' and table_name='uso_diario' order by ordinal_position")).rows.map((r) => r.column_name);
  confere(JSON.stringify(colunas) === JSON.stringify(["dia", "evento", "total"]), `colunas da tabela: ${colunas}`);
  confere((await db.query("select relrowsecurity from pg_class where relname='uso_diario'")).rows[0].relrowsecurity === true, "RLS ligado");
  confere((await db.query("select count(*)::int as n from pg_policies where tablename='uso_diario'")).rows[0].n === 0, "nenhuma política de acesso");

  // 3. quem pode o quê: a chave secreta soma; a pública não chega a nada
  confere(await prv("select has_table_privilege('service_role','uso_diario','select') and has_table_privilege('service_role','uso_diario','insert') and has_table_privilege('service_role','uso_diario','update') as v"), "conferência do script: a chave secreta tem select, insert e update na tabela");
  confere(await prv("select not has_function_privilege('anon','registrar_uso(text,bigint)','execute') and not has_table_privilege('anon','uso_diario','select') as v"), "conferência do script: a chave pública não chega");
  for (const papel of ["anon", "authenticated"]) {
    confere(!(await prv(`select has_function_privilege('${papel}', 'registrar_uso(text,bigint)', 'execute') as v`)), `${papel} NÃO executa registrar_uso`);
    for (const p of ["select", "insert", "update", "delete", "truncate"]) confere(!(await prv(`select has_table_privilege('${papel}', 'uso_diario', '${p}') as v`)), `${papel} NÃO faz ${p} em uso_diario`);
  }
  confere(await prv("select has_function_privilege('service_role', 'registrar_uso(text,bigint)', 'execute') as v"), "service_role executa registrar_uso");

  // 4. a soma, chamando COMO A API (service_role)
  await db.exec("set role service_role");
  for (const e of ["busca", "busca", "busca", "busca_sem_resultado", "historico", "historico", "abertura", "atualizacao_da_lista", "atualizacao_da_lista"]) await db.query(`select registrar_uso('${e}')`);
  await db.query("select registrar_uso('busca', 5)");
  await db.query("select registrar_uso('historico', 1000000)");
  await db.exec("reset role");
  const linhas = (await db.query("select evento, total::int as total from uso_diario order by evento")).rows.map((r) => `${r.evento}|${r.total}`);
  confere(JSON.stringify(linhas) === JSON.stringify(["abertura|1", "atualizacao_da_lista|2", "busca|8", "busca_sem_resultado|1", "historico|1000002"]), `somas (uma a uma e em lote): ${linhas.join("  ")}`);
  const dia = (await db.query("select distinct dia::text as dia, ((now() at time zone 'America/Sao_Paulo')::date)::text as brasilia from uso_diario")).rows;
  confere(dia.length === 1 && dia[0].dia === dia[0].brasilia, `o dia gravado é o de Brasília: ${JSON.stringify(dia)}`);

  // 5. quantidade fora de 1 a 1.000.000 é ignorada, sem erro e sem mudar nada
  await db.exec("set role service_role");
  for (const q of ["0", "-1", "-5000", "1000001", "null"]) await db.query(`select registrar_uso('abertura', ${q})`);
  await db.exec("reset role");
  confere((await db.query("select total::int as t from uso_diario where evento='abertura'")).rows[0].t === 1, "quantidade 0, negativa, acima de 1.000.000 ou nula é ignorada (abertura continua em 1)");

  // 6. o banco recusa o que não é da lista (mesmo para quem escreve direto na tabela)
  await db.exec("set role service_role");
  await falha("evento fora da lista", "select registrar_uso('termo')");
  await falha("evento com um CEP", "select registrar_uso('30130010', 2)");
  await falha("evento vazio", "select registrar_uso('')");
  await falha("evento nulo", "select registrar_uso(null)");
  await falha("evento em maiúsculas", "select registrar_uso('Busca')");
  await falha("insert direto com evento livre", "insert into uso_diario (dia, evento, total) values (current_date, 'arroz', 1)");
  await falha("total negativo", "insert into uso_diario (dia, evento, total) values (current_date, 'busca', -1)");
  await falha("coluna de CEP não existe", "insert into uso_diario (dia, evento, total, cep) values (current_date, 'busca', 1, '30130010')");
  await falha("coluna de estado não existe", "insert into uso_diario (dia, evento, total, uf) values (current_date, 'busca', 1, 'MG')");
  await falha("a assinatura antiga (text, text) não existe", "select registrar_uso('busca', 'MG')");
  await db.exec("reset role");

  // 7. de verdade, trocando de papel
  await db.exec("set role anon");
  await falha("anon chamando a função", "select registrar_uso('busca')");
  await falha("anon lendo a tabela", "select * from uso_diario");
  await db.exec("reset role");
  await db.exec("set role authenticated");
  await falha("authenticated chamando a função", "select registrar_uso('busca', 3)");
  await falha("authenticated lendo a tabela", "select * from uso_diario");
  await db.exec("reset role");

  // 8. a consulta de leitura que está nos comentários do script e em docs/uso_do_site.md
  const porDia = (await db.query(`select dia,
       coalesce(sum(total) filter (where evento = 'abertura'), 0)             as aberturas_do_site,
       coalesce(sum(total) filter (where evento = 'busca'), 0)                as buscas,
       coalesce(sum(total) filter (where evento = 'busca_sem_resultado'), 0)  as buscas_sem_resultado,
       coalesce(sum(total) filter (where evento = 'atualizacao_da_lista'), 0) as atualizacoes_da_lista,
       coalesce(sum(total) filter (where evento = 'historico'), 0)            as historicos
from uso_diario group by dia order by dia desc limit 30`)).rows[0];
  confere(Number(porDia.aberturas_do_site) === 1 && Number(porDia.buscas) === 8 && Number(porDia.buscas_sem_resultado) === 1 && Number(porDia.atualizacoes_da_lista) === 2 && Number(porDia.historicos) === 1000002,
    `consulta "por dia": ${JSON.stringify(porDia, (k, v) => typeof v === "bigint" ? Number(v) : v)}`);
}

await cenario("padrão antigo do Supabase", true);
await cenario("padrão novo (sem permissão automática)", false);

console.log(`\nRESUMO: ${ok} ok, ${falhas.length} falhas`);
for (const f of falhas) console.log("  -", f);
process.exit(falhas.length ? 1 : 0);
