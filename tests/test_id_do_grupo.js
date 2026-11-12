// Testes do identificador dos itens da lista de compras (id_do_grupo), que fica dentro de site/index.html.
// Rodar com:  node tests/test_id_do_grupo.js
// O nome do grupo exato (`produto_base`) é o do primeiro produto que entrou nele e muda de um dia para o outro; o código de barras não.
// A API manda `id_do_grupo` (o código sem zeros à esquerda, com o tamanho quando dois grupos dividem o código). O site identifica o
// item da lista por ele, acha o item de hoje na resposta da API e junta o que o esquema antigo, por nome, deixou duplicado.
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");

const bloco = (ini, fim) => {
  const a = html.indexOf(ini), b = html.indexOf(fim);
  if (a < 0 || b < 0) throw new Error(`marcadores ${ini} / ${fim} não encontrados em site/index.html`);
  return html.slice(a, b);
};
const semAcento = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const { idDoGrupo, grupoDeHoje, juntarRepetidos } = new Function("semAcento",
  bloco("/* @equivalencia-inicio */", "/* @equivalencia-fim */") + bloco("/* @lista-inicio */", "/* @lista-fim */")
  + "; return { idDoGrupo, grupoDeHoje, juntarRepetidos };")(semAcento);

let ok = 0; const erros = [];
const confere = (cond, texto) => { if (cond) ok++; else erros.push(texto); };
const igual = (obtido, esperado, texto) => confere(JSON.stringify(obtido) === JSON.stringify(esperado), `${texto}\n      obtido:   ${JSON.stringify(obtido)}\n      esperado: ${JSON.stringify(esperado)}`);

const op = (id, supermercado, nome, preco) => ({ id, supermercado, nome, preco_varejo: preco, preco_atacado: preco, quantidade_atacado: 1, atualizado_em: "2026-11-12T09:30:00+00:00" });
const grupoApi = (produto_base, ean, id_do_grupo, ...opcoes) => ({ produto_base, ean, ...(id_do_grupo ? { id_do_grupo } : {}), vencedor_preco_baixo: opcoes[0].supermercado, opcoes_de_compra: opcoes });
const hoje = (...grupos) => ({ carrinho_comparativo: grupos });

// ---- o identificador ----
igual(idDoGrupo({ produto_base: "Arroz Camil 5kg", id_do_grupo: "7896006711155" }), "ex:7896006711155", "exato com id da API: usa o id");
igual(idDoGrupo({ produto_base: "Arroz Camil 5kg" }), "ex:Arroz Camil 5kg", "exato sem id (sem código de barras ou guardado antes): usa o nome");
igual(idDoGrupo({ produto_base: "Arroz branco tipo 1, 5 kg", equivalente: true, chave: "arroz|branco|tipo 1|5000g", id_do_grupo: "x" }), "eq:arroz|branco|tipo 1|5000g", "equivalente: sempre pela chave");
confere(idDoGrupo({ produto_base: "Arroz Camil 5kg", id_do_grupo: "1" }) !== idDoGrupo({ produto_base: "Arroz Camil 5kg" }), "o mesmo nome com e sem id são ids diferentes (até o item guardado ser atualizado)");
confere(idDoGrupo({ produto_base: "A", id_do_grupo: "789|200.0ml" }) !== idDoGrupo({ produto_base: "B", id_do_grupo: "789|1000.0ml" }), "dois grupos que dividem o código têm ids diferentes pelo tamanho");
confere(idDoGrupo({ produto_base: "Nome de ontem", id_do_grupo: "789" }) === idDoGrupo({ produto_base: "Nome de hoje", id_do_grupo: "789" }), "o nome do grupo mudou, o id não");

