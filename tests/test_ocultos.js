// Testes do aviso "N produtos que apenas citam a palavra foram ocultados", que fica dentro de site/index.html.
// Rodar com:  node tests/test_ocultos.js
// A API esconde o produto que só cita a palavra buscada quando há produtos suficientes que são do que foi buscado
// (veja busca.py). O site conta quantos foram escondidos, só nos mercados que entregam na cidade, e oferece mostrá-los.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const a = html.indexOf("/* @ocultos-inicio */"), b = html.indexOf("/* @ocultos-fim */");
if (a < 0 || b < 0) throw new Error("marcadores @ocultos-inicio / @ocultos-fim não encontrados em site/index.html");
const { somarMercados, notasDaBusca } = new Function(html.slice(a, b) + "; return { somarMercados, notasDaBusca };")();

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const igual = (obtido, esperado, texto) => confere(JSON.stringify(obtido) === JSON.stringify(esperado), `${texto}\n      obtido:   ${JSON.stringify(obtido)}\n      esperado: ${JSON.stringify(esperado)}`);

const TODOS = new Set(["Apoio Entrega", "Atacadao", "Supernosso", "Super ABC"]);
const SEM_ABC = new Set(["Apoio Entrega", "Atacadao", "Supernosso"]);
const busca = (extra) => ({ termo: "arroz", todos: false, ocultosSoCitam: 0, soCitamPorMercado: {}, ocultosPeloLimite: 0, ...extra });

// ---- ocultados: a frase e o botão para mostrar ----
igual(notasDaBusca(busca({ ocultosSoCitam: 13, soCitamPorMercado: { "Apoio Entrega": 5, Supernosso: 8 } }), TODOS),
  [{ texto: "13 produtos que apenas citam “arroz” foram ocultados.", botao: "Mostrar também" }], "plural: 13 produtos");
igual(notasDaBusca(busca({ termo: "sal", ocultosSoCitam: 1, soCitamPorMercado: { Atacadao: 1 } }), TODOS),
  [{ texto: "1 produto que apenas cita “sal” foi ocultado.", botao: "Mostrar também" }], "singular: 1 produto");

// ---- só contam os mercados que entregam na cidade ----
igual(notasDaBusca(busca({ ocultosSoCitam: 9, soCitamPorMercado: { "Apoio Entrega": 5, "Super ABC": 4 } }), SEM_ABC),
  [{ texto: "5 produtos que apenas citam “arroz” foram ocultados.", botao: "Mostrar também" }], "o Super ABC não entrega na cidade: só os 5 do Apoio");
igual(notasDaBusca(busca({ ocultosSoCitam: 4, soCitamPorMercado: { "Super ABC": 4 } }), SEM_ABC), [], "tudo o que foi ocultado é de mercado que não entrega: nenhuma nota");

// ---- nada escondido: nenhuma nota ----
igual(notasDaBusca(busca(), TODOS), [], "busca sem nada oculto");
igual(notasDaBusca({ termo: "arroz" }, TODOS), [], "resposta de API antiga, sem os campos novos");
igual(notasDaBusca(busca({ ocultosSoCitam: 0, soCitamPorMercado: { Supernosso: 3 } }), TODOS), [],
  "poucos produtos principais: a API já mostrou todos, então não há o que avisar");

// ---- depois de "Mostrar também": a frase muda e o botão desfaz ----
igual(notasDaBusca(busca({ todos: true, soCitamPorMercado: { "Apoio Entrega": 5, Supernosso: 8 } }), TODOS),
  [{ texto: "Mostrando também 13 produtos que apenas citam “arroz”.", botao: "Ocultar de novo" }], "mostrando também (plural)");
igual(notasDaBusca(busca({ termo: "sal", todos: true, soCitamPorMercado: { Atacadao: 1 } }), TODOS),
  [{ texto: "Mostrando também 1 produto que apenas cita “sal”.", botao: "Ocultar de novo" }], "mostrando também (singular)");
igual(notasDaBusca(busca({ todos: true, soCitamPorMercado: {} }), TODOS), [], "pediu todos e não havia nenhum que só citasse");
igual(notasDaBusca(busca({ todos: true, soCitamPorMercado: { "Super ABC": 4 } }), SEM_ABC), [], "mostrando também, mas só de mercado que não entrega");

// ---- teto de resultados ----
igual(notasDaBusca(busca({ termo: "a", ocultosPeloLimite: 7738 }), TODOS),
  [{ texto: "Há mais 7738 produtos além dos mostrados. Digite mais palavras para refinar a busca." }], "teto: sem botão");
igual(notasDaBusca(busca({ ocultosPeloLimite: 1 }), TODOS),
  [{ texto: "Há mais 1 produto além dos mostrados. Digite mais palavras para refinar a busca." }], "teto: singular");
igual(notasDaBusca(busca({ ocultosSoCitam: 2, soCitamPorMercado: { Supernosso: 2 }, ocultosPeloLimite: 5 }), TODOS).map((n) => n.botao || null),
  ["Mostrar também", null], "ocultados e teto juntos: duas notas, só a primeira com botão");

// ---- valores estranhos não viram NaN na tela ----
igual(somarMercados({ A: "x", B: -3, C: "4", D: null }, new Set(["A", "B", "C", "D"])), 4, "ignora texto, negativo e nulo; aceita número em texto");
igual(somarMercados(undefined, TODOS), 0, "sem dicionário");
igual(notasDaBusca(busca({ ocultosSoCitam: 3, soCitamPorMercado: "estranho" }), TODOS), [], "dicionário inválido não quebra");

if (erros.length) { console.error(`${erros.length} falha(s):\n  - ` + erros.join("\n  - ")); process.exit(1); }
console.log(`${ok} verificações passaram, 0 falharam`);
