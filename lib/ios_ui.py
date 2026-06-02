#!python3
# Small Pythonista UI helpers (main-thread UIKit / console).

import sys

UIUserInterfaceStyleDark = 2
_TOUCH_SHIELD_TAG = 0x50C05


def is_pythonista() -> bool:
    return "Pythonista" in sys.executable


def _iter_app_windows(app):
    seen = []
    try:
        window = app.keyWindow()
        if window is not None:
            seen.append(window)
            yield window
    except Exception:
        pass
    try:
        for window in app.windows():
            if window is not None and window not in seen:
                seen.append(window)
                yield window
    except Exception:
        pass
    try:
        for scene in app.connectedScenes():
            try:
                for window in scene.windows():
                    if window is not None and window not in seen:
                        seen.append(window)
                        yield window
            except Exception:
                pass
    except Exception:
        pass


def _remove_touch_shields(window) -> None:
    try:
        for subview in window.subviews():
            try:
                if subview.tag() == _TOUCH_SHIELD_TAG:
                    subview.removeFromSuperview()
            except Exception:
                pass
    except Exception:
        pass


def _apply_touch_block(enabled: bool) -> None:
    from objc_util import ObjCClass

    app = ObjCClass("UIApplication").sharedApplication()
    if not enabled:
        for window in _iter_app_windows(app):
            _remove_touch_shields(window)
        return

    UIView = ObjCClass("UIView")
    UIColor = ObjCClass("UIColor")
    # UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight
    flex = 18
    for window in _iter_app_windows(app):
        _remove_touch_shields(window)
        try:
            shield = UIView.alloc().initWithFrame_(window.bounds())
            shield.setTag_(_TOUCH_SHIELD_TAG)
            shield.setAutoresizingMask_(flex)
            shield.setBackgroundColor_(UIColor.clearColor())
            shield.setUserInteractionEnabled_(True)
            window.addSubview_(shield)
            window.bringSubviewToFront_(shield)
        except Exception:
            pass


def block_touch_input(enabled: bool = True) -> bool:
    """Full-screen UIKit overlay that absorbs taps (no Pythonista ui module)."""
    if not is_pythonista():
        return False
    try:
        from objc_util import on_main_thread

        on_main_thread(_apply_touch_block)(bool(enabled))
        return True
    except Exception:
        return False


def restore_touch_input() -> bool:
    return block_touch_input(False)


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

    for window in _iter_app_windows(app):
        _style_window(window)


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
