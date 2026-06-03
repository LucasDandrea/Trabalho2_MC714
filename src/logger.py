"""Logging visualmente didatico (ANSI + emojis) para a demonstracao em video.

Cada no recebe uma cor propria (para diferenciar os nos no terminal) e cada
tipo de evento recebe um emoji/tag proprio (para diferenciar os algoritmos).
Toda a escrita no stdout passa por um Lock global, pois o servidor gRPC usa
multiplas threads e prints concorrentes embaralhariam as linhas.
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

    def _emit(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        line = f"{self.color}{DIM}[{stamp}]{RESET}{self.color} {text}{RESET}"
        with _print_lock:
            print(line, flush=True)

    # --- Eventos por algoritmo ---

    def lamport(self, msg: str) -> None:
        self._emit(f"🟢 [LAMPORT] {msg}")

    def ricart(self, msg: str, level: str = "info") -> None:
        emoji = _RICART_EMOJI.get(level, "⚪")
        self._emit(f"{emoji} [RICART]  {msg}")

    def bully(self, msg: str) -> None:
        self._emit(f"👑 [BULLY]   {msg}")

    # --- Eventos gerais ---

    def net(self, msg: str) -> None:
        self._emit(f"📡 [NET]     {msg}")

    def info(self, msg: str) -> None:
        self._emit(f"ℹ️  [INFO]    {msg}")

    def warn(self, msg: str) -> None:
        self._emit(f"⚠️  [WARN]    {msg}")

    def error(self, msg: str) -> None:
        self._emit(f"❌ [ERROR]   {msg}")
