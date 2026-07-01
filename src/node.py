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

import os
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
from src.logger import NodeLogger, enable_ansi, record_msg
from src.dashboard_api import start_dashboard_api
from src import config

DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "8000"))
# Se, ao esperar REPLYs, algum peer nao responder um heartbeat dentro deste
# tempo, ele e considerado fora do ar e a espera pelo REPLY dele e liberada
# (evita deadlock quando um no cai devendo REPLYs adiados).
REPLY_LIVENESS_TIMEOUT = 3.0

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
        # AUTO_CS=1 -> tenta entrar na Regiao Critica periodicamente sozinho.
        # AUTO_CS=0 (padrao) -> so entra quando o usuario clica "Pedir RC".
        self.auto_cs = os.environ.get("AUTO_CS", "0") == "1"

        self.log = NodeLogger(self.node_id)
        self.clock = LamportClock(self.node_id, self.log)
        self.ra = RicartAgrawala(self.node_id, peer_ids, self.clock, self.log)
        self.bully = BullyElection(self.node_id, peer_ids, self.clock, self.log)

        self._channels: Dict[int, grpc.Channel] = {}
        self._stubs: Dict[int, pb_grpc.NodeServiceStub] = {}
        self._stop = threading.Event()
        self._cs_event = threading.Event()
        self._ready = threading.Event()
        # Simulacao de queda controlada pelo dashboard (botao "Matar no").
        self._killed = threading.Event()
        # "Portao" de pausa: SET = rodando, CLEAR = pausado. Quando pausado, os
        # loops de fundo (heartbeat, secao critica) bloqueiam e o tempo/relogio
        # de Lamport param de avancar -- congelamento real da simulacao.
        self._pause_gate = threading.Event()
        self._pause_gate.set()
        # Acorda o cs_loop para tentar a Regiao Critica imediatamente (botao
        # "Pedir Regiao Critica"), sem esperar o intervalo automatico.
        self._cs_trigger = threading.Event()

        self.log.info(
            f"Node {self.node_id} inicializado | "
            f"Peers: {peer_ids} | CS_INTERVAL: {self.cs_interval}s | "
            f"Regiao Critica: {'AUTOMATICA' if self.auto_cs else 'MANUAL (botao Pedir RC)'}"
        )

    def is_ready(self) -> bool:
        return self._ready.is_set()

    # ==================================================================
    # Controles do dashboard (introspeccao + acoes ao vivo)
    # ==================================================================

    def is_killed(self) -> bool:
        return self._killed.is_set()

    def dashboard_state(self) -> dict:
        """Estado atual do no, consumido pelo dashboard web via HTTP."""
        snap = self.ra.snapshot()
        return {
            "node_id": self.node_id,
            "lamport": self.clock.time,
            "leader": self.bully.get_leader(),
            "is_leader": self.bully.is_leader(),
            "cs_state": snap["state"],
            "request_ts": snap["request_ts"],
            "pending": snap["pending"],
            "deferred": snap["deferred"],
            "killed": self.is_killed(),
            "paused": not self._pause_gate.is_set(),
            "election_in_progress": self.bully.is_election_in_progress(),
        }

    def simulate_kill(self) -> None:
        """Simula a QUEDA do no: para de responder gRPC e pausa os loops.

        Os demais nos detectam a falha (heartbeat sem resposta) e, se este era
        o lider, disparam a reeleicao Bully -- exatamente como um `docker stop`,
        porem controlavel pela UI.
        """
        if self._killed.is_set():
            return
        self._killed.set()
        # Desbloqueia quem estiver esperando (ex.: aguardando entrar na CS),
        # para que o loop perceba a "morte" e pause.
        self._cs_event.set()
        self._cs_trigger.set()
        self.log.warn(
            f"Node {self.node_id} | 💀 SIMULANDO QUEDA (parou de responder). "
            f"Os outros nos vao detectar a falha."
        )

    def revive(self) -> None:
        """Revive o no e reintegra ao cluster, disparando uma eleicao."""
        if not self._killed.is_set():
            return
        self._killed.clear()
        self.log.info(
            f"Node {self.node_id} | ♻️  REVIVIDO. Reintegrando ao cluster e "
            f"disparando eleicao..."
        )
        threading.Thread(target=self.run_election, daemon=True).start()

    def pause(self) -> None:
        """Congela a simulacao deste no (loops de fundo bloqueiam)."""
        if self._pause_gate.is_set():
            self._pause_gate.clear()
            self.log.info(f"Node {self.node_id} | ⏸️  PAUSADO (tempo congelado).")

    def resume(self) -> None:
        """Retoma a simulacao do ponto exato em que parou."""
        if not self._pause_gate.is_set():
            self._pause_gate.set()
            self.log.info(f"Node {self.node_id} | ▶️  RETOMADO.")

    def _block_while_paused(self) -> None:
        """Bloqueia enquanto o no estiver pausado (sem consumir tempo)."""
        while not self._pause_gate.is_set():
            if self._stop.is_set():
                return
            self._pause_gate.wait(0.15)

    def _pausable_wait(self, duration: float) -> None:
        """Espera `duration` segundos, mas CONGELA a contagem enquanto pausado.

        Usado no tempo de posse da Regiao Critica e no intervalo do heartbeat,
        para que uma pausa nao deixe o tempo passar "por baixo".
        """
        remaining = duration
        while remaining > 0 and not self._stop.is_set():
            self._block_while_paused()
            if self._stop.is_set():
                return
            step = 0.1 if remaining > 0.1 else remaining
            if self._stop.wait(step):
                return
            remaining -= step

    def force_cs_request(self) -> None:
        """Acorda o cs_loop para tentar entrar na Regiao Critica agora."""
        if self._killed.is_set():
            return
        self.log.ricart(
            f"Node {self.node_id} | (dashboard) Pedido manual de Regiao Critica.",
            level="want",
        )
        self._cs_trigger.set()

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
                    pong = stub.Heartbeat(
                        pb.Ping(node_id=self.node_id, lamport_ts=ts),
                        timeout=PEER_WAIT_SLEEP,
                    )
                    new = self.clock.update(pong.lamport_ts, from_node=pid)
                    record_msg(pid, self.node_id, "PONG", new)
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

    # NOTA: as mensagens sao registradas para a animacao no RECEPTOR (server.py
    # e o retorno do Pong abaixo), ja com o clock de Lamport resultante -- assim
    # a bolinha e o numero do relogio ficam sincronizados no painel.

    def send_request(self, peer_id: int, ts: int) -> None:
        msg = pb.CsRequest(node_id=self.node_id, lamport_ts=ts)
        # A tolerancia a falha (peer caido) e tratada pelo cs_loop, que verifica
        # a vivacidade dos pendentes via heartbeat (ver _resolve_dead_pending).
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
            pong = stub.Heartbeat(msg, timeout=HEARTBEAT_TIMEOUT)
        except grpc.RpcError:
            return None
        # Recebemos o Pong (a confirmacao de que o peer esta vivo). Isso e uma
        # RECEPCAO de mensagem, entao o relogio de Lamport tem que evoluir aqui
        # tambem: C = max(C, ts_recebido) + 1. (Antes so o lado que RECEBIA o
        # ping atualizava; o lado que pingava ignorava o timestamp da volta.)
        new = self.clock.update(pong.lamport_ts, from_node=peer_id)
        # Bolinha de VOLTA (Pong): lider -> este no, ja com o clock resultante.
        record_msg(peer_id, self.node_id, "PONG", new)
        return pong

    # ==================================================================
    # Secao Critica (loop de contencao + execucao)
    # ==================================================================

    def cs_loop(self) -> None:
        """Thread que tenta entrar na Secao Critica.

        Dois modos (controlados pela env AUTO_CS):
          - AUTO_CS=1: o no tenta entrar periodicamente, sozinho (comportamento
            "vivo" classico).
          - AUTO_CS=0 (padrao): MANUAL. O no so tenta entrar quando o usuario
            clica em "Pedir RC" no painel. Assim a Regiao Critica fica vazia
            ate voce pedir -- ideal para conduzir a demonstracao na mao.
        """
        if self.auto_cs:
            self._cs_trigger.wait(random.uniform(1, self.cs_interval))

        while not self._stop.is_set():
            # Pausado: congela o loop da Regiao Critica.
            self._block_while_paused()
            if self._stop.is_set():
                return

            # No "morto" (simulacao de queda): nao disputa a Regiao Critica.
            if self._killed.is_set():
                self._stop.wait(0.5)
                continue

            if self.auto_cs:
                self._cs_trigger.clear()
                self._run_one_cs_cycle()
                if self._stop.is_set():
                    return
                jitter = random.uniform(0.5 * self.cs_interval, 1.5 * self.cs_interval)
                # Acorda antes se o dashboard pedir Regiao Critica manualmente.
                self._cs_trigger.wait(jitter)
            else:
                # Modo manual: dorme ate o usuario clicar "Pedir RC".
                if not self._cs_trigger.wait(0.5):
                    continue
                self._cs_trigger.clear()
                if self._killed.is_set() or self._stop.is_set():
                    continue
                self._run_one_cs_cycle()

    def _run_one_cs_cycle(self) -> None:
        """Executa uma tentativa completa de entrar e sair da Secao Critica."""
        self._cs_event.clear()

        ts, targets = self.ra.request_cs()
        for pid in targets:
            self.send_request(pid, ts)

        # Espera todos os REPLYs. Mas nao espera para sempre: a cada
        # REPLY_LIVENESS_TIMEOUT, checa se algum peer pendente caiu (para
        # nao travar eternamente esperando o REPLY de um no morto).
        while not self._cs_event.wait(REPLY_LIVENESS_TIMEOUT):
            if self._stop.is_set() or self._killed.is_set():
                return
            self._block_while_paused()   # nao verifica vivacidade enquanto pausado
            if self._stop.is_set() or self._killed.is_set():
                return
            self._resolve_dead_pending()

        if self._stop.is_set() or self._killed.is_set():
            return

        self.do_critical_section()

    def _resolve_dead_pending(self) -> None:
        """Destrava a espera por REPLYs de peers que cairam.

        Para cada peer de quem ainda esperamos REPLY, manda um heartbeat:
          - se responde, o peer esta VIVO (so esta adiando) -> continua esperando;
          - se nao responde, o peer esta MORTO -> tratamos como permissao
            concedida (um no fora do ar nao pode estar na Regiao Critica).
        Assim, matar um no nunca congela a exclusao mutua dos demais.
        """
        snap = self.ra.snapshot()
        if snap["state"] != "WANTED":
            return
        for pid in snap["pending"]:
            if self._stop.is_set() or self._killed.is_set():
                return
            if self.send_heartbeat(pid) is None:
                self.log.warn(
                    f"Node {self.node_id} | Node {pid} nao respondeu ao heartbeat; "
                    f"considerado fora do ar. Liberando a espera pelo REPLY dele."
                )
                if self.ra.on_reply(pid):
                    self.notify_cs_acquired()

    def do_critical_section(self) -> None:
        """Executa o 'trabalho' na Secao Critica e libera ao sair."""
        # No modo manual, segura a Regiao Critica por mais tempo para dar
        # folga para narrar / pausar a tela durante a apresentacao.
        duration = random.uniform(1.0, 3.0) if self.auto_cs else random.uniform(5.0, 7.0)
        self.log.ricart(
            f"Node {self.node_id} | >>> TRABALHANDO na Secao Critica "
            f"por {duration:.1f}s... (Lamport: {self.clock.time})",
            level="enter",
        )

        # Congela a posse da Regiao Critica se a simulacao for pausada.
        self._pausable_wait(duration)

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
        if self._killed.is_set():
            return
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
            # Pausado: congela (nao pinga, nao evolui relogio).
            self._block_while_paused()
            if self._stop.is_set():
                return

            # No "morto": nao monitora nem dispara eleicoes ate ser revivido.
            if self._killed.is_set():
                self._stop.wait(HEARTBEAT_INTERVAL)
                continue

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

            self._pausable_wait(HEARTBEAT_INTERVAL)

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

        # Sobe a API HTTP de introspeccao/controle para o dashboard web.
        start_dashboard_api(self, DASHBOARD_PORT)

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
