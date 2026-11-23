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
confere(/5 primeiros dígitos do CEP/.test(texto), 'o aviso diz que nos registros ficam só "5 primeiros dígitos do CEP" (tests/test_privacidade.py torna isso verdade)');
confere(/não usa cookies/.test(texto), "o aviso diz que o site não usa cookies");
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
