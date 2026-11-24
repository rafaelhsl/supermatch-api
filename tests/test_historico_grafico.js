// Testes das contas do gráfico do histórico de preços, que ficam dentro de site/index.html (bloco @historico).
// Rodar com:  node tests/test_historico_grafico.js
// A API manda os intervalos em que cada preço valeu ({ desde, ate, preco }; ate vazio = vale até hoje) e o "hoje" de Brasília. O site monta as
// séries, a escala dos eixos, o traço em degraus, o preço de cada dia e as frases. O desenho em si (SVG, mouse, teclado) é conferido em
// tests/navegador/test_site_historico.py.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const a = html.indexOf("/* @historico-inicio */"), b = html.indexOf("/* @historico-fim */");
if (a < 0 || b < 0) throw new Error("marcadores @historico-inicio / @historico-fim não encontrados em site/index.html");
const moeda = (n) => n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const { diaDoIso, dataDoDia, montarSerie, marcasDeData, escalaDePrecos, caminhoEmDegraus, espalharRotulos, precoNoDia, situacaoDaSerie, fraseDoGrafico } = new Function("moeda",
  html.slice(a, b) + "; return { diaDoIso, dataDoDia, montarSerie, marcasDeData, escalaDePrecos, caminhoEmDegraus, espalharRotulos, precoNoDia, situacaoDaSerie, fraseDoGrafico };")(moeda);

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const igual = (obtido, esperado, texto) => confere(JSON.stringify(obtido) === JSON.stringify(esperado), `${texto}\n      obtido:   ${JSON.stringify(obtido)}\n      esperado: ${JSON.stringify(esperado)}`);
const perto = (obtido, esperado, texto) => confere(Math.abs(obtido - esperado) < 1e-9, `${texto}\n      obtido:   ${obtido}\n      esperado: ${esperado}`);
const T = (texto) => texto.replace(/\u00a0/g, " ");           // o real escreve "R$\u00a020,00" com espaço sem quebra

const d = diaDoIso;
const ATA = { id: "Atacadao", nome: "Atacadão", cor: "#eb6834", chave: "v:1:1" };
const SUP = { id: "Supernosso", nome: "Supernosso", cor: "#6250d6", chave: "v:2:2" };
const ABC = { id: "Super ABC", nome: "Super ABC", cor: "#1baf7a", chave: "n:0123456789abcdef0123" };
const prod = (p, intervalos) => ({ mercado: p.id, chave: p.chave, intervalos });
const resposta = (hoje, ...produtos) => ({ hoje, produtos });

// ---- o dia ----
igual(d("2026-11-18") - d("2026-11-17"), 1, "dias seguidos diferem de 1");
igual(d("2026-12-01") - d("2026-11-30"), 1, "a virada de mês");
igual(d("2027-01-01") - d("2026-12-31"), 1, "a virada de ano");
igual(d("2026-03-29") - d("2026-03-28"), 1, "o dia não depende de fuso nem de horário de verão");
igual(d("2026-11-18T10:44:50+00:00"), d("2026-11-18"), "com hora, vale o dia");
for (const ruim of ["", null, undefined, "ontem", "2026-13-01", "2026-02-31", "18/11/2026", 20261118]) confere(isNaN(d(ruim)), `data que não existe é NaN: ${JSON.stringify(ruim)}`);
igual(dataDoDia(d("2026-11-04")), "04/11", "04/11 (com zero à esquerda)");
igual(dataDoDia(d("2026-12-31")), "31/12", "31/12");

