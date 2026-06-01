#!python3
# Safe mode: LAN log server only (no proxy). Run after a crash to read persisted logs.
#
#   python debug_server.py
#   python debug_server.py --port 8765
#   python socks5.py --safe
#
# Open from PC: http://<phone-ip>:8765/

import asyncio
import sys

LISTEN_HOST = "0.0.0.0"
LAN_DEBUG_PORT = 8765
REQUEST_DARK_MODE = True
KEEP_SCREEN_AWAKE = True

if "Pythonista" in sys.executable:
    try:
        from lib.ios_ui import keep_screen_awake, request_dark_mode

        if REQUEST_DARK_MODE:
            request_dark_mode()
        if KEEP_SCREEN_AWAKE:
            keep_screen_awake(True)
    except Exception:
        pass


def _parse_port() -> int:
    for i, arg in enumerate(sys.argv):
        if arg in ("--port", "-p") and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return LAN_DEBUG_PORT


def run_safe_mode(port: int | None = None) -> None:
    from lib.log_paths import ensure_log_dirs, write_ok_probe
    from lib.lan_debug_server import run_lan_debug_server

    port = LAN_DEBUG_PORT if port is None else port
    ensure_log_dirs()
    write_ok_probe(mode="safe")
    print("Safe mode — LAN log server only (no proxy)", flush=True)
    print("Log dir:", ensure_log_dirs(), flush=True)
    print("Open http://<phone-ip>:{}/".format(port), flush=True)
    try:
        asyncio.run(run_lan_debug_server(LISTEN_HOST, port, safe_mode=True))
    except KeyboardInterrupt:
        print("Stopped.", flush=True)


if __name__ == "__main__":
    run_safe_mode(_parse_port())
