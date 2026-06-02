#!python3
# Socks5/HTTP Proxy server for Pythonista by @nneonneo
# Pretty statistics view and IPv6 support added by @philrosenthal

import ipaddress
import logging
import os
import socket
import sys
import threading
import traceback

from lib.socks5_server import AsyncSocks5Handler
from lib.http_proxy_server import AsyncHTTPProxyHandler
from lib.proxy_server import AsyncProxyServer
from lib.status import StatusMonitor

logging.basicConfig(level=logging.ERROR)

# IP over which the proxy will be available (probably WiFi IP)
PROXY_HOST = "172.20.10.1"
# IP over which the proxy will attempt to connect to the Internet
CONNECT_HOST_IPV4 = None
CONNECT_HOST_IPV6 = None
PREFER_SYSTEM_DNS = "Pythonista" in sys.executable
SKIP_IPV6_CONNECTIVITY_TEST = "Pythonista" in sys.executable
# Time out connections after being idle for this long (in seconds)
IDLE_TIMEOUT = 1800

LISTEN_HOST = "0.0.0.0"
SOCKS_PORT = 9876
HTTP_PORT = 9877
WPAD_PORT = 8088

USE_PHONE_VPN = True
CUSTOM_RESOLVERS = []

# File logging + LAN debug server.
LOG_TO_FILE = True
LAN_DEBUG_ENABLED = True
LAN_DEBUG_PORT = 8765
FILE_LOG_LEVEL = logging.INFO
# False = print startup banner once; no console redraw or error log lines.
LIVE_CONSOLE_REFRESH = False

# Pythonista: dark UI + prevent auto-lock while the script runs.
REQUEST_DARK_MODE = True
KEEP_SCREEN_AWAKE = True
# Pythonista: transparent overlay blocks accidental taps (Stop UI also blocked; use auto-exit or LAN /restart).
BLOCK_TOUCH_INPUT = True
# Pythonista: stop proxy and quit the app when backgrounded or screen locks.
EXIT_WHEN_BACKGROUNDED = True
EXIT_TERMINATE_PYTHONISTA = True
EXIT_GRACE_SECONDS = 2.0
# Write "Run SOCKS Proxy.py" beside this folder for the Shortcuts script picker.
INSTALL_SHORTCUT_LAUNCHER = True

if "Pythonista" in sys.executable:
    try:
        from lib.ios_ui import block_touch_input, keep_screen_awake, request_dark_mode

        if REQUEST_DARK_MODE:
            request_dark_mode()
        if KEEP_SCREEN_AWAKE:
            keep_screen_awake(True)
        if BLOCK_TOUCH_INPUT:
            block_touch_input(True)
    except Exception:
        pass


def is_globally_routable(ipv6_address):
    non_routable_networks = [
        "ff00::/8",  # Multicast address range
        "fe80::/10",  # Link-local address range
        "fc00::/7",  # Unique local address range
        "::/8",  # Unspecified address range
        "2001:db8::/32",  # Documentation address range
        "2001::/32",  # Teredo address range
        "2002::/16",  # 6to4 address range
        "ff02::/16",  # Link-local multicast address range
    ]
    for network in non_routable_networks:
        if ipaddress.ip_address(ipv6_address) in ipaddress.ip_network(network):
            return False
    return True


DEFAULT_RESOLVERS = [
    "1.0.0.1",
    "1.1.1.1",
    "8.8.8.8",
    "2606:4700:4700::1111",
    "2606:4700:4700::1001",
    "2001:4860:4860::8844",
]

try:
    # TODO: configurable DNS (or find a way to use the cell network's own DNS)
    import dns.asyncresolver

    resolver = dns.asyncresolver.Resolver(configure=False)
    resolver.nameservers += CUSTOM_RESOLVERS or DEFAULT_RESOLVERS
except ImportError:
    # pip install dnspython
    print("Warning: dnspython not available; falling back to system DNS")
    resolver = None

initial_output = ""