// ---- montar a série ----
{
  const r = resposta("2026-11-24",
    prod(ATA, [{ desde: "2026-11-12", ate: null, preco: 22.5 }, { desde: "2026-11-04", ate: "2026-11-11", preco: 24.99 }]),     // fora de ordem de propósito
    prod(SUP, [{ desde: "2026-11-04", ate: null, preco: 24.99 }]),
    prod(ABC, []));
  const g = montarSerie(r, [ATA, SUP, ABC]);
  igual(g.hoje, d("2026-11-24"), "hoje vem da API");
  igual(g.inicio, d("2026-11-04"), "o gráfico começa no primeiro registro de todos");
  igual(g.series.map((s) => s.id), ["Atacadao", "Supernosso"], "uma série por mercado que tem histórico, na ordem pedida");
  igual(g.semHistorico.map((p) => p.id), ["Super ABC"], "o mercado sem histórico vai para a lista dos sem histórico");
  const ata = g.series[0];
  igual(ata.segmentos.map((s) => [s.desde, s.ate, s.preco, s.fim]),
    [[d("2026-11-04"), d("2026-11-11"), 24.99, d("2026-11-12")], [d("2026-11-12"), d("2026-11-24"), 22.5, d("2026-11-24")]],
    "dois degraus em ordem; o primeiro termina no dia em que o segundo começa");
  igual([ata.atual, ata.menor, ata.maior, ata.mudancas, ata.saiuEm, ata.primeiroDia], [22.5, 22.5, 24.99, 1, null, d("2026-11-04")], "preço de hoje, menor, maior, mudanças");
  igual(ata.ultimaMudanca, { dia: d("2026-11-12"), de: 24.99, para: 22.5 }, "a última mudança: quando e de quanto para quanto");
  const sup = g.series[1];
  igual([sup.mudancas, sup.ultimaMudanca, sup.atual], [0, null, 24.99], "preço que nunca mudou: nenhuma mudança");
}

// ---- série com buraco (o produto saiu e voltou) ----
{
  const g = montarSerie(resposta("2026-11-24", prod(ABC, [{ desde: "2026-11-06", ate: "2026-11-09", preco: 8 }, { desde: "2026-11-15", ate: null, preco: 8.5 }])), [ABC]);
  const s = g.series[0];
  igual(s.segmentos.map((p) => [p.desde, p.ate, p.fim]), [[d("2026-11-06"), d("2026-11-09"), d("2026-11-09")], [d("2026-11-15"), d("2026-11-24"), d("2026-11-24")]], "com buraco, o primeiro degrau termina no último dia dele (nada é ligado por cima do buraco)");
  igual(precoNoDia(s, d("2026-11-09")), 8, "último dia antes do buraco");
  igual(precoNoDia(s, d("2026-11-10")), null, "dentro do buraco não há preço");
  igual(precoNoDia(s, d("2026-11-14")), null, "o dia antes de voltar também não");
  igual(precoNoDia(s, d("2026-11-15")), 8.5, "o dia em que voltou");
  igual(precoNoDia(s, d("2026-11-24")), 8.5, "hoje");
  igual(precoNoDia(s, d("2026-11-05")), null, "antes do primeiro registro");
  igual(s.mudancas, 1, "o preço que voltou diferente conta como mudança");
}
{
  const g = montarSerie(resposta("2026-11-24", prod(ABC, [{ desde: "2026-11-06", ate: "2026-11-09", preco: 8 }, { desde: "2026-11-15", ate: null, preco: 8 }])), [ABC]);
  igual(g.series[0].mudancas, 0, "voltou ao mesmo preço depois do buraco: não houve mudança");
}

// ---- produto que o mercado deixou de listar ----
{
  const g = montarSerie(resposta("2026-11-24", prod(SUP, [{ desde: "2026-11-04", ate: "2026-11-18", preco: 5.5 }])), [SUP]);
  const s = g.series[0];
  igual([s.atual, s.saiuEm, s.segmentos[0].fim], [null, d("2026-11-19"), d("2026-11-18")], "intervalo fechado e sem sucessor: sem preço de hoje, com o dia em que saiu");
  igual(situacaoDaSerie(s, g.hoje), "Sem preço desde 19/11", "a tabela diz desde quando não há preço");
}

