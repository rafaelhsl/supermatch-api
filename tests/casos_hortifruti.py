"""Casos do filtro de dados/lista_hortifruti.json, com nomes e categorias REAIS dos mercados (coletados em 17/11/2026).

`entram`: fresco, vendido por quilo ou em pacote. `saem`: processado, congelado, conserva, tempero, fruta seca ou outro produto que só tem o nome parecido.
Cada item é (nome, categoria). Os nomes vêm dos mercados; o que entra e o que sai foi conferido à mão.
"""
CASOS = {
    'banana': {
        "entram": [
            ('Banana Caturra Sn 1Kg', 'Hortifrúti > Frutas'),
            ('Banana Maçã Bandeja 1Kg', 'Hortifrúti > Frutas'),
            ('Banana Prata Sn 1Kg', 'Hortifrúti > Frutas'),
            ('Banana Terra 1Kg', 'Hortifrúti > Frutas'),
            ('Banana Prata Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
            ('Banana Chips Aritana Cebola e Salsa 50g', 'Mercearia > Chips e batatas palha'),
            ('Banana Frita Laminada Aritana', 'Mercearia > Chips e batatas palha'),
            ('Bananada Zelia 400g-Lt', 'Mercearia > Doces > Doces de Fruta'),
            ('Bananada Zélia Pacote 500 g', 'Mercearia > Doces > Doces de Fruta'),
            ('Bananada Predilecta Pacote 350g', 'Mercearia > Doces e Geléias'),
        ],
    },
    'maçã': {
        "entram": [
            ('Maca Imp Granny Smith 500g', 'Hortifrúti > Frutas'),
            ('MACA ORG BUONA VITA 400G-PC', 'Hortifrúti > Frutas'),
            ('MACA ORGANICA 250-BJ', 'Hortifrúti > Frutas'),
            ('MACA RED 800G-BJ', 'Hortifrúti > Frutas'),
            ('Maçã Gala Bandeja 800g', 'Hortifrúti > Frutas'),
        ],
        "saem": [
            ('Maçã De Peito Chef Resfriado 1Kg', 'Aves, Carnes e Peixes > Carne Bovina'),
        ],
    },
    'laranja': {
        "entram": [
            ('Laranja Bahia Importada 1Kg', 'Hortifrúti > Frutas'),
            ('Laranja Pera Pacote 3 kg', 'Hortifrúti > Frutas'),
            ('Laranja Seleta 1Kg', 'Hortifrúti > Frutas'),
            ("Laranja Serra D'Água Pacote 1Kg", 'Hortifrúti > Frutas'),
            ('Laranja Bahia Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
            ('Laranja Em Rodelas Supernosso 400g', 'Padaria > Rotisseria'),
        ],
    },
    'limão': {
        "entram": [
            ('Limão Siciliano Bandeja 400g', 'Hortifrúti > Frutas'),
            ('Limão Tahiti Pacote 500g', 'Hortifrúti > Frutas'),
            ('Limão Siciliano Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
            ('Limão-taiti 19kg', 'Hortifrúti > Frutas > Fruta fresca'),
            ('Limão-taiti Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
        ],
    },
    'mamão': {
        "entram": [
            ('Mamão Formosa Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
            ('Mamao Pre Cozido Frutt Minas 800g', 'Mercearia > Doces > Doces de Fruta'),
        ],
    },
    'melancia': {
        "entram": [
            ('Melancia  Sn 2Kg', 'Hortifrúti > Frutas'),
            ('Melancia Amarela 1.2Kg', 'Hortifrúti > Frutas'),
            ('Melancia Baby 1.4Kg', 'Hortifrúti > Frutas'),
            ('Melancia Lelezinha 1Kg', 'Hortifrúti > Frutas'),
            ('Melancia Magali 1Kg', 'Hortifrúti > Frutas'),
        ],
        "saem": [
        ],
    },
    'abacaxi': {
        "entram": [
            ('Abacaxi Supernosso Unidade', 'Hortifrúti > Frutas'),
            ('Abacaxi un', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
            ('Abacate Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
            ('Abacaxi em Calda Rodelas Predilecta Lata Peso Líquido 820g Peso Drenado 400g', 'Mercearia > Doces > Doces de Fruta'),
            ('Abacaxi em Calda Rodelas Predilecta Lata Peso Líquido 820g Peso Drenado 400g', 'Mercearia > Doces e Geléias'),
        ],
    },
    'manga': {
        "entram": [
            ('Manga Keyte 1Kg', 'Hortifrúti > Frutas'),
            ('Manga Palmer Sn 1Kg', 'Hortifrúti > Frutas'),
            ('Manga Rosa 700g', 'Hortifrúti > Frutas'),
            ('Manga Palmer Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
            ('Manga Tommy Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
            ('Mangada Zélia Lata 400g', 'Mercearia > Doces > Doces de Fruta'),
        ],
    },
    'uva': {
        "entram": [
            ('UVA MIMO SELECAO ARRA CHERRY 400G', 'Hortifrúti > Frutas'),
            ('UVA SWEET GREEN  LUVI 400G RESERVA', 'Hortifrúti > Frutas'),
            ('Uva Niágara 500g', 'Hortifrúti > Frutas > Fruta fresca'),
            ('Uva Thompson 500g', 'Hortifrúti > Frutas > Fruta fresca'),
            ('Uva Vitória 400g', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
            ('Uva Passas Clara Supernosso 150g', 'Hortifrúti > Castanhas e Frutas Secas'),
            ('Uva Passas Preta  Apreço 150g', 'Hortifrúti > Empório'),
            ('Uva Passa Escura Dunorte Sem Semente 150g', 'Hortifrúti > Frutas > Fruta seca e processada'),
            ('Uva Passa La Violetera Branca 150g', 'Hortifrúti > Frutas > Fruta seca e processada'),
            ('Uva Passa La Violetera Branca 200g', 'Hortifrúti > Frutas > Fruta seca e processada'),
        ],
    },
    'morango': {
        "entram": [
            ('Morango un', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
            ('Morango com Amora Congelados DHFoods 1,02 kg', 'Congelados e resfriados > Polpas e frutas'),
            ('morango congelado fruta campo 1,02kg', 'Congelados e resfriados > Polpas e frutas'),
            ('Morango Congelado Original Food Pacote 1,02Kg', 'Congelados e resfriados > Polpas e frutas'),
        ],
    },
    'abacate': {
        "entram": [
            ('Abacate Avocado In Natura 500g', 'Hortifrúti > Frutas'),
            ('Abacate Orgânico do Chico', 'Hortifrúti > Frutas'),
            ('Abacate Sn 1Kg', 'Hortifrúti > Frutas'),
            ('Abacate Quilo', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
        "saem": [
            ('Abacaxi un', 'Hortifrúti > Frutas > Fruta fresca'),
        ],
    },
    'tomate': {
        "entram": [
            ('Tomate Fonte Forte Com Rama 1Kg', 'Hortifrúti > Legumes'),
            ('Tomate Grape Mini Bandeja 300g', 'Hortifrúti > Legumes'),
            ('Tomate Italiano Supernosso 500g', 'Hortifrúti > Legumes'),
            ('Tomate Maçã Bandeja 500g', 'Hortifrúti > Legumes'),
            ('TOMATE ORGÂNICO DO CHICO 500 G', 'Hortifrúti > Legumes'),
        ],
        "saem": [
            ('TOMATE SECO SPECIALE 100G', 'Hortifrúti > Legumes'),
            ('Tomate Triturado Vale Fértil 1,01kg', 'Mercearia > Enlatados e Conservas'),
            ('Tomate Pelado Argentino La Campagnola 400g', 'Mercearia > Molhos e Condimentos > Tomate Pelado'),
            ('Tomate Italiano Sem Pele SuperNosso 400g Peso Drenado 240g', 'Mercearia > Molhos e condimentos'),
            ('Tomate Sem Pele Italiano San Frediano 2,5Kg', 'Mercearia > Molhos e condimentos'),
        ],
    },
    'batata': {
        "entram": [
            ('Batata Bolinha Recanto da Lua 500g', 'Hortifrúti > Legumes'),
            ('Batata Doce Orgânico do Chico 500g', 'Hortifrúti > Legumes'),
            ('Batata Inglesa Bolinha Pacote 1 Kg', 'Hortifrúti > Legumes'),
            ('Batata Inglesa Vermelha Asterix 1Kg', 'Hortifrúti > Legumes'),
            ('Batata Doce Quilo', 'Hortifrúti > Legumes e vegetais > Batata'),
        ],
        "saem": [
            ('BATATA CONG B-BRASIL 700G AIR FRYER', 'Categorizar'),
            ('Batata Pré-Frita Bem Brasil Congelada Corte Fino 1,5kg', 'Frios e congelados > Legumes e vegetais > Batata congelada'),
            ('Batata Frita Ondulada Ruffles Churrasco 33g', 'Mercearia > Chips e batatas palha'),
            ('Batata Ruffles Original Tubo 100g', 'Mercearia > Chips e batatas palha'),
            ("Batata Italiana Alfredo's Truffle  Salt Sem Glúten 100g", 'Mercearia > Salgadinho e Batata Palha'),
        ],
    },
    'cebola': {
        "entram": [
            ('Cebola Orgânico do Chico 400g', 'Hortifrúti > Legumes'),
            ('Cebola R-lua Mini 300g', 'Hortifrúti > Legumes'),
            ('Cebola Roxa 500g', 'Hortifrúti > Legumes'),
            ('CEBOLA ROXA ORG 400G', 'Hortifrúti > Legumes'),
            ('CEBOLA ROXA REDINHA ALIMENT+350G', 'Hortifrúti > Legumes'),
        ],
        "saem": [
            ('Cebola Triturada Daí Alimentos Pote 200 g', 'Categorizar'),
            ('Cebolinha Maço', 'Hortifrúti > Verduras e hortaliças > Verdura'),
            ('Cebola, Alho e Salsa Kitano Pouch 40g', 'Mercearia > Temperos e especiarias'),
            ('Cebola em Flocos Super Nosso 160g', 'Visualizar Mais Produtos'),
            ('Cebola Granulada Kitano Pouch 50g Embalagem Econômica', 'Visualizar Mais Produtos'),
        ],
    },
    'cenoura': {
        "entram": [
            ('Cenoura Baroa Eleve Bandeja 500g', 'Hortifrúti > Legumes'),
            ('CENOURA ORG CHICO 130G', 'Hortifrúti > Legumes'),
            ('Cenoura Orgânico do Chico 500g', 'Hortifrúti > Legumes'),
            ('Cenoura Vermelha Sn 1Kg', 'Hortifrúti > Legumes'),
            ('Cenoura Quilo', 'Hortifrúti > Legumes e vegetais > Legume e vegetal'),
        ],
        "saem": [
            ('Cenoura Processada Recanto da Lua 300g', 'Hortifrúti > Legumes'),
            ('CENOURA RALADA 130G', 'Hortifrúti > Legumes'),
            ('CENOURA  HIGIENIZADA PURO SER 100G', 'Hortifrúti > Verduras'),
            ('Cenoura Processada Ralada Eleve 150g', 'Hortifrúti > Verduras'),
        ],
    },
    'alho': {
        "entram": [
            ('Alho Roxo Cheiroso com Casca 200g', 'Hortifrúti > Legumes'),
            ('Alho Roxo Cheiroso com Casca 500g', 'Hortifrúti > Legumes'),
            ('Alho Roxo Dai Alimentos Pacote 500 g', 'Hortifrúti > Legumes'),
            ('Alho Sn 1Kg', 'Hortifrúti > Legumes'),
            ('Alho a granel 10kg', 'Hortifrúti > Legumes e vegetais > Alho e cebola'),
        ],
        "saem": [
            ('Alho Frito Dai Alimentos Pote 80 g', 'Categorizar'),
            ('Alho Inteiro Grano Congelado 1,1kg', 'Frios e congelados > Legumes e vegetais > Legume e vegetal'),
            ('Alho Picado Garlic Foods 200g', 'Hortifrúti > Legumes e vegetais > Alho e cebola'),
            ('Alho Cheiroso Massa 500g', 'Visualizar Mais Produtos'),
            ('Alho Frito Ccheiroso 80g', 'Visualizar Mais Produtos'),
        ],
    },
    'pepino': {
        "entram": [
            ('Pepino Baby Snackpep 200g', 'Hortifrúti > Legumes'),
            ('Pepino Caipira Bandeja 500g', 'Hortifrúti > Legumes'),
            ('Pepino Comum Bandeja 500g', 'Hortifrúti > Legumes'),
            ('PEPINO JAP NECTAR 350G-BJ', 'Hortifrúti > Legumes'),
            ('PEPINO ORG 400G', 'Hortifrúti > Legumes'),
        ],
        "saem": [
            ('Pepino em Conserva Suave Hemmer Vidro Peso Líquido 550g Peso Drenado 300g', 'Mercearia > Enlatados e Conservas'),
            ('Pepinos em Conserva Agridoce Hemmer Vidro 440g', 'Mercearia > Enlatados e Conservas'),
        ],
    },
    'abobrinha': {
        "entram": [
            ('Abobrinha Italiana 500g', 'Hortifrúti > Legumes'),
            ('Abobrinha Italiana Orgânico do Chico 500g', 'Hortifrúti > Legumes'),
            ('Abóbora Italiana Quilo', 'Hortifrúti > Legumes e vegetais > Legume e vegetal'),
        ],
        "saem": [
            ('Abóbora Japonesa/Cabotiá Quilo', 'Hortifrúti > Legumes e vegetais > Legume e vegetal'),
            ('Abóbora Moranga Quilo', 'Hortifrúti > Legumes e vegetais > Legume e vegetal'),
        ],
    },
    'abóbora': {
        "entram": [
            ('Abobora Jacare 1Kg', 'Hortifrúti > Legumes'),
            ('Abóbora Japonesa Inteira 1Kg', 'Hortifrúti > Legumes'),
            ('Abóbora Japonesa Orgânico do Chico 500g', 'Hortifrúti > Legumes'),
            ('Abóbora Pump 500g', 'Hortifrúti > Legumes'),
            ('Abóbora Vermelha 1.5Kg', 'Hortifrúti > Legumes'),
        ],
        "saem": [
        ],
    },
    'chuchu': {
        "entram": [
            ('Chuchu 500g', 'Hortifrúti > Legumes'),
            ('Chuchu Orgânico do Chico 500g', 'Hortifrúti > Legumes'),
            ('Chuchu Quilo', 'Hortifrúti > Legumes e vegetais > Legume e vegetal'),
        ],
        "saem": [
        ],
    },
    'mandioca': {
        "entram": [
            ('Mandioca 1.5Kg', 'Hortifrúti > Legumes'),
            ('Mandioca-aipim Quilo', 'Hortifrúti > Legumes e vegetais > Legume e vegetal'),
        ],
        "saem": [
            ('Mandioca Congelada Sadia Veg&Tal Pacote 900g', 'Congelados e Resfriados > Vegetais'),
            ('Mandioca supreme Seara Nature 600g', 'Congelados e Resfriados > Vegetais'),
            ('Mandioca Aipim Cozida no Vapor Vapza Caixa 500g 2 Unidades de 250g Cada', 'Hortifrúti > Legumes'),
            ('MANDIOCA DESCASCADA ORGÂNICO DO CHICO BANDEJA 500 G', 'Hortifrúti > Legumes'),
            ('Mandioca Processada a Vácuo 700g', 'Hortifrúti > Legumes'),
        ],
    },
    'beterraba': {
        "entram": [
            ('Beterraba  Sn 500g', 'Hortifrúti > Legumes'),
            ('BETERRABA ORG CHICO 150G', 'Hortifrúti > Legumes'),
            ('Beterraba Orgânico do Chico 500g', 'Hortifrúti > Legumes'),
            ('Beterraba Quilo', 'Hortifrúti > Legumes e vegetais > Legume e vegetal'),
        ],
        "saem": [
        ],
    },
    'pimentão': {
        "entram": [
            ('PIMENTAO COLORIDO NECTAR 400G', 'Hortifrúti > Legumes'),
            ('Pimentão Amarelo 300g', 'Hortifrúti > Legumes'),
            ('Pimentão Colorido Orgânico 400g Cio Da Terra', 'Hortifrúti > Legumes'),
            ('Pimentão Verde 250g', 'Hortifrúti > Legumes'),
            ('Pimentão Vermelho 300g', 'Hortifrúti > Legumes'),
        ],
        "saem": [
        ],
    },
    'repolho': {
        "entram": [
            ('Repolho Comum 1Kg', 'Hortifrúti > Legumes'),
            ('REPOLHO MISTO 200G', 'Hortifrúti > Legumes'),
            ('Repolho Roxo 800g', 'Hortifrúti > Legumes'),
            ('Repolho Verde Orgânico do Chico Unidade', 'Hortifrúti > Verduras'),
            ('Repolho Branco Quilo', 'Hortifrúti > Verduras e hortaliças > Verdura'),
        ],
        "saem": [
        ],
    },
    'brócolis': {
        "entram": [
            ('BROCOLIS NINJA NECTAR 200G', 'Hortifrúti > Verduras'),
            ('BROCOLIS ORG CHICO 400G', 'Hortifrúti > Verduras'),
        ],
        "saem": [
            ('BROCOLIS SADIA VEG&TAL 300G-PC CONG', 'Congelados e Resfriados > Vegetais'),
            ('Brócolis Daucy Congelado Pacote 300 g', 'Congelados e Resfriados > Vegetais'),
            ('Brócolis florete congelado Seara Nature 300g', 'Congelados e Resfriados > Vegetais'),
            ('Brócolis Congelado Fresco Sadia Veg&Tal Pacote 1,05kg', 'Congelados e resfriados > Vegetais'),
            ('Brócolis Grano Congelado 1kg', 'Frios e congelados > Legumes e vegetais > Legume e vegetal'),
        ],
    },
    'alface': {
        "entram": [
            ('Alface americada terefolhas', 'Hortifrúti > Verduras'),
            ('Alface Americana Todo Verde Un', 'Hortifrúti > Verduras'),
            ('Alface Crespa Hidropônica Todo Verde Unidade', 'Hortifrúti > Verduras'),
            ('Alface Crespa Unidade', 'Hortifrúti > Verduras'),
            ('Alface Hidropônica Mimosa Todo Verde Unidade', 'Hortifrúti > Verduras'),
        ],
        "saem": [
        ],
    },
    'couve': {
        "entram": [
            ('Couve Baby Hidropônica Todo Verde Unidade', 'Hortifrúti > Verduras'),
            ('COUVE ELEVE 200G', 'Hortifrúti > Verduras'),
            ('Couve Hidroponico Recanto Lua Un', 'Hortifrúti > Verduras'),
            ('Couve Unidade', 'Hortifrúti > Verduras'),
            ('Couve Manteiga Maço', 'Hortifrúti > Verduras e hortaliças > Verdura'),
        ],
        "saem": [
            ('COUVE FLOR SADIA 300G-PC CONG', 'Congelados e Resfriados > Vegetais'),
            ('COUVE FLOR FLORETE 250G', 'Hortifrúti > Verduras'),
            ('Couve Manteiga Processada 150g Recanto Da Lua', 'Hortifrúti > Verduras'),
            ('COUVE PICADA 200G', 'Hortifrúti > Verduras'),
            ('Couve Flor Unidade', 'Visualizar Mais Produtos'),
        ],
    },
    'couve-flor': {
        "entram": [
            ('Couve Flor Unidade', 'Visualizar Mais Produtos'),
            ('Couve-Flor 300g', 'Visualizar Mais Produtos'),
        ],
        "saem": [
        ],
    },
}

# Nomes inventados (ou, nos de couve-flor e abóbora, reais) para os termos que o bruto de 17/11 não cobria. Todos têm de SAIR.
# Nomes REAIS do robô do Super ABC (18/11/2026, CEP de Betim). O robô não traz categoria: só o nome separa o fresco do resto.
# Entram (termo -> nomes) e saem (termo -> nomes). Produtos com peso aproximado no nome ("400 G (1 A 2 Unidades)") entram: é como o ABC vende.
SUPER_ABC = {
    "entram": {
        "banana": ["Banana Caturra 1,2 Kg (5 A 6 Unidades)", "Banana Prata 1,2 Kg (5 A 6 Unidades))"],
        "maçã": ["Maçã Gala 150/165 300g (1 A 2 Unidades)", "Maca Pink Lady Kg"],
        "laranja": ["Laranja Pera Rio 400 G (1 A 2 Unidades)"],
        "limão": ["Limão Tahiti 400 G (3 A 4 Unidades)"],
        "mamão": ["Mamão Havai 700 G", "Mamão Formosa 1.5 Kg"],
        "melancia": ["Melancia Inteira 10 Kg (1 Unidade)", "Melancia Baby Amarela Inteira 3 Kg"],
        "abacaxi": ["Abacaxi Und"],
        "manga": ["Manga Palmer 600 G (1 A 2 Unidades)", "Manga Tommy 900 G (1 A 2 Unidades)"],
        "uva": ["Uva Vitória 500 G", "Uva Thompson 500 G"],
        "abacate": ["Abacate 1kg ( 1 A 2 Unidades )"],
        "tomate": ["Tomate Longa Vida 500 G (1 A 2 Unidades)", "Tomate Grape Bandeja", "Tomate Italiano 600 G (3 A 4 Unidades)"],
        "batata": ["Batata Doce 800 G (1 A 2 Unidades)", "Batata Doce Roxa 800 G (1 A 2 Unidades)", "Batata 400 G (1 A 2 Unidades)"],
        "cebola": ["Cebola Roxa 400 G (1 A 2 Unidades)", "Cebola Branca 400 G (1 A 2 Unidades)"],
        "cenoura": ["Cenoura Vermelha 2a 300 G (1 A 2 Unidades)", "Cenoura Branca Bandeja"],
        "alho": ["Alho Granel Número 4 300g (1 A 2 Unidades)", "Alho Premium Abc 350g Embalagem"],
        "pepino": ["Pepino Japonês 350g (1 A 2 Unidades)", "Pepino Caipira Unidade 300g"],
        "abóbora": ["Abóbora Híbrida 2.5 Kg (1 Unidade)", "Abóbora Menina 500g"],
        "chuchu": ["Chuchu 400 G (1 A 2 Unidades)"],
        "beterraba": ["Beterraba Unidade 300 G (1 A 2 Unidades)"],
        "pimentão": ["Pimentão Verde 500 G (1 A 2 Unidades)", "Pimentão Misto 600 G (1 A 2 Unidades)"],
        "repolho": ["Repolho Verde Inteiro", "Repolho Roxo Embalagem 550g"],
        "brócolis": ["Brócolis Ninja Bandeja", "Brócolis Und", "Brocólis Ninja Edl Bandeja"],
        "alface": ["Alface Und", "Alface Americana Unidade", "Alface Roxa Und"],
        "couve": ["Couve Unidade"],
        "couve-flor": ["Couve Flor 300 G"],
    },
    "saem": {
        "maçã": ["Maca Peito Bovina Peça/Pedaço 500g", "Maca Peito Bovina Peça Principal 500g"],                 # corte de carne, não fruta
        "tomate": ["Tomate Pelado La Pastina Lata 240g", "Tomate Pelado Inteiro Sacciali Lata 1,5kg", "Tomate Pelado Sacciali Lata 240g"],   # conserva
        "batata": ["Batata Ondulada Bem Brasil 2kg Pct"],                                                          # congelada
    },
}

ADAPTADOS = {
    'abóbora': [
        ('Abóbora Italiana Quilo', 'Hortifrúti > Legumes e vegetais > Legume e vegetal'),
    ],
    'melancia': [
        ('Melancia Fatiada Processada 500g', 'Hortifrúti > Frutas'),
    ],
    'chuchu': [
        ('Chuchu em Conserva 400g', 'Mercearia > Enlatados e Conservas'),
    ],
    'beterraba': [
        ('Beterraba Ralada Processada 150g', 'Hortifrúti > Legumes'),
    ],
    'pimentão': [
        ('Pimentão em Conserva Hemmer 300g', 'Mercearia > Enlatados e Conservas'),
    ],
    'repolho': [
        ('Repolho Picado Higienizado 200g', 'Hortifrúti > Verduras'),
    ],
    'alface': [
        ('Alface Americana Higienizada Picada 150g', 'Hortifrúti > Verduras'),
    ],
    'limão': [
        ('Limão Taiti Suco Concentrado 500ml', 'Mercearia > Sucos'),
    ],
    'couve-flor': [
        ('Couve Flor Sadia 300g Cong', 'Congelados e Resfriados > Vegetais'),
        ('Mix Couve Flor Nectar 320g', 'Visualizar Mais Produtos'),
    ],
}
