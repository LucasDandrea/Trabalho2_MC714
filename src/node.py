"""Orquestrador do no distribuido.

O Node integra LamportClock + RicartAgrawala + BullyElection, expoem o
servidor gRPC (via server.py) e gerencia as threads de background:
  - wait_for_peers(): retry com backoff ate todos os pares estarem vivos.
  - cs_loop(): periodicamente tenta entrar na Secao Critica.
  - heartbeat_loop(): pinga o lider; dispara eleicao se timeout.
  - run_election(): executa o fluxo Bully (ELECTION -> COORDINATOR).
  - send_reply() / send_request(): RPCs fire-and-forget para os pares.

TODA chamada gRPC sai daqui (camada de rede). Os modulos de algoritmo
(ricart_agrawala.py, bully.py) permanecem puros (logica de decisao).
"""

import random
import threading
import time
from concurrent import futures
from typing import Dict, Optional

import grpc

import node_pb2 as pb
import node_pb2_grpc as pb_grpc

from src.lamport_clock import LamportClock
from src.ricart_agrawala import RicartAgrawala
from src.bully import BullyElection
from src.server import NodeServiceHandler
from src.logger import NodeLogger, enable_ansi
from src import config

RPC_TIMEOUT = 3
HEARTBEAT_INTERVAL = 2.0
HEARTBEAT_TIMEOUT = 2.0
ELECTION_WAIT = 5.0
COORDINATOR_RETRIES = 3
COORDINATOR_RETRY_DELAY = 1.0
PEER_WAIT_RETRIES = 30
PEER_WAIT_SLEEP = 2.0


