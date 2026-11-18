"""Testes da equivalência do hortifrúti (família "frutas, verduras e legumes" de equivalencia.py), sem rede e sem banco.

Rodar com:  python tests/test_equivalencia_hortifruti.py

Diferente das outras famílias, esta olha também a UNIDADE que o banco guarda ("kg": o preço é por quilo, qualquer que seja o peso do nome;
"un": por pacote ou unidade). Por isso cada nome vem com a unidade: (nome, unidade). Os nomes são REAIS, da coleta de 17/11/2026 (Supernosso,
Atacadão e Apoio); os poucos que não existiam naquele dia, e foram escritos para exercitar uma regra, estão marcados "adaptado".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import equivalencia as eq  # noqa: E402

ok, erros = 0, []


def confere(condicao, texto):
    global ok
    if condicao:
        ok += 1
    else:
        erros.append(texto)


def chave(item):
    nome, unidade = item
    r = eq.equivalencia(nome, unidade=unidade)
    return r.chave if r else None


def juntam(*itens):
    chaves = [chave(i) for i in itens]
    confere(chaves[0] is not None and all(c == chaves[0] for c in chaves), f"deveriam ser equivalentes: {itens}  ->  {chaves}")


def separam(a, b):
    ca, cb = chave(a), chave(b)
    confere(ca is not None and cb is not None and ca != cb, f"deveriam ser reconhecidos e diferentes: {a} -> {ca} | {b} -> {cb}")


def fora(item):
    confere(chave(item) is None, f"deveria ficar de fora: {item} -> {chave(item)}")


KG, UN = "kg", "un"

# ============================== o preço por quilo vale "1 kg", seja qual for o peso do nome ==============================
juntam(("Banana Prata Quilo", KG), ("Banana Prata Sn 1Kg", KG))                                       # Atacadão x Supernosso
juntam(("Tomate Italiano Supernosso 500g", KG), ("Tomate Italiano Quilo", KG))                         # o 500 g do nome é a porção; o preço é de 1 kg
juntam(("Pimentão Verde 250g", KG), ("Pimentão Verde Quilo", KG))
juntam(("Limão Siciliano Bandeja 400g", KG), ("Limão Siciliano Quilo", KG))
juntam(("Cebola Roxa 500g", KG), ("Cebola Roxa Quilo", KG))
juntam(("Cebola Sn 500g", KG), ("Cebola Quilo", KG))
juntam(("Mandioca 1.5Kg", KG), ("Mandioca-aipim Quilo", KG))                                          # aipim é mandioca; 1,5 kg é a porção
juntam(("Banana Prata Orgânica 800g", KG), ("Banana Prata Orgânica 1Kg", KG))                          # adaptado: o 2º, em 1 kg
confere(chave(("Tomate Italiano Supernosso 500g", KG)) != chave(("Tomate Italiano Supernosso 500g", UN)), "o MESMO nome com unidade kg e un tem de dar chaves diferentes")
confere(chave(("Tomate Italiano Supernosso 500g", KG)) != chave(("Tomate Italiano Supernosso 500g", None)), "sem a unidade, vale o peso do nome (500 g), não o quilo")
juntam(("Batata Inglesa Bolinha Pacote 1 Kg", UN), ("Batata Bolinha Quilo", UN))                       # pacote de 1 kg = o preço do quilo; "Quilo" sem número vale 1 kg
juntam(("Maçã Gala Bandeja 800g", UN), ("Maçã Gala 800g", UN))                                          # adaptado: o 2º, sem "Bandeja"
juntam(("Batata Doce Quilo", KG), ("Batata Doce Branca 1Kg", KG))                                       # a cor da batata-doce não separa

# ============================== sinônimos e jeitos de escrever ==============================
juntam(("Banana Nanica Quilo", KG), ("Banana Caturra Sn 1Kg", KG))                                     # caturra é nanica
juntam(("Batata Lavada Quilo", KG), ("Batata Ingelsa Supernosso 1Kg", KG))                             # lavada = inglesa; "ingelsa" é erro de digitação do mercado
juntam(("Abóbora Italiana Quilo", KG), ("Abobrinha Italiana 500g", KG))                                 # o Atacadão chama a abobrinha de abóbora italiana
juntam(("Cenoura Vermelha Sn 1Kg", KG), ("Cenoura Quilo", KG))                                         # a cenoura vermelha é a cenoura comum
juntam(("Limão Tahiti Pacote 500g", UN), ("Limão-taiti Pacote 500g", UN))                                # adaptado: o 2º, escrito com hífen e "taiti"
juntam(("Repolho Branco Quilo", KG), ("Repolho Comum 1Kg", KG), ("Repolho Verde Quilo", KG))                    # adaptado: o 3º; branco, comum e verde são o mesmo repolho
juntam(("Cenoura Orgânico do Chico 500g", UN), ("Cenoura Orgânica 500g", UN))                          # adaptado: o 2º, sem a marca
juntam(("CEBOLA ROXA ORG 400G", UN), ("Cebola Roxa Orgânica 400g", UN))                                # adaptado: abreviação "ORG" e "orgânica"

# ============================== sem peso: por unidade ou maço ==============================
juntam(("Alface Crespa un", UN), ("Alface Crespa Unidade", UN), ("Alface Crespa Hidropônica Todo Verde Unidade", UN))   # hidropônica é como se cultiva, não outra alface
juntam(("Alface Lisa Maço", UN), ("Alface Hidropônica Lisa Todo Verde Unidade", UN))                    # maço e unidade, aqui, são a mesma venda
juntam(("Couve Manteiga Maço", UN), ("Couve Manteiga Unidade", UN))                                      # adaptado: o 2º

# ============================== o que NÃO é a mesma coisa ==============================
separam(("Banana Prata Quilo", KG), ("Banana Nanica Quilo", KG))
separam(("Banana Prata Quilo", KG), ("Banana-da-terra Quilo", KG))
separam(("Banana Prata Orgânica 800g", KG), ("Banana Prata Sn 1Kg", KG))                               # orgânico custa o dobro: nunca se junta
separam(("Cebola Roxa Quilo", KG), ("Cebola Quilo", KG))
separam(("Tomate Italiano Quilo", KG), ("Tomate Salada Quilo", KG))
separam(("Tomate Italiano Quilo", KG), ("Tomate Grape Mini Bandeja 300g", UN))
separam(("Maçã Nacional Gala Quilo", KG), ("Maçã Nacional Fuji Quilo", KG))
separam(("Maca Imp Granny Smith 500g", KG), ("Maçã Granny Smith Quilo", KG))                          # adaptado: importada x nacional
separam(("Batata Doce Quilo", KG), ("Batata Lavada Quilo", KG))
separam(("Batata Doce Quilo", KG), ("Batata Quilo", KG))                                                 # adaptado: a doce não vira a "batata" sem variedade
separam(("Batata Inglesa Vermelha Asterix 1Kg", KG), ("Batata Ingelsa Supernosso 1Kg", KG))
separam(("Pimentão Verde Quilo", KG), ("Pimentão Vermelho Quilo", KG))
separam(("Pepino Comum Quilo", KG), ("Pepino Japonês Quilo", KG))
separam(("Abóbora Japonesa/Cabotiá Quilo", KG), ("Abóbora Moranga Quilo", KG))
separam(("Alho Roxo Cheiroso com Casca 500g", UN), ("Alho Poró Eleve 130g", UN))                      # alho e alho-poró são outras plantas
separam(("Couve Manteiga Maço", UN), ("Couve Flor Unidade", UN))                                         # couve e couve-flor também
separam(("Alface Crespa un", UN), ("Alface Americana un", UN))
separam(("Alface Americana Todo Verde Un", UN), ("ALFACE AMERICANA NECTAR 250 GRAMAS", UN))             # a unidade (a cabeça) e o pacote de 250 g
separam(("Cebola Roxa 500g", KG), ("Cebola Roxa 400g", UN))                                             # adaptado: o preço por quilo e o pacote de 400 g
separam(("Banana Prata Quilo", KG), ("Cebola 19kg", UN))
separam(("Cebola Quilo", KG), ("Cebola 19kg", UN))                                                       # o saco de 19 kg é outra compra

# ============================== fora: processado, outra coisa com o mesmo começo ==============================
for item in [
    ("Banana Frita Laminada Aritana", UN), ("Banana Chips Aritana Cebola e Salsa 50g", UN), ("Bananada Predilecta Pacote 350g", UN),
    ("Uva Passa La Violetera Escura 150g", UN), ("Uva Passas Clara Supernosso 150g", UN), ("TOMATE SECO SPECIALE 100G", UN),
    ("Tomate Pelado Argentino La Campagnola 400g", UN), ("Tomate Triturado Sacciali Vidro 910g", UN), ("Tomate Sem Pele Italiano San Frediano 2,5Kg", UN),
    ("CENOURA RALADA 130G", UN), ("Cenoura Processada Ralada Eleve 150g", UN), ("CENOURA  HIGIENIZADA PURO SER 100G", UN),
    ("Alho Picado Garlic Foods 200g", UN), ("Alho Frito Garlic Foods 500g", UN), ("Alho Descascado 250g", UN), ("ALHO TRITD DAI 2KG-PT S/SAL", UN),
    ("Alho Pó Bombay Herbs & Spices Pouch 40g", UN), ("Alho Cheiroso Massa 500g", UN), ("Cebola em Pó Super Nosso 50g", UN), ("Cebola Crispy E Alho 100g", UN),
    ("Cebola para Conserva 1kg", UN), ("Pepinos em Conserva Agridoce Hemmer Vidro 440g", UN), ("Abacaxi em Calda Rodelas Predilecta Lata 820g", UN),
    ("Laranja Em Rodelas Supernosso 400g", UN), ("Mamao Pre Cozido Frutt Minas 800g", UN), ("Maçã De Peito Chef Resfriado 1Kg", KG),
    ("Batata Pré-Frita Palito Congelada Bem Brasil 1,05kg", UN), ("BATATA CONG B-BRASIL 700G AIR FRYER", UN), ("Batata Ruffles Original 115g", UN),
    ("Batata Tex Tubo Queijo 100g", UN), ("Batata Rosti Cozida no Vapor Vapza 400g", UN), ("Mandioca Descascada Nectarminas 700G", UN),
    ("Mandioca Processada a Vácuo 700g", UN), ("Mandioca Aipim Cozida no Vapor Vapza Caixa 500g 2 Unidades de 250g Cada", UN), ("BROCOLIS SADIA VEG&TAL 300G-PC CONG", UN),
    ("BROCOLIS FLORETE 250G", UN), ("COUVE FLOR SADIA 300G-PC CONG", UN), ("COUVE PICADA 200G", UN), ("Couve Manteiga Processada 150g Recanto Da Lua", UN),
    ("Morango Congelado Original Food Pacote 1,02Kg", UN), ("Brócolis Ninja Eleve Processado Unidade", UN), ("Tomate em Cubos Pack 3 unidades", UN),
    ("Batata Cong Pacote 700g", UN), ("Mandioca Cong Pacote 500g", UN),                                    # adaptado: só a abreviação de congelada
    ("Cebolinha Maço", UN), ("Acelga un", UN), ("Almeirão Maço", UN),                                    # fresco, mas fora da tabela de produtos: sem chave, só no modo exato
]:
    fora(item)

# ============================== a unidade chega até a equivalência pela API ==============================
com = eq.com_equivalencia([
    {"nome": "Tomate Italiano Supernosso 500g", "unidade": "kg", "id": 1}, {"nome": "Tomate Italiano Quilo", "unidade": "kg", "id": 2},
    {"nome": "Tomate Italiano Supernosso 500g", "unidade": "un", "id": 3}, {"nome": "Arroz Branco Camil Tipo 1 5kg", "unidade": "un", "id": 4},
    {"nome": "Banana Prata Quilo", "id": 5}])
confere(com[0]["chave_equivalencia"] == com[1]["chave_equivalencia"] != com[2]["chave_equivalencia"], f"com_equivalencia ignora a unidade: {[c.get('chave_equivalencia') for c in com]}")
confere(com[0]["rotulo_equivalencia"] == "Tomate italiano, 1 kg" and com[2]["rotulo_equivalencia"] == "Tomate italiano, 500 g", f"rótulos: {[c.get('rotulo_equivalencia') for c in com]}")
confere(com[3]["chave_equivalencia"].startswith("arroz|"), "as outras famílias seguem iguais, com ou sem unidade")
confere(com[4]["chave_equivalencia"].startswith("hortifruti|banana|prata|") and "unidade" not in com[4], "produto sem o campo unidade (robô do Super ABC) segue pelo peso do nome")

# ============================== rótulos legíveis ==============================
rotulos = {
    ("Banana Prata Orgânica 800g", KG): "Banana prata orgânica, 1 kg",
    ("Maca Imp Granny Smith 500g", KG): "Maçã granny smith importada, 1 kg",
    ("Tomate Fonte Forte Com Rama 1Kg", KG): "Tomate com rama, 1 kg",
    ("CEBOLA ROXA ORG 400G", UN): "Cebola roxa orgânica, 400 g",
    ("Alface Americana Todo Verde Un", UN): "Alface americana, unidade",
    ("Abóbora Italiana Quilo", KG): "Abobrinha, 1 kg",
    ("Couve Flor Unidade", UN): "Couve-flor, unidade",
    ("Pimentão Block Laranja Rei 1Kg", KG): "Pimentão laranja, 1 kg",
}
for item, esperado in rotulos.items():
    r = eq.equivalencia(item[0], unidade=item[1])
    confere(r is not None and r.rotulo == esperado, f"rótulo de {item[0]}: {r.rotulo if r else None!r} (esperado {esperado!r})")

# ============================== a família está na lista, no fim, e as 57 anteriores não mudaram ==============================
confere(eq.FAMILIAS[-1].id == "hortifruti" and eq.FAMILIAS[-1].titulo == "frutas, verduras e legumes" and eq.FAMILIAS[-1].usa_unidade, "a família do hortifrúti é a última e pede a unidade")
confere(len(eq.FAMILIAS) == 58 and sum(1 for f in eq.FAMILIAS if f.usa_unidade) == 1, f"famílias: {len(eq.FAMILIAS)}; só uma pede a unidade")
confere("frutas, verduras e legumes" in eq.familias_equivalentes(), "a lista de famílias que o site mostra traz o hortifrúti")

if erros:
    print(f"{len(erros)} falha(s):\n  - " + "\n  - ".join(erros))
    sys.exit(1)
print(f"ok: {ok} verificações passaram")
