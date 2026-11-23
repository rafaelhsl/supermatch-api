# Carga diária de preços

A carga busca os preços dos quatro mercados e grava no Supabase (como ela coleta está em [`coletor_por_api.md`](coletor_por_api.md) e [`robos.md`](robos.md); o histórico, em [`historico_de_precos.md`](historico_de_precos.md)). Quem a executa é o workflow [`main.yml`](../.github/workflows/main.yml), "Carga diária de preços". Esta página explica **como e quando ele é disparado**.

## Por que dois disparos

O agendador do GitHub (`schedule`) é de graça, mas atrasa: marcado para 11:17 UTC (08:17 em Brasília), a carga vinha começando por volta das 18:40 UTC (**15:40**). Quem abria o site de manhã via os preços do dia anterior. Por isso:

| | Disparo | Quando | Papel |
|---|---|---|---|
| 1 | **cron-job.org** chama a API do GitHub | todo dia às **07:30 de Brasília**, na hora | **principal**: garante os preços de manhã |
| 2 | agendador do GitHub (`schedule`) | 11:17 UTC, mas atrasa horas | **reserva**: se o disparo 1 falhou, o dia não fica sem carga |

Para a reserva não repetir o trabalho, o primeiro job do workflow (`decidir`, "Já houve carga hoje?") confere, **só nas execuções agendadas**, se já houve hoje (dia de Brasília) uma carga **completa e bem-sucedida**: `gravar=sim`, todos os mercados. Se houve, a de reserva pula o job de carga (aparece como "skipped"). Se o disparo principal falhou (execução vermelha) ou não aconteceu, a reserva carrega. Qualquer dúvida ou erro na conferência também resulta em carregar. A regra está em [`guarda_da_carga.py`](../guarda_da_carga.py) e é testada por `tests/test_guarda_da_carga.py`.

O título de cada execução (`run-name`) traz `gravar=` e `mercados=`, por exemplo `Carga (disparada) | gravar=sim | mercados=todos | coleta=api`. É por ele que a guarda reconhece a carga completa de hoje. Um teste confere que o `run-name` e a guarda continuam combinando.

Também há uma fila (`concurrency`): duas cargas ao mesmo tempo (o disparo externo junto com a reserva, ou um clique duplo no botão) não se atropelam; a segunda espera a primeira terminar.

## Configurar o disparo externo (cron-job.org)

### 1. Criar o token no GitHub

O cron-job.org precisa de uma "senha" que só autorize disparar workflows deste repositório.

1. No GitHub, clique na sua foto (canto superior direito) → **Settings** → no fim do menu da esquerda, **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. **Token name:** `cron-job.org: carga Supermatch`.
3. **Expiration:** 1 ano (anote a data numa agenda: veja "Renovar o token" abaixo).
4. **Resource owner:** `rafaelhsl`.
5. **Repository access:** **Only select repositories** → `supermatch-api`.
6. **Permissions** → **Repository permissions** → **Actions: Read and write**. Deixe todo o resto sem acesso (o "Metadata: Read-only" aparece sozinho).
7. **Generate token** e copie o valor (começa com `github_pat_`). Ele só aparece **uma vez**.

> **Não cole o token em conversa nenhuma, nem em arquivo do repositório.** Ele vai só no cron-job.org. Com essas permissões ele dispara e cancela execuções deste repositório; não lê o segredo do Supabase e não altera código. Se vazar, apague-o em Developer settings (e crie outro): nada mais fica exposto.

### 2. Criar a tarefa no cron-job.org

Em **Cronjobs → Create cronjob**:

| Campo | Valor |
|---|---|
| Title | `Supermatch: carga diária` |
| URL | `https://api.github.com/repos/rafaelhsl/supermatch-api/actions/workflows/main.yml/dispatches` |
| Execution schedule | todos os dias, **07:30**, fuso **America/Sao_Paulo** (confira o fuso: sem isso o horário vira o do servidor) |
| Aba **Advanced** → Request method | **POST** |
| Request body | veja o passo 3 |
| Headers (aba Advanced; **uma linha para cada um**, botão **+ ADD**: nunca junte vários no valor do `Authorization`, o GitHub leria tudo como se fosse o token e responderia 401) | `Authorization` = `Bearer ` e o token (a palavra Bearer, um espaço, e o token); `Accept` = `application/vnd.github+json`; `X-GitHub-Api-Version` = `2022-11-28`; `Content-Type` = `application/json` |
| Notifications | avise quando a tarefa **falhar** |

O GitHub responde `204 No Content` quando aceita o disparo, e o cron-job.org conta qualquer resposta 2xx como sucesso.

