// Testes da atualização dos preços da lista de compras, que fica dentro de site/index.html.
// Rodar com:  node tests/test_lista.js
// A lista é salva no navegador com os preços de quando cada item entrou. Ao abrir a página, o site consulta de novo os itens
// com mais de 3 horas: decide quais estão velhos, qual termo consultar e qual grupo da resposta é o mesmo item.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const bloco = (ini, fim) => {
  const a = html.indexOf(ini), b = html.indexOf(fim);
  if (a < 0 || b < 0) throw new Error(`marcadores ${ini} / ${fim} não encontrados em site/index.html`);
  return html.slice(a, b);
};
const semAcento = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
// o bloco da lista usa agruparEquivalentes (motor de equivalência), então os dois blocos andam juntos
const { itemDesatualizado, termoDoItem, grupoDeHoje, idDoGrupo, juntarRepetidos, VALIDADE_DOS_PRECOS_DA_LISTA_MS } = new Function("semAcento",
  bloco("/* @equivalencia-inicio */", "/* @equivalencia-fim */") + bloco("/* @lista-inicio */", "/* @lista-fim */")
  + "; return { itemDesatualizado, termoDoItem, grupoDeHoje, idDoGrupo, juntarRepetidos, VALIDADE_DOS_PRECOS_DA_LISTA_MS };")(semAcento);

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const igual = (obtido, esperado, texto) => confere(JSON.stringify(obtido) === JSON.stringify(esperado), `${texto}\n      obtido:   ${JSON.stringify(obtido)}\n      esperado: ${JSON.stringify(esperado)}`);

const op = (id, supermercado, nome, preco, extra = {}) => ({ id, supermercado, nome, preco_varejo: preco, preco_atacado: preco, quantidade_atacado: 1, atualizado_em: "2026-11-10T12:00:00+00:00", ...extra });

// ---- quais itens estão velhos ----
const H = 60 * 60 * 1000, agora = Date.now();
confere(VALIDADE_DOS_PRECOS_DA_LISTA_MS === 3 * H, "os preços valem 3 horas");
confere(itemDesatualizado({ qtd: 1 }, agora), "item sem hora (guardado numa versão antiga) é velho");
confere(itemDesatualizado({ qtd: 1, em: 0 }, agora), "hora zero é velha");
confere(!itemDesatualizado({ qtd: 1, em: agora }, agora), "item de agora está em dia");
confere(!itemDesatualizado({ qtd: 1, em: agora - 2.9 * H }, agora), "2h54 ainda está em dia");
confere(itemDesatualizado({ qtd: 1, em: agora - 3.1 * H }, agora), "3h06 é velho");

// ---- qual termo consultar ----
igual(termoDoItem({ produto_base: "Arroz Tio João Tipo 1 5kg", opcoes_de_compra: [op(1, "Atacadao", "Arroz Tio João 5kg", 20), op(2, "Supernosso", "Arroz Tio João 5kg", 21, { termo: "arroz" })] }),
  "arroz", "o termo do catálogo, que vem em cada opção");
igual(termoDoItem({ produto_base: "Óleo de Soja Liza 900ml", opcoes_de_compra: [op(1, "Atacadao", "Óleo de Soja Liza 900ml", 7)] }),
  "oleo", "item antigo, sem termo nas opções: primeira palavra do nome, sem acento");
igual(termoDoItem({ produto_base: "Leite condensado sem lactose, 395 g", equivalente: true, opcoes_de_compra: [op(1, "Atacadao", "Leite Condensado Italac Zero Lactose 395g", 8, { termo: "leite condensado" })] }),
  "leite condensado", "item equivalente também usa o termo do catálogo");
igual(termoDoItem({ produto_base: "", opcoes_de_compra: [] }), "", "sem nada para consultar: vazio");

// ---- qual grupo da resposta é o mesmo item: exato ----
const exato = { produto_base: "Arroz Tio João Tipo 1 5kg", ean: "7893500000001", opcoes_de_compra: [op(1, "Atacadao", "Arroz Tio João 5kg", 20)] };
const grupoApi = (produto_base, ean, ...opcoes) => ({ produto_base, ean, vencedor_preco_baixo: opcoes[0].supermercado, opcoes_de_compra: opcoes });
const hoje = (...grupos) => ({ carrinho_comparativo: grupos });

