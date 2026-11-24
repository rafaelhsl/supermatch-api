// O aviso de privacidade de site/index.html (a janela "Privacidade e seus dados") diz para onde o CEP vai. Este teste trava isso: se o site passar
// a falar com um endereço novo, ou deixar de falar com um que o aviso cita, o teste falha e lembra de atualizar o aviso (e docs/privacidade.md).
// Rodar com:  node tests/test_privacidade.js
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const igual = (obtido, esperado, texto) => confere(JSON.stringify(obtido) === JSON.stringify(esperado), `${texto}\n      obtido:   ${JSON.stringify(obtido)}\n      esperado: ${JSON.stringify(esperado)}`);

const script = html.slice(html.indexOf("<script>"), html.lastIndexOf("</script>"));
const dialogo = html.slice(html.indexOf('<dialog id="janelaPrivacidade"'), html.indexOf("</dialog>", html.indexOf('<dialog id="janelaPrivacidade"')));
const texto = dialogo.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
confere(dialogo.length > 100, 'a janela "janelaPrivacidade" existe');

// ---- com quem o navegador conversa: endereços no script (fetch, constante da API) e arquivos externos do <head> (fontes) ----
const hosts = new Set();
for (const m of script.matchAll(/["'`]https:\/\/([a-z0-9.-]+)/gi)) hosts.add(m[1]);
// (o <link rel="canonical"> e as tags og:* só dizem o endereço do próprio site para quem monta a prévia do link: o navegador não pede nada a eles)
for (const m of html.slice(0, html.indexOf("<style>")).matchAll(/<link(?![^>]*rel="canonical")[^>]+href="https:\/\/([a-z0-9.-]+)/gi)) hosts.add(m[1]);
igual([...hosts].sort(), ["brasilapi.com.br", "supermatch-api.onrender.com", "viacep.com.br"],
  "os únicos endereços externos do site (se mudar, atualize o aviso de privacidade e docs/privacidade.md); as letras vêm de site/fonts/, não do Google");
confere(!/googleapis|gstatic|fonts\.google/.test(html), "nada do Google no site: as fontes são hospedadas aqui (tests/test_fontes.py confere os arquivos)");

// ---- e o aviso cita cada um, com o nome que a pessoa reconhece ----
for (const [nome, fala] of [["BrasilAPI", "BrasilAPI"], ["ViaCEP", "ViaCEP"], ["Render", "Render"], ["Netlify", "Netlify"]]) {
  confere(texto.includes(nome), `o aviso cita ${fala}`);
}
confere(!/Google/.test(texto), "o aviso não cita o Google (o site não pede nada a ele: as letras são daqui)");
confere(/guardados por 7 dias/.test(texto), 'o aviso diz que os registros da API ficam guardados por 7 dias (o prazo do plano gratuito do Render; docs/privacidade.md)');
confere(/5 primeiros dígitos do CEP/.test(texto), 'o aviso diz que nos registros ficam só "5 primeiros dígitos do CEP" (tests/test_privacidade.py torna isso verdade)');
confere(/não usa cookies/.test(texto), "o aviso diz que o site não usa cookies");

// ---- a medição de uso sem rastrear (medidor_de_uso.py): o que o aviso diz e o que o site de fato manda ----
confere(/O que medimos/.test(texto), 'o aviso tem a seção "O que medimos"');
const sqlDoUso = fs.readFileSync(path.join(__dirname, "..", "docs", "sql", "uso_do_site.sql"), "utf8").replace(/--.*$/gm, "");
const eventosDoSql = [...(sqlDoUso.match(/check \(evento in \(([^)]*)\)\)/) || ["", ""])[1].matchAll(/'([a-z_]+)'/g)].map((m) => m[1]);
const FRASE_DE_CADA_SOMA = {
  abertura: "o site foi aberto",
  busca: "uma busca foi feita",
  busca_sem_resultado: "quantas delas não acharam nenhum produto",
  atualizacao_da_lista: "o site renovou sozinho os preços da sua lista de compras",
  historico: "o histórico de preços de um produto foi consultado",
};
igual(Object.keys(FRASE_DE_CADA_SOMA).sort(), [...eventosDoSql].sort(), "cada soma que o banco aceita (docs/sql/uso_do_site.sql) tem a sua frase neste teste: soma nova sem frase no aviso reprova aqui");
for (const [evento, frase] of Object.entries(FRASE_DE_CADA_SOMA)) confere(texto.includes(frase), `o aviso diz o que é a soma «${evento}»: «${frase}»`);
confere(/a nossa API soma, a cada dia, quantas vezes aconteceu cada uma destas coisas:/.test(texto), "o aviso diz que a soma é por dia e por tipo");
confere(/Essas somas ficam guardadas sem prazo, mas são só números: sozinhas, não dizem quem usou o site, o que buscou nem qual era o CEP\. Os registros de 7 dias da API, descritos acima, são outra coisa\./.test(texto), "o aviso diz que as somas são só números que sozinhos não identificam ninguém, e separa os registros de 7 dias (tests/test_medidor_de_uso.py torna isso verdade)");
confere(!/não há como ligar uma soma a uma pessoa/.test(texto), "o aviso não promete que é impossível ligar uma soma a uma pessoa (com poucos usuários e os registros de 7 dias com IP, não dá para prometer isso)");
confere(/itens da sua lista de compras \(o site renova os preços dela sozinho\)/.test(texto) && /os itens da lista que o site renovou/.test(texto), "o aviso diz que a renovação dos preços da lista manda os itens (e o CEP) para a API e que isso aparece nos registros de 7 dias");
const chamadasSaude = script.match(/[^\n]*\/saude[^\n]*/g) || [];
confere(chamadasSaude.length === 1 && /fetch\(API \+ "\/saude\?origem=site"\)/.test(chamadasSaude[0]), `o único pedido a /saude é o aviso de que o site abriu, sem CEP nem termo: ${JSON.stringify(chamadasSaude)}`);
const caminhosDaApi = [...new Set([...script.matchAll(/\$\{API\}\/([a-z]+)/g), ...script.matchAll(/API \+ "\/([a-z]+)/g)].map((m) => m[1]))].sort();
igual(caminhosDaApi, ["comparar", "historico", "saude"], "os únicos caminhos da nossa API que o site chama (um caminho novo, como um de medição, precisa entrar no aviso e em docs/privacidade.md)");
confere(!/sendBeacon|new Image\(|XMLHttpRequest|WebSocket|EventSource/.test(script), "o site só fala com a rede por fetch (nada de beacon, imagem, XHR, WebSocket), e todo fetch cai nos endereços e caminhos conferidos aqui");
const chamadasComparar = script.match(/[^\n]*\/comparar\?[^\n]*/g) || [];
confere(chamadasComparar.length === 2 && chamadasComparar.filter((l) => /&origem=lista`\)/.test(l)).length === 1,
  `dois pedidos a /comparar: a busca de uma pessoa (sem origem) e a renovação automática dos preços da lista (origem=lista, que a API não conta como busca): ${JSON.stringify(chamadasComparar.map((l) => l.trim().slice(0, 120)))}`);
confere(!/document\.cookie/.test(html), "o site de fato não escreve cookies");
confere(!/google-analytics|googletagmanager|gtag\(|fbq\(|hotjar|clarity\.ms|plausible|matomo|segment\.com/i.test(html), "o site não carrega analytics nem rastreadores (o aviso diz que não há)");
confere(/Apagar meus dados deste aparelho/.test(texto), 'o aviso tem o botão "Apagar meus dados deste aparelho"');

// ---- quem responde: o nome e o contato do responsável (LGPD), com o e-mail montado no script e não escrito no HTML ----
confere(/Quem responde por isto/.test(texto) && /mantido por Rafael Lima/.test(texto), 'o aviso diz quem responde: "mantido por Rafael Lima"');
confere(/id="contatoEmail"/.test(dialogo), "o aviso tem o link do e-mail do responsável");
confere(!/rafaelhsts@gmail\.com|rafaelhsts%40|mailto:[^"'+]*@/.test(html), "o e-mail NÃO está escrito inteiro no HTML (é montado pelo script, contra quem varre páginas atrás de endereços)");
confere(/CONTATO = \{ usuario: "rafaelhsts", dominio: "gmail\.com" \}/.test(script) && /"mailto:" \+ email/.test(script), "o script monta o mailto com o contato do responsável");

// ---- o que fica no aparelho: só as chaves "sm_", e o botão apaga todas ----
const chaves = new Set();
for (const m of script.matchAll(/\b(?:guardar|ler)\(\s*"([a-z_]+)"/g)) chaves.add(m[1]);
confere(chaves.size >= 3 && [...chaves].every((c) => /^[a-z]+$/.test(c)), `chaves guardadas no aparelho: ${[...chaves].join(", ")}`);
confere(/function esquecerTudo\(\)\s*\{[^}]*startsWith\(PREFIXO\)[^}]*user_cep[^}]*user_cidade/s.test(script), "esquecerTudo apaga tudo com o prefixo do site e as chaves da versão anterior");
confere(/localStorage\.setItem\(PREFIXO \+ k/.test(script) && (script.match(/localStorage\.setItem/g) || []).length === 1, "só um lugar do site grava no localStorage (guardar), sempre com o prefixo");
confere(!/sessionStorage|indexedDB/.test(script), "o site não usa outro armazenamento além do localStorage");

console.log(`${ok} verificações passaram, ${erros.length} falharam`);
if (erros.length) { for (const e of erros) console.log("  ✗ " + e); process.exit(1); }
