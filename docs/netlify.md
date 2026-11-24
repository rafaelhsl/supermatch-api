# Publicação no Netlify e os créditos

O site (`site/`) é publicado pelo Netlify a cada merge na `main` que mude algo dentro de `site/` (a regra `ignore` do [`netlify.toml`](../netlify.toml) cancela o resto). No plano gratuito do Netlify **cada publicação gasta créditos**, e em 24/11/2026 os créditos do ciclo acabaram. Esta página guarda o que se apurou nesse dia (documentação e página de preços do Netlify, lidas em 24/11/2026) e o que fazer a partir daí.

## O que custa crédito (plano gratuito)

| O quê | Custo |
|---|---|
| a cota do mês | **300 créditos**, limite rígido: o Free não compra créditos nem tem recarga automática e nunca gera cobrança |
| **deploy de produção** bem-sucedido | **15 créditos** (deploy que falha e volta para um deploy anterior não custam) |
| Deploy Preview e branch deploy | 0 (só o tráfego de quem os visita conta, como o do site) |
| build cancelado ou pulado pela regra `ignore` | a documentação não diz; pelas regras escritas, 0 (dedução) |
| banda | **20 créditos por GB** enviado aos visitantes (era 10 até 14/04/2026) |
| requisições (HTML, fontes, imagens…) | **2 créditos por 10 mil** (eram 3 até 14/04/2026) |
| formulários, Identity | grátis (o site não usa nenhum) |

Todos saem do mesmo saldo de 300. **300 ÷ 15 = no máximo 20 publicações por ciclo**, e menos que isso na prática, porque a banda e as requisições gastam do mesmo saldo. O ciclo recomeça numa data própria da conta (a desta: 27 de cada mês, segundo o aviso do Netlify).

## O que aconteceu em 24/11/2026

O histórico do git mostra **19 merges que mudaram `site/`** desde 27/10/2026, o início do ciclo, e cada um publicou o site: 19 × 15 = 285 créditos. O tráfego (inclusive as verificações de produção feitas durante o trabalho) completou os 300. O último desses merges foi o do gráfico do histórico (PR #73). A conta exata, por tipo e por dia, está no painel do Netlify (Usage & billing; veja abaixo).

O aviso do Netlify então disse: o site publicado continua no ar; foram acrescentados **30 créditos operacionais**, que só mantêm o site no ar (não pagam deploy de produção); os deploys de produção ficam **pausados** até o upgrade ou o novo ciclo; Deploy Previews e branch deploys seguem ativos; **se os 30 também acabarem, o site é suspenso** até voltarem créditos ou o ciclo reiniciar. (A documentação pública do Netlify descreve outra coisa, a pausa total, com a página "Site not available", e **não menciona créditos operacionais**: vale o aviso da conta. Não está documentado a que ritmo esses 30 créditos são gastos nem se o tráfego dos previews sai deles.)

## O que uma visita custa

Uma visita nova baixa cerca de **143 KB em 4 requisições** (medido em 24/11/2026: o HTML com 34 KB em Brotli e as 3 fontes, 109 KB). Quem já visitou reaproveita as fontes (cache de 1 ano): 1 requisição pequena. Com as taxas acima, mil visitantes novos custam **cerca de 3,7 créditos** (2,9 de banda e 0,8 de requisições):

- 30 créditos operacionais ≈ **8 mil visitantes novos**;
- um mês inteiro sem nenhuma publicação (300) ≈ 80 mil;
- cada publicação de 15 créditos "custa" o equivalente a ~4 mil visitantes novos.

## O que fazer

- **Agrupar as mudanças do site.** Cada merge em `site/` é uma publicação de 15 créditos: juntar várias mudanças num PR só (ou publicar poucas vezes por semana) deixa saldo para o tráfego. Mudança que não é do site (API, robôs, documentação, testes) não gasta nada.
- **Ver o consumo:** painel do Netlify, **Usage & billing** (Credit balance, Credit usage breakdown e "Account usage insights > Credits", que mostra por dia quanto cada tipo gastou). O painel **Observability** não mostra créditos, só tráfego.
- **No dia do reinício (27/11/2026):** conferir em Usage & billing que o saldo voltou a 300 e **disparar um deploy** (Deploys > Trigger deploy), porque o deploy barrado por falta de crédito fica "Skipped" e não é refeito sozinho (dedução: a documentação não diz). Há **relatos no fórum do Netlify (jul a set/2026)** de contas gratuitas que continuaram pausadas depois da virada do ciclo, mesmo mostrando 300/300; a saída foi abrir um chamado no suporte (o e-mail do suporte vale para todos os planos). Não há resposta oficial sobre isso.
- **Subir de plano resolve na hora** (despausa os projetos): Personal, US$ 9 por mês, 1.000 créditos (a página de preços; dá para 66 publicações se não houvesse tráfego); Pro, US$ 20 por mês, 3.000 créditos. No plano gratuito não dá para comprar créditos avulsos.
- O plano **Open Source** do Netlify (10 mil créditos, deploys de produção grátis) exige licença aprovada pela OSI, projeto não comercial e site ligado a software de código aberto: não é feito para um comparador de preços.

## O painel Observability e a privacidade

O **Observability** guarda os pedidos ao site por **1 dia no plano gratuito e no Personal** (7 dias no Pro, 30 no Enterprise): URL com parâmetros, caminho, região, código de resposta e latência, e o IP do cliente quando o pedido passa por um proxy confiável. Foi o que o dono viu em 24/11/2026 (só as últimas 24 horas). Isso é o que o dono **enxerga**; quanto tempo o Netlify guarda por conta própria é regra dele (política de privacidade). O aviso do site fala só em "registros técnicos de acesso, como o endereço IP", sem prometer prazo ([`privacidade.md`](privacidade.md)).

O Netlify também oferece uma medição de visitas "sem cookies e sem JavaScript" (Web Analytics, lida nos logs do servidor): conta **IPs distintos por dia** e, no gratuito, a janela de histórico é de 1 dia (segundo a página de preços). Não foi ativada: a medição do Supermatch é a própria soma por dia, sem IP ([`uso_do_site.md`](uso_do_site.md)).

## Se um dia for preciso sair do Netlify

O site é um arquivo, três fontes e uma imagem: mudar de hospedagem é simples, e **com um domínio próprio o endereço do site não muda** (só se aponta o domínio para o novo lugar). O que se levantou em 24/11/2026:

| Alternativa | Em poucas palavras |
|---|---|
| **Cloudflare Pages** (ou Workers com arquivos estáticos) | arquivos estáticos **grátis e sem limite de tráfego**; aceita o mesmo `_headers` do Netlify (a regra das fontes passa quase igual); no Pages grátis, 500 builds por mês (o `ignore` equivale ao "build watch paths"). A Cloudflare recomenda começar projetos novos no Workers, mas o Workers só aceita domínio com os nameservers na própria Cloudflare, enquanto o Pages aceita um subdomínio (`www`) por CNAME em qualquer DNS. Esforço: pequeno |
| GitHub Pages | grátis em repositório público, mas **não permite cabeçalho de cache** (as fontes perderiam o cache de 1 ano) e não pode ser usado como hospedagem grátis de negócio online |
| Render (site estático) | grátis, mas gasta os **mesmos 5 GB de banda por mês da API**; ao estourar, sem cartão, suspende também a API |
| Vercel Hobby | só uso pessoal/não comercial, e **pausa o site** ao estourar o limite |