// ---- dado ruim é descartado, nunca quebra ----
{
  const r = resposta("2026-11-24", prod(ATA, [
    { desde: "2026-02-31", ate: null, preco: 9 },          // data que não existe
    { desde: "2026-11-05", ate: null, preco: "abc" },      // preço que não é número
    { desde: "2026-11-06", ate: null, preco: 0 },          // preço zero
    { desde: "2026-11-07", ate: null, preco: -3 },         // preço negativo
    { desde: "2026-11-30", ate: null, preco: 9 },          // começa depois de hoje
    { desde: "2026-11-10", ate: "2026-11-09", preco: 9 },  // termina antes de começar
    { desde: "2026-11-10", ate: "lixo", preco: 9 },        // fim ilegível
    null, {},
    { desde: "2026-11-11", ate: null, preco: "7.5" },      // o único bom (preço como texto)
  ]));
  const g = montarSerie(r, [ATA]);
  igual(g.series.length === 1 && g.series[0].segmentos.map((s) => s.preco), [7.5], "só o intervalo bom sobrevive");
  igual(montarSerie(resposta("amanhã", prod(ATA, [{ desde: "2026-11-11", ate: null, preco: 7.5 }])), [ATA]), null, "sem o 'hoje' da API não há como desenhar");
  igual(montarSerie(null, [ATA]), null, "resposta nula");
  igual(montarSerie({ hoje: "2026-11-24" }, [ATA]).series, [], "resposta sem produtos: nenhuma série");
  igual(montarSerie({ hoje: "2026-11-24", produtos: "x" }, [ATA]).semHistorico.length, 1, "produtos que não é lista: ninguém tem histórico");
  igual(montarSerie(resposta("2026-11-24", prod(ATA, [{ desde: "2026-11-11", ate: null, preco: 7.5 }])), [SUP]).series, [], "o produto de outro mercado/chave não é usado");
  igual(montarSerie(resposta("2026-11-24", { mercado: "Supernosso", chave: "v:1:1", intervalos: [{ desde: "2026-11-11", ate: null, preco: 7.5 }] }), [ATA]).series, [], "a mesma chave em outro mercado é outro produto");
  igual(montarSerie(resposta("2026-11-24", { mercado: "Atacadao", chave: "v:9:9", intervalos: [{ desde: "2026-11-11", ate: null, preco: 7.5 }] }), [ATA]).series, [], "mesma mercado, chave diferente: não é o mesmo produto");
}

// ---- intervalos que se sobrepõem: vale o mais novo ----
{
  const g = montarSerie(resposta("2026-11-24", prod(ATA, [{ desde: "2026-11-04", ate: "2026-11-20", preco: 10 }, { desde: "2026-11-15", ate: null, preco: 9 }])), [ATA]);
  igual(g.series[0].segmentos.map((s) => [s.desde, s.ate, s.preco]), [[d("2026-11-04"), d("2026-11-14"), 10], [d("2026-11-15"), d("2026-11-24"), 9]], "o intervalo mais antigo é cortado onde o novo começa");
  igual(precoNoDia(g.series[0], d("2026-11-17")), 9, "no trecho sobreposto vale o novo");
}
{
  const g = montarSerie(resposta("2026-11-24", prod(ATA, [{ desde: "2026-11-15", ate: null, preco: 10 }, { desde: "2026-11-15", ate: null, preco: 9 }])), [ATA]);
  igual(g.series[0].segmentos.length, 1, "dois intervalos que começam no mesmo dia: sobra um");
}

// ---- um dia só de histórico ----
{
  const g = montarSerie(resposta("2026-11-24", prod(ATA, [{ desde: "2026-11-24", ate: null, preco: 7.5 }])), [ATA]);
  igual(g.series[0].segmentos.map((s) => [s.desde, s.ate, s.fim]), [[d("2026-11-24"), d("2026-11-24"), d("2026-11-24")]], "começou hoje: um segmento de zero dias");
  igual(situacaoDaSerie(g.series[0], g.hoje), "Primeiro registro hoje", "a tabela diz que é o primeiro registro");
  igual(fraseDoGrafico(g), "O histórico deste produto começou hoje: ainda não há mudança de preço para mostrar.", "a frase não finge uma evolução");
}

