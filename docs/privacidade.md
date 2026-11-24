# Privacidade do CEP e dos dados de quem usa o site

O site mostra um aviso de privacidade (rodapé "Privacidade e seus dados" e link "Como tratamos seus dados" na janela do CEP). Esta página é a versão para quem mantém o projeto: o que o aviso afirma, **o que torna cada frase verdadeira** e o que ainda depende de decisão do dono.

## O caminho do CEP

| Para onde | O quê | Por quê |
|---|---|---|
| localStorage do navegador (chaves `sm_...`) | CEP, cidade, lista de compras, modo de busca | a pessoa não digita de novo. Não há cookies, `sessionStorage` nem IndexedDB |
| BrasilAPI e ViaCEP (do navegador) | o CEP | descobrir a cidade (e saber se atendemos) |
| API do Supermatch, no Render (do navegador) | o CEP e o termo buscado, a cada busca e a cada atualização da lista | calcular os preços |
| ViaCEP (da API) | os 8 dígitos do CEP | saber o estado (UF) |
| API do Supermatch, no Render (do navegador), ao abrir o gráfico de preços | a chave do produto (e o mercado), **sem CEP** | desenhar a evolução do preço (`/historico`). O pedido entra no log da API, com os 7 dias do Render |
| API do Supermatch, no Render (do navegador), ao abrir a página | só o aviso de que o site abriu (`/saude?origem=site`), **sem CEP** e sem nada pessoal | acordar o servidor e somar 1 "abertura" no dia |
| Banco (Supabase), pela API | só **somas por dia**: quantas aberturas do site, buscas, atualizações da lista de compras e aberturas do histórico | saber se o site é usado (`uso_diario`; veja [`uso_do_site.md`](uso_do_site.md)) |
| Supabase (o provedor do banco), a cada soma | o provedor anota por conta própria que a API chamou `registrar_uso`: **hora, caminho e o IP do servidor do Render, sem CEP, sem termo e sem o corpo do pedido** | provedor do banco; guarda 1 dia no plano gratuito (7 no Pro), segundo a documentação dele |
| Netlify (as letras, em `fonts/`, junto com o site) | o IP, como em qualquer pedido ao site | as letras do site. **Desde 23/11/2026 não vêm mais do Google Fonts** |
| Netlify e Render | registros técnicos de acesso (IP e o que o provedor guarda) | são os provedores de hospedagem |

O banco (Supabase) **não recebe CEP**: só guarda produtos, preços e as somas por dia da medição de uso (`uso_diario`: dia, tipo e total; nada que identifique alguém).

## Medição de uso (sem rastrear)

A medição de uso (decidida em 24/11/2026) faz a API **somar por dia** quantas vezes o site foi aberto, quantas buscas foram feitas (e quantas não acharam nenhum produto), quantas vezes o site renovou sozinho os preços da lista de compras e quantas vezes o histórico de um produto foi consultado. A **tabela** é só um número por dia e tipo: não guarda CEP, estado, termo buscado, IP, horário nem identificador, e nem tem coluna para isso. Esse é o limite do "sem rastrear": dá para saber **quantas vezes**, não **quem**; a soma, sozinha, não diz quem usou o site. Isso **não muda o que os provedores guardam por conta própria**, que segue os prazos desta página: o Render guarda por 7 dias o que foi buscado (com os 5 primeiros dígitos do CEP) e o IP, e o Supabase anota por 1 dia a hora de cada soma. Com poucos usuários, quem conhece o movimento pode reconhecer a própria ação nos números; por isso o aviso diz "sozinhas" e não promete que é impossível ligar uma soma a uma pessoa. O desenho, o que cada soma quer dizer e como ler os números estão em [`uso_do_site.md`](uso_do_site.md). As somas ficam guardadas sem prazo (são só números).

## O que a API escreve no log

Até 19/11/2026 o Render guardava o **CEP inteiro** em duas linhas: a da própria API ("📡 API Recebeu pedido… CEP: '30130010'") e o log de acesso do uvicorn (`GET /comparar?cep=30130010&item=arroz`). Agora as duas trazem só os 5 primeiros dígitos (`30130-***`):

- `cep_para_o_log` (em `api_supabase.py`) faz a máscara, e o que não for CEP vira `(CEP inválido)`: o parâmetro é livre, e texto de quem chama não vai para o log;
- `EsconderCepDoLogDeAcesso` é um filtro no logger `uvicorn.access`, ligado quando a API é importada, que troca o `cep=` do endereço antes de a linha ser escrita (conferido com um uvicorn de verdade, igual ao comando do Render);
- a API só consulta o ViaCEP com 8 dígitos (o resto responde "BR" sem consulta).

**Registros antigos** (com o CEP inteiro) seguem o prazo de retenção do Render: **7 dias** no plano gratuito (informado pelo dono em 24/11/2026). Os últimos com o CEP inteiro são de 19/11/2026 (a correção entrou no ar nessa manhã) e **saem do Render até 26/11/2026**; a API não tem como apagá-los antes.

## "Apagar meus dados deste aparelho"

