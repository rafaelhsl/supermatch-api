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
| Headers | `Authorization` = `Bearer ` e o token (a palavra Bearer, um espaço, e o token); `Accept` = `application/vnd.github+json`; `X-GitHub-Api-Version` = `2022-11-28`; `Content-Type` = `application/json` |
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

## Renovar o token

Um token do GitHub vence. O GitHub costuma avisar por e-mail poucos dias antes, mas não conte só com isso: anote a data. Para renovar: Developer settings → Fine-grained tokens → abra o token → **Regenerate token** (mesmas permissões) → copie o valor novo → no cron-job.org, edite a tarefa e troque o valor do header `Authorization`. Enquanto o token estiver vencido a reserva do GitHub continua carregando, só que no fim do dia.

## Mudar o horário

É só editar o horário da tarefa no cron-job.org; não precisa mexer em código. O horário das 07:30 foi escolhido para os preços estarem prontos (≈ 07:45) antes das compras da manhã. (O comentário antigo do `main.yml` dizia que o Apoio não tinha preços antes das 7h; a causa real daquelas falhas era outra e já foi corrigida, então não há horário proibido.)