// ---- as frases ----
{
  const r = resposta("2026-11-24",
    prod(ATA, [{ desde: "2026-11-04", ate: "2026-11-11", preco: 24.99 }, { desde: "2026-11-12", ate: null, preco: 22.5 }]),
    prod(SUP, [{ desde: "2026-11-04", ate: "2026-11-19", preco: 20 }, { desde: "2026-11-20", ate: null, preco: 21.5 }]));
  const g = montarSerie(r, [ATA, SUP]);
  igual(T(fraseDoGrafico(g)), "A última mudança foi no Supernosso: o preço subiu de R$ 20,00 para R$ 21,50 em 20/11.", "vale a mudança mais recente entre os mercados");
  igual(T(fraseDoGrafico(g, "/kg")), "A última mudança foi no Supernosso: o preço subiu de R$ 20,00/kg para R$ 21,50/kg em 20/11.", "por quilo, o /kg acompanha os preços");
  igual(T(fraseDoGrafico(montarSerie(r, [ATA]))), "A última mudança foi no Atacadão: o preço baixou de R$ 24,99 para R$ 22,50 em 12/11.", "queda: baixou");
  igual(situacaoDaSerie(g.series[0], g.hoje), "Última mudança em 12/11", "a tabela: última mudança");
}
{
  const r = resposta("2026-11-24", prod(ATA, [{ desde: "2026-11-18", ate: null, preco: 3.79 }]), prod(SUP, [{ desde: "2026-11-18", ate: null, preco: 4.99 }]));
  igual(fraseDoGrafico(montarSerie(r, [ATA, SUP])), "Nenhum dos preços mudou desde 18/11.", "nada mudou, vários mercados");
  igual(fraseDoGrafico(montarSerie(r, [ATA])), "O preço não mudou desde 18/11.", "nada mudou, um mercado só");
  igual(situacaoDaSerie(montarSerie(r, [ATA]).series[0], d("2026-11-24")), "Não mudou desde 18/11", "a tabela: não mudou");
}

// ---- as marcas do eixo das datas ----
{
  const hoje = d("2026-11-24");
  igual(marcasDeData(hoje - 6, hoje, 5).map((x) => hoje - x), [6, 4, 2, 0], "6 dias e até 5 rótulos: de 2 em 2, terminando em hoje");
  igual(marcasDeData(hoje - 20, hoje, 5).map((x) => hoje - x), [14, 7, 0], "20 dias: de semana em semana, terminando em hoje");
  igual(marcasDeData(hoje - 20, hoje, 3).map((x) => hoje - x), [14, 0], "20 dias e só 3 rótulos: de 14 em 14");
  igual(marcasDeData(hoje - 60, hoje, 4).map((x) => hoje - x), [56, 28, 0], "60 dias e 4 rótulos: de 28 em 28");
  igual(marcasDeData(hoje - 1, hoje, 5).map((x) => hoje - x), [1, 0], "2 dias: os dois");
  igual(marcasDeData(hoje, hoje, 5).map((x) => hoje - x), [0], "um dia só: só hoje");
  for (const [dias, max] of [[3, 2], [10, 3], [30, 5], [90, 4], [365, 6], [1000, 5]]) {
    const m = marcasDeData(hoje - dias, hoje, max);
    confere(m.length <= Math.max(2, max) || dias > 365, `${dias} dias com ${max} rótulos: não passa do máximo (${m.length})`);
    confere(m[m.length - 1] === hoje && m.every((x, i) => !i || x > m[i - 1]) && m[0] >= hoje - dias, `${dias} dias: crescente, termina em hoje, não sai do período`);
  }
}