try:
    # We want the WiFi address so that clients know what IP to use.
    # We want the non-WiFi (cellular?) address so that we can force network
    #  traffic to go over that network. This allows the proxy to correctly
    #  forward traffic to the cell network even when the WiFi network is
    #  internet-enabled but limited (e.g. firewalled)

    from collections import defaultdict

    from lib import ifaddrs

    ipv4_output = ""
    ipv6_output = ""

    interfaces = ifaddrs.get_interfaces()
    iftypes = defaultdict(list)

    for iface in interfaces:
        if not iface.addr:
            continue
        if iface.name.startswith("lo"):
            continue
        # XXX implement better classification of interfaces
        if iface.name.startswith("en"):
            iftypes["en"].append(iface)
        elif iface.name.startswith("bridge"):
            iftypes["bridge"].append(iface)
        elif iface.name.startswith("utun"):
            iftypes["vpn"].append(iface)
        else:
            iftypes["cell"].append(iface)

    if iftypes["vpn"] and USE_PHONE_VPN:
        ipv4_output += "VPN use enabled (change with USE_PHONE_VPN)\n"
        new_ifaces = []
        new_ifaces.extend(iftypes["vpn"])
        new_ifaces.extend(iftypes["cell"])
        iftypes["cell"] = new_ifaces

    if iftypes["bridge"]:
        iface = next(
            (
                iface
                for iface in iftypes["bridge"]
                if iface.addr.family == socket.AF_INET
            ),
            None,
        )
        if iface:
            initial_output = (
                "Assuming proxy will be accessed over hotspot (%s) at %s\n"
                % (iface.name, iface.addr.address)
            )
            PROXY_HOST = iface.addr.address
    elif iftypes["en"]:
        iface = next(
            (iface for iface in iftypes["en"] if iface.addr.family == socket.AF_INET),
            None,
        )
        if iface:
            initial_output += (
                "Assuming proxy will be accessed over WiFi (%s) at %s\n"
                % (iface.name, iface.addr.address)
            )
            PROXY_HOST = iface.addr.address
    else:
        initial_output += (
            "Warning: could not get WiFi address; assuming %s\n" % PROXY_HOST
        )

    if iftypes["cell"]:
        iface_ipv4 = next(
            (iface for iface in iftypes["cell"] if iface.addr.family == socket.AF_INET),
            None,
        )
        iface_ipv6 = None

        is_vpn = iface_ipv4 and iface_ipv4.name.startswith("utun")

        if iface_ipv4:
            iface_ipv4.addr.address
            ipv4_output += "Will connect to IPv4 servers over interface %s at %s\n" % (
                iface_ipv4.name,
                iface_ipv4.addr.address,
            )
            CONNECT_HOST_IPV4 = iface_ipv4.addr.address

            # Create a list of all IPv6 addresse that are globally routable and match the IPv4 interface
            iface_ipv6_list = [
                iface
                for iface in iftypes["cell"]
                if iface.addr.family == socket.AF_INET6
                and iface.addr.address
                and (is_globally_routable(iface.addr.address) if not is_vpn else True)
                and iface.name == iface_ipv4.name
            ]

            # Select the last IPv6 address to select the temporary address for reduced tracking
            iface_ipv6 = iface_ipv6_list[-1] if iface_ipv6_list else None

        if iface_ipv6 is None and not is_vpn:
            # Create a list of all IPv6 addresses that are globally routable
            iface_ipv6_list = [
                iface
                for iface in iftypes["cell"]
                if iface.addr.family == socket.AF_INET6
                and iface.addr.address
                and is_globally_routable(iface.addr.address)
            ]

            # Select the last IPv6 address to select the temporary address for reduced tracking
            iface_ipv6 = iface_ipv6_list[-1] if iface_ipv6_list else None

        if iface_ipv6:
            iface_ipv6.addr.address
            ipv6_output += "Will connect to IPv6 servers over interface %s at %s\n" % (
                iface_ipv6.name,
                iface_ipv6.addr.address,
            )
            if SKIP_IPV6_CONNECTIVITY_TEST:
                CONNECT_HOST_IPV6 = iface_ipv6.addr.address
                ipv6_output += "Skipping IPv6 connectivity test (Pythonista)\n"
            else:
                test_socket = None
                try:
                    test_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    test_socket.settimeout(5)
                    test_socket.bind((iface_ipv6.addr.address, 0))
                    test_socket.connect(("2606:4700:4700::1111", 80))
                    CONNECT_HOST_IPV6 = iface_ipv6.addr.address
                except Exception as e:
                    ipv6_output += (
                        "Failed to connect to 2606:4700:4700::1111 over IPv6 due to: %s\n"
                        % str(e)
                    )
                    CONNECT_HOST_IPV6 = None
                finally:
                    if test_socket is not None:
                        test_socket.close()

    initial_output += ipv4_output + ipv6_output
except Exception as e:
    logging.error("Address detection failed: %s: %s", (type(e).__name__, e))
    import traceback

    traceback.print_exc()

    interfaces = None


def _setup_logging() -> None:
    if not LOG_TO_FILE:
        return
    from lib.file_logging import install_crash_hooks, setup_file_logging
    from lib.log_paths import write_ok_probe

    setup_file_logging(level=FILE_LOG_LEVEL)
    install_crash_hooks()
    write_ok_probe(mode="full")


