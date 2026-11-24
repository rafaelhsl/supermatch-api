"""Medição de uso do site SEM rastrear ninguém: só somas por dia (desenho e limites em docs/uso_do_site.md).

O que é guardado: quantas vezes, em cada dia, aconteceu cada coisa da lista EVENTOS. Só isso: um número por dia e por tipo.
O que NUNCA passa por aqui: CEP, estado, termo buscado, produto, endereço IP, navegador, horário da chamada ou qualquer identificador
de pessoa. A função que grava (`registrar_uso`, em docs/sql/uso_do_site.sql) só recebe UM texto, de uma lista fechada, e a tabela
`uso_diario` só tem dia, evento e total: não há onde guardar mais nada. Por isso também não dá para saber "quantas pessoas":
isso exigiria reconhecer cada uma. Só se sabe quantas vezes.

A contagem nunca atrasa nem derruba uma resposta: o pedido do usuário só põe o nome do evento numa fila e segue; um fio próprio
manda a fila para o banco, uma soma por vez. Se o banco estiver fora (ou o SQL ainda não tiver sido rodado), a contagem falha em
silêncio (um aviso curto no log, no máximo um a cada 10 minutos) e a busca continua normal. Se a fila encher, as contagens que
sobrarem são descartadas: medir é secundário, atender é o que importa.
"""
import queue
import threading
import time

# A lista fechada de coisas contadas. Precisa ser igual à da restrição `check` de docs/sql/uso_do_site.sql (tests/test_medidor_de_uso.py confere).
EVENTO_ABERTURA = "abertura"                    # o site foi aberto (ou recarregado): ele chama GET /saude?origem=site; os monitores que chamam /saude sem isso não contam
EVENTO_BUSCA = "busca"                          # um pedido de busca a /comparar, feito por uma pessoa (inclui "mostrar também" e "buscar de novo")
EVENTO_BUSCA_SEM_RESULTADO = "busca_sem_resultado"      # a mesma busca, quando não encontrou nenhum produto (conta além de "busca")
EVENTO_ATUALIZACAO_DA_LISTA = "atualizacao_da_lista"    # um pedido a /comparar feito pelo site sozinho, para renovar os preços da lista de compras (origem=lista)
EVENTO_HISTORICO = "historico"                  # um pedido a /historico: alguém abriu o gráfico de preços de um produto
EVENTOS = (EVENTO_ABERTURA, EVENTO_BUSCA, EVENTO_BUSCA_SEM_RESULTADO, EVENTO_ATUALIZACAO_DA_LISTA, EVENTO_HISTORICO)

# Os valores que o site manda em `origem` para dizer de onde vem o pedido (qualquer outro valor, ou nenhum, é "pedido comum")
ORIGEM_DO_SITE = "site"         # GET /saude?origem=site: o site acabou de abrir
ORIGEM_DA_LISTA = "lista"       # GET /comparar?...&origem=lista: renovação automática dos preços da lista

INTERVALO_ENTRE_AVISOS = 600        # segundos: um aviso de falha por 10 minutos, para um banco fora do ar não encher o log
CAPACIDADE_DA_FILA = 500


class MedidorDeUso:
    """Soma, em segundo plano, uma ocorrência de cada vez. `enviar(evento)` é quem grava (no banco, em produção)."""

    def __init__(self, enviar, capacidade=CAPACIDADE_DA_FILA, agora=time.monotonic, avisar=print):
        self._enviar = enviar
        self._fila = queue.Queue(maxsize=capacidade)
        self._agora = agora
        self._avisar = avisar
        self._trava = threading.Lock()
        self._fio = None
        self._ultimo_aviso = None
        self.descartados = 0        # contagens perdidas porque a fila estava cheia (para diagnóstico e teste)

    def contar(self, evento):
        """Registra UMA ocorrência. Nunca levanta erro, nunca espera: o que não é da lista fechada é ignorado."""
        try:
            if evento not in EVENTOS:
                return
            self._garantir_fio()
            self._fila.put_nowait(evento)
        except queue.Full:
            self.descartados += 1
        except Exception:
            pass

    def esperar_esvaziar(self, limite=5.0) -> bool:
        """Espera a fila ser toda enviada (para os testes e para desligar com calma). True = esvaziou dentro do limite."""
        fim = time.monotonic() + limite
        while self._fila.unfinished_tasks:
            if time.monotonic() >= fim:
                return False
            time.sleep(0.005)
        return True

    def _garantir_fio(self):
        with self._trava:
            if self._fio is None:
                self._fio = threading.Thread(target=self._rodar, name="medidor-de-uso", daemon=True)
                self._fio.start()

    def _rodar(self):
        while True:
            evento = self._fila.get()
            try:
                self._enviar(evento)
            except Exception as erro:
                self._avisar_falha(erro)
            finally:
                self._fila.task_done()

    def _avisar_falha(self, erro):
        agora = self._agora()
        if self._ultimo_aviso is not None and agora - self._ultimo_aviso < INTERVALO_ENTRE_AVISOS:
            return
        self._ultimo_aviso = agora
        try:
            self._avisar(f"⚠️ Medição de uso indisponível (a busca segue normal): {type(erro).__name__}: {str(erro)[:200]}")
        except Exception:
            pass
