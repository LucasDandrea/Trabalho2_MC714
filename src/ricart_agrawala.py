"""Exclusao mutua distribuida - algoritmo de Ricart-Agrawala.

Este modulo contem APENAS a logica de estado/decisao do algoritmo. Ele NAO faz
nenhuma chamada de rede: os metodos retornam os "alvos" (listas de node_ids)
para que o orquestrador (node.py) dispare as RPCs gRPC correspondentes.

Integracao com Lamport: a prioridade entre dois pedidos concorrentes pela
Secao Critica e dada pelo par (lamport_ts, node_id) -- ordenacao total. Quanto
MENOR o par, MAIOR a prioridade.

Padrao assincrono (requisito do projeto): quando um pedido alheio precisa ser
ADIADO, ele e apenas registrado na fila `_deferred` e o handler responde Ack na
hora. So ao SAIR da Secao Critica e que `release_cs()` devolve a lista de nos
adiados para o orquestrador enviar proativamente os REPLYs (ReplyAccess).

Thread-safety: todo o estado (state, request_ts, pendencias, adiados) e
protegido por um unico threading.Lock (`_lock`).
"""

import threading
from typing import List, Tuple


class State:
    RELEASED = "RELEASED"  # nao quer e nao esta na Secao Critica
    WANTED = "WANTED"      # quer entrar e aguarda REPLYs
    HELD = "HELD"          # esta dentro da Secao Critica


class RicartAgrawala:
    def __init__(self, node_id: int, peers: List[int], clock, logger):
        self.node_id = node_id
        self.peers = list(peers)  # ids dos demais nos
        self.clock = clock
        self.log = logger

        self._lock = threading.Lock()
        self.state = State.RELEASED
        self.request_ts = None              # timestamp do nosso pedido atual
        self._pending_replies = set()       # de quem ainda esperamos REPLY
        self._deferred = set()              # pedidos que adiamos (responder ao sair)

    # ------------------------------------------------------------------
    # Solicitar a Secao Critica
    # ------------------------------------------------------------------
    def request_cs(self) -> Tuple[int, List[int]]:
        """Marca o no como WANTED e devolve (request_ts, alvos_para_REQUEST).

        O orquestrador deve enviar RequestAccess(node_id, request_ts) a todos
        os alvos e aguardar os REPLYs (que chegam via on_reply()).
        """
        with self._lock:
            self.state = State.WANTED
            ts = self.clock.tick()  # evento de "querer entrar" = tick local
            self.request_ts = ts
            self._pending_replies = set(self.peers)
            targets = list(self.peers)
            self.log.ricart(
                f"Node {self.node_id} | Solicitando Secao Critica... "
                f"(Lamport: {ts}, aguardando {len(targets)} REPLYs)",
                level="want",
            )
        return ts, targets

    # ------------------------------------------------------------------
    # Receber um REQUEST de outro no
    # ------------------------------------------------------------------
    def on_request(self, from_id: int, ts: int) -> bool:
        """Decide o que fazer com um REQUEST recebido.

        Retorna:
          True  -> conceder AGORA (orquestrador envia ReplyAccess imediatamente)
          False -> ADIAR (registrado em _deferred; responde-se ao sair da CS)

        Regra: adiamos o pedido alheio se estamos na CS (HELD) ou se queremos
        entrar (WANTED) e nosso par (request_ts, node_id) tem prioridade
        (e estritamente menor) sobre o par (ts, from_id) do solicitante.
        """
        with self._lock:
            we_have_priority = self.state == State.HELD or (
                self.state == State.WANTED
                and (self.request_ts, self.node_id) < (ts, from_id)
            )

            if we_have_priority:
                self._deferred.add(from_id)
                self.log.ricart(
                    f"Node {self.node_id} | Pedido do Node {from_id} ADIADO "
                    f"(minha prioridade: (ts={self.request_ts},id={self.node_id}) "
                    f"< (ts={ts},id={from_id}))",
                    level="defer",
                )
                return False

            self.log.ricart(
                f"Node {self.node_id} | Concedendo permissao ao Node {from_id} "
                f"imediatamente (estado={self.state})",
                level="grant",
            )
            return True

    # ------------------------------------------------------------------
    # Receber um REPLY de outro no
    # ------------------------------------------------------------------
    def on_reply(self, from_id: int) -> bool:
        """Registra um REPLY recebido.

        Retorna True quando TODOS os REPLYs chegaram e o no pode ENTRAR na
        Secao Critica (transicao WANTED -> HELD feita atomicamente aqui).
        """
        with self._lock:
            self._pending_replies.discard(from_id)
            remaining = len(self._pending_replies)

            if self.state == State.WANTED and remaining == 0:
                self.state = State.HELD
                self.log.ricart(
                    f"Node {self.node_id} | Entrou na Secao Critica! "
                    f"(Lamport: {self.clock.time})",
                    level="enter",
                )
                return True

            self.log.ricart(
                f"Node {self.node_id} | REPLY recebido de Node {from_id} "
                f"(faltam {remaining})",
                level="info",
            )
            return False

    # ------------------------------------------------------------------
    # Sair da Secao Critica
    # ------------------------------------------------------------------
    def release_cs(self) -> List[int]:
        """Libera a Secao Critica e devolve a lista de nos ADIADOS.

        O orquestrador deve enviar ReplyAccess (REPLY) a cada um deles.
        """
        with self._lock:
            self.state = State.RELEASED
            self.request_ts = None
            deferred = sorted(self._deferred)
            self._deferred.clear()
            alvo = deferred if deferred else "ninguem"
            self.log.ricart(
                f"Node {self.node_id} | Saiu da Secao Critica. "
                f"Enviando REPLY adiado para: {alvo}",
                level="release",
            )
        return deferred

    # ------------------------------------------------------------------
    # Introspeccao (para logs/monitoramento)
    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self.state,
                "request_ts": self.request_ts,
                "pending": sorted(self._pending_replies),
                "deferred": sorted(self._deferred),
            }
