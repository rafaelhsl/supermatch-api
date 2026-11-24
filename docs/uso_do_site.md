# Medição de uso (sem rastrear ninguém)

Para saber se o site está sendo usado (e quanto, depois de divulgado), a API **soma por dia** cinco coisas. É só isso: números. Decidido pelo dono em 24/11/2026: *"a medida deve ser feita sem rastrear"*.

## O que é somado

| Soma (`evento`) | Quando conta 1 |
|---|---|
| `abertura` | o site foi aberto (ou recarregado): ele chama `GET /saude?origem=site` |
| `busca` | um pedido de busca a `/comparar` (inclui "Mostrar também" e "Buscar de novo"). **Cada produto pesquisado conta 1.** É um pedido à API, então vem do site, mas também de robôs e de chamadas diretas |
| `busca_sem_resultado` | a mesma busca, quando não achou nenhum produto (conta além de `busca`) |
| `atualizacao_da_lista` | o site renovando sozinho os preços da lista de compras (`/comparar?...&origem=lista`: 1 por termo dos itens da lista com preço de mais de 3 horas, ao abrir a página e ao voltar à aba). **Não conta como busca**: não foi ninguém que buscou |
| `historico` | o site consultou o histórico de preços de um produto (`/historico` respondeu; vale também quando a resposta veio do cache da API). **Reabrir o mesmo gráfico em até 10 minutos não chega à API** (o navegador guarda a resposta) e não conta |

## O que a medição nunca guarda

Na tabela `uso_diario` e no que a API envia: CEP (nem os 5 primeiros dígitos), **estado**, termo buscado, produto, endereço IP, navegador, horário da chamada e qualquer identificador de pessoa. A tabela tem **três colunas**: `dia`, `evento` e `total`. Não há onde guardar mais nada, e o banco recusa qualquer evento fora da lista.

Isso **não muda o que os provedores guardam por conta própria** ([`privacidade.md`](privacidade.md)): o Render guarda por 7 dias o que foi buscado e os 5 primeiros dígitos do CEP (e o IP); o Netlify guarda o IP; e o **Supabase anota cada chamada a `registrar_uso`** (hora, caminho e o IP do servidor do Render, sem o corpo do pedido; 1 dia no plano gratuito, 7 no Pro, segundo a documentação dele). Esse último registro não traz CEP, termo, produto nem o tipo da soma.

(Uma versão anterior deste desenho guardava também o estado do CEP nas buscas. Saiu antes de ir ao ar: o site já barra CEP de cidade não atendida antes de chamar a API, então o estado quase sempre seria MG e não diria nada. Menos dado é mais privacidade.)

Por isso também **não dá para saber "quantas pessoas"**: isso exigiria reconhecer cada uma (cookie, IP, impressão digital do navegador), que é exatamente o rastreamento que o aviso promete não fazer. Só se sabe **quantas vezes**.

## Como funciona

```
site (abre)    ──GET /saude?origem=site──────┐
site (busca)   ──GET /comparar ──────────────┤
site (lista)   ──GET /comparar?origem=lista ─┼─►  API (api_supabase.py)  ─►  fila  ─►  fio próprio  ─►  rpc registrar_uso(evento, quantidade)  ─►  uso_diario
site (gráfico) ──GET /historico ─────────────┘     _medidor.contar(...)    (500)     (medidor_de_uso.py)     soma no dia de Brasília
```

- [`medidor_de_uso.py`](../medidor_de_uso.py) guarda a lista fechada de eventos e o `MedidorDeUso`. O pedido do usuário só **põe o nome do evento numa fila e segue**; um fio à parte manda a fila para o banco. **O que chegou enquanto um envio estava em andamento sai junto**, num pedido por tipo com a quantidade (por exemplo, `busca` × 15): com muito movimento, o banco recebe poucos pedidos, não um por ocorrência.
- **A contagem nunca atrasa nem derruba uma resposta.** Se o banco estiver fora, ou o SQL ainda não tiver sido rodado, a soma falha em silêncio: o log do Render mostra `⚠️ Medição de uso indisponível (a busca segue normal): ...` no máximo uma vez a cada 10 minutos. Se a fila encher (500 somas esperando), as que sobrarem são descartadas, com um aviso `⚠️ Medição de uso: a fila encheu ...` (também no máximo um a cada 10 minutos): medir é secundário, atender é o que importa.
- **Só o servidor de verdade conta.** O medidor nasce desligado e `ciclo_de_vida` (em `api_supabase.py`) o liga quando o servidor sobe e o desliga ao cair, dando até 2 segundos para o que está na fila sair. Os testes, que chamam as funções da API direto, nunca falam com o banco por causa da medição.
- A soma em si é uma função do banco (`registrar_uso`, em [`sql/uso_do_site.sql`](sql/uso_do_site.sql)): `insert … on conflict do update set total = total + quantidade`, atômica, então dois pedidos ao mesmo tempo não perdem contagem. Quantidade fora de 1 a 1.000.000 é ignorada. O dia é o de Brasília, o da hora em que a soma chega ao banco; só o dia é guardado.
- Só a chave secreta (a da API) chama a função e acessa a tabela: RLS ligado sem nenhuma política, `revoke` para `anon` e `authenticated` e um `grant` explícito à chave secreta (o Supabase está deixando de dar permissão automática em tabela nova; sem o `grant` toda soma falharia com "permission denied").
- `/saude` sem `origem=site` **não conta**: o Health Check do Render (a cada poucos segundos) e os monitores externos não inflam a medição.