def _configure_console_logging(stats: StatusMonitor) -> None:
    """Attach stats handler; drop stderr logging when the console UI is quiet."""
    root = logging.getLogger()
    root.addHandler(stats)
    if LIVE_CONSOLE_REFRESH:
        return
    for handler in list(root.handlers):
        if isinstance(handler, logging.StreamHandler):
            root.removeHandler(handler)


def create_wpad_server(hhost, hport, phost, socks_port, http_port):
    from lib.wpad import create_wpad_server as _create, stop_wpad_server as _stop

    return _create(hhost, hport, phost, socks_port, http_port)


def stop_wpad_server(server, thread=None, timeout=5.0):
    from lib.wpad import stop_wpad_server as _stop

    _stop(server, thread, timeout)


def _cleanup_proxy_session(wpad_server, wpad_thread) -> None:
    from lib.proxy_control import wait_for_ports_free

    stop_wpad_server(wpad_server, wpad_thread)
    if not wait_for_ports_free(timeout=5.0):
        print(
            "Warning: proxy ports still in use after stop; restart may fail.",
            flush=True,
        )


def _restore_ios_ui() -> None:
    if "Pythonista" not in sys.executable or not BLOCK_TOUCH_INPUT:
        return
    try:
        from lib.ios_ui import restore_touch_input

        restore_touch_input()
    except Exception:
        pass


def run_wpad_server(server):
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


class RestartProxy(Exception):
    """In-process restart requested via /restart or control file."""


def _poll_control() -> None:
    from lib.proxy_control import is_restart_requested, is_shutdown_requested

    if is_restart_requested():
        raise RestartProxy
    if is_shutdown_requested():
        raise KeyboardInterrupt


