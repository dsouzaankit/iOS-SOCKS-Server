#!python3
# Small Pythonista UI helpers (main-thread UIKit / console).

import sys

UIUserInterfaceStyleDark = 2


def is_pythonista() -> bool:
    return "Pythonista" in sys.executable


def _apply_dark_mode() -> None:
    from objc_util import ObjCClass

    app = ObjCClass("UIApplication").sharedApplication()
    style = UIUserInterfaceStyleDark

    def _style_window(window) -> None:
        if window is None:
            return
        try:
            window.setOverrideUserInterfaceStyle_(style)
        except Exception:
            pass
        try:
            vc = window.rootViewController()
            if vc is not None:
                vc.setOverrideUserInterfaceStyle_(style)
        except Exception:
            pass

    try:
        _style_window(app.keyWindow())
    except Exception:
        pass

    try:
        for window in app.windows():
            _style_window(window)
    except Exception:
        pass

    try:
        for scene in app.connectedScenes():
            try:
                for window in scene.windows():
                    _style_window(window)
            except Exception:
                pass
    except Exception:
        pass


def request_dark_mode() -> bool:
    """Ask iOS to use dark appearance for Pythonista while this script runs."""
    if not is_pythonista():
        return False
    try:
        from objc_util import on_main_thread

        on_main_thread(_apply_dark_mode)()
        return True
    except Exception:
        return False


def keep_screen_awake(enabled: bool = True) -> bool:
    if not is_pythonista():
        return False
    try:
        import console
        from objc_util import on_main_thread

        on_main_thread(console.set_idle_timer_disabled)(bool(enabled))
        return True
    except Exception:
        return False
