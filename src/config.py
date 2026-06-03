"""Configuracao do no via variaveis de ambiente.

Cada conteiner Docker recebe NODE_ID, PEERS e opcionalmente CS_INTERVAL.
PEERS e uma string "host1:port1,host2:port2,...", onde cada entrada tem o
formato "nodeN:50051" (o hostname coincide com o nome do servico no
docker-compose, e a porta gRPC e fixa em 50051 dentro da rede bridge).
"""

import os
from typing import Dict, Tuple

GRPC_PORT = 50051


def load() -> Tuple[int, Dict[int, str], float]:
    """Retorna (node_id, peers_map, cs_interval).

    peers_map: {peer_id: "host:port", ...}  (exclui o proprio no)
    cs_interval: segundos entre tentativas de entrar na CS.
    """
    node_id = int(os.environ["NODE_ID"])

    peers_raw = os.environ.get("PEERS", "")
    peers_map: Dict[int, str] = {}
    for entry in peers_raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        host, port = entry.rsplit(":", 1)
        # hostname "nodeN" -> extrair N como peer_id
        peer_id = int(host.replace("node", ""))
        if peer_id != node_id:
            peers_map[peer_id] = f"{host}:{port}"

    cs_interval = float(os.environ.get("CS_INTERVAL", "5"))

    return node_id, peers_map, cs_interval
