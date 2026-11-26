"""Casos do filtro de dados/lista_carnes_e_frios.json, com nomes e categorias REAIS dos mercados (coletados em 26/11/2026).

`entram`: o corte ou queijo, a peso ou embalado, comum, premium ou congelado (a separação em faixas é da chave de equivalência, não da lista). `saem`: a mesma peça de porco,
carne de sol, hambúrguer, salgadinho, limpador "Mr Músculo" ou outro produto que só tem o nome parecido. Cada item é (nome, categoria).
O Super ABC não traz categoria: os casos dele (SUPER_ABC) são só o nome. Os nomes vêm dos mercados; o que entra e o que sai foi conferido à mão.
"""
CASOS = {
    "patinho": {
        "entram": [
            ("Patinho Moído Supernosso 450g", "Aves, Carnes e Peixes > Carne Bovina"),
            ("Patinho Bovino Porcionado Resfriado 1.3Kg", "Aves, Carnes e Peixes > Carne Bovina"),
        ],
        "saem": [
            ("Carne Suína Patinho Sadia Cong C/ osso Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne suína"),
        ],
    },
    "acém": {
        "entram": [
            ("Carne Bovina Acém Porc Friboi Resf Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
            ("Carne Bovina Acém Plena Resfriada Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
            ("Acém Porcionado Resfriado 1.3Kg", "Aves, Carnes e Peixes > Carne Bovina"),
        ],
        "saem": [
        ],
    },
    "coxão mole": {
        "entram": [
            ("Carne Bov Coxão Mole Friboi Porcionada Resf Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
        ],
        "saem": [
            ("Carne Suína Coxão Mole Sadia Cong Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne suína"),
            ("Carne de Sol Bov Coxão Mole Plena Resf Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
        ],
    },
    "músculo": {
        "entram": [
            ("Musculo Porcionado A Resfriado 1.4Kg", "Açougue > Carne Bovina"),
            ("Músculo Porcionado Resfriado Peça 1Kg", "Açougue > Carne Bovina"),
            ("Músculo Bovino Angus Moído Supernosso 450g", "Aves, Carnes e Peixes > Carne Bovina"),
            ("Músculo Bovino Angus Super Nosso Em Cubos Resfriado 600g", "Aves, Carnes e Peixes > Carne Bovina"),
        ],
        "saem": [
            ("LIMP MR MUSCULO 400ML", "Produtos de Limpeza > Para Cozinha"),
            ("Desengordurante Mr Músculo Cozinha Laranja 500ml 20% de Desconto", "Produtos de Limpeza > Para Cozinha"),
            ("Limpador Mr Músculo Banheiro Total Refil 400ml Oferta Especial", "Produtos de Limpeza > Para Banheiro"),
            ("Desengordurante Mr Músculo Cozinha Refil Laranja 400ml Menor Preço", "Produtos de Limpeza > Para Cozinha"),
            ("Limpador Mr Músculo Banheiro Tira Limo Aparelho 500ml 30% de Desconto", "Produtos de Limpeza > Para Banheiro"),
            ("Limpador Mr Músculo Banheiro Tira Limo Aparelho 500ml Oferta Especial", "Limpeza > Limpeza de banheiro > Desinfetante sanitário"),
        ],
    },
    "alcatra": {
        "entram": [
            ("Miolo Alcatra Maturatta Churrasco Especial 1.7Kg", "Aves, Carnes e Peixes > Carne Bovina"),
            ("Bombom Da Alcatra Angus Super Nosso Resfriado 900g", "Aves, Carnes e Peixes > Carne Bovina"),
        ],
        "saem": [
            ("Alcatra Suína Temperada Supernosso 1Kg", "Aves, Carnes e Peixes > Carne Suína"),
            ("Alcatra Suína Premiada Temperada Resfriada 1Kg", "Aves, Carnes e Peixes > Carne Suína"),
        ],
    },
    "fraldinha": {
        "entram": [
            ("Fraldinha Peca 1Kg", "Açougue > Carne Bovina"),
            ("Carne Bovina Fraldinha Friboi Resf Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
            ("Carne Bovina Fraldinha Plena Resf Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
            ("Fraldinha Bassi Limpa Resfriada 1Kg", "Aves, Carnes e Peixes > Carne Bovina"),
            ("Fraldinha Plena Chef Peça 1.2Kg", "Aves, Carnes e Peixes > Carne Bovina"),
        ],
        "saem": [
            ("Hambúrguer Bovino Maturatta Congelado Fraldinha 180g", "Frios e congelados > Hambúrgueres > Hambúrguer bovino"),
        ],
    },
    "picanha": {
        "entram": [
            ("Picanha Fatiada 1Kg", "Açougue > Carne Bovina"),
            ("Picanha Tradicional 1.4Kg", "Açougue > Carne Bovina"),
            ("Carne Bovina Picanha Maturatta Resf Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
            ("Carne Bovina Picanha Bordon Resf Fat Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
            ("Picanha Montana 1.5Kg", "Aves, Carnes e Peixes > Carne Bovina"),
            ("Picanha Bassi Resfriada 1.4Kg", "Aves, Carnes e Peixes > Carne Bovina"),
        ],
        "saem": [
            ("Salgadinho Pingo Douro Picanha 120g", "Mercearia > Chips e batatas palha"),
            ("Hot Hit picanha Seara 145g", "Congelados e resfriados > Lanches e massas congelados"),
            ("Picanha Suína Cozinha Premiada Temperada 1Kg", "Açougue > Carne Suína"),
            ("Hot Pocket X-Picanha Sadia 145g", "Congelados e resfriados > Lanches e massas congelados"),
            ("Batata Frita Lisa Lays Picanha 62g", "Mercearia > Chips e batatas palha"),
            ("Caldo em Pó Picanha na Brasa Sazón Caixa 32,5g", "Mercearia > Temperos e especiarias"),
        ],
    },
    "contra filé": {
        "entram": [
            ("Contra File Resf 1Kg", "Açougue > Carne Bovina"),
            ("Contra Filé Noix Peça 1.4Kg", "Açougue > Carne Bovina"),
            ("Contra Filé Bov Maturatta Resf Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
            ("Contra Filé Bov Friboi Porc Resf Preço por quilo na peça", "Carnes, aves e peixes > Carnes > Carne bovina"),
            ("Contra Filé Bovino Carapreta Congelado 1Kg", "Aves, Carnes e Peixes > Carne Bovina"),
            ("Contrafilé Reserva Bife 600g", "Aves, Carnes e Peixes > Carne Bovina"),
        ],
        "saem": [
        ],
    },
    "queijo minas": {
        "entram": [
            ("QUEIJO MINAS PAD ITAMBE 150G FAT", "Visualizar Mais Produtos"),
            ("Queijo Supernosso Minas Padrão 1Kg", "Frios e Laticínios > Queijos"),
            ("Queijo Minas Padrão Serro 500g", "Frios e Laticínios > Queijos"),
            ("Queijo Minas Padrão Cristaulat 450g", "Frios e Laticínios > Queijos"),
            ("Queijo Minas Padrão Itambé Fatiado 150g", "Frios e congelados > Queijos > Queijo minas frescal e padrão"),
            ("Queijo Minas Frescal Porto Alegre Preço por quilo na peça", "Frios e congelados > Queijos > Queijo minas frescal e padrão"),
            ("Queijo Minas Artesanal Serro 700g", "Frios e Laticínios > Queijos"),
            ("Queijo Minas Curado Barão Canastra 1Kg", "Frios e Laticínios > Queijos"),
        ],
        "saem": [
            ("Pão de Queijo Congelado Forno de Minas Pacote 1000g", "Congelados e resfriados > Lanches e massas congelados"),
            ("Pão de Queijo Congelado Tradicional Mania de Minas Pacote 800g", "Congelados e resfriados > Lanches e massas congelados"),
            ("Pão de Queijo Congelado Lanche Forno de Minas Pacote 1kg", "Congelados e resfriados > Lanches e massas congelados"),
            ("Pão de Queijo Congelado Tradicional Forno de Minas Pacote 1kg", "Congelados e resfriados > Lanches e massas congelados"),
            ("Chipa de Queijo Congelada Food Service Forno de Minas Profissional Pacote 1kg", "Congelados e resfriados > Lanches e massas congelados"),
            ("Creme de Queijo Minas Frescal Porto Alegre 200g", "Frios e Laticínios > Queijos"),
        ],
    },
    "queijo parmesão": {
        "entram": [
            ("Queijo Parmesão Président 180g", "Frios e Laticínios > Queijos"),
            ("Queijo Parmesão Cilindro Président 180g", "Frios e Laticínios > Queijos"),
            ("Queijo Parmesão Président Cilindro 180g", "Frios e congelados > Queijos > Queijo especial"),
            ("Queijo Parmesão Galbani 180g", "Frios e congelados > Queijos > Queijo especial"),
            ("Queijo Parmesão Nacon Arg 1Kg", "Frios e Laticínios > Queijos"),
            ("Queijo Parmesão Faixa Azul 150g", "Frios e Laticínios > Queijos"),
        ],
        "saem": [
            ("Queijo Parmesão Vegano de Castanha de Caju Vida Veg 150g", "Frios e Laticínios > Queijos"),
            ("Queijo Parmesão Ralado Itambé Pacote 50g", "Frios e Laticínios > Queijos"),
            ("Queijo Parmesão Ralado Président Pacote 50g", "Frios e Laticínios > Queijos"),
            ("Queijo Parmesão Ralado Vigor Pacote 50g", "Frios e Laticínios > Queijos"),
            ("Fettuccine Ao Molho Bolonhesa Com Queijo Parmesão Ralado Perdigão Meu Menu Pacote 300G", "Padaria e Rotisseria > Rotisseria"),
            ("Molho para Salada Caesar com Cebola, Alho e Especiarias Queijo Parmesão Hellmann's Squeeze 210ml", "Mercearia > Temperos e especiarias"),
            ("Estouradinho de Queijo Parmesão e Chia 120g", "Padaria > Confeitaria > Biscoitos"),
        ],
    },
}

SUPER_ABC = {
    "entram": {
        "patinho": [
            "Carne Bovina Patinho Embalagem 500g",
            "Carne Bovina Patinho Moída 500g",
            "Carne Bovina Patinho Bandeja 500g",
        ],
        "acém": [
            "Carne Bovina Acém Peça Porcionado 1,2kg",
            "Carne Bovina Miolo Acém Kg",
        ],
        "coxão mole": [
        ],
        "músculo": [
            "Carne Bovina Músculo Peça/pedaço 500g",
            "Carne Bovina Músculo Embalagem 500g",
        ],
        "alcatra": [
            "Carne Bovina Alcatra Bombom 500g",
            "Carne Bovina Coração De Alcatra Matturat 1,5kg",
            "Carne Bovina Alcatra Bandeja 500g",
            "Carne Bovina Alcatra Strogonoff 500g",
        ],
        "fraldinha": [
            "Carne Bovina Fraldinha Friboi Maturada 1,6kg",
            "Carne Bovina Fraldinha Embalagem 1,4kg",
        ],
        "picanha": [
            "Picanha Friboi Maturatta Embalada 1,6kg",
            "Carne Bovina Picanha Peça Principal 1,500 Kg",
            "Carne Bovina Picanha Pedaço 500g",
            "Carne Bovina Picanha Resfriada Bordon 1,6kg",
        ],
        "contra filé": [
            "Carne Bovina Contra Filé Maturatta Embalada 1,6kg",
            "Carne Bovina Contra Filé 500g",
            "Carne Bovina Contra Filé Strogn 500g",
            "Carne Bovina Contra Filé Porcionado 500g",
        ],
        "queijo minas": [
            "Queijo Minas Artesanal Barão 500g",
            "Queijo Minas Artesanal Mineirinho 800 G",
            "Queijo Minas Padrao President 150g Fat",
            "Queijo Minas Padrao Itambe 150g Fat",
        ],
        "queijo parmesão": [
            "Queijo Parmesão President Cilindro 180g",
            "Queijo Parmesao President Frac 180g",
        ],
    },
    "saem": {
        "patinho": [
            "Patinho Suíno Esp Bj Embalagem 400g",
            "Carne Patinho Suíno 500g Em Bandeja Especial",
        ],
        "acém": [
        ],
        "coxão mole": [
        ],
        "músculo": [
            "Limpador Mr Músculo Cozinha Limão Refil 400ml",
            "Desengordurante Mr Músculo Cozinha Refil Laranja 400ml Oferta Especial",
            "Limpador Mr. Músculo Banheiro Total Refil 400ml Oferta Especial",
            "Desengordurante Mr músculo Cozinha Limão 500 Ml Com 30% De Desconto",
            "Desengordurante Mr músculo Cozinha Laranja 500 Ml Com 30% De Desconto",
        ],
        "alcatra": [
            "Alcatra Suína Esp Bj Embalagem 400g",
            "Alcatra Suína Embalagem 400g",
            "Carne Alcatra Suína Em Bandeja Pururuca 500g",
            "Carne Alcatra Suína Em Bandeja Especial 500g",
            "Maminha Alcatra Bovina Embalagem 1,5kg",
        ],
        "fraldinha": [
            "Hambúguer Bovino Sabor Fraldinha Maturatta Friboi 180g",
            "Carne Suina Fraldinha Suinco Kg Temp",
        ],
        "picanha": [
            "Picanha Suína A Pururuca Embalagem 400g",
            "Picanha Suína Espanhol Bandeja Embalagem 400g",
            "Picanha Suína Embalagem 400g",
            "Hot Pocket X Picanha 145g",
            "Hambúrguer Bovino Nabraska Perdigão 150g Com Picanha",
        ],
        "contra filé": [
            "Carne Bovina Capa Contra File Embalagem 1kg",
        ],
        "queijo minas": [
            "Pão De Queijo Forno Minas Coquetel 1kg",
            "Pão De Queijo Forno De Minas 1kg Edição 30 Anos",
        ],
        "queijo parmesão": [
            "Queijo Parmesão Ral Vigor 50g",
            "Queijo Parmesão Itambé Ralado 50g",
            "Queijo Parmesão Ral Barao 40g",
            "Queijo Parmesão Vale Da Canastra 40g Ralado",
        ],
    },
}