// ---- achar o item de hoje na resposta da API ----
{
  const guardado = { produto_base: "Arroz Tio João Tipo 1 5kg", ean: "7893500000001", id_do_grupo: "7893500000001", opcoes_de_compra: [op(1, "Atacadao", "Arroz Tio João 5kg", 20)] };
  let novo = grupoDeHoje(guardado, hoje(grupoApi("Arroz Branco Tio João 5 kg", "7893500000001", "7893500000001", op(11, "Atacadao", "x", 18.5))));
  confere(novo && novo.opcoes_de_compra[0].preco_varejo === 18.5, "acha pelo id_do_grupo mesmo com o nome do grupo mudado");

  const dividido = (nome, id, preco) => grupoApi(nome, "7896478801361", id, op(preco, "Atacadao", nome, preco));
  const resp = hoje(dividido("Refrigerante Mate Couro 200ml", "7896478801361|200.0ml", 3), dividido("Refrigerante Mate Couro 1L", "7896478801361|1000.0ml", 8));
  novo = grupoDeHoje({ produto_base: "Refrigerante Mate Couro 1L", ean: "7896478801361", id_do_grupo: "7896478801361|1000.0ml", opcoes_de_compra: [op(1, "Atacadao", "x", 7)] }, resp);
  confere(novo && novo.opcoes_de_compra[0].preco_varejo === 8, "dois grupos com o mesmo código: o id (com o tamanho) escolhe o certo");
  novo = grupoDeHoje({ produto_base: "Refrigerante Mate Couro 1L", ean: "7896478801361", opcoes_de_compra: [op(1, "Atacadao", "x", 7)] }, resp);
  confere(novo && novo.opcoes_de_compra[0].preco_varejo === 8, "item antigo, sem id, com 2 grupos de mesmo código: o nome desempata");
  confere(grupoDeHoje({ produto_base: "Refrigerante Mate Couro (nome antigo)", ean: "7896478801361", opcoes_de_compra: [op(1, "Atacadao", "x", 7)] }, resp) === null,
    "item antigo, sem id, com 2 grupos de mesmo código e nenhum com o mesmo nome: não escolhe no chute (null)");
  novo = grupoDeHoje({ produto_base: "Café Pilão 500g", ean: "7891", opcoes_de_compra: [op(1, "Atacadao", "x", 7)] }, hoje(grupoApi("Café Pilão 500g (nome de hoje)", "07891", "7891", op(5, "Atacadao", "x", 6))));
  confere(novo && novo.opcoes_de_compra[0].preco_varejo === 6, "item antigo com um só grupo de mesmo código (mesmo com zero à esquerda): acha, e o nome pode ter mudado");
  confere(grupoDeHoje({ produto_base: "Sabão Brilhante 1kg", opcoes_de_compra: [op(1, "Super ABC", "x", 7)] }, hoje(grupoApi("Sabão Brilhante 1kg", undefined, undefined, op(5, "Super ABC", "x", 6)))).opcoes_de_compra[0].preco_varejo === 6, "sem código de barras: acha pelo nome");
  confere(grupoDeHoje({ produto_base: "Sabão Brilhante 1kg", opcoes_de_compra: [op(1, "Super ABC", "x", 7)] }, hoje(grupoApi("Outro Sabão 1kg", undefined, undefined, op(5, "Super ABC", "x", 6)))) === null, "sem código de barras e sem o mesmo nome: null");
}

// ---- juntar o que o esquema antigo duplicou ----
{
  const item = (nome, id, qtd) => ({ grupo: { produto_base: nome, ...(id ? { id_do_grupo: id } : {}), opcoes_de_compra: [] }, qtd, em: 1 });
  const lista = [item("Arroz Camil 5kg", "789", 2), item("Feijão 1kg", "111", 1), item("Arroz Camil Tipo 1 5 kg", "789", 3), item("Sabão A", null, 1), item("Sabão B", null, 1)];
  const nova = juntarRepetidos(lista);
  igual(nova.map((i) => [i.grupo.produto_base, i.qtd]), [["Arroz Camil 5kg", 5], ["Feijão 1kg", 1], ["Sabão A", 1], ["Sabão B", 1]], "mesmo id vira um item só, somando as quantidades; por nome (sem id) nada se junta");
  confere(lista[0].qtd === 2 && lista.length === 5, "não mexe na lista recebida");
  igual(juntarRepetidos([]), [], "lista vazia");
  igual(juntarRepetidos([item("Sabão A", null, 1), item("Sabão A", null, 2)]).map((i) => i.qtd), [3], "dois itens sem id e com o mesmo nome também se juntam (é o mesmo id de antes)");
}

if (erros.length) { console.error(`${erros.length} falha(s):\n  - ` + erros.join("\n  - ")); process.exit(1); }
console.log(`${ok} verificações passaram, 0 falharam`);
