// Testes do "preço por quilo" do site (docs/hortifruti.md), que fica dentro de site/index.html (bloco @unidade).
// Rodar com:  node tests/test_unidade.js
// A API manda `unidade: "kg"` na opção quando o preço é por quilo. O site só mostra "/kg" e conta a lista em quilos nesse caso;
// qualquer outro valor (un, vazio, ausente, lixo) é um produto comum, igual ao de antes.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const a = html.indexOf("/* @unidade-inicio */"), b = html.indexOf("/* @unidade-fim */");
if (a < 0 || b < 0) throw new Error("marcadores @unidade-inicio / @unidade-fim não encontrados em site/index.html");
const { porQuilo, grupoPorQuilo, passoDaLista, quantidadeNaLista, quantidadesDaLista, textoDasQuantidades } = new Function(
  html.slice(a, b) + "; return { porQuilo, grupoPorQuilo, passoDaLista, quantidadeNaLista, quantidadesDaLista, textoDasQuantidades };")();

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

// ---- o cabeçalho do cupom: quilos e unidades não se somam ----
const item = (qtd, ...unidades) => ({ grupo: grupo(...unidades), qtd });
igual(quantidadesDaLista([]), { unidades: 0, quilos: 0 }, "lista vazia");
igual(quantidadesDaLista([item(3, "un"), item(2, undefined)]), { unidades: 5, quilos: 0 }, "só produtos comuns: soma de unidades, como sempre");
igual(quantidadesDaLista([item(2, "kg", "kg")]), { unidades: 0, quilos: 2 }, "só item por quilo: quilos");
igual(quantidadesDaLista([item(2, "kg"), item(3, "un"), item(1, "kg")]), { unidades: 3, quilos: 3 }, "misturado: cada um com a sua conta");
igual(quantidadesDaLista([item(1, "un", "kg")]), { unidades: 0, quilos: 1 }, "grupo com uma opção por quilo conta em quilos");
igual(textoDasQuantidades({ unidades: 1, quilos: 0 }), "1 unidade", "uma unidade (singular, como antes)");
igual(textoDasQuantidades({ unidades: 4, quilos: 0 }), "4 unidades", "várias unidades (como antes)");
igual(textoDasQuantidades({ unidades: 0, quilos: 1 }), "1 kg", "um quilo");
igual(textoDasQuantidades({ unidades: 0, quilos: 2.5 }), "2.5 kg", "quilos");
igual(textoDasQuantidades({ unidades: 1, quilos: 2 }), "1 unidade e 2 kg", "unidade e quilos");
igual(textoDasQuantidades({ unidades: 3, quilos: 1 }), "3 unidades e 1 kg", "unidades e quilo");
igual(textoDasQuantidades({ unidades: 0, quilos: 0 }), "0 unidades", "lista vazia: como antes");

console.log(`${ok} verificações passaram, ${erros.length} falharam`);
if (erros.length) { for (const e of erros) console.log("  ✗ " + e); process.exit(1); }
