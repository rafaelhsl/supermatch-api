# Nome e domínio: Econolista

**Decidido em 27/11/2026:** o site passa a se chamar **Econolista** (antes, "Supermatch") e o endereço é **`econolista.com.br`**, registrado no Registro.br pelo dono do projeto em 27/11/2026 (vence em 27/11/2027; conferido no RDAP do Registro.br). O motivo da troca: o nome antigo soava estrangeiro, e `supermatch.com` e `supermatch.com.br` já eram de outras pessoas (conferido em 24/11/2026).

## O que se apurou antes de registrar

- **Domínio:** `econolista.com.br`, `econolistas.com.br`, `econolista.net.br`, `econolista.net` e `econolista.app` estavam livres em 27/11/2026. `econolista.com` está registrado por terceiros e **estacionado** (a página redireciona para um anúncio de domínio à venda).
- **INPI** (busca do dono): nenhuma marca igual ou parecida.
- **Instagram:** `@econolistas` sem atualizações desde 2020 e `@econolista` sem postagens. Nenhum dos dois é concorrente.
- **Marca não é domínio.** Domínio registrado não protege o nome: no Brasil vale quem deposita primeiro no INPI. Veja "O que falta" abaixo.

## O que mudou no repositório

- **O nome que as pessoas veem** (`site/index.html`): o título, o logo, o aviso de privacidade ("A Econolista não tem cadastro, anúncios nem rastreadores…", "A Econolista é mantida por Rafael Lima"), o rodapé, a mensagem sem JavaScript e o assunto do e-mail de privacidade ("Econolista: privacidade"). O nome leva o artigo **feminino** ("a Econolista").
- **Pré-visualização do link:** as três tags de endereço (`canonical`, `og:url` e `og:image`) apontam para `https://econolista.com.br/`, e a imagem `site/og.png` foi refeita com o nome novo (`docs/og/og.html` e `docs/og/gerar_og.py`). `tests/test_og.py` confere que as três são do mesmo endereço e que é o domínio próprio.
- **O que NÃO mudou, de propósito** (nomes técnicos que ninguém vê e que mudar só traria risco):
  - o endereço da API (`supermatch-api.onrender.com`), o serviço do Render e o repositório do GitHub (`rafaelhsl/supermatch-api`);
  - o objeto `Supermatch` dentro do JavaScript do site e o prefixo `sm_` das chaves guardadas no aparelho (trocá-lo faria cada pessoa perder a lista e o CEP salvos);
  - os nomes dentro de serviços externos (o token e o agendamento do cron-job.org, em [`carga_diaria.md`](carga_diaria.md)).

## Como ligar o domínio ao site (feito pelo dono; leva de minutos a algumas horas)

O site já está no Netlify. Falta dizer ao Netlify que o domínio é dele e apontar o domínio para lá:

1. **No Netlify:** abra o site, **Domain management → Add a domain** e digite `econolista.com.br`. Confirme que você é o dono (o Netlify pede para confirmar). Ele mostra os valores de DNS que quer; use os que ele mostrar.
2. **No Registro.br** (o domínio usa o DNS do próprio Registro.br, `a.auto.dns.br` e `b.auto.dns.br`): em **Editar zona** (ou "Configurar DNS"), crie:
   - um registro **A** do domínio sem `www` apontando para **`75.2.60.5`** (o balanceador do Netlify);
   - um registro **CNAME** de **`www`** para **`spontaneous-hamster-cd3133.netlify.app`**.
3. **Esperar valer:** no DNS do Registro.br, até 1 hora; em outras redes, até cerca de 48 horas. Se não abrir logo, é normal: espere antes de mexer nos registros.
4. **HTTPS:** de volta no Netlify, em **Domain management → HTTPS → Verify DNS configuration / Provision certificate**. O certificado é gratuito e sai sozinho depois que o DNS vale.
5. **Endereço principal:** deixe **`econolista.com.br`** (sem `www`) como o domínio principal do site; o Netlify redireciona o `www` para ele.

O endereço antigo (`spontaneous-hamster-cd3133.netlify.app`) continua funcionando e não redireciona sozinho; quem já tem o link antigo segue usando.

Se um dia o DNS for entregue ao Netlify (em vez de mantido no Registro.br), é preciso **desligar o DNSSEC** do domínio antes: o Netlify DNS não o suporta.

## Ordem para publicar

1. O dono liga o domínio (acima) e confirma que `https://econolista.com.br/` abre **o site atual**, com o cadeado.
2. Só então se faz o merge desta troca de nome: as tags `canonical`, `og:url` e `og:image` passam a apontar para o domínio, e um domínio que ainda não abre estragaria a prévia do link e a leitura dos buscadores.
3. Depois de publicar, conferir `https://econolista.com.br/og.png`, abrir o site em celular e computador e, se quiser, forçar a prévia nova nas redes (veja [`site.md`](site.md#pré-visualização-do-link-tags-og)).

## O que falta (do dono, não do repositório)

- **Depositar a marca no INPI** (domínio não protege o nome). Pesquisar antes por **radical** e pelo som ("Econolist", "Econo Lista", "Economista"), nas classes de **serviço de comparação de preços e publicidade (35)** e de **software e aplicativo online (42; às vezes a 9)**, e conferir os pedidos **em andamento**, não só as marcas concedidas.
- **Buscar fora do INPI:** o nome no Google, na Play Store e na App Store, no LinkedIn, no Reclame Aqui e como razão social ou nome fantasia no CNPJ.
- **Reservar o nome nas redes** (TikTok, YouTube, X, Facebook e o Instagram: o `@econolista` está tomado, então algo como `@econolista.br`).
- **Registrar também `econolistas.com.br`** (o plural; o perfil `@econolistas` mostra que as pessoas escrevem assim).
- **E-mail do domínio** (por exemplo `contato@econolista.com.br`): o Registro.br não inclui; precisa de um serviço de e-mail (Zoho Mail, Google Workspace…). Hoje o aviso de privacidade usa o e-mail pessoal do responsável, montado no script (`CONTATO`, em `site/index.html`); trocar é uma linha, e `tests/test_privacidade.js` e `tests/navegador/test_site_privacidade.py` conferem.
- **Titular do domínio:** está no nome de quem registrou. Se a monetização passar por um CNPJ, vale transferir o titular antes de a marca ser depositada.