let novo = grupoDeHoje(exato, hoje(grupoApi("Arroz Camil 5kg", "7891", op(9, "Atacadao", "Arroz Camil 5kg", 22)), grupoApi("Arroz Tio João Tipo 1 5kg", "7893500000001", op(11, "Atacadao", "Arroz Tio João 5kg", 18.5), op(12, "Supernosso", "Arroz Tio João 5kg", 19.9))));
igual(novo && novo.opcoes_de_compra.map((o) => o.preco_varejo), [18.5, 19.9], "exato: acha o grupo pelo código de barras e traz os preços de hoje");
novo = grupoDeHoje(exato, hoje(grupoApi("Arroz Tio João Branco 5 kg (outro nome hoje)", "07893500000001", op(11, "Atacadao", "Arroz Tio João 5kg", 18.5))));
confere(novo && novo.opcoes_de_compra[0].preco_varejo === 18.5, "exato: o nome do grupo mudou, mas o código de barras (mesmo com zero à esquerda) acha o item");
novo = grupoDeHoje({ produto_base: "Café Pilão 500g", opcoes_de_compra: [op(1, "Super ABC", "Café Pilão 500g", 20)] }, hoje(grupoApi("Café Pilão 500g", undefined, op(5, "Super ABC", "Café Pilão 500g", 19))));
confere(novo && novo.opcoes_de_compra[0].preco_varejo === 19, "exato sem código de barras: acha pelo nome");
confere(grupoDeHoje(exato, hoje(grupoApi("Arroz Camil 5kg", "7891", op(9, "Atacadao", "Arroz Camil 5kg", 22)))) === null, "exato: produto que sumiu da resposta dá null (o item fica com o último preço)");
confere(grupoDeHoje(exato, { carrinho_comparativo: null }) === null && grupoDeHoje(exato, null) === null && grupoDeHoje(exato, {}) === null, "resposta inválida dá null, sem quebrar");
confere(grupoDeHoje(exato, hoje({ produto_base: "Arroz Tio João Tipo 1 5kg", ean: "7893500000001", opcoes_de_compra: [] })) === null, "grupo sem opções não vale");

// ---- equivalente: pela chave que a API manda ----
const sal = { chave_equivalencia: "sal|refinado|1000g", rotulo_equivalencia: "Sal refinado, 1 kg" };
const itemSal = { produto_base: "Sal refinado, 1 kg", equivalente: true, chave: "sal|refinado|1000g", opcoes_de_compra: [op(1, "Atacadao", "Sal Cisne 1kg", 3, sal)] };
const respSal = { equivalencia_familias: ["sal", "arroz"], carrinho_comparativo: [
  { produto_base: "a", opcoes_de_compra: [op(21, "Atacadao", "Sal Refinado Lebre 1kg", 2.4, sal), op(22, "Supernosso", "Sal Refinado Cisne 1kg", 3.1, sal)] },
  { produto_base: "b", opcoes_de_compra: [op(23, "Apoio Entrega", "Sal Grosso Lebre 1kg", 2.9, { chave_equivalencia: "sal|grosso|1000g", rotulo_equivalencia: "Sal grosso, 1 kg" })] },
] };
novo = grupoDeHoje(itemSal, respSal);
igual(novo && novo.opcoes_de_compra.map((o) => o.preco_varejo).sort(), [2.4, 3.1], "equivalente: junta pela chave da API e traz os preços de hoje (o sal grosso não entra)");
confere(grupoDeHoje({ ...itemSal, chave: "sal|marinho|1000g" }, respSal) === null, "equivalente: chave que não existe mais dá null");

// API antiga (sem equivalencia_familias): o site usa o motor próprio, e a chave guardada é a mesma nas 11 famílias antigas
const itemArroz = { produto_base: "Arroz branco tipo 1, 5 kg", equivalente: true, chave: "arroz|branco|tipo 1|5000g", opcoes_de_compra: [op(1, "Atacadao", "Arroz Branco Camil Tipo 1 5kg", 25)] };
novo = grupoDeHoje(itemArroz, hoje(grupoApi("Arroz Branco Camil Tipo 1 5kg", "1", op(31, "Atacadao", "Arroz Branco Camil Tipo 1 5kg", 23.5), op(32, "Supernosso", "Arroz Branco Tio João Tipo 1 5kg", 24))));
igual(novo && novo.opcoes_de_compra.map((o) => o.preco_varejo).sort(), [23.5, 24], "equivalente com API antiga: o motor do site acha a mesma chave");

