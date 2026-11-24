# Licença e domínio próprio

Duas decisões que são do dono do projeto (dúvidas de 24/11/2026). A da **licença está tomada: sem licença**. A do **domínio segue aberta**, junto com a escolha de um **novo nome** para o site (veja abaixo). Esta página explica cada uma em linguagem simples e diz o que se sabe; o que foi apurado vem da documentação do GitHub, do `choosealicense.com`, da lei e do Registro.br, lidos em 24/11/2026.

## Licença do código

**Decidido em 24/11/2026: o repositório fica SEM licença**, porque o dono pretende ganhar dinheiro com o site. Os direitos autorais ficam todos com ele, e ninguém pode copiar, reaproveitar ou vender o código sem autorização. Se um dia quiser abrir, o caminho está no fim desta seção; abrir depois é fácil, fechar não. O que protege o **nome** do site é outra coisa: o registro da marca no INPI (veja "Nome do site").

**O que é.** Um arquivo (`LICENSE`), na raiz do repositório, que diz o que as outras pessoas podem fazer com o seu código.

**Como está hoje.** O repositório é público, ou seja, qualquer um pode **ler** o código, e **não tem licença**. Nesse caso valem os direitos autorais, que no Brasil existem sozinhos, sem precisar registrar nada (Lei 9.609/1998, art. 2º; o registro no INPI é opcional). Na prática: o autor mantém todos os direitos e **ninguém pode copiar, reaproveitar, modificar nem vender o código** sem autorização. O GitHub só deixa as pessoas verem e fazer uma cópia ("fork") dentro do próprio GitHub. É a situação mais protegida.

**As opções.**

| Opção | O que permite | O que exige | Quando faz sentido |
|---|---|---|---|
| **Sem licença** (como hoje) | só ver e copiar dentro do GitHub | tudo é reservado ao autor | quando ainda não se decidiu, ou se pensa em ganhar dinheiro com o código |
| **MIT** | qualquer um usar, modificar e **até vender** cópias, inclusive um concorrente | manter o aviso de autoria; vem "sem garantia" | quando se quer que o código seja livre e conhecido |
| **Apache 2.0** | o mesmo da MIT, e ainda dá uso das patentes dos autores | manter os avisos e declarar o que mudou | o mesmo caso, com mais proteção jurídica |
| **GPL / AGPL** | usar e modificar | **quem publicar uma versão modificada tem de abrir o código dela também** (a AGPL vale até para site na internet) | quando se quer impedir que alguém pegue, melhore e feche |
| **PolyForm Noncommercial** | uso **sem fins comerciais** | acordo com o autor para uso comercial | quando se quer liberar só para estudo e uso pessoal (não é "código aberto" no sentido estrito) |

**O que a licença não cobre.** Só o **código**. Não cobre os **preços** coletados dos supermercados nem as **marcas** deles, e não dá permissão de nada que os mercados proíbam nos termos de uso dos sites deles (**esses termos não foram lidos neste projeto**: vale ler antes de divulgar muito).

**Recomendação.** **Não fazer nada agora.** Abrir depois é fácil; fechar depois não, porque quem já copiou o código sob uma licença aberta continua com o direito de usar essa cópia. A pergunta que decide é: *há plano de ganhar dinheiro com o Supermatch (anúncio, parceria, assinatura)?* Se sim, ficar sem licença (ou PolyForm). Se a ideia é que outras pessoas possam reaproveitar o código, a MIT é a mais simples e comum.

**Como adicionar, quando decidir.** No GitHub, na página do repositório: **Add file > Create new file**, nome `LICENSE`; o GitHub oferece modelos prontos ("Choose a license template"). O GitHub passa a mostrar a licença no topo da página.

## Domínio próprio

**O que é.** Um endereço registrado **em seu nome**, como `supermatch.com.br`, que passa a ser o **link real do site**. Hoje o link é um endereço que o Netlify sorteou (`spontaneous-hamster-cd3133.netlify.app`).

**Por que ter antes de divulgar.** O endereço que se divulga (WhatsApp, grupos, redes) fica gravado nas conversas das pessoas. Com um domínio próprio, **trocar de hospedagem depois não muda o link**: só se muda para onde o domínio aponta. Sem ele, sair do Netlify obriga a divulgar um link novo e a trocar as tags de prévia do repositório. (Veja [`netlify.md`](netlify.md): os créditos do plano gratuito do Netlify são a razão mais provável para uma troca.)

**Custo e cadastro** (segundo o Registro.br; conferir na hora de pagar):

