"""Logging visualmente didatico (ANSI + emojis) para a demonstracao em video.

Cada no recebe uma cor propria (para diferenciar os nos no terminal) e cada
tipo de evento recebe um emoji/tag proprio (para diferenciar os algoritmos).
Toda a escrita no stdout passa por um Lock global, pois o servidor gRPC usa
multiplas threads e prints concorrentes embaralhariam as linhas.

Alem de imprimir no terminal, cada evento e gravado num buffer em memoria
(ring buffer) para que o dashboard web (dashboard_api.py) possa consultar os
logs estruturados via HTTP e exibi-los ao vivo, coloridos por no e por
algoritmo. O terminal continua funcionando exatamente como antes.
"""

import sys
import threading
import time

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Paleta de cores ANSI (foreground) usada para diferenciar os nos.
_PALETTE = [
    "\033[36m",  # ciano
    "\033[32m",  # verde
    "\033[33m",  # amarelo
    "\033[35m",  # magenta
    "\033[34m",  # azul
    "\033[31m",  # vermelho
    "\033[96m",  # ciano claro
    "\033[92m",  # verde claro
]

# Emojis por nivel de evento do Ricart-Agrawala.
_RICART_EMOJI = {
    "want": "🟡",
    "defer": "🔴",
    "grant": "🟢",
    "enter": "✅",
    "release": "🔵",
    "info": "⚪",
}

# Lock global de escrita: garante que cada linha de log saia inteira.
_print_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Ring buffer de logs estruturados (consumido pelo dashboard via HTTP).
# Cada entrada: {seq, time, node, category, level, msg}. O `seq` e um contador
# monotonico por PROCESSO (cada no e um processo/conteiner separado), o que
# permite ao dashboard buscar apenas o que e novo (?since=<ultimo_seq>).
# ---------------------------------------------------------------------------
_BUFFER_MAX = 2000
_log_buffer = []
_log_seq = 0
_buffer_lock = threading.Lock()


def _record(node_id: int, category: str, level: str, msg: str) -> None:
    global _log_seq
    with _buffer_lock:
        _log_seq += 1
        _log_buffer.append(
            {
                "seq": _log_seq,
                "time": time.strftime("%H:%M:%S"),
                "node": node_id,
                "category": category,
                "level": level,
                "msg": msg,
            }
        )
        excess = len(_log_buffer) - _BUFFER_MAX
        if excess > 0:
            del _log_buffer[:excess]


def get_logs(since: int = 0):
    """Retorna as entradas de log com seq > `since` (para polling incremental)."""
    with _buffer_lock:
        return [e for e in _log_buffer if e["seq"] > since]


# ---------------------------------------------------------------------------
# Ring buffer de MENSAGENS trocadas na rede (consumido pela animacao do painel).
# Cada no registra suas mensagens de SAIDA: {seq, t, src, dst, kind}. O painel
# usa isso para animar um "pacote" viajando do emissor ao receptor.
# ---------------------------------------------------------------------------
_MSG_MAX = 1500
_msg_buffer = []
_msg_seq = 0
_msg_lock = threading.Lock()


def record_msg(src: int, dst: int, kind: str, clock: int) -> None:
    """Registra a CHEGADA de uma mensagem `src`->`dst` do tipo `kind`.

    `clock` e o valor do relogio de Lamport do destino JA ATUALIZADO por essa
    recepcao. O painel usa isso para atualizar o numero exibido exatamente
    quando a bolinha (pacote) pousa no no destino -- animacao e relogio 100%
    sincronizados.
    """
    global _msg_seq
    with _msg_lock:
        _msg_seq += 1
        _msg_buffer.append(
            {
                "seq": _msg_seq,
                "t": time.time(),
                "src": src,
                "dst": dst,
                "kind": kind,
                "clock": clock,
            }
        )
        excess = len(_msg_buffer) - _MSG_MAX
        if excess > 0:
            del _msg_buffer[:excess]


def get_msgs(since: int = 0):
    """Retorna as mensagens com seq > `since` (para animar apenas as novas)."""
    with _msg_lock:
        return [m for m in _msg_buffer if m["seq"] > since]


def enable_ansi() -> None:
    """Habilita sequencias ANSI e UTF-8 no stdout.

    No Linux (conteineres Docker) ja funciona; no Windows precisamos habilitar
    o Virtual Terminal Processing e forcar UTF-8 para os emojis nao quebrarem.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            # -11 = STD_OUTPUT_HANDLE; 7 = ENABLE_PROCESSED_OUTPUT |
            # ENABLE_WRAP_AT_EOL_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


class NodeLogger:
    """Logger por no, com cor fixa e helpers por tipo de evento."""

    def __init__(self, node_id: int):
        self.node_id = node_id
        self.color = _PALETTE[node_id % len(_PALETTE)]

    def _emit(self, text: str, category: str, msg: str, level: str = "info") -> None:
        stamp = time.strftime("%H:%M:%S")
        line = f"{self.color}{DIM}[{stamp}]{RESET}{self.color} {text}{RESET}"
        with _print_lock:
            print(line, flush=True)
        _record(self.node_id, category, level, msg)

    # --- Eventos por algoritmo ---

    def lamport(self, msg: str) -> None:
        self._emit(f"🟢 [LAMPORT] {msg}", "lamport", msg)

    def ricart(self, msg: str, level: str = "info") -> None:
        emoji = _RICART_EMOJI.get(level, "⚪")
        self._emit(f"{emoji} [RICART]  {msg}", "ricart", msg, level)

    def bully(self, msg: str) -> None:
        self._emit(f"👑 [BULLY]   {msg}", "bully", msg)

    # --- Eventos gerais ---

    def net(self, msg: str) -> None:
        self._emit(f"📡 [NET]     {msg}", "net", msg)

    def info(self, msg: str) -> None:
        self._emit(f"ℹ️  [INFO]    {msg}", "info", msg)

    def warn(self, msg: str) -> None:
        self._emit(f"⚠️  [WARN]    {msg}", "warn", msg, level="warn")

    def error(self, msg: str) -> None:
        self._emit(f"❌ [ERROR]   {msg}", "error", msg, level="error")