### 3. Testar antes de ligar de verdade

1. Primeiro, com o **corpo de teste**, que só coleta o Supernosso e **não grava nada**:
   ```json
   {"ref":"main","inputs":{"mercados":"Supernosso","gravar":"nao"}}
   ```
   Use o botão de teste da tarefa. O resultado deve ser **204** e, em poucos segundos, aparecer em **Actions** uma execução chamada `Carga (disparada) | gravar=nao | mercados=Supernosso | coleta=api`.
2. Se deu certo, troque o corpo pelo **definitivo** (todos os mercados, gravando, por API):
   ```json
   {"ref":"main"}
   ```
   e ative a tarefa. (Sem `inputs`, valem os padrões do workflow.)

Dá para testar também do seu computador, sem o cron-job.org:
```
gh api -X POST repos/rafaelhsl/supermatch-api/actions/workflows/main.yml/dispatches -f ref=main -f "inputs[mercados]=Supernosso" -f "inputs[gravar]=nao"
```

### Códigos de erro mais comuns

| Resposta | Significa |
|---|---|
| 204 | funcionou |
| 401 | token errado, vencido ou apagado (renove) |
| 403 ou 404 | o token não tem a permissão "Actions: Read and write", ou não vale para este repositório |
| 422 | o corpo está errado (por exemplo, `ref` diferente de uma branch existente ou um `inputs` com valor inválido) |

## Conferir que está funcionando

- **De manhã:** em Actions deve haver uma execução `Carga (disparada) | gravar=sim | mercados=todos | coleta=api`, criada por volta de 07:30 e verde uns 15 minutos depois.
- **À tarde:** a execução `Carga (agendada do GitHub) …` aparece com o job "Já houve carga hoje?" verde e o job de carga **pulado**. Isso é o esperado.
- **No site:** o `atualizado_em` dos preços é o de hoje de manhã.

## Se algo falhar

- **O disparo principal falhou ou a carga ficou vermelha:** o GitHub avisa por e-mail; a reserva roda no fim do dia (não pula, porque só a carga bem-sucedida conta). O site fica no máximo um dia com preços velhos.
- **O cron-job.org avisou de falha (401):** o token venceu ou foi apagado; veja abaixo.
- **Rodou duas vezes no mesmo dia:** é inofensivo (carga repetida não duplica nada; só repete o trabalho). Se acontecer sempre, confira se o `run-name` do `main.yml` ainda traz `gravar=` e `mercados=`.

## Quando um mercado cai no meio da carga

Na carga de 18/11/2026 (disparada de uma branch de teste e cancelada depois de 47 minutos), o Atacadão respondeu **HTTP 403 a todos os 100 termos** e o Super ABC não conseguiu **abrir a lista de unidades em nenhum**. O coletor perguntou os 100 termos mesmo assim, e o robô gastou três tentativas de uns 45 segundos em cada um (324 falhas, quase uma hora). Dois mecanismos, em [`disjuntor.py`](../disjuntor.py), evitam esse desperdício:

- **Disjuntor por mercado.** Depois de **6 falhas seguidas** (um acerto no meio zera a conta) o mercado é dado como fora do ar e **os termos que faltam não são tentados**; ficam registrados como "não tentado: o mercado falhou 6 vezes seguidas; a última: ...". No log aparecem as 6 falhas de verdade e **uma linha** com o total de termos pulados, em vez de 94 linhas iguais. Cada mercado tem o seu disjuntor: um mercado caído não atrapalha os outros.
- **Segunda rodada.** Quando a primeira rodada acaba com termos sem resultado (falhos ou pulados), a carga **espera 60 segundos** e tenta **uma vez** cada um deles, com um disjuntor novo. Um bloqueio ou uma lentidão que passou em um minuto deixa de custar o dia daquele mercado, e a falha passageira de um termo deixa de tornar a coleta "parcial". Se o mercado continua fora do ar, o disjuntor abre de novo e a carga desiste: no pior caso são 12 tentativas por mercado, em vez de 100 (API) ou 300 (robô, com as repetições).

