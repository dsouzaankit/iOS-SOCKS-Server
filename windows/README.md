# Windows setup (per PC)

All Windows-side scripts and config live in this folder (same layout as Loop Segments `windows/`).

## Files

| File | Purpose |
|------|---------|
| `ios-socks-windows.example.json` | Template — copy to `ios-socks-windows.json` |
| `ios-socks-windows.json` | **Your** phone IP, ports, iCloud path (gitignored) |
| `Set-IOSSocksWindows.ps1` | Create or update config (`-Show` for diagnostics) |
| `windows-proxy.ps1` | Enable/disable PAC proxy (registry + WinINET connection blob) |
| `WinInet-ProxySettings.ps1` | Low-level PAC blob writer (dot-sourced) |
| `Socks-Proxy-On.cmd` | One-click **ON** (PAC proxy from config) |
| `Socks-Proxy-Off.cmd` | One-click **OFF** (restores prior proxy) |
| `Install-SocksDailyShortcuts.ps1` | Desktop shortcuts to the `.cmd` pair |
| `IOS-Socks-Windows.ps1` | Shared config loader (dot-sourced; do not run directly) |
| [potplayer/](potplayer/README.md) | Optional PotPlayer proxy calibration + toggle |

## First time on this PC

```powershell
cd windows
Copy-Item ios-socks-windows.example.json ios-socks-windows.json
.\Set-IOSSocksWindows.ps1 -PhoneHost 10.0.100.10
```

## Daily use — one-click pair

1. Run **`socks5.py`** on the iPhone (keep Pythonista in the foreground).
2. Double-click **`Socks-Proxy-On.cmd`** in this folder.
3. When done, double-click **`Socks-Proxy-Off.cmd`**.

Pin to the desktop once:

```powershell
.\Install-SocksDailyShortcuts.ps1
```

PowerShell equivalent:

```powershell
.\windows-proxy.ps1 -Action On
.\windows-proxy.ps1 -Action Off
.\windows-proxy.ps1 -Action Status
```

## Config fields (`ios-socks-windows.json`)

| Field | Purpose |
|-------|---------|
| `phoneLanHost` | iPhone IP from Pythonista banner (hotspot often `172.20.10.1`) |
| `wpadPort` | PAC / WPAD port (default **8088**) |
| `socksPort` | SOCKS port (default **9876**) |
| `httpPort` | HTTP proxy port (default **9877**) |
| `lanDebugPort` | LAN log server (default **8765**; change if Loop Segments uses 8765) |
| `iCloudDownloads` | Folder for `deploy.ps1` zip copy (optional) |
| `potPlayerProxy` | When `true`, On/Off also apply calibrated PotPlayer proxy patches |
| `potPlayerRegKey` | Registry app key under `HKCU\Software\Daum\` (default `PotPlayerMini64`) |

Legacy one-line **`ios-socks-phone-ip.txt`** is still read/written (gitignored).

## Media players and PAC

**`Socks-Proxy-On.cmd` / `windows-proxy.ps1`** turn on Windows **PAC** (setup script → phone WPAD). That is **not** a guarantee that every app uses the phone.

| App type | Typical behavior |
|----------|------------------|
| Edge, Chrome, many WinINET apps | Often use PAC when proxy is On |
| PotPlayer, VLC, MPC-HC, mpv, most players | Usually **ignore PAC** and often **ignore** system manual HTTP too; use **in-app** proxy or Proxifier |

Players usually connect straight to `https://…` on port 443. PAC only helps apps that ask Windows for a proxy rule first.

**What to do for streaming**

1. Keep **Socks-Proxy-On** for browsers and apps that respect system proxy.
2. In each player: **SOCKS5** → `phoneLanHost`:**`socksPort`** (9876) or **HTTP** → `phoneLanHost`:**`httpPort`** (9877).
3. **PotPlayer + Clash:** [potplayer/README.md](potplayer/README.md#clash--mihomo-recommended-for-potplayer) — use `potplayer/clash-potplayer.example.yaml` (TUN + `PROCESS-NAME`; **`fallback`** group with `interval` for SOCKS→HTTP→DIRECT).
4. **PotPlayer without Clash:** same folder — `potPlayerProxy: true` + calibration, or F5 → SOCKS5.
5. **Proxifier** (or similar): force a given `.exe` through SOCKS/HTTP when the app has no proxy UI.

**Sanity check:** With proxy On, load a site in **Edge** and watch Pythonista or `http://<phone-ip>:8765/`. If the browser hits the phone but the player does not, PAC is working — the player is bypassing it.

### Off does not clear Settings → Proxy

**Off** restores what you had before **On**, or fully disables PAC if the backup file is already gone. Windows also stores proxy in a **connection blob**; if that blob was not restored, Settings could still show “Use setup script”.

1. Run **`Socks-Proxy-Off.cmd`** and read the message — expect `Setup script and manual proxy are off`.
2. If PAC is still on, delete `%LOCALAPPDATA%\iOS-SOCKS-Server-proxy-backup.json` and run **Off** again.
3. Run **On** again before the next tether session so a new backup is saved.
