# Medição de uso (sem rastrear ninguém)

Para saber se o site está sendo usado (e quanto, depois de divulgado), a API **soma por dia** cinco coisas. É só isso: números. Decidido pelo dono em 24/11/2026: *"a medida deve ser feita sem rastrear"*.

## O que é somado

| Soma (`evento`) | Quando conta 1 |
|---|---|
| `abertura` | o site foi aberto (ou recarregado): ele chama `GET /saude?origem=site` |
| `busca` | um pedido de busca a `/comparar` feito por uma pessoa (inclui "Mostrar também" e "Buscar de novo"). **Cada produto pesquisado conta 1** |
| `busca_sem_resultado` | a mesma busca, quando não achou nenhum produto (conta além de `busca`) |
| `atualizacao_da_lista` | o site renovando sozinho os preços da lista de compras (`/comparar?...&origem=lista`: 1 por produto da lista, ao abrir a página e ao voltar à aba depois de 3 h). **Não conta como busca**: não foi ninguém que buscou |
| `historico` | alguém abriu o gráfico de preços de um produto (`/historico` respondeu; vale também quando a resposta veio do cache) |

## O que nunca é guardado

CEP (nem os 5 primeiros dígitos), **estado**, termo buscado, produto, endereço IP, navegador, horário da chamada e qualquer identificador de pessoa. A tabela `uso_diario` tem **três colunas**: `dia`, `evento` e `total`. Não há onde guardar mais nada, e o banco recusa qualquer evento fora da lista.

(Uma versão anterior deste desenho guardava também o estado do CEP nas buscas. Saiu antes de ir ao ar: o site já barra CEP de cidade não atendida antes de chamar a API, então o estado quase sempre seria MG e não diria nada. Menos dado é mais privacidade.)

Por isso também **não dá para saber "quantas pessoas"**: isso exigiria reconhecer cada uma (cookie, IP, impressão digital do navegador), que é exatamente o rastreamento que o aviso promete não fazer. Só se sabe **quantas vezes**.

## Como funciona

```
site (abre)    ──GET /saude?origem=site──────┐
site (busca)   ──GET /comparar ──────────────┤
site (lista)   ──GET /comparar?origem=lista ─┼─►  API (api_supabase.py)  ─►  fila  ─►  fio próprio  ─►  rpc registrar_uso(evento)  ─►  uso_diario
site (gráfico) ──GET /historico ─────────────┘     _medidor.contar(...)    (500)     (medidor_de_uso.py)    soma 1 no dia de Brasília
```

- [`medidor_de_uso.py`](../medidor_de_uso.py) guarda a lista fechada de eventos e o `MedidorDeUso`. O pedido do usuário só **põe o nome do evento numa fila e segue**; um fio à parte manda a fila para o banco, uma soma por vez.
- **A contagem nunca atrasa nem derruba uma resposta.** Se o banco estiver fora, ou o SQL ainda não tiver sido rodado, a soma falha em silêncio: o log do Render mostra `⚠️ Medição de uso indisponível (a busca segue normal): ...` no máximo uma vez a cada 10 minutos. Se a fila encher (500 somas esperando), as que sobrarem são descartadas: medir é secundário, atender é o que importa.
- A soma em si é uma função do banco (`registrar_uso`, em [`sql/uso_do_site.sql`](sql/uso_do_site.sql)): `insert … on conflict do update set total = total + 1`, atômica, então dois pedidos ao mesmo tempo não perdem contagem. O dia é o de Brasília e só o dia é guardado.
- Só a chave secreta (a da API) chama a função e acessa a tabela: RLS ligado sem nenhuma política, e `revoke` para `anon` e `authenticated`. O script foi rodado num Postgres de verdade (PGlite, imitando os papéis e os privilégios padrão do Supabase) em 24/11/2026: restrições, soma, dia de Brasília, permissões e "rodar duas vezes" conferidos.
- `/saude` sem `origem=site` **não conta**: o Health Check do Render (a cada poucos segundos) e os monitores externos não inflam a medição.

## Para ligar (uma vez)

1. No Supabase, abra o **SQL Editor** e rode o conteúdo de [`sql/uso_do_site.sql`](sql/uso_do_site.sql). Pode rodar mais de uma vez; não mexe em nenhuma tabela existente.
2. Pronto: a API já começa a contar (não precisa reiniciar). Antes disso ela segue funcionando normalmente, só sem contar.
3. Conferência, depois de abrir o site e fazer uma busca: `select * from uso_diario order by dia desc;` deve mostrar linhas de hoje.

