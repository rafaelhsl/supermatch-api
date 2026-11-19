# Privacidade do CEP e dos dados de quem usa o site

O site mostra um aviso de privacidade (rodapé "Privacidade e seus dados" e link "Como tratamos seus dados" na janela do CEP). Esta página é a versão para quem mantém o projeto: o que o aviso afirma, **o que torna cada frase verdadeira** e o que ainda depende de decisão do dono.

## O caminho do CEP

| Para onde | O quê | Por quê |
|---|---|---|
| localStorage do navegador (chaves `sm_...`) | CEP, cidade, lista de compras, modo de busca | a pessoa não digita de novo. Não há cookies, `sessionStorage` nem IndexedDB |
| BrasilAPI e ViaCEP (do navegador) | o CEP | descobrir a cidade (e saber se atendemos) |
| API do Supermatch, no Render (do navegador) | o CEP e o termo buscado, a cada busca e a cada atualização da lista | calcular os preços |
| ViaCEP (da API) | os 8 dígitos do CEP | saber o estado (UF) |
| Google Fonts (do navegador) | o endereço IP do aparelho | as letras do site |
| Netlify e Render | registros técnicos de acesso (IP e o que o provedor guarda) | são os provedores de hospedagem |

O banco (Supabase) **não recebe CEP**: só guarda produtos e preços.

## O que a API escreve no log

Até 19/11/2026 o Render guardava o **CEP inteiro** em duas linhas: a da própria API ("📡 API Recebeu pedido… CEP: '30130010'") e o log de acesso do uvicorn (`GET /comparar?cep=30130010&item=arroz`). Agora as duas trazem só os 5 primeiros dígitos (`30130-***`):

- `cep_para_o_log` (em `api_supabase.py`) faz a máscara, e o que não for CEP vira `(CEP inválido)`: o parâmetro é livre, e texto de quem chama não vai para o log;
- `EsconderCepDoLogDeAcesso` é um filtro no logger `uvicorn.access`, ligado quando a API é importada, que troca o `cep=` do endereço antes de a linha ser escrita (conferido com um uvicorn de verdade, igual ao comando do Render);
- a API só consulta o ViaCEP com 8 dígitos (o resto responde "BR" sem consulta).

**Registros antigos** (com o CEP inteiro) seguem o prazo de retenção do Render e saem sozinhos; a API não tem como apagá-los.

## "Apagar meus dados deste aparelho"

Apaga todas as chaves `sm_...` do navegador e as da versão anterior do site (`user_cep`, `user_cidade`: se ficassem, o CEP voltava sozinho) e recarrega a página. Não toca em chaves que não são do site. Antes de 19/11/2026 `esquecerTudo` existia no código mas nenhum botão o usava, e deixava o modo de busca e as chaves antigas.

## O que trava cada frase do aviso

| O aviso diz | Quem garante |
|---|---|
| "não tem cadastro, anúncios nem rastreadores" | `tests/test_privacidade.js`: nenhum analytics/rastreador no HTML |
| "não usa cookies" | o mesmo teste: nenhum `document.cookie` |
| o CEP só vai para BrasilAPI, ViaCEP e a nossa API; o IP vai ao Google Fonts | o mesmo teste: a lista dos endereços externos do site **tem de ser exatamente esta**; se o site falar com um endereço novo, o teste falha e lembra de atualizar o aviso e esta página |
| "nos nossos registros ficam o que você buscou e só os 5 primeiros dígitos do CEP" | `tests/test_privacidade.py` (a máscara, o filtro do uvicorn, o print, e uma varredura que falha se um `print`/log novo escrever o CEP cru) |
| "Apagar meus dados" apaga tudo | `tests/navegador/test_site_privacidade.py`: com `sm_*`, `user_*` e uma chave de outro site guardadas, sobra só a de fora |
| o aviso abre do rodapé e da janela do CEP, cabe em 320 px, Esc fecha e o foco volta | o mesmo teste de navegador |

## O que falta decidir (é do dono)

- **Contato.** Um aviso de privacidade costuma trazer um e-mail para dúvidas e pedidos de exclusão. O aviso **não tem** porque não há um contato definido para o projeto; quando houver, entra no fim da janela (e aqui).
- **Quem é o controlador dos dados** (nome ou apelido do projeto, para a LGPD). Idem.
- **Fontes do Google.** Hospedar as três famílias (Unbounded, Hanken Grotesk, Martian Mono) no próprio site tiraria o IP do Google Fonts do aviso, e o site passaria a falar só com quem o aviso já cita. É um passo à parte: os arquivos de fonte vão para `site/`.
- **Retenção.** O prazo dos registros do Render e do Netlify depende do plano de cada um; vale conferir nos painéis.
