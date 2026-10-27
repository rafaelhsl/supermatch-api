# Robôs de coleta: como cada um define e confirma a localização

Os preços de um supermercado online dependem de onde você está: a loja que atende o seu CEP, a
região de entrega, o catálogo disponível. Por isso cada robô **informa o CEP antes de buscar** e só
segue se o site **confirmar** que assumiu esse CEP. Se não confirmar, o robô para e levanta um erro,
em vez de devolver preços de um lugar desconhecido.

Código comum: [`robos_comum.py`](../robos_comum.py). Erros:

- `LocalizacaoNaoConfirmada`: o site não atende o CEP, ou o robô não conseguiu informá-lo.
- `BuscaNaoRealizada`: a busca não abriu a página de resultados (a URL não traz o termo buscado),
  então o que está na tela não é o resultado da busca.

Os dois herdam de `FalhaNoRobo`. A carga ([`alimentar_banco.py`](../alimentar_banco.py)) trata cada
falha por mercado e item, sem derrubar os outros robôs.

## Como cada site confirma o CEP

Verificado em 26/10/2026 com os CEPs 30130010 (BH Centro), 32607600 (Betim), 38400100 (Uberlândia)
e 32041000 (Contagem). Os sites mudam: se um robô começar a falhar, é aqui que se confere primeiro.

| Mercado | Como o robô informa o CEP | Sinal de que foi aceito | Quando não atende |
|---|---|---|---|
| **Atacadão** | "Informar localização" > "Entrega em Casa" > digita o CEP > número genérico `100` > Confirmar | O cabeçalho passa a dizer `Entregue pela Loja - <loja> para o CEP 32607-600` | O cabeçalho não muda e o robô aborta |
| **Apoio** | Ícone do carrinho (`a.btn-top-cart`) abre "Informe seu CEP"; digita e clica em Buscar; escolhe "Quero receber" | O quadro mostra `Atendemos sua região` e `CEP informado 32607-600` | O quadro nunca aparece e o painel volta ao início |
| **Supernosso** | Clica em "qual a forma de entrega?" > digita o CEP (tecla por tecla) > envia > escolhe o horário da entrega agendada | O cabeçalho passa a dizer `entrega no cep 32.607-600` | O site mostra "que pena, ainda não atendemos a sua região" |
| **Super ABC** | Não localiza por CEP. O robô descobre a **cidade** do CEP (ViaCEP, com BrasilAPI de reserva) e escolhe uma unidade dessa cidade no seletor de lojas | O botão do cabeçalho passa a mostrar a unidade e a cidade (`ABC Atacado e Varejo Betim - Betim / MG`) | Não há unidade na cidade (Contagem, por exemplo) e o robô aborta |

### Pegadinhas que já custaram tempo

- **Supernosso:** o campo de CEP é `input[name='cep']` com texto `00000000` (não tem a palavra "CEP"
  nem `postalCode`); tem máscara, então precisa ser digitado tecla por tecla. Logo depois de
  confirmar, a página **recarrega**; uma busca feita antes disso é apagada
  (`esperar_recarregamento`).
- **Apoio:** o campo também tem máscara (`30130010` vira `30130-010` com atraso); o botão Buscar só
  funciona depois disso. O texto "Carrinho" aparece também no título escondido do painel, por isso o
  robô usa o seletor `a.btn-top-cart`. Clicar em "Comprar" para abrir o painel adicionaria um produto
  ao carrinho.
- **Super ABC:** a busca de unidade por CEP não funciona (só por nome ou endereço). Unidades na
  região de BH: Barreiro e Horto (BH), Betim, Pará de Minas e Itaúna. Em cidades com mais de uma
  unidade, o robô escolhe a primeira da lista.
- **Atacadão:** as lojas variam por CEP (Betim, Pampulha, Uberlândia), mas nos produtos testados
  os preços foram iguais.
