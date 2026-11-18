"""Disjuntor por mercado e a segunda rodada da coleta (docs/carga_diaria.md, "Quando um mercado cai no meio da carga").

Dois problemas da carga de 18/11/2026 (execução 44274084420, cancelada depois de 47 minutos):
- o Atacadão respondeu HTTP 403 a TODOS os 100 termos, e o coletor perguntou os 100 mesmo assim;
- o Super ABC não conseguiu abrir a lista de unidades em nenhum termo, e o robô gastou 3 tentativas de ~45 s em cada um dos 100.

A regra é simples: um mercado que falha várias vezes SEGUIDAS está fora do ar (ou nos bloqueando), e insistir só gasta tempo e
estressa o site. O disjuntor "abre", os termos que faltam não são tentados e, no fim, a segunda rodada tenta de novo, uma vez, depois
de uma pausa, tudo o que não deu certo. Se o mercado voltou, a carga se completa; se não, o disjuntor abre de novo e a carga desiste
com os dados antigos do mercado mantidos (é a regra de sempre para quem não chega a 90% dos termos).

Este módulo só decide; quem tenta, espera e conta é o coletor (coletor_vtex.py) e a carga (alimentar_banco.py).
"""

# Quantas falhas seguidas (sem nenhum acerto no meio) abrem o disjuntor. Dá folga para o dia ruim de um termo isolado
# (a coleta parcial aceita 10%) e ainda para o mercado fora do ar em minutos, não em quase uma hora.
LIMITE_DE_FALHAS_SEGUIDAS = 6

# Segundos de espera antes da segunda rodada: um bloqueio ou uma lentidão passageira costuma passar em um ou dois minutos.
PAUSA_DA_SEGUNDA_RODADA = 60

NAO_TENTADO = "não tentado"


class Disjuntor:
    """Conta as falhas seguidas de um mercado. Depois de aberto, fica aberto (um acerto atrasado de outro termo não o fecha)."""

    def __init__(self, limite=None):
        # None: o limite padrão; 0: sem disjuntor (nunca abre)
        self.limite = LIMITE_DE_FALHAS_SEGUIDAS if limite is None else limite
        self.seguidas = 0
        self.ultimo_motivo = ""
        self._aberto = False

    @property
    def aberto(self):
        return self._aberto

    def acertou(self):
        self.seguidas = 0

    def errou(self, motivo):
        self.seguidas += 1
        self.ultimo_motivo = str(motivo)
        if self.limite and self.seguidas >= self.limite:
            self._aberto = True

    def explicacao(self):
        return f"o mercado falhou {self.seguidas} vezes seguidas; a última: {self.ultimo_motivo[:200]}"

    def motivo_de_pulo(self):
        """O que fica registrado no termo que não chegou a ser tentado."""
        return f"{NAO_TENTADO}: {self.explicacao()}"


def foi_pulado(motivo):
    """Este motivo de falha é de um termo que o disjuntor não deixou tentar?"""
    return str(motivo or "").startswith(NAO_TENTADO)