// ---- identificador do grupo na lista ----
igual(idDoGrupo({ produto_base: "Arroz Camil 5kg", id_do_grupo: "7896006711155" }), "ex:7896006711155", "exato com id da API: usa o id");
igual(idDoGrupo({ produto_base: "Arroz Camil 5kg" }), "ex:Arroz Camil 5kg", "exato sem id (sem código de barras ou guardado antes): usa o nome");
igual(idDoGrupo({ produto_base: "Arroz branco tipo 1, 5 kg", equivalente: true, chave: "arroz|branco|tipo 1|5000g", id_do_grupo: "x" }), "eq:arroz|branco|tipo 1|5000g", "equivalente: sempre pela chave");
confere(idDoGrupo({ produto_base: "Arroz Camil 5kg", id_do_grupo: "1" }) !== idDoGrupo({ produto_base: "Arroz Camil 5kg" }), "o mesmo nome com e sem id são ids diferentes (até o item guardado ser atualizado)");
igual(idDoGrupo({ produto_base: "A", id_do_grupo: "789|200.0ml" }) === idDoGrupo({ produto_base: "B", id_do_grupo: "789|1000.0ml" }), false, "dois grupos que dividem o código têm ids diferentes pelo tamanho");

// ---- achar o item pelo id da API, mesmo com o nome do grupo mudado ----
{
  const guardado = { produto_base: "Arroz Tio João Tipo 1 5kg", ean: "7893500000001", id_do_grupo: "7893500000001", opcoes_de_compra: [op(1, "Atacadao", "Arroz Tio João 5kg", 20)] };
  novo = grupoDeHoje(guardado, hoje({ ...grupoApi("Arroz Branco Tio João 5 kg", "7893500000001", op(11, "Atacadao", "x", 18.5)), id_do_grupo: "7893500000001" }));
  confere(novo && novo.opcoes_de_compra[0].preco_varejo === 18.5, "acha pelo id_do_grupo mesmo com o nome do grupo mudado");
  const dividido = (nome, id, preco) => ({ ...grupoApi(nome, "7896478801361", op(preco, "Atacadao", nome, preco)), id_do_grupo: id });
  const resp = hoje(dividido("Refrigerante Mate Couro 200ml", "7896478801361|200.0ml", 3), dividido("Refrigerante Mate Couro 1L", "7896478801361|1000.0ml", 8));
  novo = grupoDeHoje({ produto_base: "Refrigerante Mate Couro 1L", ean: "7896478801361", id_do_grupo: "7896478801361|1000.0ml", opcoes_de_compra: [op(1, "Atacadao", "x", 7)] }, resp);
  confere(novo && novo.opcoes_de_compra[0].preco_varejo === 8, "dois grupos com o mesmo código: o id (com o tamanho) escolhe o certo");
  novo = grupoDeHoje({ produto_base: "Refrigerante Mate Couro 1L", ean: "7896478801361", opcoes_de_compra: [op(1, "Atacadao", "x", 7)] }, resp);
  confere(novo && novo.opcoes_de_compra[0].preco_varejo === 8, "item antigo, sem id, com 2 grupos de mesmo código: o nome desempata");
  confere(grupoDeHoje({ produto_base: "Refrigerante Mate Couro (nome antigo)", ean: "7896478801361", opcoes_de_compra: [op(1, "Atacadao", "x", 7)] }, resp) === null, "item antigo, sem id, com 2 grupos de mesmo código e nenhum com o mesmo nome: não escolhe no chute (null)");
  confere(grupoDeHoje({ produto_base: "Café Pilão 500g", ean: "7891", opcoes_de_compra: [op(1, "Atacadao", "x", 7)] }, hoje(grupoApi("Café Pilão 500g", "7891", op(5, "Atacadao", "x", 6)))).opcoes_de_compra[0].preco_varejo === 6, "item antigo com um só grupo de mesmo código: acha");
}

// ---- juntar o que o esquema antigo duplicou ----
{
  const item = (nome, id, qtd) => ({ grupo: { produto_base: nome, ...(id ? { id_do_grupo: id } : {}), opcoes_de_compra: [] }, qtd, em: 1 });
  const lista = [item("Arroz Camil 5kg", "789", 2), item("Feijão 1kg", "111", 1), item("Arroz Camil Tipo 1 5 kg", "789", 3), item("Sabão A", null, 1), item("Sabão B", null, 1)];
  const nova = juntarRepetidos(lista);
  igual(nova.map((i) => [i.grupo.produto_base, i.qtd]), [["Arroz Camil 5kg", 5], ["Feijão 1kg", 1], ["Sabão A", 1], ["Sabão B", 1]], "mesmo id vira um item só, somando as quantidades; por nome (sem id) nada se junta");
  confere(lista[0].qtd === 2 && lista.length === 5, "não mexe na lista recebida");
  igual(juntarRepetidos([]), [], "lista vazia");
}

if (erros.length) { console.error(`${erros.length} falha(s):\n  - ` + erros.join("\n  - ")); process.exit(1); }
console.log(`${ok} verificações passaram, 0 falharam`);
