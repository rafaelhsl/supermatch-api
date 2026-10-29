// Testes das regras de "produto equivalente" e da cobertura por cidade, que ficam dentro de site/index.html.
// Rodar com:  node tests/test_equivalencia.js
// Cada caso vem de nomes reais de produtos dos mercados. Os "juntam" garantem que marcas diferentes caem no mesmo
// grupo; os "separam" garantem que o que não é equivalente nunca é juntado; os "fora" garantem que o que não é
// comida (ou é de outra categoria) fica de fora.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const bloco = (ini, fim) => {
  const a = html.indexOf(ini), b = html.indexOf(fim);
  if (a < 0 || b < 0) throw new Error(`marcadores ${ini} / ${fim} não encontrados em site/index.html`);
  return html.slice(a, b);
};
const semAcento = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const { equivalencia, agruparEquivalentes } = new Function("semAcento", bloco("/* @equivalencia-inicio */", "/* @equivalencia-fim */") + "; return { equivalencia, agruparEquivalentes };")(semAcento);

const CIDADES = new Function("return " + /const CIDADES_ATENDIDAS = (\[[\s\S]*?\]);/.exec(html)[1])();
const cidadeAtendida = (cidade) => {
  const [nome, uf] = String(cidade || "").split("/");
  return uf === "MG" && CIDADES.some((c) => semAcento(c) === semAcento(nome));
};

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const chave = (nome) => { const e = equivalencia(nome); return e ? e.chave : null; };
const juntam = (...nomes) => { const k = nomes.map(chave); confere(k[0] !== null && k.every((x) => x === k[0]), `deveriam ser equivalentes: ${nomes.join("  |  ")}  ->  ${k.join("  |  ")}`); };
const separam = (a, b) => confere(chave(a) !== null && chave(b) !== null && chave(a) !== chave(b), `deveriam ser reconhecidos e diferentes: ${a} -> ${chave(a)}  |  ${b} -> ${chave(b)}`);
const fora = (nome) => confere(chave(nome) === null, `deveria ficar de fora: ${nome}  ->  ${chave(nome)}`);

// ---- juntam: marcas diferentes, mesmo produto e tamanho ----
juntam("Arroz Branco Camil Tipo 1 5kg", "Arroz Agulhinha Tipo 1 Patosul Pacote 5kg", "arroz tia ju tipo 1 5kg", "Arroz Tipo 1 Codisul 5 Kg Pac", "Arroz T1 Amaral 5kg", "Arroz Branco Tipo 1 Prato Fino Pacote 5kg");
juntam("Arroz Parboilizado T1 Prato Fino 5kg", "Arroz Sepé Parboilizado Tipo 1 5kg", "arroz prato fino parboilizado tipo 1 pacote 5kg");
juntam("Feijão Carioca Camil 1kg", "Feijão Carioca Carrijo Tipo 1 1kg", "Feijao Amaral 1kg Carioca T1");
juntam("Feijão Preto Pachá 1Kg", "FEIJAO PTO CARRIJO 1KG-PC T1", "Feijão Abc Tipo 1 Preto 1kg");
juntam("Óleo de Soja Liza PET 900ml", "Óleo de Soja Tipo 1 Abc Garrafa 900ml", "Óleo de Soja Soya 900ml");
juntam("Óleo Liza Girassol 900ml", "Óleo de Girassol Sinhá Pet 900 ml");
juntam("Óleo Composto Maria Tradicional 500ml", "Óleo Misto de Soja e Oliva St. Isabel 500ml");
juntam("Café Torrado Moído Extra Forte Pouch União 500g", "Café Pilão Extra Forte Vácuo 500g", "café torrado e moído extraforte barão pacote 500g");
juntam("Café 3 Corações Tradicional - Vácuo 500g", "Café Tradicional Abc 500 G Pacote");
juntam("Manteiga com Sal Porto Alegre 200 G", "Manteiga Itambé Com sal com 200g", "Manteiga Sibele C Sal 200g");
juntam("Açúcar Refinado União 1 Kg em Embalagem Pacote", "Açúcar Refinado Caravelas Pacote 1kg");
juntam("Açúcar Cristal Delta Pacote 2 kg", "Açúcar Cristal Cururipe 2kg");
juntam("Macarrão Espaguete Ovos Santa Amália 500g", "Macarrão com Ovos Bulnez Espaguete 500g");
juntam("Detergente Líquido Ypê Coco 500ml", "detergente ypê neutro 500ml", "Detergente Líquido Limpol Limão 500ml");
juntam("Sabão em Pó Tixan Ypê Maciez 1,6kg", "Sabão em Pó Omo Lavagem Perfeita 1.6kg");
juntam("Sabão Líquido Tixan Ypê Maciez 3L", "Sabão Líquido Lavagem Perfeita Omo 3 L");
juntam("Amaciante Concentrado Downy Brisa Suave 1L", "Amaciante Concentrado Comfort Brisa Elegante 1 L");
juntam("Papel Higiênico Folha Dupla Abc 30m L12p11", "Papel Higiênico Bianco Folha Dupla 30m 12 rolos", "Papel Higiênico Folha Dupla Neutro Max Pure 30m Pacote Leve 12 Pague 11 Unidades");
juntam("Papel Higiênico F/S Abc 60m com 12", "Papel Higiênico Mili Bianco Folha Simples 60 Metros Embalagem Econômica 12 Unidades");

