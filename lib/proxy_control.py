#!python3
"""Graceful stop / in-process restart coordination."""

from __future__ import annotations

import os
import socket
import time
import urllib.error
import urllib.request

from . import log_paths

CONTROL_STOP = "stop"
CONTROL_RESTART = "restart"
DEFAULT_PORTS = (9876, 9877, 8088)
DEFAULT_DEBUG_PORT = 8765
DEFAULT_SHUTDOWN_WAIT = 30.0


def clear_shutdown_request() -> None:
    try:
        os.remove(log_paths.control_file_path())
    except OSError:
        pass


def request_shutdown() -> None:
    _write_control(CONTROL_STOP)


def request_restart() -> None:
    _write_control(CONTROL_RESTART)


def _write_control(value: str) -> None:
    log_paths.ensure_log_dirs()
    log_paths._atomic_write(
        log_paths.control_file_path(),
        (value + "\n").encode("utf-8"),
    )


def is_shutdown_requested() -> bool:
    return _read_control() == CONTROL_STOP


def is_restart_requested() -> bool:
    return _read_control() == CONTROL_RESTART


def _read_control() -> str:
    return log_paths.read_text_file(log_paths.control_file_path()).strip()


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def any_proxy_port_in_use(ports: tuple[int, ...] = DEFAULT_PORTS) -> bool:
    return any(port_in_use(port) for port in ports)


def wait_for_ports_free(
    ports: tuple[int, ...] = DEFAULT_PORTS,
    timeout: float = DEFAULT_SHUTDOWN_WAIT,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any_proxy_port_in_use(ports):
            return True
        time.sleep(0.5)
    return not any_proxy_port_in_use(ports)


def stop_running_proxy(
    *,
    debug_port: int = DEFAULT_DEBUG_PORT,
    wait_timeout: float = DEFAULT_SHUTDOWN_WAIT,
) -> bool:
    """Ask a running proxy to stop and wait until its ports are free."""
    if not any_proxy_port_in_use():
        clear_shutdown_request()
        return True

    request_shutdown()
    _try_http_shutdown(debug_port, restart=False)
    if wait_for_ports_free(timeout=wait_timeout):
        clear_shutdown_request()
        return True
    return False


def _try_http_shutdown(
    debug_port: int = DEFAULT_DEBUG_PORT, *, restart: bool = False
) -> None:
    path = "/restart" if restart else "/shutdown"
    url = "http://127.0.0.1:{}{}".format(debug_port, path)
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            resp.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        pass


def prepare_fresh_start(
    *,
    debug_port: int = DEFAULT_DEBUG_PORT,
    wait_timeout: float = DEFAULT_SHUTDOWN_WAIT,
) -> bool:
    if not any_proxy_port_in_use():
        clear_shutdown_request()
        return True

    request_restart()
    _try_http_shutdown(debug_port, restart=True)
    if wait_for_ports_free(timeout=wait_timeout):
        clear_shutdown_request()
        return True
    return False
