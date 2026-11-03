// Testes da entrega por cidade dentro de site/index.html: quem entrega onde e se a tabela do site bate com a do levantamento.
// Rodar com:  node tests/test_entrega.js
const fs = require("fs");
const path = require("path");
const raiz = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(raiz, "site", "index.html"), "utf8");

const bloco = (ini, fim) => {
  const a = html.indexOf(ini), b = html.indexOf(fim);
  if (a < 0 || b < 0) throw new Error(`marcadores ${ini} / ${fim} não encontrados em site/index.html`);
  return html.slice(a, b);
};
const semAcento = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const MERCADOS = [{ id: "Apoio Entrega", nome: "Apoio Entrega" }, { id: "Atacadao", nome: "Atacadão" }, { id: "Supernosso", nome: "Supernosso" }, { id: "Super ABC", nome: "Super ABC" }];
const corpo = bloco("/* @entrega-inicio */", "/* @entrega-fim */") + bloco("/* @entrega-regras-inicio */", "/* @entrega-regras-fim */");
const { ENTREGA_POR_CIDADE, situacaoDeEntrega, mercadosDaCidade } =
  new Function("semAcento", "MERCADOS", corpo + "; return { ENTREGA_POR_CIDADE, situacaoDeEntrega, mercadosDaCidade };")(semAcento, MERCADOS);
const CIDADES = new Function("return " + /const CIDADES_ATENDIDAS = (\[[\s\S]*?\]);/.exec(html)[1])();

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const nomes = (cidade) => mercadosDaCidade(cidade).map((m) => m.nome).join(", ");

// ---- a tabela do site é a do levantamento ----
const levantamento = JSON.parse(fs.readFileSync(path.join(raiz, "dados", "entrega_por_cidade.json"), "utf8")).cidades;
const esperado = {};
for (const [cidade, porMercado] of Object.entries(levantamento)) esperado[cidade] = Object.fromEntries(Object.entries(porMercado).map(([m, info]) => [m, info.situacao]));
confere(JSON.stringify(ENTREGA_POR_CIDADE) === JSON.stringify(esperado),
  "site/index.html está desatualizado em relação a dados/entrega_por_cidade.json: rode  python levantar_entrega.py --relatorio");
// toda cidade atendida tem linha na tabela, com os 4 mercados
for (const cidade of CIDADES) {
  confere(ENTREGA_POR_CIDADE[cidade] && MERCADOS.every((m) => ENTREGA_POR_CIDADE[cidade][m.id]), `falta a linha de entrega da cidade ${cidade}`);
}

// ---- as regras ----
confere(situacaoDeEntrega("Betim/MG", "Atacadao") === "atende", "Atacadão atende Betim");
confere(situacaoDeEntrega("Contagem/MG", "Super ABC") === "nao_atende", "Super ABC não atende Contagem");
confere(situacaoDeEntrega("Santa Luzia/MG", "Atacadao") === "parcial", "Atacadão atende só parte de Santa Luzia");
confere(situacaoDeEntrega("Ibirite/MG", "Apoio Entrega") === "atende", "aceita a cidade sem acento");
confere(situacaoDeEntrega("São Joaquim de Bicas/MG", "Supernosso") === "nao_atende", "Supernosso não atende São Joaquim de Bicas");
confere(situacaoDeEntrega("Juatuba/MG", "Super ABC") === "atende", "cidade sem levantamento não esconde nada");
confere(situacaoDeEntrega("", "Super ABC") === "atende", "sem cidade não esconde nada");

confere(nomes("Belo Horizonte/MG") === "Apoio Entrega, Atacadão, Supernosso, Super ABC", `BH: ${nomes("Belo Horizonte/MG")}`);
confere(nomes("Contagem/MG") === "Apoio Entrega, Atacadão, Supernosso", `Contagem: ${nomes("Contagem/MG")}`);
confere(nomes("Nova Lima/MG") === "Apoio Entrega, Supernosso", `Nova Lima: ${nomes("Nova Lima/MG")}`);
confere(nomes("Sarzedo/MG") === "Apoio Entrega, Atacadão", `Sarzedo: ${nomes("Sarzedo/MG")}`);
confere(mercadosDaCidade("Igarapé/MG").length === 0, "Igarapé não tem nenhum mercado");
confere(mercadosDaCidade("Brumadinho/MG").length === 1 && mercadosDaCidade("Brumadinho/MG")[0].nome === "Atacadão", "Brumadinho só tem o Atacadão");
const parciais = (cidade) => mercadosDaCidade(cidade).filter((m) => m.parcial).map((m) => m.nome).join(", ");
confere(parciais("Santa Luzia/MG") === "Atacadão", `parcial em Santa Luzia: ${parciais("Santa Luzia/MG")}`);
confere(parciais("Betim/MG") === "", "nada parcial em Betim");

console.log(`${ok} verificações passaram, ${erros.length} falharam`);
erros.forEach((e) => console.log("  FALHA:", e));
process.exit(erros.length ? 1 : 0);
