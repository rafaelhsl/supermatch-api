"""Medição de uso do site SEM rastrear ninguém: só somas por dia (desenho e limites em docs/uso_do_site.md).

O que é guardado: quantas vezes, em cada dia, aconteceu cada coisa da lista EVENTOS. Só isso: um número por dia e por tipo.
O que a tabela NÃO guarda, e este código nunca recebe: CEP, estado, termo buscado, produto, endereço IP, navegador, horário da chamada
ou qualquer identificador de pessoa. A função que grava (`registrar_uso`, em docs/sql/uso_do_site.sql) só recebe um texto, de uma lista
fechada, e uma quantidade; a tabela `uso_diario` só tem dia, evento e total: não há onde guardar mais nada. Por isso também não dá para
saber "quantas pessoas": isso exigiria reconhecer cada uma. Só se sabe quantas vezes. (O provedor do banco registra por conta própria
que a API chamou a função e a que horas, sem o corpo do pedido: veja docs/uso_do_site.md.)

A contagem nunca atrasa nem derruba uma resposta: o pedido do usuário só põe o nome do evento numa fila e segue; um fio próprio
manda a fila para o banco. Tudo o que chegou enquanto um envio estava em andamento sai junto, num pedido por tipo com a quantidade
(assim, mesmo com muito movimento, o banco recebe poucos pedidos). Se o banco estiver fora (ou o SQL ainda não tiver sido rodado),
a contagem falha em silêncio (um aviso curto no log, no máximo um a cada 10 minutos) e a busca continua normal. Se a fila encher,
as contagens que sobrarem são descartadas (com um aviso, também no máximo um a cada 10 minutos): medir é secundário, atender é o
que importa.

O medidor NASCE DESLIGADO (sem `enviar`): só o servidor de verdade o liga (`ligar`, em `ciclo_de_vida` de api_supabase.py). Assim os
testes, que chamam as funções da API direto, nunca fazem uma chamada de rede por causa da medição (nem sujam a tabela de produção).
"""
import queue
import threading
import time
from collections import Counter

# A lista fechada de coisas contadas. Precisa ser igual à da restrição `check` de docs/sql/uso_do_site.sql (tests/test_medidor_de_uso.py confere).
EVENTO_ABERTURA = "abertura"                    # o site foi aberto (ou recarregado): ele chama GET /saude?origem=site; os monitores que chamam /saude sem isso não contam
EVENTO_BUSCA = "busca"                          # um pedido de busca a /comparar (inclui "mostrar também" e "buscar de novo"; pode vir de qualquer cliente, não só do site)
EVENTO_BUSCA_SEM_RESULTADO = "busca_sem_resultado"      # a mesma busca, quando não encontrou nenhum produto (conta além de "busca")
EVENTO_ATUALIZACAO_DA_LISTA = "atualizacao_da_lista"    # um pedido a /comparar feito pelo site sozinho, para renovar os preços da lista de compras (origem=lista)
EVENTO_HISTORICO = "historico"                  # um pedido a /historico: o site consultou o histórico de um produto (reabrir o mesmo gráfico em até 10 min não chega à API)
EVENTOS = (EVENTO_ABERTURA, EVENTO_BUSCA, EVENTO_BUSCA_SEM_RESULTADO, EVENTO_ATUALIZACAO_DA_LISTA, EVENTO_HISTORICO)

# Os valores que o site manda em `origem` para dizer de onde vem o pedido (qualquer outro valor, ou nenhum, é "pedido comum")
ORIGEM_DO_SITE = "site"         # GET /saude?origem=site: o site acabou de abrir
ORIGEM_DA_LISTA = "lista"       # GET /comparar?...&origem=lista: renovação automática dos preços da lista

INTERVALO_ENTRE_AVISOS = 600        # segundos: um aviso por tipo de problema a cada 10 minutos, para um banco fora do ar não encher o log
CAPACIDADE_DA_FILA = 500            # contagens esperando envio; também é o máximo que sai junto num lote


