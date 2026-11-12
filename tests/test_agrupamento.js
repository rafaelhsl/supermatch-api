// Testes do agrupamento do modo "Produto equivalente" dentro de site/index.html.
// Rodar com:  node tests/test_agrupamento.js
// Quem decide o que é equivalente é a API (equivalencia.py, testada em tests/test_equivalencia.py): cada produto chega com
// `chave_equivalencia` e `rotulo_equivalencia`. O site só junta os que têm a mesma chave, conta o produto repetido uma vez só
// e descarta preço muito abaixo do normal do grupo (erro de coleta).
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const a = html.indexOf("/* @equivalencia-inicio */"), b = html.indexOf("/* @equivalencia-fim */");
if (a < 0 || b < 0) throw new Error("marcadores @equivalencia-inicio / @equivalencia-fim não encontrados em site/index.html");
const { agruparEquivalentes } = new Function(html.slice(a, b) + "; return { agruparEquivalentes };")();

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };

const mk = (id, supermercado, nome, preco, extra = {}) => ({ id, supermercado, nome, preco_varejo: preco, preco_atacado: preco, quantidade_atacado: 1, ...extra });
const chave = (c, r) => ({ chave_equivalencia: c, rotulo_equivalencia: r });
const BRANCO = chave("arroz|branco|tipo 1|5000g", "Arroz branco tipo 1, 5 kg");
const PARBO = chave("arroz|parboilizado|tipo 1|5000g", "Arroz parboilizado tipo 1, 5 kg");

// ---- uma busca real misturada ----
{
  const brutos = [
    { produto_base: "a", opcoes_de_compra: [mk(1, "Atacadao", "Arroz Branco Camil Tipo 1 5kg", 24.9, BRANCO), mk(2, "Supernosso", "arroz branco camil tipo 1 5kg", 24.99, BRANCO)] },
    { produto_base: "b", opcoes_de_compra: [mk(3, "Apoio Entrega", "Arroz Tia Ju Tipo 1 5kg", 19.99, BRANCO), mk(1, "Atacadao", "Arroz Branco Camil Tipo 1 5kg", 24.9, BRANCO)] },   // repetido: conta uma vez
    { produto_base: "c", opcoes_de_compra: [mk(4, "Super ABC", "Arroz Parboilizado T1 Prato Fino 5kg", 29.9, PARBO), mk(5, "Super ABC", "Biscoito de Arroz Camil 150g", 5)] },       // sem chave: fica de fora
  ];
  const g = agruparEquivalentes(brutos);
  confere(g.length === 2, `deveria haver 2 grupos (branco e parboilizado), há ${g.length}`);
  confere(g[0].equivalente === true && g[0].opcoes_de_compra.length === 3, "o grupo do arroz branco junta 3 produtos distintos (o repetido conta uma vez)");
  confere(g[0].produto_base === "Arroz branco tipo 1, 5 kg" && g[0].chave === "arroz|branco|tipo 1|5000g", `rótulo e chave do grupo vêm da API: ${g[0].produto_base} / ${g[0].chave}`);
  confere(g[1].opcoes_de_compra.length === 1 && g[1].opcoes_de_compra[0].id === 4, "o parboilizado fica sozinho; o biscoito, sem chave, não entra em grupo nenhum");
  confere(g[0].opcoes_de_compra.every((o) => o.chave_equivalencia === g[0].chave), "só entram no grupo produtos com a chave dele");
}

// ---- o que a API manda é o que vale ----
{
  const sal = chave("sal|refinado|1000g", "Sal refinado, 1 kg");
  const brutos = [
    { produto_base: "a", opcoes_de_compra: [mk(1, "Atacadao", "Sal Refinado Cisne 1kg", 3, sal), mk(2, "Supernosso", "Sal Refinado Globo 1kg", 2.5, sal)] },
    { produto_base: "b", opcoes_de_compra: [mk(3, "Super ABC", "Sal com Moedor Lemon Pepper 70g", 12), mk(4, "Apoio Entrega", "Arroz Branco Camil Tipo 1 5kg", 24.9)] },   // sem chave: o nome, sozinho, não basta
  ];
  const g = agruparEquivalentes(brutos);
  confere(g.length === 1 && g[0].chave === "sal|refinado|1000g" && g[0].opcoes_de_compra.length === 2, `só o sal tem chave: ${JSON.stringify(g.map((x) => x.chave))}`);
  confere(agruparEquivalentes([]).length === 0, "sem produtos, sem grupos");
  confere(agruparEquivalentes([{ produto_base: "x", opcoes_de_compra: [mk(9, "Atacadao", "Arroz Branco Camil Tipo 1 5kg", 24.9)] }]).length === 0, "API sem chaves de equivalência: nenhum grupo (o site não adivinha pelo nome)");
  confere(agruparEquivalentes([{ produto_base: "x", opcoes_de_compra: [mk(9, "Supernosso", "Produto Sem Rótulo 1kg", 5, { chave_equivalencia: "x|1000g" })] }])[0].produto_base === "x|1000g", "chave sem rótulo: usa a chave como rótulo");
  const semId = [{ produto_base: "x", opcoes_de_compra: [{ supermercado: "Atacadao", nome: "Sal Cisne 1kg", preco_varejo: 3, ...sal }, { supermercado: "Atacadao", nome: "Sal Cisne 1kg", preco_varejo: 3, ...sal }] }];
  confere(agruparEquivalentes(semId)[0].opcoes_de_compra.length === 1, "sem `id`, o mesmo mercado e nome contam uma vez só");
}

// ---- ordem: quem tem mais mercados primeiro, depois alfabética ----
{
  const x = chave("a|1000g", "Banana"), y = chave("b|1000g", "Abacate"), z = chave("c|1000g", "Zebra");
  const g = agruparEquivalentes([{ produto_base: "t", opcoes_de_compra: [
    mk(1, "Atacadao", "n1", 1, x), mk(2, "Supernosso", "n2", 1, x),
    mk(3, "Atacadao", "n3", 1, y),
    mk(4, "Atacadao", "n4", 1, z), mk(5, "Super ABC", "n5", 1, z) ] }]);
  confere(g.map((q) => q.produto_base).join(",") === "Banana,Zebra,Abacate", `ordem dos grupos: ${g.map((q) => q.produto_base).join(",")}`);
}

// ---- erro de coleta: preço muito abaixo do normal sai do grupo ----
{
  const feijao = chave("feijao|carioca|tipo 1|1000g", "Feijão carioca tipo 1, 1 kg");
  const seis = [10, 10.5, 11, 11.5, 12, 0.78].map((p, i) => mk(100 + i, "Supernosso", `Feijão Carioca Marca${i} 1kg`, p, feijao));
  const gf = agruparEquivalentes([{ produto_base: "f", opcoes_de_compra: seis }]);
  confere(gf.length === 1 && gf[0].opcoes_de_compra.every((o) => o.preco_varejo > 5), "preço de R$ 0,78 num grupo de R$ 10 a 12 é descartado como erro de coleta");
  const quatro = [10, 10.5, 11, 0.78].map((p, i) => mk(200 + i, "Supernosso", `Feijão Carioca Marca${i} 1kg`, p, feijao));
  confere(agruparEquivalentes([{ produto_base: "f", opcoes_de_compra: quatro }])[0].opcoes_de_compra.length === 4, "com menos de 5 produtos no grupo o filtro não age (não há mediana confiável)");
}

console.log(`${ok} verificações passaram, ${erros.length} falharam`);
erros.forEach((e) => console.log("  FALHA:", e));
process.exit(erros.length ? 1 : 0);
