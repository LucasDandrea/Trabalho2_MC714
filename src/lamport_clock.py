"""Relogio logico de Lamport (thread-safe).

Regras de Lamport implementadas:
  - tick():  evento interno / ANTES de enviar uma mensagem -> C = C + 1
  - update(): ao RECEBER uma mensagem com timestamp T -> C = max(C, T) + 1

Thread-safety: o servidor gRPC processa varias RPCs em paralelo, entao todo
acesso ao contador e protegido por um threading.Lock. A escrita no log e feita
FORA da regiao critica do lock, para nunca segurar o lock durante I/O.
"""

import threading
from typing import Optional


class LamportClock:
    def __init__(self, node_id: int, logger=None):
        self.node_id = node_id
        self._logger = logger
        self._lock = threading.Lock()
        self._time = 0

    def tick(self) -> int:
        """Evento local / pre-envio: incrementa e retorna o novo valor."""
        with self._lock:
            self._time += 1
            return self._time

    def update(self, received_ts: int, from_node: Optional[int] = None) -> int:
        """Recepcao de mensagem: C = max(C, received_ts) + 1.

        Retorna o novo valor do relogio. Faz o log didatico do salto do clock.
        """
        with self._lock:
            old = self._time
            self._time = max(self._time, received_ts) + 1
            new = self._time

        if self._logger is not None:
            via = f" (via msg de Node {from_node})" if from_node is not None else ""
            self._logger.lamport(
                f"Node {self.node_id} | Clock atualizado: {old} -> {new}{via}"
            )
        return new

    @property
    def time(self) -> int:
        """Leitura atomica do valor atual do relogio."""
        with self._lock:
            return self._time
