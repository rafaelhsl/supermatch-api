// Testes do selo "caiu X% em 7 dias", que fica dentro de site/index.html (a função quedaDaOpcao).
// Rodar com:  node tests/test_queda.js
// A API marca a opção com queda_preco = { preco_antes, percentual, dias } (veja quedas.py). O site só mostra o selo se a marca
// bate com o preço que ele mesmo exibe, e refaz o percentual com os dois preços.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const a = html.indexOf("/* @queda-inicio */"), b = html.indexOf("/* @queda-fim */");
if (a < 0 || b < 0) throw new Error("marcadores @queda-inicio / @queda-fim não encontrados em site/index.html");
const { quedaDaOpcao } = new Function(html.slice(a, b) + "; return { quedaDaOpcao };")();

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const igual = (obtido, esperado, texto) => confere(JSON.stringify(obtido) === JSON.stringify(esperado), `${texto}\n      obtido:   ${JSON.stringify(obtido)}\n      esperado: ${JSON.stringify(esperado)}`);
const opcao = (preco, queda) => ({ preco_varejo: preco, ...(queda ? { queda_preco: queda } : {}) });

// ---- o caso normal: a margarina que foi de 14,99 para 7,99 ----
igual(quedaDaOpcao(opcao(7.99, { preco_antes: 14.99, percentual: 47, dias: 7 })), { percentual: 47, antes: 14.99, dias: 7 }, "queda de 47% em 7 dias");

// ---- sem marca, sem selo ----
igual(quedaDaOpcao(opcao(7.99)), null, "opção sem queda_preco (API antiga ou produto sem queda)");
igual(quedaDaOpcao(opcao(7.99, null)), null, "queda_preco vazio");
igual(quedaDaOpcao(null), null, "opção nula (mercado que não vende)");
igual(quedaDaOpcao(undefined), null, "opção indefinida");
igual(quedaDaOpcao({ queda_preco: { preco_antes: 10, percentual: 20, dias: 7 } }), null, "sem preço atual");

// ---- o selo só vale se bate com o preço mostrado ----
igual(quedaDaOpcao(opcao(8.99, { preco_antes: 14.99, percentual: 47, dias: 7 })), { percentual: 40, antes: 14.99, dias: 7 }, "o percentual é refeito com os preços da tela (a marca dizia 47%)");
igual(quedaDaOpcao(opcao(14.99, { preco_antes: 14.99, percentual: 47, dias: 7 })), null, "o preço já voltou ao de antes: sem selo");
igual(quedaDaOpcao(opcao(16, { preco_antes: 14.99, percentual: 47, dias: 7 })), null, "o preço passou do de antes: sem selo");
igual(quedaDaOpcao(opcao(14.95, { preco_antes: 14.99, percentual: 47, dias: 7 })), null, "queda que arredonda para 0%: sem selo");
igual(quedaDaOpcao(opcao(0, { preco_antes: 14.99, percentual: 100, dias: 7 })), null, "preço atual zerado: dado ruim, sem selo");

// ---- dias e dados mal formados ----
igual(quedaDaOpcao(opcao(5, { preco_antes: 10, percentual: 50 })), { percentual: 50, antes: 10, dias: 7 }, "sem dias: assume 7");
igual(quedaDaOpcao(opcao(5, { preco_antes: 10, percentual: 50, dias: 14 })), { percentual: 50, antes: 10, dias: 14 }, "dias vem da API (14)");
igual(quedaDaOpcao(opcao("7.99", { preco_antes: "14.99", dias: "7" })), { percentual: 47, antes: 14.99, dias: 7 }, "números vindos como texto");
igual(quedaDaOpcao(opcao(7.99, { preco_antes: "abc" })), null, "preço de antes ilegível");
igual(quedaDaOpcao(opcao(7.99, { preco_antes: -3 })), null, "preço de antes negativo");

if (erros.length) {
  console.error(`${erros.length} falha(s):\n - ` + erros.join("\n - "));
  process.exit(1);
}
console.log(`${ok} verificações passaram`);
