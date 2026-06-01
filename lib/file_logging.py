#!python3
# File logging — atomic latest log + session history (Loop Segments style).

import logging
import sys
import threading
import traceback
from typing import Optional

from . import log_paths

_file_writer: Optional["FileLogWriter"] = None


class FileLogWriter:
    """Writes ISO8601 lines to proxy_latest.txt and the current session file."""

    def __init__(self, session_path: str):
        self._session_path = session_path
        self._lock = threading.Lock()
        self._lines: list[str] = []

    def log_line(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)
            body = "".join(self._lines).encode("utf-8")
            log_paths._atomic_write(log_paths.latest_log_path(), body)
            log_paths._atomic_write(self._session_path, body)
            tail = self._lines[-12:]
            log_paths._atomic_write(
                log_paths.progress_log_path(),
                "".join(tail).encode("utf-8"),
            )

    def log(self, message: str) -> None:
        self.log_line("{} {}\n".format(log_paths._iso_now(), message))


class FileLogHandler(logging.Handler):
    def __init__(self, writer: FileLogWriter, level: int = logging.NOTSET):
        super().__init__(level)
        self._writer = writer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._writer.log_line(
                "{} [{}] {}\n".format(
                    log_paths._iso_now(),
                    record.levelname,
                    msg,
                )
            )
        except Exception:
            pass


def get_file_writer() -> Optional[FileLogWriter]:
    return _file_writer


def setup_file_logging(level: int = logging.INFO) -> FileLogWriter:
    global _file_writer
    log_paths.ensure_log_dirs()
    log_paths.prune_old_logs()
    log_paths.clear_crash_marker()
    session = log_paths.new_session_log_path()
    _file_writer = FileLogWriter(session)
    _file_writer.log("=== session {} ===".format(session))
    root = logging.getLogger()
    root.setLevel(level)
    handler = FileLogHandler(_file_writer, level=level)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root.addHandler(handler)
    return _file_writer


def log_banner(text: str) -> None:
    writer = _file_writer
    if writer is None:
        return
    for line in text.splitlines():
        writer.log(line)


def install_crash_hooks() -> None:
    def _excepthook(exc_type, exc, tb):
        msg = "".join(traceback.format_exception(exc_type, exc, tb))
        writer = _file_writer
        if writer is not None:
            writer.log("FATAL uncaught exception:")
            for line in msg.splitlines():
                writer.log(line)
        log_paths.write_crash_marker(exc)
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook


def log_crash(exc: BaseException) -> None:
    writer = _file_writer
    if writer is not None:
        writer.log("FATAL proxy crash: {}: {}".format(type(exc).__name__, exc))
        writer.log(traceback.format_exc())
    log_paths.write_crash_marker(exc)