O que sobra de falha segue a regra de sempre (tabela em [`robos.md`](robos.md#a-carga-e-as-falhas)): até 10% dos termos, a coleta é **parcial**; acima disso o mercado **não é gravado**, os dados do dia anterior ficam e a execução fica vermelha. Quem decide é o restante da carga, não o disjuntor: ele só economiza o tempo e o desgaste de insistir.

Duas decisões:

- O **HTTP 403 não entrou** na lista de status que o coletor repete na hora (`STATUS_QUE_REPETE`). Um 403 costuma ser bloqueio, e martelar o site em seguida só piora; quem cuida dele é a segunda rodada, depois da pausa.
- A mensagem de erro do Super ABC deixou de ser cortada em 300 caracteres (agora 3.000). O motivo real de um clique que esgota o tempo ("element intercepts pointer events", "not visible"...) vem no **fim** do log do Playwright, e o corte o escondia justamente ali ("...waiting for element to be visible, enabled and").

Os dois números, `LIMITE_DE_FALHAS_SEGUIDAS = 6` e `PAUSA_DA_SEGUNDA_RODADA = 60` (segundos), ficam no topo de `disjuntor.py`. Os testes: `python tests/test_disjuntor.py` (a regra), `tests/test_coletor_vtex.py` (a coleta pela API) e `tests/test_carga.py` (o robô e a carga).

## Renovar o token

Um token do GitHub vence. O token criado em 13/11/2026 vale até **13/11/2027** (a data também aparece no cabeçalho `github-authentication-token-expiration` da resposta do teste). O GitHub costuma avisar por e-mail poucos dias antes, mas não conte só com isso: anote a data numa agenda. Na renovação, aproveite para trocar também o valor do cabeçalho `X-GitHub-Api-Version` por uma versão mais nova: o GitHub avisa (cabeçalho `Sunset` da resposta) que a `2022-11-28` deixa de funcionar em **10/03/2028**. Para renovar: Developer settings → Fine-grained tokens → abra o token → **Regenerate token** (mesmas permissões) → copie o valor novo → no cron-job.org, edite a tarefa e troque o valor do header `Authorization`. Enquanto o token estiver vencido a reserva do GitHub continua carregando, só que no fim do dia.

### O lembrete automático

Não depende de lembrar de olhar a agenda: o workflow [`lembretes.yml`](../.github/workflows/lembretes.yml) roda todo dia (09:23 em Brasília), lê [`dados/lembretes.json`](../dados/lembretes.json) e, quando chega o dia de um lembrete, **abre uma issue no repositório, atribuída ao dono** (o GitHub manda o e-mail). Hoje são três:

| Quando | O quê |
|---|---|
| 13/10/2027 | **Renovar o token** (vence em 13/11/2027). A issue traz o passo a passo, manda trocar também o `X-GitHub-Api-Version` e **acrescentar os próximos lembretes** |
| 06/11/2027 | **Última chamada**: faltam 7 dias para o token vencer |
| 10/02/2028 | **Trocar a versão da API do GitHub** (a `2022-11-28` deixa de funcionar em 10/03/2028), caso não tenha sido trocada na renovação |

- **Uma issue por lembrete**, uma vez só: se já existe uma com o mesmo título (aberta ou **fechada**), não abre outra. Se o workflow ficar parado, o lembrete atrasado sai quando ele voltar.
- **Depois de renovar o token, acrescente os próximos lembretes** em `dados/lembretes.json` (o vencimento novo menos 30 dias e menos 7 dias): sem isso o ciclo para depois de 2028. A issue de renovação repete este pedido.
- Se o workflow falhar (o GitHub não conseguiu listar ou abrir issues), a execução fica vermelha e o GitHub avisa por e-mail: ele **nunca** abre issue sem conferir antes o que já existe.
- O workflow só tem a permissão de abrir issue (`issues: write`) e ler o código; não usa nenhum segredo.
- **Ver o que cada lembrete faria** (não abre nada): `python lembretes.py` (precisa do `gh` logado) ou, no GitHub, Actions → "Lembretes por data" → Run workflow (com `criar = nao`). Para **testar de verdade**, rode com `criar = sim` e `hoje = 2027-10-14`: com `hoje` preenchido o workflow entende que é um teste e abre a issue do token com o título **"TESTE: Lembrete: ..."** e um aviso no começo; as issues que já existem não contam, então o teste pode ser repetido e, mesmo depois de fechado, **não impede o lembrete de verdade** de abrir em 13/10/2027. Feche a issue de teste em seguida.
- `python tests/test_lembretes.py` confere a regra (quando abre, não repete, o arquivo mal formado é recusado), que as datas batem com esta página e que o workflow só pode abrir issue.

## Mudar o horário

É só editar o horário da tarefa no cron-job.org; não precisa mexer em código. O horário das 07:30 foi escolhido para os preços estarem prontos (≈ 07:45) antes das compras da manhã. (O comentário antigo do `main.yml` dizia que o Apoio não tinha preços antes das 7h; a causa real daquelas falhas era outra e já foi corrigida, então não há horário proibido.)