// ---- a escala dos preços ----
{
  const e = escalaDePrecos([7.99, 5.99, 6.49]);
  confere(e.min < 5.99 && e.max > 7.99, "a escala cobre o menor e o maior preço");
  confere(e.ticks.length >= 2 && e.ticks.length <= 5, `entre 2 e 5 riscos: ${e.ticks}`);
  confere(e.ticks.every((t) => t >= e.min && t <= e.max), "os riscos ficam dentro da escala");
  confere(e.ticks.every((t, i) => !i || t > e.ticks[i - 1]), "os riscos crescem");
  const passos = e.ticks.slice(1).map((t, i) => Math.round((t - e.ticks[i]) * 10000) / 10000);
  confere(passos.every((p) => p === passos[0]), `os riscos são equidistantes: ${passos}`);
  confere([1, 2, 2.5, 5].some((f) => Math.abs(Math.log10(passos[0] / f) % 1) < 1e-9 || Math.abs(Math.abs(Math.log10(passos[0] / f) % 1) - 1) < 1e-9), `o passo é redondo: ${passos[0]}`);
}
{
  const e = escalaDePrecos([7.99, 7.99]);
  confere(e.min < 7.99 && e.max > 7.99, "preço único: a escala dá folga dos dois lados");
  confere(e.ticks.length >= 2, `preço único ainda tem riscos: ${e.ticks}`);
}
{
  const e = escalaDePrecos([259.99, 49.9]);
  confere(e.ticks.length <= 5 && e.min < 49.9 && e.max > 259.99, `faixa larga (carne): ${e.ticks}`);
  igual(escalaDePrecos([]), null, "sem preços, sem escala");
  igual(escalaDePrecos([0, -1, NaN]), null, "só preço ruim, sem escala");
  confere(escalaDePrecos([0.5, 0.75]).min >= 0, "a escala nunca desce abaixo de zero");
  confere(escalaDePrecos([0.05, 5]).min >= 0, "mesmo com uma folga maior que o menor preço, a escala não desce abaixo de zero");
  const pequeno = escalaDePrecos([0.99, 1.19]);
  confere(pequeno.ticks.length >= 2, `preços baixos: ${pequeno.ticks}`);
}

// ---- o traço em degraus ----
{
  const x = (dia) => (dia - 100) * 10, y = (p) => 200 - p * 10;
  const seg = (desde, ate, preco, fim) => ({ desde, ate, preco, fim });
  igual(caminhoEmDegraus([seg(100, 109, 5, 110), seg(110, 120, 8, 120)], x, y), "M0 150H100V120H200", "dois degraus colados: reta, subida vertical, reta");
  igual(caminhoEmDegraus([seg(100, 120, 5, 120)], x, y), "M0 150H200", "um preço só: uma reta");
  igual(caminhoEmDegraus([seg(100, 103, 5, 103), seg(110, 120, 6, 120)], x, y), "M0 150H30M100 140H200", "com buraco: dois traços separados");
  igual(caminhoEmDegraus([seg(120, 120, 5, 120)], x, y), "M200 150H200", "um dia só: um traço de comprimento zero (a ponta o mostra)");
  igual(caminhoEmDegraus([], x, y), "", "sem segmentos, sem traço");
  confere(!/L/.test(caminhoEmDegraus([seg(100, 109, 5, 110), seg(110, 120, 8, 120)], x, y)), "nunca há linha diagonal");
}

// ---- os rótulos das pontas não se sobrepõem ----
{
  igual(espalharRotulos([100, 200], 14, 0, 300), [100, 200], "longe um do outro: ficam onde estão");
  igual(espalharRotulos([100, 104], 14, 0, 300), [100, 114], "perto: o de baixo desce");
  igual(espalharRotulos([100, 100, 100], 14, 0, 300), [100, 114, 128], "iguais: em fila, na ordem");
  igual(espalharRotulos([114, 100], 14, 0, 300), [114, 100], "fora de ordem: cada um volta ao seu lugar na lista");
  const perto = espalharRotulos([296, 298, 300], 14, 0, 300);
  confere(perto.every((v) => v <= 300) && perto[1] - perto[0] >= 14 && perto[2] - perto[1] >= 14, `no fim da faixa: sobem para caber (${perto})`);
  igual(espalharRotulos([], 14, 0, 300), [], "lista vazia");
  const quatro = espalharRotulos([150, 152, 151, 149], 14, 0, 300);
  const ordenados = [...quatro].sort((p, q) => p - q);
  confere(ordenados.every((v, i) => !i || v - ordenados[i - 1] >= 14 - 1e-9), `quatro mercados no mesmo preço: nenhum em cima do outro (${quatro})`);
}

if (erros.length) { console.error(`FALHOU (${erros.length}):\n- ` + erros.join("\n- ")); process.exit(1); }
console.log(`ok: ${ok} conferências passaram`);