class Node:
    def __init__(self):
        enable_ansi()
        self.node_id, self.peers_map, self.cs_interval = config.load()
        peer_ids = sorted(self.peers_map.keys())

        self.log = NodeLogger(self.node_id)
        self.clock = LamportClock(self.node_id, self.log)
        self.ra = RicartAgrawala(self.node_id, peer_ids, self.clock, self.log)
        self.bully = BullyElection(self.node_id, peer_ids, self.clock, self.log)

        self._channels: Dict[int, grpc.Channel] = {}
        self._stubs: Dict[int, pb_grpc.NodeServiceStub] = {}
        self._stop = threading.Event()
        self._cs_event = threading.Event()
        self._ready = threading.Event()

        self.log.info(
            f"Node {self.node_id} inicializado | "
            f"Peers: {peer_ids} | CS_INTERVAL: {self.cs_interval}s"
        )

    def is_ready(self) -> bool:
        return self._ready.is_set()

    # ==================================================================
    # Canais gRPC e stubs
    # ==================================================================

    def _get_stub(self, peer_id: int) -> Optional[pb_grpc.NodeServiceStub]:
        if peer_id in self._stubs:
            return self._stubs[peer_id]
        addr = self.peers_map.get(peer_id)
        if addr is None:
            return None
        channel = grpc.insecure_channel(addr)
        stub = pb_grpc.NodeServiceStub(channel)
        self._channels[peer_id] = channel
        self._stubs[peer_id] = stub
        return stub

    # ==================================================================
    # Wait-for-peers (resiliencia de inicializacao)
    # ==================================================================

    def wait_for_peers(self) -> None:
        self.log.net(
            f"Node {self.node_id} | Aguardando peers estarem prontos..."
        )
        ready = set()
        for attempt in range(1, PEER_WAIT_RETRIES + 1):
            if self._stop.is_set():
                return
            for pid in self.peers_map:
                if pid in ready:
                    continue
                try:
                    stub = self._get_stub(pid)
                    if stub is None:
                        continue
                    ts = self.clock.tick()
                    stub.Heartbeat(
                        pb.Ping(node_id=self.node_id, lamport_ts=ts),
                        timeout=PEER_WAIT_SLEEP,
                    )
                    ready.add(pid)
                    self.log.net(
                        f"Node {self.node_id} | Peer {pid} respondeu! "
                        f"({len(ready)}/{len(self.peers_map)} prontos)"
                    )
                except grpc.RpcError:
                    pass

            if len(ready) == len(self.peers_map):
                self.log.net(
                    f"Node {self.node_id} | Todos os {len(ready)} peers prontos!"
                )
                return

            backoff = min(PEER_WAIT_SLEEP * (1 + 0.3 * attempt), 10)
            time.sleep(backoff)

        self.log.warn(
            f"Node {self.node_id} | Timeout aguardando peers. "
            f"Prontos: {sorted(ready)}. Seguindo mesmo assim."
        )

    # ==================================================================
    # RPCs de saida (fire-and-forget)
    # ==================================================================

    def _safe_rpc(self, peer_id: int, method: str, msg):
        stub = self._get_stub(peer_id)
        if stub is None:
            return None
        try:
            fn = getattr(stub, method)
            return fn(msg, timeout=RPC_TIMEOUT)
        except grpc.RpcError as e:
            self.log.warn(
                f"Node {self.node_id} | RPC {method} para Node {peer_id} "
                f"falhou: {e.code().name}"
            )
            return None

    def send_request(self, peer_id: int, ts: int) -> None:
        msg = pb.CsRequest(node_id=self.node_id, lamport_ts=ts)
        self._safe_rpc(peer_id, "RequestAccess", msg)

    def send_reply(self, peer_id: int) -> None:
        ts = self.clock.tick()
        msg = pb.CsReply(node_id=self.node_id, lamport_ts=ts)
        self._safe_rpc(peer_id, "ReplyAccess", msg)

    def send_election(self, peer_id: int) -> Optional[pb.Ack]:
        ts = self.clock.tick()
        msg = pb.ElectionMsg(node_id=self.node_id, lamport_ts=ts)
        return self._safe_rpc(peer_id, "Election", msg)

    def _send_coordinator_with_retry(self, peer_id: int) -> None:
        """Envia COORDINATOR com retry, pois o peer pode nao estar 100% pronto."""
        for attempt in range(COORDINATOR_RETRIES):
            ts = self.clock.tick()
            msg = pb.CoordinatorMsg(leader_id=self.node_id, lamport_ts=ts)
            result = self._safe_rpc(peer_id, "Coordinator", msg)
            if result is not None:
                return
            time.sleep(COORDINATOR_RETRY_DELAY * (attempt + 1))

    def send_heartbeat(self, peer_id: int) -> Optional[pb.Pong]:
        ts = self.clock.tick()
        msg = pb.Ping(node_id=self.node_id, lamport_ts=ts)
        stub = self._get_stub(peer_id)
        if stub is None:
            return None
        try:
            return stub.Heartbeat(msg, timeout=HEARTBEAT_TIMEOUT)
        except grpc.RpcError:
            return None

    # ==================================================================
    # Secao Critica (loop de contencao + execucao)
    # ==================================================================

    def cs_loop(self) -> None:
        """Thread que periodicamente tenta entrar na Secao Critica."""
        initial_delay = random.uniform(1, self.cs_interval)
        time.sleep(initial_delay)

        while not self._stop.is_set():
            self._cs_event.clear()

            ts, targets = self.ra.request_cs()
            for pid in targets:
                self.send_request(pid, ts)

            self._cs_event.wait()

            if self._stop.is_set():
                return

            self.do_critical_section()
            jitter = random.uniform(0.5 * self.cs_interval, 1.5 * self.cs_interval)
            self._stop.wait(jitter)

    def do_critical_section(self) -> None:
        """Executa o 'trabalho' na Secao Critica e libera ao sair."""
        duration = random.uniform(1.0, 3.0)
        self.log.ricart(
            f"Node {self.node_id} | >>> TRABALHANDO na Secao Critica "
            f"por {duration:.1f}s... (Lamport: {self.clock.time})",
            level="enter",
        )

        self._stop.wait(duration)

        deferred = self.ra.release_cs()
        for pid in deferred:
            threading.Thread(
                target=self.send_reply,
                args=(pid,),
                daemon=True,
            ).start()

    def notify_cs_acquired(self) -> None:
        """Chamado internamente quando on_reply retorna True (todos os REPLYs)."""
        self._cs_event.set()

    # ==================================================================
    # Eleicao Bully
    # ==================================================================

    def run_election(self) -> None:
        higher = self.bully.start_election()

        if not higher:
            self._announce_leader()
            return

        any_responded = False
        for pid in higher:
            ack = self.send_election(pid)
            if ack is not None:
                any_responded = True

        if not any_responded:
            self._announce_leader()
            return

        self.log.bully(
            f"Node {self.node_id} | Nos maiores responderam. "
            f"Aguardando COORDINATOR por {ELECTION_WAIT}s..."
        )
        deadline = time.time() + ELECTION_WAIT
        while time.time() < deadline:
            if self.bully.get_leader() is not None:
                return
            time.sleep(0.5)

        self.log.bully(
            f"Node {self.node_id} | Timeout esperando COORDINATOR. "
            f"Reassumindo eleicao..."
        )
        self.bully.finish_election()
        self.run_election()

    def _announce_leader(self) -> None:
        targets = self.bully.become_leader()
        for pid in targets:
            threading.Thread(
                target=self._send_coordinator_with_retry,
                args=(pid,),
                daemon=True,
            ).start()

    # ==================================================================
    # Heartbeat (detector de falhas do lider)
    # ==================================================================

    def heartbeat_loop(self) -> None:
        time.sleep(HEARTBEAT_INTERVAL)
        while not self._stop.is_set():
            leader = self.bully.get_leader()

            if leader is None:
                if not self.bully.is_election_in_progress():
                    self.log.bully(
                        f"Node {self.node_id} | Nenhum lider conhecido. "
                        f"Disparando eleicao..."
                    )
                    self.run_election()
            elif leader != self.node_id:
                pong = self.send_heartbeat(leader)
                if pong is None:
                    self.bully.report_leader_failure(leader)
                    self.run_election()

            self._stop.wait(HEARTBEAT_INTERVAL)

    # ==================================================================
    # Eleicao inicial
    # ==================================================================

    def initial_election(self) -> None:
        self.log.bully(
            f"Node {self.node_id} | Eleicao inicial ao entrar no cluster..."
        )
        self.run_election()

    # ==================================================================
    # Servidor gRPC + startup
    # ==================================================================

    def start(self) -> None:
        port = config.GRPC_PORT
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
        handler = NodeServiceHandler(self)
        pb_grpc.add_NodeServiceServicer_to_server(handler, server)
        server.add_insecure_port(f"0.0.0.0:{port}")
        server.start()
        self.log.net(
            f"Node {self.node_id} | Servidor gRPC escutando em 0.0.0.0:{port}"
        )

        self.wait_for_peers()
        self._ready.set()

        startup_jitter = random.uniform(0.5, 2.0)
        self.log.info(
            f"Node {self.node_id} | Peers prontos. Aguardando "
            f"{startup_jitter:.1f}s antes da eleicao inicial..."
        )
        time.sleep(startup_jitter)

        self.initial_election()

        threads = [
            threading.Thread(target=self.cs_loop, daemon=True, name="cs_loop"),
            threading.Thread(target=self.heartbeat_loop, daemon=True, name="hb_loop"),
        ]
        for t in threads:
            t.start()

        self.log.info(
            f"Node {self.node_id} | Loops de CS e Heartbeat iniciados. "
            f"Rodando... (Ctrl+C para parar)"
        )

        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            self.log.info(f"Node {self.node_id} | Encerrando...")
            self._stop.set()
            server.stop(grace=2)
