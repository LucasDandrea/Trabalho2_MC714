"""Eleicao de lider - algoritmo do Valentao (Bully).

Este modulo contem APENAS a logica de estado/decisao do Bully. Ele NAO faz
chamadas de rede: os metodos devolvem os "alvos" (listas de node_ids) para o
orquestrador (node.py) disparar as RPCs Election / Coordinator e cuidar dos
timeouts e do heartbeat.

Ideia do Bully:
  - Ao detectar a falha do lider, o no inicia uma ELEICAO e envia ELECTION a
    todos os nos de ID MAIOR.
  - Se algum no maior responde (o proprio Ack da RPC ja e o "OK"), este no
    desiste e aguarda o anuncio COORDINATOR.
  - Se nenhum no maior responde, o no se declara LIDER e envia COORDINATOR a
    todos os outros.

Thread-safety: `leader_id` e `election_in_progress` sao protegidos por
threading.Lock (`_lock`), pois sao lidos/escritos por varias threads (handlers
gRPC, loop de heartbeat e loop de eleicao).
"""

import threading
from typing import List, Optional


class BullyElection:
    def __init__(self, node_id: int, peers: List[int], clock, logger):
        self.node_id = node_id
        self.peers = list(peers)
        self.higher_peers = sorted(p for p in self.peers if p > node_id)
        self.lower_peers = sorted(p for p in self.peers if p < node_id)
        self.clock = clock
        self.log = logger

        self._lock = threading.Lock()
        self.leader_id: Optional[int] = None
        self.election_in_progress = False

    # ------------------------------------------------------------------
    # Inicio de eleicao
    # ------------------------------------------------------------------
    def start_election(self) -> List[int]:
        """Marca eleicao em andamento e devolve os IDs MAIORES a contatar.

        Se a lista vier vazia, o orquestrador deve chamar become_leader(),
        pois nao existe ninguem maior para assumir.
        """
        with self._lock:
            self.election_in_progress = True
            alvo = self.higher_peers if self.higher_peers else "nenhum (sou o maior)"
            self.log.bully(
                f"Node {self.node_id} | Iniciando eleicao... contatando IDs maiores: {alvo}"
            )
            return list(self.higher_peers)

    def report_leader_failure(self, dead_leader_id: Optional[int]) -> None:
        """Loga a deteccao de falha do lider e zera o lider conhecido."""
        with self._lock:
            self.leader_id = None
            self.log.bully(
                f"Node {self.node_id} | Falha do lider (Node {dead_leader_id}) "
                f"detectada! Iniciando eleicao..."
            )

    # ------------------------------------------------------------------
    # Recepcao de ELECTION
    # ------------------------------------------------------------------
    def on_election(self, from_id: int) -> bool:
        """Recebe ELECTION de um no de ID menor.

        O Ack da RPC ja serve como "OK, eu assumo" (somos maior que `from_id`).
        Retorna True se este no deve INICIAR a sua propria eleicao (caso ainda
        nao haja uma em andamento). Seta election_in_progress atomicamente
        para impedir que multiplos ELECTION concorrentes disparem threads
        de eleicao duplicadas.
        """
        with self._lock:
            should_start = not self.election_in_progress
            if should_start:
                self.election_in_progress = True
            self.log.bully(
                f"Node {self.node_id} | Recebeu ELECTION de Node {from_id}. "
                f"Respondo OK (tenho ID maior)"
                + (" e assumo a eleicao." if should_start else " (eleicao ja em andamento).")
            )
        return should_start

    # ------------------------------------------------------------------
    # Tornar-se lider
    # ------------------------------------------------------------------
    def become_leader(self) -> List[int]:
        """Declara este no como lider e devolve os alvos do COORDINATOR."""
        with self._lock:
            self.leader_id = self.node_id
            self.election_in_progress = False
            self.log.bully(
                f"Node {self.node_id} | Nenhum no maior respondeu. "
                f"SOU O NOVO LIDER! Anunciando COORDINATOR a {self.peers}"
            )
            return list(self.peers)

    # ------------------------------------------------------------------
    # Recepcao de COORDINATOR
    # ------------------------------------------------------------------
    def on_coordinator(self, leader_id: int) -> None:
        """Reconhece o anuncio de um novo lider."""
        with self._lock:
            self.leader_id = leader_id
            self.election_in_progress = False
            self.log.bully(
                f"Node {self.node_id} | Reconhece Node {leader_id} como o novo LIDER."
            )

    # ------------------------------------------------------------------
    # Acessores thread-safe
    # ------------------------------------------------------------------
    def get_leader(self) -> Optional[int]:
        with self._lock:
            return self.leader_id

    def is_leader(self) -> bool:
        with self._lock:
            return self.leader_id == self.node_id

    def set_leader(self, leader_id: int) -> None:
        with self._lock:
            self.leader_id = leader_id

    def is_election_in_progress(self) -> bool:
        with self._lock:
            return self.election_in_progress

    def finish_election(self) -> None:
        """Encerra o estado de eleicao em andamento (ex.: apos timeout tratado)."""
        with self._lock:
            self.election_in_progress = False