## Antes de ligar: a ordem importa

A contagem **começa no momento em que o SQL existe** no Supabase. Por isso a ordem certa é:

1. O PR da medição mesclado e a API publicada no Render (é automático ao mesclar).
2. **O site novo publicado no Netlify.** Abra o site, clique em "Privacidade e seus dados" no rodapé e confira que existe a seção **"O que medimos"**. Se o deploy ficou "Skipped" (créditos do Netlify, [`netlify.md`](netlify.md)), dispare *Trigger deploy*. Enquanto o site antigo estiver no ar, ele chama `/saude` sem `origem` (nenhuma `abertura` é contada) e renova a lista sem `origem=lista` (cada renovação conta como `busca`), e o aviso público ainda não fala de medição.
3. **Só então rodar o SQL** (próxima seção).

Anote aqui a data em que ligou (os números só valem a partir dela): **ligada em ___/___/2026**. (Preencher ao ligar.)

## Para ligar (uma vez)

1. Abra o arquivo [`sql/uso_do_site.sql`](sql/uso_do_site.sql), selecione tudo (`Ctrl+A`) e copie.
2. No Supabase, abra o **SQL Editor**, crie uma consulta nova (**New query**), cole e clique em **Run**. Deu certo quando aparece `Success. No rows returned`. Pode rodar mais de uma vez; não mexe em nenhuma tabela existente.
3. Conferência, em duas partes:
   - ainda no SQL Editor, rode as duas consultas "Conferências" do fim do arquivo: **as duas devem responder `true`**;
   - abra o site, faça uma busca e, em seguida, rode `select * from uso_diario order by dia desc;`: devem aparecer **uma linha `abertura` e uma `busca`** de hoje. Se aparecer só `busca`, sem `abertura`, o site novo ainda não foi publicado no Netlify ([`netlify.md`](netlify.md)).
4. **Se não aparecer nada em alguns minutos:** abra o **Logs** do serviço no Render e procure `Medição de uso indisponível`. A causa mais provável é o SQL não ter rodado até o fim (rode de novo e veja se deu erro); a mensagem do próprio banco aparece depois dos dois-pontos (`Could not find the function` = o SQL não rodou; `permission denied` = falta a permissão da chave secreta, que o script dá).

## Para desligar ou zerar

Comandos do SQL Editor (apagam dados, então só se for essa a intenção):

- **Parar de contar:** `drop function registrar_uso(text, bigint);` (a API segue normal; só passa a falhar em silêncio, com o aviso no log).
- **Zerar os números:** `delete from uso_diario;`
- **Tirar tudo:** `drop function registrar_uso(text, bigint); drop table uso_diario;`

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

Como ler: **aberturas** é o movimento do site (conta recarregar a página, e a mesma pessoa várias vezes: não é número de pessoas); **buscas ÷ aberturas** é a média de buscas por abertura (pode passar de 1: não é a porcentagem de quem busca); **buscas sem resultado ÷ buscas** mostra o que o catálogo não cobre (sem dizer o quê: o termo não é guardado); **históricos** mostra o interesse no gráfico.

## Limites (o que esses números não dizem)