if __name__ == "__main__":
    import asyncio

    if "--safe" in sys.argv:
        from debug_server import run_safe_mode

        port = LAN_DEBUG_PORT
        for i, arg in enumerate(sys.argv):
            if arg in ("--port", "-p") and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
                break
        run_safe_mode(port)
        sys.exit(0)

    from lib.wpad import make_pac_bytes

    _setup_logging()

    if "Pythonista" in sys.executable and EXIT_WHEN_BACKGROUNDED:
        from lib.ios_lifecycle import install_exit_on_background, schedule_terminate_pythonista
        from lib.proxy_control import request_shutdown

        def _on_background_exit(reason: str) -> None:
            print("Stopping proxy (%s)." % reason, flush=True)
            request_shutdown()
            if EXIT_TERMINATE_PYTHONISTA:
                schedule_terminate_pythonista(EXIT_GRACE_SECONDS)

        if not install_exit_on_background(_on_background_exit):
            print(
                "Warning: could not install background/lock exit handler.",
                flush=True,
            )

    _session_state: dict = {"debug_started": False}
    _stats_log_handler = None
    _console_logging_ready = False

    while True:
        session_output = initial_output

        if INSTALL_SHORTCUT_LAUNCHER and "Pythonista" in sys.executable:
            from lib.shortcut_launcher import (
                install_shortcuts_launcher,
                launcher_banner_lines,
            )

            _proxy_dir = os.path.dirname(os.path.abspath(__file__))
            launcher_result = install_shortcuts_launcher(_proxy_dir, quiet=True)
            session_output += launcher_banner_lines(
                launcher_result,
                _proxy_dir,
                proxy_host=PROXY_HOST or LISTEN_HOST,
                debug_port=LAN_DEBUG_PORT,
            )

        pac_body = make_pac_bytes(PROXY_HOST, HTTP_PORT, SOCKS_PORT)
        wpad_server = create_wpad_server(
            LISTEN_HOST, WPAD_PORT, PROXY_HOST, SOCKS_PORT, HTTP_PORT
        )

        session_output += "PAC URL: http://{}:{}/wpad.dat\n".format(
            PROXY_HOST, WPAD_PORT
        )
        session_output += "SOCKS Address: {}:{}\n".format(
            PROXY_HOST or LISTEN_HOST, SOCKS_PORT
        )
        session_output += "HTTP Proxy Address: {}:{}\n".format(
            PROXY_HOST or LISTEN_HOST, HTTP_PORT
        )
        if "Pythonista" in sys.executable:
            if EXIT_WHEN_BACKGROUNDED:
                if EXIT_TERMINATE_PYTHONISTA:
                    session_output += (
                        "Auto-exit: proxy stops and Pythonista closes when "
                        "backgrounded or screen locks.\n"
                    )
                else:
                    session_output += (
                        "Auto-stop: proxy stops when backgrounded or screen locks "
                        "(Pythonista stays open).\n"
                    )
            else:
                session_output += (
                    "Keep Pythonista in the foreground — do not lock the phone "
                    "or switch apps.\n"
                )
            if BLOCK_TOUCH_INPUT:
                session_output += (
                    "Touch input blocked — use auto-exit, LAN /restart, or force-quit "
                    "to stop (in-app Stop is disabled).\n"
                )
        if LAN_DEBUG_ENABLED:
            session_output += "Debug log LAN: http://{}:{}/\n".format(
                PROXY_HOST or LISTEN_HOST, LAN_DEBUG_PORT
            )
            session_output += "  safe mode: python debug_server.py\n"

        if LOG_TO_FILE:
            from lib.file_logging import log_banner

            log_banner(session_output)

        stats = StatusMonitor(session_output)
        root_logger = logging.getLogger()
        if _stats_log_handler is not None:
            root_logger.removeHandler(_stats_log_handler)
        root_logger.addHandler(stats)
        _stats_log_handler = stats
        if not _console_logging_ready:
            if not LIVE_CONSOLE_REFRESH:
                for handler in list(root_logger.handlers):
                    if isinstance(handler, logging.StreamHandler) and handler is not stats:
                        root_logger.removeHandler(handler)
            _console_logging_ready = True

        from lib.proxy_control import clear_shutdown_request

        clear_shutdown_request()

        wpad_thread = threading.Thread(
            target=run_wpad_server, args=(wpad_server,), name="wpad"
        )
        wpad_thread.daemon = True
        wpad_thread.start()

        async def main():
            if LAN_DEBUG_ENABLED and not _session_state["debug_started"]:
                from lib.lan_debug_server import start_lan_debug_server_thread

                def _lan_debug_status() -> dict:
                    live = _session_state.get("stats")
                    if live is None:
                        return {}
                    return {
                        "connections": live.num_connections,
                        "errors": live.num_errors,
                        "socksPort": SOCKS_PORT,
                        "httpPort": HTTP_PORT,
                    }

                start_lan_debug_server_thread(
                    LISTEN_HOST,
                    LAN_DEBUG_PORT,
                    safe_mode=False,
                    status_fn=_lan_debug_status,
                )
                _session_state["debug_started"] = True

            _session_state["stats"] = stats

            socks_srv = AsyncProxyServer(
                AsyncSocks5Handler,
                listen_hosts=LISTEN_HOST,
                listen_port=SOCKS_PORT,
                traffic_stats=stats,
                resolver=resolver,
                connect_host_ipv4=CONNECT_HOST_IPV4,
                connect_host_ipv6=CONNECT_HOST_IPV6,
                prefer_system_dns=PREFER_SYSTEM_DNS,
                http_port=HTTP_PORT,
                pac_body=pac_body,
            )
            http_srv = AsyncProxyServer(
                AsyncHTTPProxyHandler,
                listen_hosts=LISTEN_HOST,
                listen_port=HTTP_PORT,
                traffic_stats=stats,
                resolver=resolver,
                connect_host_ipv4=CONNECT_HOST_IPV4,
                connect_host_ipv6=CONNECT_HOST_IPV6,
                prefer_system_dns=PREFER_SYSTEM_DNS,
                access_log=LIVE_CONSOLE_REFRESH,
                pac_body=pac_body,
            )
            socks_task = asyncio.create_task(socks_srv.run())
            http_task = asyncio.create_task(http_srv.run())
            try:
                if LIVE_CONSOLE_REFRESH:
                    await stats.render_forever(shutdown_check=_poll_control)
                else:
                    stats.display_once()
                    await stats.idle_forever(shutdown_check=_poll_control)
            finally:
                for task in (socks_task, http_task):
                    task.cancel()
                await asyncio.gather(socks_task, http_task, return_exceptions=True)
                await socks_srv.close()
                await http_srv.close()

        try:
            asyncio.run(main())
            _cleanup_proxy_session(wpad_server, wpad_thread)
            _restore_ios_ui()
            break
        except RestartProxy:
            print("Restarting proxy...", flush=True)
            clear_shutdown_request()
            _cleanup_proxy_session(wpad_server, wpad_thread)
            _session_state["stats"] = None
            continue
        except KeyboardInterrupt:
            print("Shutting down.", flush=True)
            clear_shutdown_request()
            _cleanup_proxy_session(wpad_server, wpad_thread)
            _restore_ios_ui()
            break
        except Exception as exc:
            _restore_ios_ui()
            print("Proxy crashed:", exc, flush=True)
            traceback.print_exc()
            if LOG_TO_FILE:
                from lib.file_logging import log_crash

                log_crash(exc)
            raise
