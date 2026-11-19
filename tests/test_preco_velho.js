// Testes do aviso de "preço velho" do site (bloco @preco-velho de site/index.html).
// Rodar com:  node tests/test_preco_velho.js
// A carga roda todo dia de manhã; um preço com mais de 36 h de idade quer dizer que a coleta de um dia não veio. Só então o site avisa.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const a = html.indexOf("/* @preco-velho-inicio */"), b = html.indexOf("/* @preco-velho-fim */");
if (a < 0 || b < 0) throw new Error("marcadores @preco-velho-inicio / @preco-velho-fim não encontrados em site/index.html");
const { PRECO_VELHO_HORAS, avisoDePrecoVelho } = new Function(html.slice(a, b) + "; return { PRECO_VELHO_HORAS, avisoDePrecoVelho };")();

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const igual = (obtido, esperado, texto) => confere(JSON.stringify(obtido) === JSON.stringify(esperado), `${texto}\n      obtido:   ${JSON.stringify(obtido)}\n      esperado: ${JSON.stringify(esperado)}`);

const AGORA = Date.parse("2026-11-19T13:00:00Z");
const haHoras = (h) => new Date(AGORA - h * 3600000).toISOString();

igual(PRECO_VELHO_HORAS, 36, "o limite é de 36 horas (um dia e meio)");

// ---- o dia a dia não avisa ----
igual(avisoDePrecoVelho(haHoras(0.5), AGORA), null, "preço de meia hora atrás");
igual(avisoDePrecoVelho(haHoras(6), AGORA), null, "preço de hoje cedo");
igual(avisoDePrecoVelho(haHoras(24), AGORA), null, "preço de ontem à mesma hora (a carga é diária)");
igual(avisoDePrecoVelho(haHoras(32), AGORA), null, "preço de 32 h: a carga de ontem veio tarde (a reserva do GitHub chega a atrasar)");
igual(avisoDePrecoVelho(haHoras(36), AGORA), null, "exatamente 36 h ainda é normal");

// ---- uma coleta que não veio avisa, com a data ----
const velho = avisoDePrecoVelho(haHoras(36.1), AGORA);
confere(velho && velho.dias === 1 && /há 1 dia\b/.test(velho.texto), `36 h: «há 1 dia»: ${velho && velho.texto}`);
const trasantes = avisoDePrecoVelho("2026-11-16T10:44:50+00:00", AGORA);
igual(trasantes && trasantes.dia, "16/11", "a data mostrada é a do preço, no horário de Brasília");
confere(trasantes && trasantes.dias === 3 && /há 3 dias/.test(trasantes.texto), `16/11 visto em 19/11: «há 3 dias»: ${trasantes && trasantes.texto}`);
confere(trasantes && /Estes preços são de 16\/11/.test(trasantes.texto) && /Confira no site do mercado antes de comprar/.test(trasantes.texto), "o texto diz a data e manda conferir no mercado");
confere(avisoDePrecoVelho(haHoras(24 * 40), AGORA).dias === 40, "40 dias");

// ---- a data é a de Brasília, não a do UTC ----
igual(avisoDePrecoVelho("2026-11-17T01:30:00Z", AGORA).dia, "16/11", "01:30 UTC de 17/11 é 22:30 de 16/11 em Brasília");

// ---- dado ruim não vira aviso (nem erro) ----
for (const ruim of [undefined, null, "", "ontem", "2026-13-45", {}, []]) igual(avisoDePrecoVelho(ruim, AGORA), null, `data ilegível: ${JSON.stringify(ruim)}`);
igual(avisoDePrecoVelho(haHoras(-5), AGORA), null, "hora no futuro (relógio errado): não avisa");
igual(avisoDePrecoVelho(haHoras(-50), AGORA), null, "hora bem no futuro (relógio muito errado): não avisa");
confere(avisoDePrecoVelho(haHoras(50)) !== undefined, "sem o 'agora', usa o relógio do aparelho (não quebra)");

console.log(`${ok} verificações passaram, ${erros.length} falharam`);
if (erros.length) { for (const e of erros) console.log("  ✗ " + e); process.exit(1); }
