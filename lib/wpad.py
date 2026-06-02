"""WPAD / PAC file server."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .quiet_http import NoAccessLogMixin


def make_pac_bytes(phost: str, http_port: int, socks_port: int) -> bytes:
    return (
        """
function FindProxyForURL(url, host)
{
   if (isInNet(host, "192.168.0.0", "255.255.0.0")) {
      return "DIRECT";
   } else if (isInNet(host, "172.16.0.0", "255.240.0.0")) {
      return "DIRECT";
   } else if (isInNet(host, "10.0.0.0", "255.0.0.0")) {
      return "DIRECT";
   } else {
      return "PROXY %s:%d; SOCKS5 %s:%d; SOCKS %s:%d";
   }
}
"""
        % (phost, http_port, phost, socks_port, phost, socks_port)
    ).lstrip().encode()


def create_wpad_server(
    hhost: str, hport: int, phost: str, socks_port: int, http_port: int
) -> HTTPServer:
    pac_body = make_pac_bytes(phost, http_port, socks_port)

    class HTTPHandler(NoAccessLogMixin, BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-type", "application/x-ns-proxy-autoconfig")
            self.end_headers()

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "application/x-ns-proxy-autoconfig")
            self.send_header("Content-Length", str(len(pac_body)))
            self.end_headers()
            self.wfile.write(pac_body)

    HTTPServer.allow_reuse_address = True
    return HTTPServer((hhost, hport), HTTPHandler)


def stop_wpad_server(server: HTTPServer, thread: threading.Thread | None = None, timeout: float = 5.0) -> None:
    """Stop serve_forever and release the listen socket (needed before in-process restart)."""
    try:
        server.shutdown()
    except Exception:
        pass
    try:
        server.server_close()
    except Exception:
        pass
    if thread is not None and thread.is_alive():
        thread.join(timeout=timeout)