- **Apoio, no GitHub:** a prateleira de resultados demora mais para aparecer nos servidores do
  GitHub do que na máquina local. Com espera fixa de 7 s, 4 de 11 buscas voltaram com 0 itens sem
  aviso; por isso o robô espera os produtos aparecerem de verdade (até 20 s).
- **Super ABC, busca:** a página tem dois campos de busca iguais (desktop e celular); só o visível
  serve. A URL de resultados vem **codificada duas vezes** (`Açucar` vira `A%25C3%25A7ucar`).
- **Supernosso, no começo da carga:** com os 4 navegadores abrindo juntos, uma etapa (painel de CEP,
  cabeçalho ou a busca de "Arroz") se perde de vez em quando. Isolada, a mesma busca passa sempre.

## Etiquetas de promoção no nome

Os cards trazem rótulos antes do nome (`Patrocinado | Leve 4 Pague 3 | café 3 corações ... | R$ 21,99`).
Antes, o rótulo virava o nome do produto. Agora `eh_etiqueta_promocional` os descarta, e textos com
`R$` ou palavras de botão (`lista`) nunca viram nome.

## Rodando localmente para ver o robô trabalhar

Os robôs rodam sem janela (`headless=True`). Para assistir, troque temporariamente para
`headless=False` (e, se quiser, `slow_mo=250` no `launch`). Para rodar a carga inteira sem gravar
nada no banco:

```
SEM_GRAVAR=1 python alimentar_banco.py     # PowerShell: $env:SEM_GRAVAR = "1"; python alimentar_banco.py
```

Ela mostra um resumo por mercado no fim e sai com código `1` se algum robô falhou.

## Falhas: o que repete e o que para

Um robô levanta `FalhaNoRobo` quando prefere parar a devolver dado duvidoso:

- localização não confirmada;
- busca que não abriu a página de resultados;
- página de resultados **sem nenhum produto com preço** (quase sempre é página lida cedo demais).

A carga (`com_novas_tentativas`) **repete o robô uma vez, com navegador novo**, quando a falha é
passageira. Falhas **definitivas** não são repetidas: "o site informa que não atende a região"
(Supernosso) e "o Super ABC não tem unidade na cidade".

## Verificação feita antes de entrar na `main`

Carga completa com `SEM_GRAVAR=1`, 4 robôs em paralelo, 11 buscas, CEP 32607600 (Betim):

| Onde | Resultado |
|---|---|
| GitHub Actions, 27/10/2026 | sucesso, 0 falhas, 0 repetições: Apoio 256, Atacadão 223, Supernosso 224, Super ABC 304 itens; 44 de 44 localizações confirmadas |
| Máquina local, mesmo dia | sucesso, 0 falhas em duas rodadas seguidas; contagens iguais (Apoio 256, Atacadão 224, Supernosso 224, Super ABC 304). Na primeira, a repetição automática salvou a busca de "Arroz" do Supernosso; na segunda não precisou de nenhuma |

Antes das correções, no GitHub: 3 falhas do Supernosso, 1 falso alarme do Super ABC e 4 buscas do Apoio
com 0 itens sem aviso. Testes isolados por CEP: Atacadão, Apoio, Supernosso e Super ABC aceitam BH e
Betim; Apoio e Supernosso recusam Uberlândia; o Super ABC recusa Contagem (sem unidade).

## A carga e as falhas

- Cada mercado é gravado **só se foi coletado por inteiro**. Se um robô falhar, os dados antigos
  daquele mercado ficam no banco (antes, a tabela era apagada no começo e uma falha deixava o
  mercado vazio).
- A gravação insere os produtos novos primeiro e só depois apaga os antigos do mesmo mercado
  (`atualizado_em` anterior ao início da carga).
- Se qualquer mercado falhar, a execução termina com erro: o GitHub marca a execução como falha,
  mostra o motivo em destaque e envia o e-mail de aviso.
