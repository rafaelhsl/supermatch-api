// Testes do "preço por quilo" do site (docs/hortifruti.md), que fica dentro de site/index.html (bloco @unidade).
// Rodar com:  node tests/test_unidade.js
// A API manda `unidade: "kg"` na opção quando o preço é por quilo. O site só mostra "/kg" e conta a lista em quilos nesse caso;
// qualquer outro valor (un, vazio, ausente, lixo) é um produto comum, igual ao de antes.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const a = html.indexOf("/* @unidade-inicio */"), b = html.indexOf("/* @unidade-fim */");
if (a < 0 || b < 0) throw new Error("marcadores @unidade-inicio / @unidade-fim não encontrados em site/index.html");
const { porQuilo, grupoPorQuilo, passoDaLista, quantidadeNaLista } = new Function(
  html.slice(a, b) + "; return { porQuilo, grupoPorQuilo, passoDaLista, quantidadeNaLista };")();

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const igual = (obtido, esperado, texto) => confere(JSON.stringify(obtido) === JSON.stringify(esperado), `${texto}\n      obtido:   ${JSON.stringify(obtido)}\n      esperado: ${JSON.stringify(esperado)}`);
const grupo = (...unidades) => ({ opcoes_de_compra: unidades.map((u) => (u === undefined ? { preco_varejo: 5 } : { preco_varejo: 5, unidade: u })) });

// ---- a opção: só "kg" conta ----
igual(porQuilo({ preco_varejo: 3.79, unidade: "kg" }), true, "unidade kg: preço por quilo");
igual(porQuilo({ preco_varejo: 3.79, unidade: "un" }), false, "unidade un: preço do pacote");
igual(porQuilo({ preco_varejo: 3.79, unidade: null }), false, "unidade nula (robô do Super ABC): como está");
igual(porQuilo({ preco_varejo: 3.79 }), false, "sem o campo (API antiga, item salvo antes): como está");
igual(porQuilo({ preco_varejo: 3.79, unidade: "KG" }), false, "só a grafia exata da API vale (kg minúsculo)");
igual(porQuilo({ preco_varejo: 3.79, unidade: " kg" }), false, "com espaço, não vale");
igual(porQuilo({ preco_varejo: 3.79, unidade: "kilo" }), false, "outra palavra, não vale");
igual(porQuilo({ preco_varejo: 3.79, unidade: ["kg"] }), false, "lista com kg dentro, não vale");
igual(porQuilo(null), false, "opção nula (mercado que não vende)");
igual(porQuilo(undefined), false, "opção indefinida");

// ---- o grupo: basta uma opção por quilo ----
igual(grupoPorQuilo(grupo("kg", "kg")), true, "todas por quilo");
igual(grupoPorQuilo(grupo("un", "kg")), true, "uma por quilo (a outra é um pacote de 1 kg): a lista conta em kg");
igual(grupoPorQuilo(grupo("un", "un")), false, "só pacotes");
igual(grupoPorQuilo(grupo(undefined, null)), false, "sem unidade em nenhuma");
igual(grupoPorQuilo({ opcoes_de_compra: [] }), false, "grupo sem opções");
igual(grupoPorQuilo({}), false, "grupo sem a lista de opções");
igual(grupoPorQuilo(null), false, "grupo nulo");
igual(grupoPorQuilo(undefined), false, "grupo indefinido");

// ---- os textos ----
igual(passoDaLista(true), "1 kg", "passo de item por quilo");
igual(passoDaLista(false), "uma unidade", "passo de item comum (o texto de sempre)");
igual(quantidadeNaLista(3, true), "3 kg", "3 quilos na lista");
igual(quantidadeNaLista(1, true), "1 kg", "1 quilo na lista");
igual(quantidadeNaLista(3, false), "3", "item comum: só o número, como antes");
igual(quantidadeNaLista(1, false), "1", "item comum, uma unidade");

console.log(`${ok} verificações passaram, ${erros.length} falharam`);
if (erros.length) { for (const e of erros) console.log("  ✗ " + e); process.exit(1); }