// ---- separam: parecidos, mas não equivalentes ----
separam("Arroz Branco Camil Tipo 1 5kg", "Arroz Parboilizado T1 Prato Fino 5kg");
separam("Arroz Branco Camil Tipo 1 5kg", "Arroz Integral Tio João Tipo 1 1kg");
separam("Arroz Branco Camil Tipo 1 5kg", "Arroz Branco Camil Tipo 1 2kg");
separam("Arroz Branco Camil Tipo 1 5kg", "Arroz Rubi Fora de Tipo 5kg");
separam("Feijão Carioca Camil 1kg", "Feijão Preto Pachá 1Kg");
separam("Óleo de Soja Liza PET 900ml", "Óleo de Girassol Liza PET 900ml");
separam("Óleo de Soja Liza PET 900ml", "Óleo de Soja Soya 500ml");
separam("Café Torrado Moído Extra Forte Pouch União 500g", "Café Torrado Moído Tradicional Pouch União 500g");
separam("Café Tradicional Abc 500 G Pacote", "Café Solúvel Granulado Tradicional 3 Corações Vidro 500g");
separam("Café 3 Corações Descafeinado Vácuo 250g", "Café 3 Corações Tradicional - Vácuo 250g");
separam("Manteiga com Sal Porto Alegre 200 G", "Manteiga Itambé Sem sal com 200g");
separam("Manteiga com Sal Porto Alegre 200 G", "Manteiga Extra com Sal Itambé 200g");
separam("Açúcar Cristal Delta Pacote 2 kg", "Açúcar Refinado União 2kg");
separam("Açúcar Demerara Naturale União 1kg", "Açúcar Mascavo Vitão 1kg");
separam("Macarrão Espaguete Ovos Santa Amália 500g", "Macarrão Parafuso Ovos Santa Amália 500g");
separam("Macarrão Espaguete Ovos Santa Amália 500g", "Macarrão Espaguete Semola Número 8 Abc 500 G");
separam("Detergente Líquido Ypê Coco 500ml", "Detergente em pó para Máquina de Lavar Louças Ypê 450g");
separam("Sabão em Pó Tixan Ypê Maciez 1,6kg", "Sabão Líquido Tixan Ypê Maciez 1,6l");
separam("Amaciante Concentrado Downy Brisa Suave 1L", "Amaciante Ypê Tradicional Aconchego 1 Litro");
separam("Papel Higiênico Folha Dupla Abc 30m L12p11", "Papel Higiênico Folha Simples Personal 30m 12 rolos");
separam("Papel Higiênico Folha Dupla Abc 30m L12p11", "Papel Higiênico Folha Dupla Abc 30m 4 rolos");

