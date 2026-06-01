import asyncio
import copy
import io
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib import parse

from . import status
from .proxy_server import (
    AsyncProxyHandler,
    AsyncProxyServer,
    SocketAddress,
    Socks5AddressType,
)
from .quiet_http import OptionalAccessLogMixin

logger = logging.getLogger("http")

# Client closed early (common for CONNECT / PAC / cancelled requests).
_BENIGN_CLIENT_ERRORS = (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError)


def _benign_client_disconnect(exc: BaseException) -> bool:
    if isinstance(exc, _BENIGN_CLIENT_ERRORS):
        return True
    return isinstance(exc, OSError) and exc.errno in (32, 54)  # EPIPE, ECONNRESET


def _connect_error_message(address: SocketAddress, exc: BaseException) -> str:
    detail = str(exc)
    if not detail:
        if isinstance(exc, OSError) and exc.errno is not None:
            detail = "errno %s (%s)" % (exc.errno, exc.strerror or "unknown")
        else:
            detail = repr(exc)
    return "Unable to connect to host %s: %s" % (address, detail)


def _is_pac_path(path: str) -> bool:
    lower = path.lower().split("?", 1)[0]
    if lower.endswith("/wpad.dat") or lower.endswith("wpad.dat"):
        return True
    if lower.endswith("/wpad") or lower.endswith("/proxy.pac"):
        return True
    parsed = parse.urlparse(path, "http")
    plower = parsed.path.lower()
    return plower.endswith("/wpad.dat") or plower.endswith("/wpad") or plower.endswith(
        "/proxy.pac"
    )


class AsyncHTTPProxyHandler(
    AsyncProxyHandler, OptionalAccessLogMixin, BaseHTTPRequestHandler
):
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        server: "AsyncProxyServer",
    ):
        AsyncProxyHandler.__init__(self, reader, writer, server)
        # XXX hack: skip BaseHTTPRequestHandler.__init__ since it will automatically
        # try to call setup/handle/finish
        # XXX hack: don't set rfile; we'll use an artificial rfile to avoid blocking
        self.wfile = writer

    async def handle(self):
        self.raw_requestline = await self.reader.readline()
        if not self.raw_requestline:
            return

        # hack so parse_request won't block
        headers = bytearray()
        while True:
            line = await self.reader.readline()
            headers += line
            if line in (b"\r\n", b"\n", b""):
                break
        self.rfile = io.BytesIO(headers)

        if not self.parse_request():
            return

        mname = "do_" + self.command
        if not hasattr(self, mname):
            self.send_error(
                HTTPStatus.NOT_IMPLEMENTED, "Unsupported method (%r)" % self.command
            )
            return

        try:
            await getattr(self, mname)()
            await self.writer.drain()
        except Exception as e:
            if _benign_client_disconnect(e):
                logger.debug("%s: client disconnected (%s)", self.log_tag, e)
            else:
                logger.error("%s: %s: %s", self.log_tag, type(e).__name__, e)

    def log_error(self, format, *args):
        logger.error("%s: " + format, self.log_tag, *args)

    async def _serve_pac(self) -> None:
        body = getattr(self.server, "pac_body", None)
        if not body:
            self.send_error(HTTPStatus.NOT_FOUND, "PAC not configured")
            return
        content = b"" if self.command == "HEAD" else body
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ns-proxy-autoconfig")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if content:
            self.wfile.write(content)

    async def do_CONNECT(self):
        address: SocketAddress
        bits = self.path.split(":", 1)
        if len(bits) == 1:
            address = bits[0], 80
        else:
            address = bits[0], int(bits[1])

        try:
            connection = await self.server.tcp_connect(
                Socks5AddressType.DOMAIN, address
            )
        except Exception as e:
            self.send_error(
                HTTPStatus.BAD_GATEWAY,
                _connect_error_message(address, e),
            )
            return

        self.send_response(200, "Connection established")
        self.end_headers()
        await self.tcp_forward(connection)

    async def do_verb(self):
        (scm, netloc, path, params, query, fragment) = parse.urlparse(self.path, "http")
        if scm == "http":
            default_port = 80
        elif scm == "https":
            default_port = 443
        else:
            self.send_error(HTTPStatus.BAD_REQUEST, "bad scheme %s" % scm)
            return

        if fragment or not netloc:
            self.send_error(HTTPStatus.BAD_REQUEST, "bad url %s" % self.path)
            return

        address: SocketAddress
        bits = netloc.split(":", 1)
        if len(bits) == 1:
            address = bits[0], default_port
        else:
            address = bits[0], int(bits[1])

        try:
            connection = await self.server.tcp_connect(
                Socks5AddressType.DOMAIN, address
            )
        except Exception as e:
            self.send_error(
                HTTPStatus.BAD_GATEWAY,
                _connect_error_message(address, e),
            )
            return

        s_reader, s_writer = connection
        headers = copy.copy(self.headers)
        headers["Connection"] = "close"
        del headers["Proxy-Connection"]
        s_writer.write(
            (
                "%s %s %s\r\n"
                % (
                    self.command,
                    parse.urlunparse(("", "", path, params, query, "")),
                    self.request_version,
                )
            ).encode("utf8")
        )
        for k, v in headers.items():
            s_writer.write(("%s: %s\r\n" % (k, v)).encode("utf8"))
        s_writer.write(b"\r\n")

        # Simple, dumb proxy: don't interpret upstream response, just forward it onto
        # the client and close the connection at the end.
        # We don't support Proxy-Connection: keep-alive.
        await self.tcp_forward(connection)

    do_GET = do_verb
    do_HEAD = do_verb
    do_POST = do_verb
    do_PUT = do_verb
    do_DELETE = do_verb
    do_OPTIONS = do_verb


if __name__ == "__main__":
    # Testing purposes only
    stats = status.StatusMonitor("HTTP Server", interval=1)
    logging.getLogger().addHandler(stats)

    async def main() -> None:
        server = AsyncProxyServer(
            AsyncHTTPProxyHandler, listen_port=9877, traffic_stats=stats
        )
        asyncio.create_task(server.run())
        await stats.render_forever()

    asyncio.run(main())
