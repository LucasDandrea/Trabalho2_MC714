"""Mini-servidor HTTP de introspeccao e controle de cada no (para o dashboard).

Cada no do cluster sobe, alem do servidor gRPC, um pequeno servidor HTTP
(biblioteca padrao, sem dependencias novas) que serve como "porta de vidro"
para o dashboard web:

  GET  /state         -> JSON com o estado atual do no (relogio de Lamport,
                         lider conhecido, estado do Ricart-Agrawala, se esta
                         "morto", etc.).
  GET  /logs?since=N  -> logs estruturados novos (seq > N) desse no.
  POST /election      -> dispara uma eleicao Bully a partir deste no.
  POST /kill          -> simula a QUEDA deste no (para de responder gRPC).
  POST /revive        -> revive o no e reintegra ao cluster.
  POST /request_cs    -> pede para este no tentar entrar na Regiao Critica ja.

Todas as respostas levam cabecalhos CORS liberados, pois a pagina do dashboard
e servida por outra origem (o container `dashboard`) e faz fetch direto para
cada no via portas publicadas no host (localhost:1800X).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from src import logger


def _make_handler(node):
    """Cria a classe de handler HTTP amarrada a instancia do `node`."""

    class Handler(BaseHTTPRequestHandler):
        # Silencia o log padrao do http.server para nao poluir o stdout
        # (que e a nossa saida bonita colorida dos algoritmos).
        def log_message(self, *args, **kwargs):
            return

        def _send(self, code=200, payload=None):
            body = json.dumps(payload if payload is not None else {}).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._send(204, {})

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/state":
                self._send(200, node.dashboard_state())
                return

            if path == "/logs":
                qs = parse_qs(parsed.query)
                since = int(qs.get("since", ["0"])[0])
                self._send(200, {"logs": logger.get_logs(since)})
                return

            if path == "/messages":
                qs = parse_qs(parsed.query)
                since = int(qs.get("since", ["0"])[0])
                self._send(200, {"messages": logger.get_msgs(since)})
                return

            self._send(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path.rstrip("/") or "/"

            if path == "/election":
                threading.Thread(target=node.run_election, daemon=True).start()
                self._send(200, {"ok": True, "action": "election"})
                return

            if path == "/kill":
                node.simulate_kill()
                self._send(200, {"ok": True, "action": "kill"})
                return

            if path == "/revive":
                node.revive()
                self._send(200, {"ok": True, "action": "revive"})
                return

            if path == "/pause":
                node.pause()
                self._send(200, {"ok": True, "action": "pause"})
                return

            if path == "/resume":
                node.resume()
                self._send(200, {"ok": True, "action": "resume"})
                return

            if path == "/request_cs":
                node.force_cs_request()
                self._send(200, {"ok": True, "action": "request_cs"})
                return

            self._send(404, {"error": "not found"})

    return Handler


def start_dashboard_api(node, port: int = 8000):
    """Sobe o servidor HTTP de controle numa thread daemon e o retorna."""
    server = ThreadingHTTPServer(("0.0.0.0", port), _make_handler(node))
    thread = threading.Thread(
        target=server.serve_forever, daemon=True, name="dashboard_api"
    )
    thread.start()
    node.log.net(
        f"Node {node.node_id} | Dashboard API HTTP escutando em 0.0.0.0:{port}"
    )
    return server