- Sem "pessoas" e sem "voltaram": só contagens. Uma pessoa que abre o site 5 vezes são 5 aberturas.
- **Servem para ver tendência, não para prestar contas.** A API é pública: qualquer um pode chamá-la em laço e inflar os números (e, enquanto a fila estiver cheia, somas legítimas se perdem). Com poucos usuários, quem conhece o movimento também reconhece a própria ação nos números.
- `abertura` inclui recarregar a página, abas de pré-visualização do Netlify, execuções locais do site (todos falam com a API de produção), abas esquecidas e robôs que executam JavaScript. **Nos primeiros dias, os testes do próprio dono e os de quem mantém o projeto entram na conta.** Link compartilhado no WhatsApp **não** conta (a prévia não executa o site).
- `busca` conta pedidos à API, não "sessões": quem busca 5 produtos faz 5 buscas.
- Enquanto o site antigo (ou uma aba aberta antes da publicação) falar com a API, não há `abertura` e a renovação da lista conta como `busca`.
- Se o servidor reiniciar de repente, perdem-se as poucas somas que estavam na fila; no desligamento normal, o servidor espera até 2 segundos para enviá-las.
- O dia gravado é o da hora em que a soma chega ao banco (Brasília), que pode ser o dia seguinte para uma ocorrência feita um instante antes da meia-noite.
- Ver as visitas no Netlify é outra coisa: o painel **Observability** do Netlify mostra só as últimas 24 horas no plano gratuito (veja [`privacidade.md`](privacidade.md) e [`netlify.md`](netlify.md)).

## O que trava cada garantia

| Garantia | Quem trava |
|---|---|
| a lista de eventos é fechada e igual no Python e no SQL | `tests/test_medidor_de_uso.py` (lê o `check` do SQL e compara com `EVENTOS`) |
| cada soma tem a sua frase no aviso do site | `tests/test_privacidade.js` (lê o `check` do SQL: soma nova sem frase no aviso reprova) e `tests/navegador/test_site_privacidade.py` |
| só o nome do evento e a quantidade saem da API; nada de CEP, estado, termo, produto ou IP | `tests/test_medidor_de_uso.py`: busca com CEP e termo "secretos", lista, gráfico e abertura; confere que nenhuma chamada ao banco, nem o pedido HTTP de verdade, contém nada deles |
| a tabela só tem `dia`, `evento`, `total`, sem horário; o script não faz mais nada | o mesmo teste, que compara o script **comando por comando** com a lista esperada (outra coluna, outra tabela, `alter table`, `do $$`... reprovam até a lista ser atualizada de propósito) |
| só a chave secreta acessa a tabela e a função | `tests/test_sql.py` (toda tabela nova com RLS, toda função nova fechada para `anon`/`authenticated`), o teste acima e `tests/postgres_de_verdade/` (num Postgres de verdade, nos dois padrões de permissão do Supabase) |
| a contagem não atrasa nem derruba a busca, e o fio se recria se morrer | `tests/test_medidor_de_uso.py`: banco lento (0,6 s) não atrasa a resposta; banco sem a função não atrapalha e avisa uma vez; fila cheia descarta e avisa; fio que não subiu ou morreu é recriado |
| os testes nunca falam com o banco por causa da medição | `tests/test_medidor_de_uso.py`: o medidor nasce desligado, e só `ciclo_de_vida` o liga e o desliga; o arquivo importa `tests/sem_rede.py`, que faz qualquer chamada de rede de verdade falhar na hora |
| `/saude` de monitor não conta, o do site sim; a lista não conta como busca | o mesmo teste, `tests/test_privacidade.js` e os de navegador `test_site_privacidade.py` (o site só chama `/saude?origem=site` ao abrir) e `test_site_lista.py` (a renovação da lista manda `origem=lista`) |

**Conferência em Postgres de verdade** (PGlite, o Postgres em WebAssembly): `tests/postgres_de_verdade/testa_uso_do_site.mjs` roda o script SQL imitando o Supabase, nos **dois** padrões de permissão (o antigo, em que tabela e função novas nascem acessíveis às três chaves, e o novo, sem permissão automática), e confere restrições, soma (um a um e em lote), quantidade fora de 1 a 1.000.000, dia de Brasília, quem pode o quê e "rodar duas vezes". Foi feito à mão em 24/11/2026 (76 verificações) e não roda no CI: rode de novo sempre que mexer no SQL (`docs/testes.md`).

## Acrescentar uma soma nova

1. Inclua o nome em `EVENTOS` de `medidor_de_uso.py` e chame `_medidor.contar(...)` no ponto certo de `api_supabase.py`.
2. Acrescente o nome ao `check (evento in (...))` de `sql/uso_do_site.sql`. O teste confere que as duas listas são iguais. Atenção: numa tabela que **já existe**, o `create table if not exists` não troca a restrição; trocá-la é uma migração à parte (um script novo em `docs/sql/`, e o `tests/test_sql.py`, que só aceita scripts aditivos, vai pedir uma exceção). Combine com o dono antes.
3. Acrescente a frase da soma nova ao aviso do site ("O que medimos") e ao dicionário `FRASE_DE_CADA_SOMA` de `tests/test_privacidade.js` (o teste reprova até isso estar feito), e atualize esta página. Se a soma nova guardar algo além de um número por dia, **pare**: isso deixa de ser "sem rastrear" e é decisão do dono.