## Para ler os números

No SQL Editor (ou em **Table Editor > `uso_diario`**):

```sql
-- por dia, os últimos 30
select dia,
       coalesce(sum(total) filter (where evento = 'abertura'), 0)             as aberturas_do_site,
       coalesce(sum(total) filter (where evento = 'busca'), 0)                as buscas,
       coalesce(sum(total) filter (where evento = 'busca_sem_resultado'), 0)  as buscas_sem_resultado,
       coalesce(sum(total) filter (where evento = 'atualizacao_da_lista'), 0) as atualizacoes_da_lista,
       coalesce(sum(total) filter (where evento = 'historico'), 0)            as historicos
from uso_diario
group by dia
order by dia desc
limit 30;
```

Como ler: **aberturas** mostra o alcance da divulgação; **buscas ÷ aberturas** mostra quanto de quem abre chega a buscar; **buscas sem resultado ÷ buscas** mostra o que o catálogo não cobre (sem dizer o quê: o termo não é guardado); **históricos** mostra o interesse no gráfico.

## Limites (o que esses números não dizem)

- Sem "pessoas" e sem "voltaram": só contagens. Uma pessoa que abre o site 5 vezes são 5 aberturas.
- `abertura` inclui recarregar a página, abas de pré-visualização do Netlify, execuções locais do site (todos falam com a API de produção), abas esquecidas e robôs que executam JavaScript. **Nos primeiros dias, os testes do próprio dono e os de quem mantém o projeto entram na conta.** Link compartilhado no WhatsApp **não** conta (a prévia não executa o site).
- `busca` conta pedidos à API, não "sessões": quem busca 5 produtos faz 5 buscas.
- Se o servidor reiniciar, pode perder as poucas somas que estavam na fila naquele instante.
- Ver as visitas no Netlify é outra coisa: o painel **Observability** do Netlify mostra só as últimas 24 horas no plano gratuito (veja [`privacidade.md`](privacidade.md)).

## O que trava cada garantia

| Garantia | Quem trava |
|---|---|
| a lista de eventos é fechada e igual no Python e no SQL | `tests/test_medidor_de_uso.py` (lê o `check` do SQL e compara com `EVENTOS`) |
| só o nome do evento sai da API; nada de CEP, estado, termo, produto ou IP | o mesmo teste: busca com CEP e termo "secretos", lista, gráfico e abertura; confere que nenhuma chamada ao banco, nem o pedido HTTP de verdade, contém nada deles |
| a tabela só tem `dia`, `evento`, `total`, sem horário | o mesmo teste, lendo o SQL |
| só a chave secreta acessa a tabela e a função | `tests/test_sql.py` (toda tabela nova com RLS, toda função nova fechada para `anon`/`authenticated`) e o teste acima |
| a contagem não atrasa nem derruba a busca | o mesmo teste: banco lento (0,6 s) não atrasa a resposta; banco sem a função não atrapalha e avisa uma vez |
| `/saude` de monitor não conta, o do site sim; a lista não conta como busca | o mesmo teste, `tests/test_privacidade.js` e os de navegador `test_site_privacidade.py` (o site só chama `/saude?origem=site` ao abrir) e `test_site_lista.py` (a renovação da lista manda `origem=lista`) |
| o aviso do site diz o que é somado | `tests/test_privacidade.js` e `tests/navegador/test_site_privacidade.py` |

## Acrescentar uma soma nova

1. Inclua o nome em `EVENTOS` de `medidor_de_uso.py` e chame `_medidor.contar(...)` no ponto certo de `api_supabase.py`.
2. Acrescente o nome ao `check (evento in (...))` de `sql/uso_do_site.sql`. O teste confere que as duas listas são iguais. Atenção: numa tabela que **já existe**, o `create table if not exists` não troca a restrição; trocá-la é uma migração à parte (um script novo em `docs/sql/`, e o `tests/test_sql.py`, que só aceita scripts aditivos, vai pedir uma exceção). Combine com o dono antes.
3. Atualize o aviso do site ("O que medimos") e esta página. Se a soma nova guardar algo além de um número por dia, **pare**: isso deixa de ser "sem rastrear" e é decisão do dono.
