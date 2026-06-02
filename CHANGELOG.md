# Changelog

## 2026-06-02

### iOS lifecycle and restart

- **Auto-exit on background / screen lock** (`EXIT_WHEN_BACKGROUNDED`, `EXIT_TERMINATE_PYTHONISTA`, `EXIT_GRACE_SECONDS` in `socks5.py`): registers UIKit notifications via `lib/ios_lifecycle.py`, requests proxy shutdown, then suspends and exits Pythonista after a short grace period. Releases ports when you leave the app or lock the device without a stuck background proxy.
- **Block touch input** (`BLOCK_TOUCH_INPUT` in `socks5.py`): transparent UIKit overlay via `lib/ios_ui.py` absorbs taps while the proxy runs; in-app Stop is disabled unless set to `False`.
- **In-process restart** (`GET http://<phone-ip>:8765/restart`): bounces SOCKS/HTTP/WPAD listeners while `socks5.py` keeps running; for stuck clients or settings changes from a PC on the same LAN (or `127.0.0.1` on the phone).
- **Control file + `/shutdown`** on the LAN debug server for coordinated stop.

### Shortcuts / launcher

- **Home screen URL** is cold start only: `pythonista3://RunSOCKSProxy.py?action=run` (no `argv=--restart`).
- Banner emphasizes **Force-restart proxy from LAN** using the phone IP from the banner; removed pythonista3 restart advisory.
- `RunSOCKSProxy.py` launcher v11: dropped `--restart` stub path; points to LAN `/restart` if ports are already in use.

### Fixes

- **LAN `/restart`:** close WPAD (`shutdown` + `server_close` + thread join), cancel and close asyncio SOCKS/HTTP servers, wait for ports before rebinding — fixes **errno 48** on in-process restart.
- `initial_output = ""` before interface detection so startup does not crash with `NameError` when `ifaddrs` fails.
- `ios_lifecycle` observer handler: no return-type annotation (Pythonista `objc_util` / `inspect.getargspec` incompatibility).
- Port-in-use check uses `connect_ex` instead of `bind` for reliability.

### Docs

- README: auto-exit section, LAN force-restart vs home-screen cold start, Error 48 troubleshooting updated.
