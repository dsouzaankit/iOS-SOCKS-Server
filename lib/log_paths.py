#!python3
# Log directory layout (mirrors Loop Segments: latest + history + ok probe).

import os
import sys
import time
from typing import List

LOG_DIR_NAME = "logs"
APP_DIR_NAME = "socks_proxy"
LATEST_LOG = "proxy_latest.txt"
PROGRESS_LOG = "proxy_progress.txt"
OK_PROBE = "proxy_ok.txt"
CRASH_MARKER = "proxy_crash.txt"
LOG_RETENTION_COUNT = 40

_version = "SOCKS Proxy (Pythonista)"


def is_pythonista() -> bool:
    return "Pythonista" in sys.executable


def app_root() -> str:
    if is_pythonista():
        return os.path.join(os.path.expanduser("~"), "Documents", APP_DIR_NAME)
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), APP_DIR_NAME
    )


def log_dir() -> str:
    return os.path.join(app_root(), LOG_DIR_NAME)


def latest_log_path() -> str:
    return os.path.join(log_dir(), LATEST_LOG)


def progress_log_path() -> str:
    return os.path.join(log_dir(), PROGRESS_LOG)


def ok_probe_path() -> str:
    return os.path.join(log_dir(), OK_PROBE)


def crash_marker_path() -> str:
    return os.path.join(log_dir(), CRASH_MARKER)


def ensure_log_dirs() -> str:
    root = app_root()
    logs = log_dir()
    os.makedirs(logs, exist_ok=True)
    return logs


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_ok_probe(mode: str = "full") -> None:
    ensure_log_dirs()
    body = "{} mode={} started={}\n".format(_version, mode, _iso_now())
    _atomic_write(ok_probe_path(), body.encode("utf-8"))


def write_crash_marker(exc: BaseException | None = None) -> None:
    ensure_log_dirs()
    lines = ["crash_at={}".format(_iso_now())]
    if exc is not None:
        lines.append("error={}: {}".format(type(exc).__name__, exc))
    _atomic_write(crash_marker_path(), "\n".join(lines).encode("utf-8") + b"\n")


def clear_crash_marker() -> None:
    try:
        os.remove(crash_marker_path())
    except OSError:
        pass


def new_session_log_path() -> str:
    ensure_log_dirs()
    name = "proxy_{}.txt".format(int(time.time()))
    return os.path.join(log_dir(), name)


def list_history_logs(limit: int = LOG_RETENTION_COUNT) -> List[str]:
    logs = log_dir()
    if not os.path.isdir(logs):
        return []
    names = []
    for name in os.listdir(logs):
        if name.startswith("proxy_") and name.endswith(".txt"):
            if name in (LATEST_LOG, PROGRESS_LOG, OK_PROBE, CRASH_MARKER):
                continue
            names.append(name)
    names.sort(reverse=True)
    return names[:limit]


def _atomic_write(path: str, data: bytes) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def prune_old_logs(keep: int = LOG_RETENTION_COUNT) -> None:
    names = list_history_logs(9999)
    for name in names[keep:]:
        try:
            os.remove(os.path.join(log_dir(), name))
        except OSError:
            pass


def read_text_file(path: str, default: str = "") -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return default