- `.com.br`, no **Registro.br**: **R$ 40 por ano** (cada ano a mais, R$ 36; dá para pagar vários de uma vez). Aceita pessoa física (**CPF**) e empresa (CNPJ). Pagamento por Pix, cartão ou boleto.
- **Privacidade do cadastro:** para pessoa física, o cadastro público do Registro.br mostra **o nome, parte do CPF e os contatos** do titular (segundo o contrato dele).
- O nome tem de 2 a 26 caracteres, e depois de registrado não pode ser trocado (só registrando outro).
- Se a anuidade não for paga, o domínio é cancelado e o nome volta a ficar livre para qualquer um registrar.
- `.com`: cerca de US$ 10 a 12 por ano em registradores como Cloudflare ou Porkbun (o valor varia). Comprar por revendedores brasileiros custa mais na renovação.

**Como se liga ao site** (eu faço o lado do repositório; o dono faz o cadastro e, se preferir, o DNS):

1. Registrar o domínio.
2. No Netlify (**Domain management**), adicionar o domínio ao site. O HTTPS (o cadeado) é **grátis e automático**.
3. Apontar o domínio: mantendo o DNS do Registro.br, um registro `CNAME` do `www` para `spontaneous-hamster-cd3133.netlify.app` e um registro `A` do domínio sem `www` para `75.2.60.5` (o Netlify mostra os valores exatos na tela). O Netlify recomenda deixar o `www` como endereço principal e redireciona o sem-`www` para ele.
4. Esperar valer: de poucas horas até **cerca de 48 horas** (no DNS do Registro.br, até 1 hora).
5. Trocar no repositório os **3 endereços** das tags de prévia (`canonical`, `og:url`, `og:image`, em `site/index.html`) e a documentação; o `tests/test_og.py` confere.

**Cuidados.**

- O endereço antigo (`.netlify.app`) **continua funcionando** e **não redireciona sozinho** para o domínio novo: o Netlify só põe um aviso de "endereço principal" para os buscadores. Para redirecionar, cria-se uma regra no Netlify (e quem já tem o link antigo segue usando).
- Se um dia o DNS for entregue ao Netlify (em vez de mantido no Registro.br), é preciso **desligar o DNSSEC** do domínio antes: o Netlify DNS não o suporta.
- Se o site não abrir pelo endereço novo nas primeiras horas, é normal: o DNS leva um tempo para valer em todo lugar. Espere antes de mexer nos registros.

## Nome do site

O nome atual, **Supermatch**, soa estrangeiro, e os dois domínios principais (`supermatch.com` e `supermatch.com.br`) **já são de outras pessoas** (conferido em 24/11/2026). O dono quer um nome brasileiro, fácil e ligado ao tema (comparar preços de supermercado). Antes de escolher:

- **Domínio:** o nome precisa ter o `.com.br` livre (conferir no Registro.br; a disponibilidade muda de um dia para o outro: registrar logo ao decidir). Registrar também o `.com`, se estiver livre e barato, evita que outra pessoa fique com ele.
- **Marca:** domínio livre **não** quer dizer marca livre. Como o dono pretende ganhar dinheiro com o site, vale pesquisar o nome no **INPI** (busca de marcas, no site do INPI) e, se estiver livre, **registrar a marca** (o pedido tem taxa: conferir no site do INPI). Também conferir o nome no Instagram, no Google e nas lojas de aplicativos.
- **Teste de boca:** dizer em voz alta "abre o ___", "olha o ___ que achei" e escrever o nome de ouvido; se alguém errar a grafia, o nome é difícil.
- O que muda no repositório com o nome novo (eu faço, num PR só, para gastar uma única publicação do Netlify): o título e os textos do site, o aviso de privacidade, as tags de prévia e a imagem `site/og.png`, o assunto do e-mail de privacidade, os documentos e os testes que citam o nome. O endereço da API (`supermatch-api.onrender.com`) e o nome do repositório são internos e podem continuar como estão.

## O que falta decidir

| Decisão | Opções | Quem |
|---|---|---|
| Licença | **decidido: sem licença** (24/11/2026) | dono |
| Nome do site | escolher o nome novo (o atual, "Supermatch", soa estrangeiro e `supermatch.com` e `supermatch.com.br` já têm dono) | dono; depois eu troco o nome no site, nos textos, nas tags de prévia e na documentação |
| Domínio | registrar o `.com.br` do nome novo (em CPF ou CNPJ) | dono; depois eu ligo no Netlify e troco as 3 tags |