Apaga todas as chaves `sm_...` do navegador e as da versão anterior do site (`user_cep`, `user_cidade`: se ficassem, o CEP voltava sozinho) e recarrega a página. Não toca em chaves que não são do site. Antes de 19/11/2026 `esquecerTudo` existia no código mas nenhum botão o usava, e deixava o modo de busca e as chaves antigas.

## O que trava cada frase do aviso

| O aviso diz | Quem garante |
|---|---|
| "não tem cadastro, anúncios nem rastreadores" | `tests/test_privacidade.js`: nenhum analytics/rastreador no HTML |
| "não usa cookies" | o mesmo teste: nenhum `document.cookie` |
| o CEP só vai para BrasilAPI, ViaCEP e a nossa API; o Google não recebe nada | o mesmo teste (e `tests/test_fontes.py`, `tests/navegador/test_site_fontes.py`): a lista dos endereços externos do site **tem de ser exatamente esta**; se o site falar com um endereço novo, o teste falha e lembra de atualizar o aviso e esta página |
| "os registros da API ficam guardados por 7 dias e trazem o que você buscou, os itens da lista que o site renovou, os produtos de que abriu o histórico e só os 5 primeiros dígitos do CEP" | `tests/test_privacidade.py` (a máscara, o filtro do uvicorn, o print, e uma varredura que falha se um `print`/log novo escrever o CEP cru) |
| "a nossa API soma, a cada dia, quantas vezes aconteceu cada uma destas coisas: o site foi aberto; uma busca foi feita, e quantas delas não acharam nenhum produto; o site renovou sozinho os preços da sua lista de compras; o histórico de preços de um produto foi consultado" | `tests/test_privacidade.js` (cada soma que o SQL aceita tem a sua frase no aviso: soma nova sem frase reprova; o único pedido a `/saude` e os dois pedidos a `/comparar`) e `tests/navegador/test_site_privacidade.py` (o texto na tela; ao abrir, o site só chama `/saude?origem=site`, sem CEP) |
| "Essas somas ficam guardadas sem prazo, mas são só números: sozinhas, não dizem quem usou o site, o que buscou nem qual era o CEP. Os registros de 7 dias da API, descritos acima, são outra coisa" | `tests/test_medidor_de_uso.py`: só o nome do evento e a quantidade saem da API (nenhuma chamada ao banco contém CEP, estado, termo, produto ou IP) e o SQL só tem `dia`, `evento` e `total`, sem horário; `tests/test_sql.py` e `tests/postgres_de_verdade/` (tabela só da chave secreta) |
| "junto com o que você busca e com os itens da sua lista de compras (o site renova os preços dela sozinho)" | `tests/test_privacidade.js` e `tests/navegador/test_site_privacidade.py` (o texto); `tests/navegador/test_site_lista.py` (a renovação manda os itens a `/comparar`, com `origem=lista`) |
| "Quando você abre o histórico de preços de um produto, a API recebe só qual é o produto, sem CEP" | `tests/navegador/test_site_historico.py`: o pedido a `/historico` só tem o parâmetro `chaves` e não contém o CEP guardado |
| "Apagar meus dados" apaga tudo | `tests/navegador/test_site_privacidade.py`: com `sm_*`, `user_*` e uma chave de outro site guardadas, sobra só a de fora |
| o aviso abre do rodapé e da janela do CEP, cabe em 320 px, Esc fecha e o foco volta | o mesmo teste de navegador |
| "O Supermatch é mantido por Rafael Lima" e o e-mail para dúvidas | `tests/test_privacidade.js` (o texto, o link e o `mailto`) e o teste de navegador (o e-mail aparece escrito, o link abre o e-mail com assunto e cabe em 320 px) |

## Quem responde

A janela diz **quem mantém o projeto (Rafael Lima, a pessoa responsável pelos dados para a LGPD)** e traz o **e-mail para dúvidas sobre os dados**. O e-mail é montado pelo script (`CONTATO` em `site/index.html`) e **não aparece escrito no HTML**: quem varre páginas atrás de endereços para spam não roda o script, e `tests/test_privacidade.js` falha se ele for escrito inteiro no HTML. Para trocar o contato, mude `CONTATO` (usuário e domínio) e o nome na mesma janela; os testes vão reclamar, de propósito, até acompanharem. Autorizado pelo próprio dono em 23/11/2026.

## O que falta decidir (é do dono)

- **Retenção.** Render: **7 dias** (plano gratuito; confirmado em 24/11/2026) e o aviso diz isso. Netlify: o painel **Observability** do plano gratuito mostra só as **últimas 24 horas** (conferido pelo dono em 24/11/2026; o Personal, o plano pago mais barato, mostra o mesmo; só o Pro mostra 7 dias e o Enterprise 30). Isso diz o que o dono consegue ver; o prazo que o provedor mantém por conta própria é regra dele (política de privacidade do Netlify). Detalhes do painel e dos planos em [`netlify.md`](netlify.md). O aviso continua falando de "registros técnicos de acesso, como o endereço IP" sem prometer prazo para o Netlify.
