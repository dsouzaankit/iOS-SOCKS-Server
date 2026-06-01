# PotPlayer proxy (optional)

PotPlayer usually **ignores Windows PAC**. This folder toggles PotPlayer’s **own** proxy (F5 → Network → Proxy server) together with `..\Socks-Proxy-On.cmd` / `Off.cmd` when `potPlayerProxy` is `true` in `..\ios-socks-windows.json`.

Config fields live in the parent **`ios-socks-windows.json`** (`potPlayerProxy`, `potPlayerRegKey`).

## Files

| File | Purpose |
|------|---------|
| `PotPlayer-Proxy-Calibrate.cmd` | **One-click** guided calibration (all steps) |
| `PotPlayer-Proxy-Calibrate-Off.cmd` | Snapshot with proxy off |
| `PotPlayer-Proxy-Calibrate-On.cmd` | Snapshot with proxy on |
| `PotPlayer-Proxy-Calibrate-Build.cmd` | Build patches from snapshots |
| `Save-PotPlayer-ProxyProfile.ps1` | Calibration (PowerShell) |
| `PotPlayer-ProxySettings.ps1` | Registry toggle (dot-sourced from `windows-proxy.ps1`) |
| `Probe-PotPlayer*.ps1` | Local diagnostics (optional) |
| `clash-potplayer.example.yaml` | **Recommended** Clash/Mihomo snippet for PotPlayer |

Calibration data is stored under `%LOCALAPPDATA%\iOS-SOCKS-Server\potplayer\` (not in this repo).

## Clash / Mihomo (recommended for PotPlayer)

PotPlayer **does not use Windows PAC**, so `Socks-Proxy-On.cmd` alone will not route the player. **Clash Verge** (with the **Mihomo / Clash Meta** core) can send **only PotPlayer** through the phone via **TUN** and `PROCESS-NAME` rules.

### Prerequisites

1. **`socks5.py` running** on the iPhone (foreground).
2. **Phone IP** from the Pythonista banner → set `server` in the YAML (and `ios-socks-windows.json` → `phoneLanHost`).
3. **Clash Verge** using **Mihomo** (Meta). `PROCESS-NAME` rules do not work on the legacy Clash core.
4. **Turn off** `..\Socks-Proxy-On.cmd` while Clash **TUN** is on (double proxy causes failures).

### Setup

1. Copy **`clash-potplayer.example.yaml`** and merge into your profile (or paste the blocks into an existing config).
2. Replace **`10.0.100.10`** with your **PHONE_IP**.
3. Enable the profile → turn **TUN** on (required for PotPlayer).
4. The example **`iPhone`** group uses **`type: fallback`** (SOCKS → HTTP → DIRECT). No manual node pick needed unless you switch to **`select`** (see below).
5. Start PotPlayer and play a URL; check Pythonista or `http://PHONE_IP:8765/`.

### Fallback proxy group (`interval`, health checks)

The example routes PotPlayer through an **`iPhone`** group with **`type: fallback`**. Mihomo / Clash Meta tries proxies **in list order** and moves down when the active one fails the health check.

| Field | Example | Meaning |
|-------|---------|---------|
| `type` | `fallback` | Auto failover (not manual `select`) |
| `url` | `http://www.gstatic.com/generate_204` | Probe URL (204 = healthy). Alternatives: `http://cp.cloudflare.com/generate_204` |
| `interval` | `300` | Re-check every **300 seconds** (5 min) |
| `timeout` | `5000` | Per-check timeout in **milliseconds** |
| `proxies` | SOCKS → HTTP → DIRECT | Try SOCKS first; on failure use HTTP, then direct |

**Order matters:** list proxies from preferred to last resort:

```yaml
proxy-groups:
  - name: iPhone
    type: fallback
    url: http://www.gstatic.com/generate_204
    interval: 300
    timeout: 5000
    proxies:
      - iOS-Phone-SOCKS
      - iOS-Phone-HTTP
      - DIRECT
```

**Tuning `interval` for tethering**

| `interval` | When to use |
|------------|-------------|
| `120` | Flaky hotspot — faster failover, more probes |
| `300` | Default in the example — balanced |
| `600` | Stable link — fewer checks |

Very low values (e.g. `10`) spam the phone running `socks5.py`; avoid unless debugging.

**`interval` does not apply to `type: select`** — that group only changes when you pick a node in Clash Verge. The YAML file includes a commented **`select`** block if you prefer manual SOCKS vs HTTP.

**When fallback moves:** each `interval`, Clash requests `url` through the current proxy. On failure it activates the next proxy in `proxies`. When SOCKS is healthy again, fallback typically **returns to the first** working entry (SOCKS).

**Other group types:** `url-test` also uses `interval` but picks the **fastest** node, not list order. `load-balance` spreads traffic; not ideal for a single phone upstream.

### What the example does

| Piece | Purpose |
|-------|---------|
| `iOS-Phone-SOCKS` | Upstream SOCKS5 to the phone (`:9876`) |
| `iPhone` (`fallback`) | Auto SOCKS → HTTP → DIRECT with `interval` health checks |
| `tun.enable: true` | Captures app traffic PotPlayer would otherwise send direct |
| `PROCESS-NAME,PotPlayerMini64.exe` | Only PotPlayer uses the phone; other apps stay **DIRECT** |

If you use 32-bit PotPlayer only, keep the `PotPlayerMini.exe` rule; 64-bit installs usually need **`PotPlayerMini64.exe`**.

### Test

```text
Clash Verge → Connections / Logs → play in PotPlayer → entries for PotPlayerMini64.exe
```

### Choose an approach

| Approach | When to use |
|----------|-------------|
| **Clash TUN + PROCESS-NAME** (this file) | PotPlayer only through phone; browsers stay direct unless you change rules |
| **`potPlayerProxy` + Socks-Proxy-On/Off** | No Clash; toggles PotPlayer registry proxy with Windows PAC |
| **PotPlayer F5 → SOCKS5** | Manual; no Clash or calibration |
| **Proxifier** | Per-`.exe` without Clash; paid |

See also [../README.md](../README.md#media-players-and-pac).

## One-time calibration

1. Close PotPlayer → double-click **`PotPlayer-Proxy-Calibrate.cmd`** and follow prompts.

Or step by step: **`-Off.cmd`** → set SOCKS5 in PotPlayer → **`-On.cmd`** → **`-Build.cmd`**.

Suggested ON settings (from parent config):

- **SOCKS5** → `phoneLanHost`:**`socksPort`** (9876)
- **HTTP** → `phoneLanHost`:**`httpPort`** (9877)

Enable `"potPlayerProxy": true` when prompted (or edit `..\ios-socks-windows.json`).

## Daily use

Run **`..\Socks-Proxy-On.cmd`** / **`Off.cmd`** as usual. Restart PotPlayer if it was open during toggle.

Desktop shortcut: run **`..\Install-SocksDailyShortcuts.ps1`** (creates **PotPlayer Proxy Calibrate** once).
