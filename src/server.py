"""Handlers gRPC do NodeService (lado servidor).

Cada handler atualiza o relogio de Lamport (clock.update) com o timestamp
recebido, delega a decisao ao modulo de estado correspondente (RicartAgrawala
ou BullyElection) e retorna um Ack imediato (fire-and-forget).

NENHUM handler bloqueia: quando o Ricart-Agrawala decide adiar um REQUEST,
o handler apenas registra na fila e retorna Ack. Quando precisa enviar um
REPLY imediato ou disparar uma eleicao, agenda a RPC via callback do
orquestrador (send_reply_fn / trigger_election_fn), que executa em thread
separada para nao segurar a thread do ThreadPool do gRPC.
"""

import threading

import grpc

import node_pb2 as pb
import node_pb2_grpc as pb_grpc

from src.logger import record_msg


class NodeServiceHandler(pb_grpc.NodeServiceServicer):
    def __init__(self, node):
        """Recebe a instancia do Node (orquestrador) para acessar clock/RA/Bully."""
        self.node = node
        self.clock = node.clock
        self.ra = node.ra
        self.bully = node.bully
        self.log = node.log

    def _ack(self) -> pb.Ack:
        ts = self.clock.tick()
        return pb.Ack(node_id=self.node.node_id, lamport_ts=ts)

    def _abort_if_dead(self, context) -> None:
        """Se o no foi 'morto' pelo dashboard, recusa a RPC (simula queda).

        Isso faz os demais nos perceberem a falha (heartbeat sem resposta) e
        dispararem a reeleicao Bully, exatamente como um `docker stop`.
        """
        if self.node.is_killed():
            context.abort(grpc.StatusCode.UNAVAILABLE, "node down (simulated)")

    # ------------------------------------------------------------------
    # Ricart-Agrawala
    # ------------------------------------------------------------------

    def RequestAccess(self, request, context):
        self._abort_if_dead(context)
        new = self.clock.update(request.lamport_ts, from_node=request.node_id)
        record_msg(request.node_id, self.node.node_id, "REQUEST", new)
        grant_now = self.ra.on_request(request.node_id, request.lamport_ts)

        if grant_now:
            threading.Thread(
                target=self.node.send_reply,
                args=(request.node_id,),
                daemon=True,
            ).start()

        return self._ack()

    def ReplyAccess(self, request, context):
        self._abort_if_dead(context)
        new = self.clock.update(request.lamport_ts, from_node=request.node_id)
        record_msg(request.node_id, self.node.node_id, "REPLY", new)
        entered = self.ra.on_reply(request.node_id)

        if entered:
            self.node.notify_cs_acquired()

        return self._ack()

    # ------------------------------------------------------------------
    # Bully
    # ------------------------------------------------------------------

    def Election(self, request, context):
        self._abort_if_dead(context)
        new = self.clock.update(request.lamport_ts, from_node=request.node_id)
        record_msg(request.node_id, self.node.node_id, "ELECTION", new)

        if not self.node.is_ready():
            self.log.net(
                f"Node {self.node.node_id} | ELECTION de Node {request.node_id} "
                f"recebido durante inicializacao (Ack enviado, eleicao adiada)"
            )
            return self._ack()

        should_start = self.bully.on_election(request.node_id)

        if should_start:
            threading.Thread(
                target=self.node.run_election,
                daemon=True,
            ).start()

        return self._ack()

    def Coordinator(self, request, context):
        self._abort_if_dead(context)
        new = self.clock.update(request.lamport_ts, from_node=request.leader_id)
        record_msg(request.leader_id, self.node.node_id, "COORDINATOR", new)
        self.bully.on_coordinator(request.leader_id)
        return self._ack()

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def Heartbeat(self, request, context):
        self._abort_if_dead(context)
        new = self.clock.update(request.lamport_ts, from_node=request.node_id)
        record_msg(request.node_id, self.node.node_id, "HEARTBEAT", new)
        ts = self.clock.tick()
        leader = self.bully.get_leader()
        return pb.Pong(
            node_id=self.node.node_id,
            lamport_ts=ts,
            leader_id=leader if leader is not None else -1,
        )