// ---- fora: não são o produto, ou não dá para garantir equivalência ----
["Biscoito Arroz Integral Natural Camil 150g", "Tempero para Feijão Sazón Pacote 60g 12 Unidades", "Feijão Carioca Pronto Camil 380g", "Arroz Carreteiro Panelinhas Seara 300g",
 "Óleo Capilar OX 120ml Nutre", "Óleo Corporal Farmax Girassol 100ml", "Sardinha Coqueiro com Óleo 125g", "Óleo Composto de Bagaço de Olliva Gallo 500ml",
 "Café em Cápsula Torrado e Moído Espresso Forza 3 Corações 80 G 10 Und", "Café Solúvel Nescafé Matinal Suave Sachet 24x40g",
 "Manteiga de Karité Pom Pom 70g", "Papel Manteiga Wyda 30cm x 7,5m Rolo", "Margarina Manteiga com Sal Claybom Pote 500g", "Manteiga Dia a Dia 500g",
 "Refrigerante Zero Açúcar Coca-Cola Garrafa 1,5l", "Açúcar Cristal 3 Corações Minissachê 400x5g", "Macarrão Instantâneo Lámen Carne Nissin Miojo Pacote 85g",
 "Detergente Sanitário Pastilha Adesiva Citrus Pato 3 Und", "Detergente Uso Geral Fresh Ajax Frasco 0,5 L", "Sabonete Barra Palmolive 85g", "Amaciante de Carne Qualimax 1.01kg",
 "Tapete Higiênico para Cães Sanol Dog 30 un", "Papel Higiênico Neve Ultracomfort"].forEach(fora);

// ---- agrupamento: uma busca real misturada ----
{
  const mk = (id, supermercado, nome, preco) => ({ id, supermercado, nome, preco_varejo: preco, preco_atacado: preco, quantidade_atacado: 1 });
  const brutos = [
    { produto_base: "a", opcoes_de_compra: [mk(1, "Atacadao", "Arroz Branco Camil Tipo 1 5kg", 24.9), mk(2, "Supernosso", "arroz branco camil tipo 1 5kg", 24.99)] },
    { produto_base: "b", opcoes_de_compra: [mk(3, "Apoio Entrega", "Arroz Tia Ju Tipo 1 5kg", 19.99), mk(1, "Atacadao", "Arroz Branco Camil Tipo 1 5kg", 24.9)] },   // repetido: conta uma vez
    { produto_base: "c", opcoes_de_compra: [mk(4, "Super ABC", "Arroz Parboilizado T1 Prato Fino 5kg", 29.9), mk(5, "Super ABC", "Biscoito de Arroz Camil 150g", 5)] },
  ];
  const g = agruparEquivalentes(brutos);
  confere(g.length === 2, `deveria haver 2 grupos (branco e parboilizado), há ${g.length}`);
  confere(g[0].equivalente === true && g[0].opcoes_de_compra.length === 3, "o grupo do arroz branco junta 3 produtos distintos");
  confere(g[0].produto_base === "Arroz branco tipo 1, 5 kg", `rótulo do grupo: ${g[0].produto_base}`);
  // erro de coleta: preço muito abaixo do normal sai do grupo
  const seis = [10, 10.5, 11, 11.5, 12, 0.78].map((p, i) => mk(100 + i, "Supernosso", `Feijão Carioca Marca${i} 1kg`, p));
  const gf = agruparEquivalentes([{ produto_base: "f", opcoes_de_compra: seis }]);
  confere(gf.length === 1 && gf[0].opcoes_de_compra.every((o) => o.preco_varejo > 5), "preço de R$ 0,78 num grupo de R$ 10 a 12 é descartado como erro de coleta");
}

// ---- cidades ----
["Belo Horizonte/MG", "BELO HORIZONTE/MG", "Betim/MG", "Brumadinho/MG", "Contagem/MG", "Esmeraldas/MG", "Ibirité/MG", "Ibirite/MG", "Igarapé/MG", "Nova Lima/MG",
 "Ribeirão das Neves/MG", "Ribeirao das Neves/MG", "Sabará/MG", "Santa Luzia/MG", "São Joaquim de Bicas/MG", "Sarzedo/MG", "Vespasiano/MG"].forEach((c) => confere(cidadeAtendida(c), `deveria atender: ${c}`));
["Uberlândia/MG", "Juiz de Fora/MG", "Juatuba/MG", "Mateus Leme/MG", "Santa Luzia/BA", "Betim/SP", "São Paulo/SP", "Rio de Janeiro/RJ", "", "Betim"].forEach((c) => confere(!cidadeAtendida(c), `NÃO deveria atender: ${c}`));
confere(CIDADES.length === 14, `são 14 cidades, há ${CIDADES.length}`);

console.log(`${ok} verificações passaram, ${erros.length} falharam`);
erros.forEach((e) => console.log("  FALHA:", e));
process.exit(erros.length ? 1 : 0);
