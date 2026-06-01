#!python3
"""Install a Pythonista script for the Shortcuts app picker."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

logger = logging.getLogger("launcher")

LAUNCHER_NAME = "RunSOCKSProxy.py"
# Removed duplicate names — deleted from On This iPhone on each install.
_STALE_LAUNCHER_NAMES = ("Run SOCKS Proxy.py",)
LAUNCHER_VERSION = 8

_LAUNCHER_TEMPLATE = '''#!/usr/bin/env python3
"""Launch iOS-SOCKS-Server (auto-generated; do not edit)."""
# launcher-version: {version}
import os
import runpy
import sys

_PROXY_DIR = {proxy_dir!r}
_SOCKS5 = os.path.join(_PROXY_DIR, "socks5.py")


def _run_proxy():
    if _PROXY_DIR not in sys.path:
        sys.path.insert(0, _PROXY_DIR)
    runpy.run_path(_SOCKS5, run_name="__main__")


if __name__ == "__main__":
    if not os.path.isfile(_SOCKS5):
        print("socks5.py not found:", _SOCKS5, flush=True)
        raise SystemExit(1)
    print("Starting proxy from", _SOCKS5, flush=True)
    _run_proxy()
'''


def _is_pythonista() -> bool:
    return "Pythonista" in sys.executable


def _launcher_body(proxy_dir: str) -> str:
    return (
        _LAUNCHER_TEMPLATE.replace("{version}", str(LAUNCHER_VERSION))
        .replace("{proxy_dir!r}", repr(proxy_dir))
    )


def _log_launcher(message: str, level: int = logging.INFO) -> None:
    try:
        from . import log_paths
        from .file_logging import get_file_writer

        writer = get_file_writer()
        if writer is not None:
            tag = "ERROR" if level >= logging.ERROR else "INFO"
            writer.log_line(
                "{} [{}] launcher: {}\n".format(log_paths._iso_now(), tag, message)
            )
            return
    except Exception:
        pass
    logger.log(level, message)


def _local_library_dir() -> str:
    return os.path.expanduser("~/Documents")


def _remove_stale_launchers() -> None:
    for name in _STALE_LAUNCHER_NAMES:
        path = os.path.join(_local_library_dir(), name)
        try:
            if os.path.isfile(path):
                os.remove(path)
                _log_launcher("removed stale launcher %s" % name)
        except OSError as exc:
            _log_launcher(
                "could not remove stale %s: %s" % (name, exc), logging.ERROR
            )


def _launcher_install_path() -> str:
    return os.path.join(_local_library_dir(), LAUNCHER_NAME)


@dataclass
class LauncherInstallResult:
    local_path: str | None
    written_paths: list[str]
    proxy_dir: str = ""


def shortcuts_launcher_run_url() -> str:
    """pythonista3:// URL for home-screen / Shortcuts Open URL."""
    try:
        import shortcuts

        return shortcuts.pythonista_url(LAUNCHER_NAME, action="run")
    except (ImportError, ValueError):
        return "pythonista3://RunSOCKSProxy.py?action=run"


def launcher_banner_lines(
    result: LauncherInstallResult, proxy_dir: str | None = None
) -> str:
    if not result.local_path:
        return "Shortcuts launcher: not installed (On This iPhone)\n"
    proxy_dir = proxy_dir or result.proxy_dir
    lines = [
        "Shortcuts: %s on On This iPhone (v%s)" % (LAUNCHER_NAME, LAUNCHER_VERSION),
        "  Home screen Open URL: %s" % shortcuts_launcher_run_url(),
        "  Project: %s" % proxy_dir,
        "  (Removed duplicate: Run SOCKS Proxy.py)",
    ]
    lines.append("")
    return "\n".join(lines)


def install_shortcuts_launcher(
    proxy_dir: str | None = None,
    *,
    quiet: bool = False,
) -> LauncherInstallResult:
    empty = LauncherInstallResult(local_path=None, written_paths=[], proxy_dir="")
    if not _is_pythonista():
        return empty

    proxy_dir = os.path.abspath(proxy_dir or os.path.dirname(os.path.dirname(__file__)))
    _remove_stale_launchers()
    body = _launcher_body(proxy_dir)
    launcher_path = _launcher_install_path()
    written: list[str] = []

    try:
        with open(launcher_path, "w", encoding="utf-8") as f:
            f.write(body)
        written.append(launcher_path)
        _log_launcher("deployed %s (v%s)" % (launcher_path, LAUNCHER_VERSION))
    except OSError as exc:
        _log_launcher(
            "install failed %s: %s" % (launcher_path, exc), logging.ERROR
        )
        if not quiet:
            print("Could not install %s: %s" % (launcher_path, exc), flush=True)

    result = LauncherInstallResult(
        local_path=launcher_path if written else None,
        written_paths=written,
        proxy_dir=proxy_dir,
    )
    if not quiet and result.local_path:
        print(launcher_banner_lines(result, proxy_dir), flush=True)
    return result


def shortcuts_run_url(
    launcher_path: str | None = None, proxy_dir: str | None = None
) -> str:
    return shortcuts_launcher_run_url()


if __name__ == "__main__":
    install_shortcuts_launcher(quiet=False)
