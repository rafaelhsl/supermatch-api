"""Testes da equivalência dos cortes de carne e queijos a peso (família "cortes de carne e queijos a peso" de equivalencia.py), sem rede e sem banco.

Rodar com:  python tests/test_equivalencia_carnes.py

Como o hortifrúti, esta família olha também a UNIDADE que o banco guarda ("kg": o preço é por quilo, qualquer que seja o peso do nome, que é o da porção;
"un": por pacote). Por isso cada nome vem com a unidade: (nome, unidade). Os nomes são REAIS, da coleta de 26/11/2026 (Apoio, Atacadão, Supernosso e Super ABC);
os poucos que não existiam naquele dia, e foram escritos para exercitar uma regra, estão marcados "adaptado".

O que esta família garante (decisão do dono, 26/11/2026): premium e congelado NUNCA se juntam com o comum e o fresco; o preço por quilo vale "1 kg".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import equivalencia as eq  # noqa: E402

ok, erros = 0, []
KG, UN = "kg", "un"


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
    confere(chave(item) is None, f"deveria ficar sem chave: {item} -> {chave(item)}")


# ============================== o preço por quilo vale 1 kg, e o peso do nome (o da porção) não conta ==============================
juntam(("Picanha Tradicional 1.4Kg", KG), ("Carne Bovina Picanha Friboi Resf Preço por quilo na peça", KG), ("Picanha A Resfriada 1.4Kg", KG),
       ("Carne Bovina Picanha Peça Principal 1,500 Kg", KG), ("Picanha Plena Chef Tradicional 1.4Kg", KG))
juntam(("Picanha Fatiada 1Kg", KG), ("Carne Bovina Picanha Bordon Resf Fat Preço por quilo na peça", KG), ("Picanha Fatiada 1.3Kg", KG),
       ("Carne Bovina Picanha Fatiada Embalada 0,8g", KG))
juntam(("Contra File Resf 1Kg", KG), ("Contra Filé Noix Peça 1.4Kg", KG), ("Contra Filé Bov Friboi Porc Resf Preço por quilo na peça", KG),
       ("Contra Filé Plena Chef Peça 1.4Kg", KG), ("Carne Bovina Contra Filé Peça 4 Kg", KG))            # sem a forma no nome, 1 kg ou mais de corte é a peça
juntam(("Músculo Porcionado Resfriado Peça 1Kg", KG), ("Carne Bov Músculo Friboi Porcionada Resf Preço por quilo na peça", KG), ("Carne Bovina Músculo Peça/pedaço 500g", KG),
       ("Musculo Porcionado A Resfriado 1.4Kg", KG))
juntam(("Acém Porcionado Resfriado 1.3Kg", KG), ("Carne Bovina Acém Plena Resfriada Preço por quilo na peça", KG), ("Carne Bovina Acém Peça Porcionado 1,2kg", KG))
juntam(("Fraldinha Peca 1Kg", KG), ("Carne Bovina Fraldinha Friboi Resf Preço por quilo na peça", KG), ("Fraldinha Plena Chef Peça 1.2Kg", KG), ("Carne Bovina Fraldinha Embalagem 1,4kg", KG))
confere(eq.equivalencia("Picanha Tradicional 1.4Kg", unidade=KG).chave.endswith("|1000g"), "o preço por quilo vale 1000 g")
confere(eq.equivalencia("Picanha Tradicional 1.4Kg", unidade=KG).rotulo == "Picanha em peça, 1 kg", f"rótulo: {eq.equivalencia('Picanha Tradicional 1.4Kg', unidade=KG).rotulo}")

# ============================== premium nunca se junta com o comum ==============================
juntam(("Picanha Bassi Resfriada 1.4Kg", KG), ("Picanha Friboi Maturatta Embalada 1,6kg", KG), ("Carne Bovina Picanha Maturatta Resf Preço por quilo na peça", KG),
       ("Picanha Maturatta Resfriado Peça 1.6Kg", KG))
separam(("Picanha Bassi Resfriada 1.4Kg", KG), ("Picanha A Resfriada 1.4Kg", KG))
separam(("Carne Bovina Picanha Maturatta Resf Preço por quilo na peça", KG), ("Carne Bovina Picanha Friboi Resf Preço por quilo na peça", KG))
separam(("Contrafilé Reserva Bife 600g", KG), ("Carne Bovina Contra Filé Bife 500g", KG))                          # reserva é a linha premium do mercado
separam(("Fraldinha Friboi Maturada Resfriada 1.2Kg", KG), ("Carne Bovina Fraldinha Friboi Resf Preço por quilo na peça", KG))
separam(("Bombom Da Alcatra Angus Super Nosso Resfriado 900g", KG), ("Bombom De Alcatra Bonne 1Kg", KG))        # Angus é premium; o outro não diz nada
separam(("Músculo Bovino Angus Super Nosso Em Cubos Resfriado 600g", KG), ("Músculo Porcionado Resfriado Peça 1Kg", KG))
separam(("Queijo Minas Artesanal Serro 700g", KG), ("Queijo Minas Padrão Serro 700g", KG))                       # artesanal conta

# ============================== congelado nunca se junta com o fresco ==============================
separam(("Picanha Angus Cong 1Kg", KG), ("Picanha Bovina A.R.G Congela 1Kg", KG))                              # os dois congelados, só um premium
separam(("Picanha Bovina A.R.G Congela 1Kg", KG), ("Picanha Tradicional 1.4Kg", KG))
separam(("Contra Filé Bovino Carapreta Congelado 1Kg", KG), ("Contra File Resf 1Kg", KG))
juntam(("Picanha Bovina A.R.G Congela 1Kg", KG), ("Picanha Congelada Importada 1Kg", KG))                       # adaptado: outro nome do mesmo estado
confere(eq.equivalencia("Picanha Bovina A.R.G Congela 1Kg", unidade=KG).rotulo == "Picanha em peça congelada, 1 kg", f"rótulo do congelado: {eq.equivalencia('Picanha Bovina A.R.G Congela 1Kg', unidade=KG).rotulo}")
confere(eq.equivalencia("Contra Filé Bovino Carapreta Congelado 1Kg", unidade=KG).rotulo == "Contra filé em peça congelado premium, 1 kg", "rótulo do premium congelado")

# ============================== o tempero e a forma ==============================
separam(("Contra Filé Temperado Resfriado 1Kg", KG), ("Contra File Resf 1Kg", KG))                              # adaptado: nenhum corte bovino temperado existia na coleta
juntam(("Contra Filé Temperado Resfriado 1Kg", KG), ("Contra Filé Temperado Peça 1.4Kg", KG))                   # adaptado

# ============================== a forma muda o preço do quilo ==============================
separam(("Picanha Fatiada 1Kg", KG), ("Picanha Tradicional 1.4Kg", KG))
separam(("Contra Filé Bife Especial 500g", KG), ("Carne Bovina Contra Filé Peça 4 Kg", KG))
separam(("Carne Bovina Contra Filé Strogn 500g", KG), ("Carne Bovina Contra Filé Bife 500g", KG))
separam(("Carne Bovina Patinho Moída 500g", KG), ("Patinho Bovino Porcionado Resfriado 1.3Kg", KG))
separam(("Steak Picanha Super Nosso Resfriada 900g", KG), ("Picanha A Resfriada 1.4Kg", KG))
juntam(("Carne Bovina Contra Filé Bife 500g", KG), ("Contra Filé Bife Pedaço 600g", KG))                        # adaptado: o 2º, de outro peso de porção, mas por quilo
juntam(("Carne Bovina Alcatra Bife 500g", KG), ("Alcatra Bife 1Kg", KG))                                       # adaptado: idem

# ============================== o corte e as partes dele ==============================
separam(("Carne Bovina Alcatra Peça 500g", KG), ("Carne Bovina Fraldinha Embalagem 1,4kg", KG))
separam(("Bombom Da Alcatra Angus Super Nosso Resfriado 900g", KG), ("Miolo Alcatra Maturatta Churrasco Especial 1.7Kg", KG))
separam(("Carne Bovina Alcatra Bombom 500g", KG), ("Carne Bovina Alcatra Peça 500g", KG))                       # o bombom é uma parte da alcatra
separam(("Carne Bovina Miolo Acém Kg", KG), ("Carne Bovina Acém Peça Porcionado 1,2kg", KG))

# ============================== o embalado de peso fixo vale o peso do nome ==============================
juntam(("Patinho Moído Supernosso 450g", UN), ("Carne Bovina Patinho Moída 450g", UN))                          # adaptado: o 2º, embalado
separam(("Patinho Moído Supernosso 450g", UN), ("Patinho Moído Supernosso 500g", UN))                           # adaptado: outro peso
separam(("Patinho Moído Supernosso 450g", UN), ("Carne Bovina Patinho Moída 500g", KG))                         # embalado e por quilo não se juntam (o preço de um é do pacote, do outro do quilo)
confere(eq.equivalencia("Patinho Moído Supernosso 450g", unidade=UN).rotulo == "Patinho moído, 450 g", "rótulo do embalado")
juntam(("Queijo Minas Padrão Itambé Fatiado 150g", UN), ("QUEIJO MINAS PADRÃO FATIADO 150G", UN), ("Queijo Minas Padrao President 150g Fat", UN))
juntam(("Queijo Parmesão Galbani 180g", UN), ("Queijo Parmesão Président Cilindro 180g", UN), ("Queijo Parmesão Fracionado Itambé 180g", UN), ("QUEIJO PARMESÃO VIGOR CILINDRO 180G", UN))
separam(("Queijo Parmesão Président 180g", UN), ("Queijo Parmesão Cilindro Faixa Azul 195g", UN))                 # pesos diferentes
separam(("Queijo Parmesão Fatiado Vigor 200g", UN), ("Queijo Parmesão Président 180g", UN))                      # adaptado: peso e forma
separam(("Queijo Parmesão Président 180g", UN), ("Queijo Parmesão Cristaulat Fração 1Kg", KG))

# ============================== queijo minas: o tipo (frescal, padrão, meia cura, curado) e o que o nome diz de especial ==============================
juntam(("Queijo Minas Frescal Cambuiense 1Kg", KG), ("Queijo Minas Frescal Porto Alegre Preço por quilo na peça", KG), ("Queijo Minas Frescal Porto Alegre Pedaço 500g", KG),
       ("Queijo Minas Frescal Muai A 1Kg", KG))
juntam(("Queijo Minas Padrão Verde Campo 1Kg", KG), ("Queijo Minas Padrão Cristaulat 450g", KG), ("Queijo Minas Padrão Porto Alegre Preço por quilo na peça", KG),
       ("Queijo Supernosso Minas Padrão 1Kg", KG), ("Queijo Minas Pad A 1Kg", KG))
juntam(("Queijo Minas Paranaíba Meia Cura 1Kg", KG), ("Queijo Minas Porto Alegre Meia Cura Fração 500g", KG), ("Queijo Minas Puroleite Meia Cura 500g", KG))
fora(("Queijo Meia Cura Porto Alegre Preço por quilo na peça", KG))             # sem "Minas" no nome: não dá para garantir que é o queijo minas
separam(("Queijo Minas Frescal Cambuiense 1Kg", KG), ("Queijo Minas Padrão Cambuiense 1Kg", KG))
separam(("Queijo Minas Padrão Cambuiense 1Kg", KG), ("Queijo Minas Meia Cura Cambuiense 1Kg", KG))               # adaptado: a mesma marca em outra cura
separam(("Queijo Minas Padrão Porto Alegre 500g", KG), ("Queijo Minas Padrão Porto Alegre Zero Lactose Preço por quilo na peça", KG))
separam(("Queijo Minas Padrão Light Porto Alegre 500g", KG), ("Queijo Minas Padrão Porto Alegre 500g", KG))
separam(("Queijo Minas Padrão Bom Destino Fracao/Bufala 450g", KG), ("Queijo Minas Padrão Serro 700g", KG))       # búfala é outro queijo
separam(("Queijo Minas Frescal Búfala Bom Destino Preço por quilo na peça", KG), ("Queijo Minas Frescal Porto Alegre Pedaço 500g", KG))
separam(("Queijo Minas Meia Cura Paladar De Minas Mini Defumado 1Kg", KG), ("Queijo Minas Paranaíba Meia Cura 1Kg", KG))
separam(("Queijo Minas Calambau Ouro Paladar De Minas Meia Cura Com Açafrão 1Kg", KG), ("Queijo Minas Paranaíba Meia Cura 1Kg", KG))
separam(("Queijo Minas Padrão Itambé Fatiado 150g", UN), ("Queijo Minas Padrão Itambé Fatiado 300g", UN))        # adaptado: outro peso
separam(("Queijo Minas Padrão Fatiado Light 600g", KG), ("Queijo Minas Padrão Itambé Fatiado 150g", UN))          # adaptado: por quilo e embalado nunca se juntam
juntam(("Queijo Minas Frescal Cambuiense 1Kg", KG), ("Queijo Minas Frescal Porto Alegre 1Kg", UN))              # adaptado: o pacote de 1 kg é o preço do quilo

# ============================== os rótulos que a pessoa vê (cada dimensão aparece na palavra certa) ==============================
def rotulo(nome, unidade):
    r = eq.equivalencia(nome, unidade=unidade)
    return r.rotulo if r else None


ROTULOS = [
    (("Queijo Minas Frescal Cambuiense 1Kg", KG), "Queijo minas frescal, 1 kg"),
    (("Queijo Minas Padrão Verde Campo 1Kg", KG), "Queijo minas padrão, 1 kg"),
    (("Queijo Minas Paranaíba Meia Cura 1Kg", KG), "Queijo minas meia cura, 1 kg"),
    (("Queijo Minas Curado Barão Canastra 1Kg", KG), "Queijo minas curado, 1 kg"),
    (("Queijo Minas Artesanal Serro 700g", KG), "Queijo minas artesanal, 1 kg"),
    (("Queijo Minas Padrão Fracionado Light Verde Campo 600g", KG), "Queijo minas padrão light, 1 kg"),
    (("Queijo Minas Padrão Fracionado Zero Lactose Verde Campo Lacfree 500g", KG), "Queijo minas padrão zero lactose, 1 kg"),
    (("Queijo Minas Padrão Bom Destino Fracao/Bufala 450g", KG), "Queijo minas padrão de búfala, 1 kg"),
    (("Queijo Minas Paladar De Minas Meia Cura Mini Defumado 1Kg", KG), "Queijo minas meia cura defumado, 1 kg"),
    (("Queijo Minas Meia Cura Com Mel 1Kg", KG), "Queijo minas meia cura temperado, 1 kg"),                         # adaptado
    (("Queijo Minas Padrão Itambé Fatiado 150g", UN), "Queijo minas padrão fatiado, 150 g"),
    (("Queijo Parmesão Président 180g", UN), "Queijo parmesão, 180 g"),
    (("Queijo Parmesão Fatiado Vigor 180g", UN), "Queijo parmesão fatiado, 180 g"),                             # adaptado: o peso
    (("Queijo Parmesão Fracionado Maturado 12 Meses Tirolez 200g", UN), "Queijo parmesão maturado, 200 g"),
    (("Queijo Parmesão Nacon Arg 1Kg", KG), "Queijo parmesão importado, 1 kg"),
    (("Carne Bovina Contra Filé Strogn 500g", KG), "Contra filé em cubos, 1 kg"),
    (("Contrafilé Reserva Bife 600g", KG), "Contra filé em bifes premium, 1 kg"),
    (("Carne Bovina Alcatra Bombom 500g", KG), "Alcatra bombom, 1 kg"),
    (("Miolo De Alcatra Light Angus Super Nosso Em Bifes 1.2Kg", KG), "Alcatra miolo em bifes premium, 1 kg"),
    (("Carne Bovina Coração De Alcatra Matturat 1,5kg", KG), "Alcatra coração em peça, 1 kg"),
    (("Carne Bovina Miolo Acém Kg", KG), "Acém miolo, 1 kg"),
    (("Carne Bovina Patinho Moída 500g", KG), "Patinho moído, 1 kg"),
    (("Carne Bovina Picanha Bordon Resf Fat Preço por quilo na peça", KG), "Picanha fatiada, 1 kg"),
    (("Picanha Bovina A.R.G Congela 1Kg", KG), "Picanha em peça congelada, 1 kg"),
    (("Contra Filé Temperado Resfriado 500g", KG), "Contra filé temperado, 1 kg"),                                # adaptado
]
for item, esperado in ROTULOS:
    confere(rotulo(*item) == esperado, f"rótulo de {item[0]}: {rotulo(*item)!r} (esperado {esperado!r})")
separam(("Queijo Minas Padrão Itambé Fatiado 150g", UN), ("Queijo Minas Padrão Fracionado 150g", UN))              # adaptado: a forma, no mesmo peso
separam(("Queijo Parmesão Fatiado Vigor 180g", UN), ("Queijo Parmesão Président 180g", UN))                       # adaptado: idem
separam(("Queijo Parmesão Tirolez 200g", UN), ("Queijo Parmesão Fracionado Maturado 12 Meses Tirolez 200g", UN))    # adaptado: o maturado
separam(("Queijo Parmesão Nacon Arg 1Kg", KG), ("Queijo Parmesão Califórnia 1Kg", KG))                            # o importado
separam(("Queijo Minas Curado Barão Canastra 1Kg", KG), ("Queijo Minas Paranaíba Meia Cura 1Kg", KG))
separam(("Queijo Minas Padrão Verde Campo 1Kg", KG), ("Queijo Minas Padrão Verde Campo Meia Cura 1Kg", KG))        # adaptado
separam(("Bombom De Alcatra Bonne 1Kg", KG), ("Miolo De Alcatra Bonne 1Kg", KG))                                  # adaptado: as partes da alcatra

# ============================== o que fica sem chave ==============================
fora(("Alcatra Suína Embalagem 400g", KG))                                      # a mesma peça, de porco
fora(("Picanha Suína Cozinha Premiada Temperada 1Kg", KG))
confere((chave(("Queijo Parmesão Ralado Itambé Pacote 50g", UN)) or "").startswith("queijo_ralado|"), "o parmesão ralado é do queijo ralado, não desta família")
fora(("Queijo Parmesão Ral Vigor 50g", UN))
fora(("Queijo Parmesão Vegano de Castanha de Caju Vida Veg 150g", UN))
fora(("Patinho Moído Supernosso", UN))                                         # adaptado: sem peso e sem ser por quilo, não dá para comparar
fora(("Patinho Moído Supernosso 2 Unidades 450g", UN))                         # adaptado: multipacote
fora(("Carne Bovina Picanha Peça 2x500g", KG))                                 # adaptado: caixa
confere((chave(("Hambúrguer Bovino Maturatta Congelado Picanha 180g", UN)) or "").startswith("hamburguer|"), "o hambúrguer é do hambúrguer, não da picanha")
fora(("Desengordurante Mr Músculo Cozinha Laranja 500ml", UN))
fora(("Pão de Queijo Forno de Minas Pacote 1kg", UN))
fora(("Capa De Filé Bovino Peça 1Kg", KG))                                     # outro corte, que esta família não conhece

# ============================== por quilo, só a família que lê a unidade sabe comparar ==============================
# O peso do nome é o da porção (a linguiça "800g" por quilo custa o quilo, e não os 800 g): uma família que não lê a unidade não pode chavear o item por quilo.
confere(chave(("Linguiça Calabresa Perdigão 800g", KG)) is None, "linguiça por quilo: sem chave (a família dela não lê a unidade)")
confere(chave(("Linguiça Calabresa Perdigão 800g", UN)) is not None, "a linguiça embalada continua com chave")
confere(chave(("Linguiça Calabresa Perdigão 800g", None)) is not None and chave(("Linguiça Calabresa Perdigão 800g", None)) == chave(("Linguiça Calabresa Perdigão 800g", UN)), "sem unidade, como sempre")
confere(chave(("Arroz Branco Camil Tipo 1 5kg", KG)) is None and chave(("Arroz Branco Camil Tipo 1 5kg", UN)) is not None, "arroz: um por quilo, se existisse, não entra na família do arroz")
confere(chave(("Banana Prata Quilo", KG)) is not None and chave(("Banana Prata Quilo", KG)).startswith("hortifruti|"), "o hortifrúti, que lê a unidade, segue como antes")

# ============================== a família está na lista, no fim, e as 58 anteriores não mudaram ==============================
confere(eq.FAMILIAS[-1].id == "carnes_a_peso" and eq.FAMILIAS[-1].titulo == "cortes de carne e queijos a peso" and eq.FAMILIAS[-1].usa_unidade, "a família é a última e pede a unidade")
confere("cortes de carne e queijos a peso" in eq.familias_equivalentes(), "a lista de famílias que o site mostra traz os cortes")
confere(all(eq.equivalencia(n, unidade=u).chave.startswith("carnes_a_peso|") for n, u in (("Picanha Tradicional 1.4Kg", KG), ("Queijo Minas Frescal Cambuiense 1Kg", KG),
                                                                                           ("Queijo Parmesão Galbani 180g", UN))), "a chave começa pelo id da família (é por ele que o agrupamento exato se trava)")

if erros:
    print(f"{len(erros)} falha(s):\n  - " + "\n  - ".join(erros))
    sys.exit(1)
print(f"ok: {ok} verificações passaram")
