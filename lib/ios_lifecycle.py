#!python3
"""Exit proxy / Pythonista when the app is backgrounded or the screen locks."""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Callable, Optional

_observer: object | None = None
_last_dispatch = 0.0
_dispatch_lock = threading.Lock()


def is_pythonista() -> bool:
    return "Pythonista" in sys.executable


def terminate_pythonista() -> None:
    """Best-effort suspend + hard exit (in-house / personal use)."""
    try:
        from objc_util import ObjCClass

        ObjCClass("UIApplication").sharedApplication().performSelector_("suspend")
    except Exception:
        pass
    os._exit(0)


def schedule_terminate_pythonista(delay: float = 2.0) -> None:
    def _run() -> None:
        time.sleep(max(0.0, delay))
        terminate_pythonista()

    threading.Thread(target=_run, name="ios-terminate", daemon=True).start()


def _dispatch(callback: Callable[[str], None], reason: str) -> None:
    global _last_dispatch
    with _dispatch_lock:
        now = time.monotonic()
        if now - _last_dispatch < 1.0:
            return
        _last_dispatch = now
    try:
        callback(reason)
    except Exception as exc:
        print("lifecycle callback failed:", exc, flush=True)


def install_exit_on_background(
    callback: Callable[[str], None],
    *,
    on_background: bool = True,
    on_screen_lock: bool = True,
) -> bool:
    """Register UIKit notifications; callback receives 'background' or 'screen_lock'."""
    global _observer
    if not is_pythonista():
        return False
    if _observer is not None:
        return True

    try:
        from objc_util import ObjCClass, ObjCInstance, create_objc_class
    except ImportError:
        return False

    notification_names: list[str] = []
    if on_background:
        notification_names.append("UIApplicationDidEnterBackgroundNotification")
    if on_screen_lock:
        notification_names.append(
            "UIApplicationProtectedDataWillBecomeUnavailableNotification"
        )
    if not notification_names:
        return False

    def lifecycle_handler(_self, _cmd, notification):
        reason = "background"
        try:
            name = str(ObjCInstance(notification).name())
            if "ProtectedData" in name:
                reason = "screen_lock"
            elif "EnterBackground" in name:
                reason = "background"
        except Exception:
            pass
        _dispatch(callback, reason)

    lifecycle_handler.encoding = "v@:@"

    Observer = create_objc_class(
        "SocksProxyLifecycleObserver",
        methods=[lifecycle_handler],
    )
    observer = Observer.alloc().init()
    center = ObjCClass("NSNotificationCenter").defaultCenter()
    for name in notification_names:
        center.addObserver_selector_name_object_(
            observer, "lifecycle_handler:", name, None
        )
    _observer = observer
    return True


def uninstall_exit_on_background() -> None:
    global _observer
    if _observer is None:
        return
    try:
        from objc_util import ObjCClass

        center = ObjCClass("NSNotificationCenter").defaultCenter()
        center.removeObserver_(_observer)
    except Exception:
        pass
    _observer = None
