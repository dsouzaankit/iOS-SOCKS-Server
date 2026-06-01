# What

A simple HTTP/SOCKS proxy designed to run on Pythonista on iOS, letting you fake-tether your devices to a phone.

## Upstream

This project is a **fork** of [nneonneo/iOS-SOCKS-Server](https://github.com/nneonneo/iOS-SOCKS-Server) ([@nneonneo](https://github.com/nneonneo)). The original `socks5.py` credits [@philrosenthal](https://github.com/philrosenthal) for the statistics view and IPv6 support.

**Fork changes (dsouzaankit):** iOS Shortcuts / `RunSOCKSProxy.py` launcher, LAN file logging and debug server, quiet console mode, Pythonista dark UI / keep-awake helpers, Windows folder (`windows/`) with per-PC config, one-click proxy on/off, `deploy.ps1`, and expanded README.

To compare with upstream: `git fetch upstream` then `git log upstream/master..HEAD`.

# Installation

- Install Pythonista from the [App Store](https://apps.apple.com/us/app/pythonista-3/id1085978097). It's a paid app, but it's worth every penny if you are a power user.
- Clone this fork or download a zip from **this** repo’s GitHub page (see [Upstream](#upstream) for the original project).
- Open the Files app, navigate to Downloads, and tap on the zip file to uncompress it.
- Move the resulting `iOS-SOCKS-Server` folder to the Pythonista iCloud directory
- Open Pythonista, navigate to iCloud, `iOS-SOCKS-Server` and open the `socks5.py` script.
- Optionally, tap the wrench on `socks5.py` → **Shortcuts…** to add a home-screen icon, or use the **iOS Shortcuts** app (see below).

## iOS Shortcuts / home screen

Your project in **Files → iCloud → Downloads** is **not** in Pythonista’s script library. Pythonista can only **run** scripts under **On This iPhone** (or its in-app iCloud library), not arbitrary Files paths.

**`RunSOCKSProxy.py`** is a tiny stub on **On This iPhone** that starts the real **`socks5.py`** using the absolute project path baked in when you run the proxy. You still need that file for a home-screen shortcut — **Open URL** is just *how* you launch it; the URL is `pythonista3://RunSOCKSProxy.py?action=run`, not a path to `socks5.py` in Downloads.

What **Open URL** replaces: the **Run Pythonista Script** shortcut action and the old duplicate **`Run SOCKS Proxy.py`** name. It does **not** replace **`RunSOCKSProxy.py`**.

### Home screen Open URL (recommended)

1. Run **`socks5.py`** once in Pythonista — installs/refreshes **`RunSOCKSProxy.py`** and prints the **Open URL** in the banner.
2. Shortcuts → **Open URL** → paste → **Add to Home Screen**.
3. Do **not** point the URL at `icloud/Downloads/.../socks5.py` (Pythonista will not find it).

### Run Pythonista Script (optional)

Same launcher: **On This iPhone** → **`RunSOCKSProxy.py`** → **Run in Pythonista ON**.

### Without the launcher

- Run **`socks5.py`** inside Pythonista (**Run**) each time, or
- Keep the whole project in **Pythonista’s** iCloud folder and use the wrench **Shortcuts…** menu on `socks5.py` (only works when the script lives in Pythonista’s library, not only in Files → Downloads).

Set `INSTALL_SHORTCUT_LAUNCHER = False` in `socks5.py` only if you will **not** use the home-screen **Open URL** (manual **Run** only). Re-run `socks5.py` with it **True** before using the shortcut again so the stub path stays current after you move the project folder.

# Running

- Connect your devices to the same WiFi network as your phone. If there's no suitable network, you can create a computer-to-computer (ad-hoc) network using your laptop and connect to it with your phone.
- Open the home screen shortcut (if you made one), or open the `socks5.py` script in Pythonista and hit Run. 
- Point your devices at the PAC URL (also called script URL, script address, etc.), or configure them to use the SOCKS proxy listed.
    - For iOS devices: open Settings, tap on Wi-Fi, tap on the (i) icon next to the network, scroll down to HTTP Proxy, tap on Configure Proxy, select Automatic, and enter the PAC URL as displayed in Pythonista in the URL field (the URL will look like http://123.123.123.123:8080/wpad.dat).
    - For macOS: open System Preferences -> Network, click on Wi-Fi, hit Advanced..., and under Proxies check SOCKS Proxy and set the host:port to the SOCKS Address as displayed in Pythonista (this will be of the form 123.123.123.123:9876).
        - If you are using an ad-hoc Wi-Fi network (i.e. Wi-Fi menu -> Create Network), you will need to do some extra setup here. Under the TCP/IP tab, copy the existing 169.254.y.z IPv4 address, then switch Configure IPv4 to Manually, enter the 169.254.y.z IP address in both IPv4 Address and Router, and enter 255.255.0.0 as Subnet Mask. Under the DNS tab, add 169.254.y.z to the DNS Servers list.
        - Make sure you set proxy settings in any other application that is not using the system proxy settings.
    - For **Windows 10/11** (same Wi‑Fi as the phone; use the PAC URL from the Pythonista banner, e.g. `http://172.20.10.1:8088/wpad.dat`):
        1. **Settings** → **Network & Internet** → **Proxy** (or search “proxy” in Settings).
        2. Under **Automatic proxy setup**, turn **Use setup script** **On**.
        3. **Script address**: paste the **PAC URL** exactly as shown in Pythonista (`http://<phone-ip>:8088/wpad.dat`).
        4. Save and leave the page. Open a browser and confirm traffic goes through the phone (check the Pythonista console or `http://<phone-ip>:8765/` if LAN debug is on).
        - **Manual HTTP proxy** (if PAC does not work): under **Manual proxy setup**, turn **Use a proxy server** **On**, set **Address** to the phone IP and **Port** to **9877** (HTTP proxy from the banner). SOCKS is not exposed in this screen; prefer the PAC URL so both HTTP and SOCKS5 are configured.
        - **Windows scripts:** everything is under [windows/](windows/README.md) — config, proxy toggle, and one-click `.cmd` files.
        - **Per-PC config:** copy `windows/ios-socks-windows.example.json` → `windows/ios-socks-windows.json`, then `.\windows\Set-IOSSocksWindows.ps1 -PhoneHost <phone-ip>`.
        - **One-click daily pair** (after `socks5.py` is running): `windows\Socks-Proxy-On.cmd` / `windows\Socks-Proxy-Off.cmd`, or `.\windows\Install-SocksDailyShortcuts.ps1` for desktop shortcuts.
        - **PowerShell:** `cd windows` then `.\windows-proxy.ps1 -Action On` / `-Action Off`. Backs up proxy once before **On**; **Off** restores. Per-user only (not `netsh winhttp`).
        - **Classic dialog**: Win+R → `inetcpl.cpl` → **Connections** → **LAN settings** → check **Use automatic configuration script** and enter the same PAC URL. Useful if Settings and legacy apps disagree.
        - **Media players and PAC:** `Socks-Proxy-On.cmd` sets Windows **PAC** (WinINET). That works for many **browsers** and some desktop apps. **Most media players** (PotPlayer, VLC, MPC-HC, mpv, etc.) open **direct TCP** to CDNs and **do not read PAC** — even when Settings shows “Use setup script”. For **PotPlayer on Windows**, the recommended setup is **Clash Verge (Mihomo) + TUN** using [windows/potplayer/clash-potplayer.example.yaml](windows/potplayer/clash-potplayer.example.yaml) (see [windows/potplayer/README.md](windows/potplayer/README.md)). Alternatives: in-player SOCKS5, `PotPlayer-Proxy-Calibrate.cmd`, or Proxifier.
        - Optional: [SSTap](https://sourceforge.net/projects/sstap/) can force more traffic through a proxy; this project is not affiliated with SSTap and cannot support it.
    - For **Linux**, use your desktop environment’s network proxy settings with the **PAC URL** if supported, or set HTTP proxy to `<phone-ip>:9877` and SOCKS5 to `<phone-ip>:9876` manually.
    - For Android: open Settings, Wi-Fi, select your network, expand the Advanced Settings, change the proxy setting to Manual, and enter the host and port for the *HTTP proxy*. Note that SOCKS proxy support on Android is limited, even when using the PAC URL, so the HTTP proxy is recommended.
        - Many applications on Android do not respect proxy settings, unfortunately, and in those cases you will have to configure the apps manually or use an app like Proxifier to force apps to use the proxy.

## Stopping on Pythonista

Tapping **Stop** in Pythonista usually works, but shutdown is **slow — often up to ~30 seconds** with active connections. The script must unwind proxy tunnels, the WPAD thread, and the asyncio event loop; until then the console may look stuck and ports **9876/9877/8088** can stay open briefly.

- **Wait for `Shutting down.` in the console** before you tap **Run** again. That line means the `KeyboardInterrupt` handler finished and it is safe to restart.
- If Stop seems hung, give it **up to ~30 seconds** while clients disconnect.
- If there is still no `Shutting down.` after ~30s, **force quit Pythonista** from the app switcher (swipe away), then reopen and run again.
- Before redeploying from a PC, force quit Pythonista so log files and listeners are fully released (faster than waiting for Stop).

# Why

Recently, while travelling, I found out that Google Fi doesn't support tethering on iOS (I guess it's a feature they want to keep Android-exclusive or something?). Since my phone has a nice, fast, unblocked connection, I wanted to let my computer access it too.

I previously wrote [Socks5-iOS](https://github.com/nneonneo/socks5-ios) for doing exactly this, but it turned out to be quite cumbersome to deploy and modify. Plus, the app expires frequently (if you don't have an iOS developer account), which makes it annoying if you need it in a pinch. Enter Pythonista - an App Store app which puts a complete Python interpreter on iOS.

This script can be used to implement a functional alternative to tethering, which I refer to fake-tethering. Fake-tethering has some substantial advantages over standard iOS tethering. It works even when carriers ban tethering, and it bypasses limits set on tethering speed since all connections originate from the phone.

While it's easiest to use this with websites, it's actually possible to tunnel any TCP connection over a SOCKS proxy. For example, here's how you would proxy an SSH connection:

`ssh -o ProxyCommand='nc -X 5 -x <IP>:9876 %h %p' user@host`

# Troubleshooting

## Error 48: Address already in use

On iOS/macOS, **errno 48** means a port the proxy needs is still held by a **previous run** (or another app). The script binds **9876** (SOCKS), **9877** (HTTP), **8088** (WPAD), and optionally **8765** (LAN debug).

**Typical causes**

- **Run** was tapped again before the last instance finished stopping (see [Stopping on Pythonista](#stopping-on-pythonista) — often **~30 seconds**).
- Pythonista was left in the background with the proxy still listening.
- The proxy was started twice (e.g. home screen **Open URL** while `socks5.py` is already running).

**Fix (in order)**

1. In Pythonista, tap **Stop** on `socks5.py` and wait until the console prints **`Shutting down.`** (up to ~30s). Then tap **Run** once.
2. If the error persists or there is no `Shutting down.` line, **force quit Pythonista** (app switcher → swipe away), reopen, and run **`socks5.py`** once — do not use the home screen shortcut until the proxy is up.
3. Before redeploying from a PC, force quit Pythonista so ports and log files are released (see [Deploy workflow](#deploy-workflow-pc--iphone-via-icloud)).
4. Only start the proxy **one way at a time** (either **Run** in Pythonista or the home screen URL, not both in quick succession).

If 48 still appears after a force quit, restart the iPhone (rare stuck listener). If another tool uses the same ports, change `SOCKS_PORT`, `HTTP_PORT`, `WPAD_PORT`, and/or `LAN_DEBUG_PORT` at the top of `socks5.py` and update client proxy/PAC settings to match.

## SOCKS5 (9876) stuck but HTTP (9877) works

Some clients (Clash, Proxifier **Check**, etc.) hung on **SOCKS5** while **HTTP** on **9877** worked. Two bugs in `lib/socks5_server.py`: missing `drain()` after the auth reply, and the SOCKS version byte was replayed so `nmethods` was read as `5` instead of `1`. Both fixed — **re-run / redeploy `socks5.py` on the phone** after updating.

Until then, point Clash or Proxifier at **HTTP** `phone-ip:9877` instead of SOCKS `9876`.

## Error 32: Broken pipe (`BrokenPipeError`, `EPIPE`)

On iOS/macOS/Windows clients talking to the phone proxy, **errno 32** means the **other side closed the TCP connection while your side was still writing**. Python reports this as `BrokenPipeError: [Errno 32] Broken pipe`. It is **not** “the proxy is broken” — it usually means a **normal early disconnect** on that one connection.

**Typical log line**

```text
http: 10.0.100.48:11552: BrokenPipeError: [Errno 32] Broken pipe
```

The IP is your PC or device (`10.0.100.48`); the proxy on the phone was forwarding when the client hung up.

**Common causes (usually harmless)**

- Browser or app **closed a tab**, cancelled a request, or finished a **PAC / WPAD** fetch (`/wpad.dat`) and dropped the socket.
- **`CONNECT` tunnel** ended (user navigated away, HTTP/2 reset, antivirus or proxy inspector cut the connection).
- Windows **turned proxy on/off** (`Socks-Proxy-Off.cmd`) while connections were still open.
- Idle tunnel closed by client, server, or middlebox; phone writes one more packet → broken pipe.

Related: **errno 54** (`ECONNRESET`, `Connection reset by peer`) is the same class of client/server hang-up. The HTTP proxy treats both as benign disconnects.

**When you can ignore it**

- Appears **occasionally** in `proxy_latest.txt` or LAN debug.
- **Browsing and apps still work** through the proxy.
- No matching **502 Bad Gateway** or “Unable to connect to host” for the site you care about.

Current code logs these at **debug** on the HTTP handler (not as a proxy failure). SOCKS handshake drops are ignored the same way.

**When to investigate**

- **Many** broken pipes per second while pages fail to load.
- Same time as **502**, DNS errors, or zero traffic on the LAN debug page.
- Only happens when Pythonista is **backgrounded** or the phone sleeps — see startup banner: keep Pythonista **in the foreground**.

**Remedy (in order)**

1. **Retry the page** — often a one-off cancelled request.
2. Confirm **`socks5.py` is running** and the PC uses the correct PAC URL / phone IP ([windows/](windows/README.md)).
3. **Toggle proxy off and on** on Windows (`Socks-Proxy-Off.cmd` then `Socks-Proxy-On.cmd`) after changing settings.
4. If errors flood and nothing loads: **Stop** proxy (wait for `Shutting down.`), force quit Pythonista if needed, **Run** once — same as [Error 48](#error-48-address-already-in-use).
5. If one app always fails but others work, that app may not honor system proxy; configure it directly or use a per-app proxy tool.

**Not the same as**

- **[Error 48](#error-48-address-already-in-use)** — port already in use at startup.
- **WinHTTP / `netsh winhttp`** — separate from WinINET PAC; broken pipe here is on the phone’s HTTP/SOCKS ports (9877 / 9876).

## Doesn't work with an ad-hoc network on macOS

macOS appears to incorrectly assess the Internet as unreachable with an ad-hoc network, even if a proxy is configured. A workaround for this, tested on macOS 10.14, is described under [issue #1](https://github.com/nneonneo/iOS-SOCKS-Server/issues/1#issuecomment-583989079).

## Logs and LAN debug (port 8765)

While the proxy runs, logs are written under **Pythonista → Documents → `socks_proxy/logs/`** (`proxy_latest.txt`, session history, crash marker).

From your PC on the same Wi‑Fi: **`http://<phone-ip>:8765/`** (live tail, history, `status.json`).

**After a crash** (proxy won't start): run safe mode to view logs only:

```text
python debug_server.py
# or
python socks5.py --safe
```

Port **8765** may conflict with Loop Segments or other tools — change `LAN_DEBUG_PORT` in `socks5.py` and `debug_server.py`.

## Deploy workflow (PC → iPhone via iCloud)

Use this when editing on Windows and syncing to Pythonista over iCloud Drive.

### 1. Force quit Pythonista on the iPhone

Before running deploy on the PC:

- Open the app switcher (swipe up from the bottom edge, or double-click Home on older phones).
- Swipe **Pythonista** away to kill it.

This stops the proxy and closes open log files. In-app **Stop** can take **up to ~30 seconds** (wait for `Shutting down.` in the console); force quit is faster and more reliable when redeploying.

### 2. Delete the old project folder in Files

Still on the iPhone, open **Files** and delete **`iOS-SOCKS-Server-master`** wherever you find it:

- **iCloud Drive → Downloads** — remove the old extracted folder (not just the zip)
- **Pythonista** (iCloud or On My iPhone) — remove the copy you run `socks5.py` from

Do this **after** force quitting Pythonista and **before** running `deploy.ps1` on the PC. Skipping this step often leaves stale files and makes iCloud re-upload the old folder to your PC.

### 3. Run deploy on the PC

From the project folder on Windows (optional: set `iCloudDownloads` in `windows/ios-socks-windows.json` via `.\windows\Set-IOSSocksWindows.ps1`):

```powershell
cd P:\all_scripts\iOS-SOCKS-Server
.\deploy.ps1
```

The script:

1. Deletes old `iOS-SOCKS-Server-master.zip` and `iOS-SOCKS-Server-master\` from  
   `C:\Users\dsouzaankit\iCloudDrive\Downloads`
2. Zips the project (skips `.git`, `__pycache__`, editor junk)
3. Copies the new zip into that iCloud Downloads folder

Wait a minute for iCloud to sync the zip to the iPhone.

### 4. Install on the iPhone

1. **Files** → **iCloud Drive** → **Downloads**
2. Tap **`iOS-SOCKS-Server-master.zip`** to unzip
3. Move or replace the folder in **Pythonista** (iCloud or On My iPhone — wherever you run `socks5.py` from)
4. Open **`socks5.py`** in Pythonista and tap **Run**

### iCloud sync note

iCloud is two-way. If the old folder still exists on the phone when the PC deletes its copy, the folder can reappear on the PC within a few seconds. Force quitting Pythonista, deleting the folder from Files (step 2), then unzipping the new zip avoids stale copies.