class MedidorDeUso:
    """Soma, em segundo plano, as ocorrências. `enviar(evento, quantidade)` é quem grava (no banco, em produção); sem ele, está desligado."""

    def __init__(self, enviar=None, capacidade=CAPACIDADE_DA_FILA, agora=time.monotonic, avisar=print):
        self._enviar = enviar
        self._capacidade = capacidade
        self._fila = queue.Queue(maxsize=capacidade)
        self._agora = agora
        self._avisar = avisar
        self._trava = threading.Lock()
        self._fio = None
        self._ultimo_aviso = {}     # tipo de problema -> quando foi avisado pela última vez
        self.descartados = 0        # contagens perdidas porque a fila estava cheia (para diagnóstico e teste)

    def ligar(self, enviar):
        """Começa a enviar (o servidor de verdade subiu)."""
        self._enviar = enviar

    def desligar(self, esperar=0.0):
        """Para de enviar (o servidor vai desligar, ou o teste acabou). Com `esperar`, dá esse tempo (em segundos) para a fila ser enviada antes."""
        if esperar and self._enviar is not None:
            self.esperar_esvaziar(esperar)
        self._enviar = None

    def contar(self, evento):
        """Registra UMA ocorrência. Nunca levanta erro, nunca espera: o que não é da lista fechada é ignorado, e desligado não conta."""
        try:
            if self._enviar is None or evento not in EVENTOS:
                return
            self._fila.put_nowait(evento)       # primeiro entra na fila: se o fio não subir agora, a próxima contagem tenta de novo e nada se perde
            self._garantir_fio()
        except queue.Full:
            self.descartados += 1
            self._avisar_no_maximo_uma_vez("fila", f"⚠️ Medição de uso: a fila encheu (o banco está lento ou fora) e as contagens que sobraram foram descartadas (já são {self.descartados}). A busca segue normal.")
        except Exception:
            pass

    def esperar_esvaziar(self, limite=30.0) -> bool:
        """Espera a fila ser toda enviada (para os testes e para desligar com calma). True = esvaziou dentro do limite."""
        fim = time.monotonic() + limite
        while self._fila.unfinished_tasks:
            if time.monotonic() >= fim:
                return False
            time.sleep(0.005)
        return True

    def _garantir_fio(self):
        with self._trava:
            if self._fio is None or not self._fio.is_alive():       # (também recria o fio se ele morreu, ou se não chegou a subir)
                fio = threading.Thread(target=self._rodar, name="medidor-de-uso", daemon=True)
                fio.start()
                self._fio = fio                                     # só guarda depois de ter subido

    def _rodar(self):
        while True:
            lote = [self._fila.get()]
            while len(lote) < self._capacidade:                     # o que chegou enquanto o envio anterior estava em andamento sai junto
                try:
                    lote.append(self._fila.get_nowait())
                except queue.Empty:
                    break
            try:
                enviar = self._enviar
                if enviar is not None:                              # (desligado enquanto esperava: a contagem é descartada)
                    for evento, quantidade in Counter(lote).items():    # um pedido por tipo, com a quantidade
                        try:
                            enviar(evento, quantidade)
                        except Exception as erro:
                            self._avisar_no_maximo_uma_vez("envio", f"⚠️ Medição de uso indisponível (a busca segue normal): {type(erro).__name__}: {str(erro)[:200]}")
            finally:
                for _ in lote:
                    self._fila.task_done()

    def _avisar_no_maximo_uma_vez(self, tipo, texto):
        agora = self._agora()
        antes = self._ultimo_aviso.get(tipo)
        if antes is not None and agora - antes < INTERVALO_ENTRE_AVISOS:
            return
        self._ultimo_aviso[tipo] = agora
        try:
            self._avisar(texto)
        except Exception:
            pass
