#!python3
# Asynchronous SOCKS5 proxy server with multi-homing support.
# Asyncified from https://github.com/rushter/socks5/blob/master/server.py by @nneonneo
# IPv6 support by @philrosenthal

import asyncio
import logging
import socket
import struct
from enum import IntEnum
from io import BytesIO
from typing import Any, BinaryIO, Callable, Coroutine

from . import status
from .proxy_server import (
    AsyncProxyHandler,
    AsyncProxyServer,
    SocketAddress,
    Socks5AddressType,
)

logger = logging.getLogger("socks5")


SOCKS_VERSION = 5
SOCKS4_VERSION = 4
SOCKS4_CONNECT = 1
SOCKS4_BIND = 2
SOCKS4_REPLY_GRANTED = 0x5A
SOCKS4_REPLY_REJECT = 0x5B


class Socks5Status(IntEnum):
    SUCCEEDED = 0  # succeeded
    ERROR = 1  # general SOCKS server failure
    EPERM = 2  # connection not allowed by ruleset
    ENETDOWN = 3  # Network unreachable
    EHOSTUNREACH = 4  # Host unreachable
    ECONNREFUSED = 5  # Connection refused
    ETIMEDOUT = 6  # TTL expired
    ENOTSUP = 7  # Command not supported
    EAFNOSUPPORT = 8  # Address type not supported


def encode_address(sockaddr: SocketAddress | None = None) -> bytes:
    # encode sockaddr as SOCKS5 address
    if sockaddr is None:
        return struct.pack("!BIH", Socks5AddressType.IPV4, 0, 0)

    address, port = sockaddr
    try:
        addrbytes = socket.inet_pton(socket.AF_INET, address)
        return struct.pack("!B4sH", Socks5AddressType.IPV4, addrbytes, port)
    except Exception:
        addrbytes = socket.inet_pton(socket.AF_INET6, address)
        return struct.pack("!B16sH", Socks5AddressType.IPV6, addrbytes, port)


class UdpForwarderProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        method: Callable[
            [asyncio.DatagramTransport, bytes, SocketAddress],
            Coroutine[None, None, None],
        ],
    ):
        self.method = method
        self.loop = asyncio.get_running_loop()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: SocketAddress) -> None:
        self.loop.create_task(self.method(self.transport, data, addr[:2]))


class UdpForwarder:
    def __init__(self, log_tag: str, server: "AsyncProxyServer", local_address: str):
        self.log_tag = log_tag + " [udp]"
        self.server = server
        self.local_address = local_address
        self.server_conn_ipv4: asyncio.DatagramTransport | None = None
        self.server_conn_ipv6: asyncio.DatagramTransport | None = None
        self.connections: dict[
            tuple[asyncio.DatagramTransport, SocketAddress], SocketAddress
        ] = {}

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.client_conn, _ = await loop.create_datagram_endpoint(
            lambda: UdpForwarderProtocol(self.on_client_datagram),
            local_addr=(self.local_address, 0),
        )

        connect_host_ipv4 = self.server.connect_host_ipv4
        connect_host_ipv6 = self.server.connect_host_ipv6

        if connect_host_ipv4 is None and connect_host_ipv6 is None:
            connect_host_ipv4 = "0.0.0.0"
            connect_host_ipv6 = "::"

        if connect_host_ipv4 is not None:
            self.server_conn_ipv4, _ = await loop.create_datagram_endpoint(
                lambda: UdpForwarderProtocol(self.on_server_datagram),
                local_addr=(connect_host_ipv4, 0),
            )

        if connect_host_ipv6 is not None:
            self.server_conn_ipv6, _ = await loop.create_datagram_endpoint(
                lambda: UdpForwarderProtocol(self.on_server_datagram),
                local_addr=(connect_host_ipv6, 0),
            )

    async def on_client_datagram(
        self,
        transport: asyncio.DatagramTransport,
        data: bytes,
        client_addr: SocketAddress,
    ) -> None:
        sockfile = BytesIO(data)
        try:
            # decode header
            _, frag, address_type = self.readstruct(sockfile, "!HBB")
            assert frag == 0, "UDP fragmentation is not supported"
            address = self.read_addrport(address_type, sockfile)
            assert address is not None, "Address type is not supported"
            payload = sockfile.read()
            self.server.traffic_stats.add_outbound(len(payload))

            resolved = await self.server.resolve_address(address_type, address)
            if resolved.ipv6 and self.server_conn_ipv6:
                self.connections[self.server_conn_ipv6, resolved.ipv6] = client_addr
                self.server_conn_ipv6.sendto(payload, resolved.ipv6)
            elif resolved.ipv4 and self.server_conn_ipv4:
                self.connections[self.server_conn_ipv4, resolved.ipv4] = client_addr
                self.server_conn_ipv4.sendto(payload, resolved.ipv4)
            else:
                logging.info(
                    "%s: unable to send UDP packet to %s", self.log_tag, address
                )
        except Exception as e:
            logging.info("%s: malformed udp packet: %s", self.log_tag, e)

    async def on_server_datagram(
        self, transport: asyncio.DatagramTransport, data: bytes, addr: SocketAddress
    ) -> None:
        self.server.traffic_stats.add_inbound(len(data))

        client_addr = self.connections.get((transport, addr), None)
        if client_addr is None:
            logging.warning(
                "%s: got packet from unknown sender %s", self.log_tag, *addr
            )
            return

        header = struct.pack("!HB", 0, 0) + encode_address(addr)
        self.client_conn.sendto(header + data, client_addr)

    def readall(self, f: BinaryIO, n: int) -> bytes:
        res = bytearray()
        while len(res) < n:
            chunk = f.read(n - len(res))
            if not chunk:
                raise EOFError()
            res += chunk
        return bytes(res)

    def readstruct(self, f: BinaryIO, fmt: str) -> tuple[Any, ...]:
        return struct.unpack(fmt, self.readall(f, struct.calcsize(fmt)))

    def read_addrport(self, address_type: int, sockf: BinaryIO) -> SocketAddress | None:
        if address_type == Socks5AddressType.IPV4:
            address = socket.inet_ntop(socket.AF_INET, self.readall(sockf, 4))
        elif address_type == Socks5AddressType.DOMAIN:
            domain_length = ord(self.readall(sockf, 1))
            address = self.readall(sockf, domain_length).decode()
        elif address_type == Socks5AddressType.IPV6:
            address = socket.inet_ntop(socket.AF_INET6, self.readall(sockf, 16))
        else:
            return None
        (port,) = self.readstruct(sockf, "!H")
        return address, port

    def close(self) -> None:
        self.client_conn.close()
        if self.server_conn_ipv4:
            self.server_conn_ipv4.close()
        if self.server_conn_ipv6:
            self.server_conn_ipv6.close()


class PrefixedStreamReader:
    """StreamReader wrapper that replays bytes already read from the client."""

    def __init__(self, reader: asyncio.StreamReader, prefix: bytes):
        self._reader = reader
        self._buffer = bytearray(prefix)

    async def _take(self, n: int) -> bytes:
        if n <= len(self._buffer):
            out = bytes(self._buffer[:n])
            del self._buffer[:n]
            return out
        out = bytes(self._buffer)
        self._buffer.clear()
        if n > len(out):
            out += await self._reader.readexactly(n - len(out))
        return out

    async def readexactly(self, n: int) -> bytes:
        return await self._take(n)

    async def readline(self) -> bytes:
        while True:
            idx = self._buffer.find(b"\n")
            if idx >= 0:
                line = bytes(self._buffer[: idx + 1])
                del self._buffer[: idx + 1]
                return line
            chunk = await self._reader.read(4096)
            if not chunk:
                if self._buffer:
                    line = bytes(self._buffer)
                    self._buffer.clear()
                    return line
                return b""
            self._buffer.extend(chunk)

    async def read(self, n: int = -1) -> bytes:
        if n == -1:
            rest = await self._reader.read()
            result = bytes(self._buffer) + rest
            self._buffer.clear()
            return result
        return await self._take(n)


class AsyncSocks5Handler(AsyncProxyHandler):
    def send_reply(
        self, status: Socks5Status, bindaddr: tuple[str, int] | None = None
    ) -> None:
        reply = struct.pack("!BBB", SOCKS_VERSION, status, 0)
        reply += encode_address(bindaddr)
        self.writer.write(reply)

    async def readstruct(self, fmt: str) -> tuple[Any, ...]:
        data = await self.reader.readexactly(struct.calcsize(fmt))
        return struct.unpack(fmt, data)

    async def _read_null_terminated(self) -> bytes:
        chunks = []
        while True:
            chunk = await self.reader.readexactly(1)
            if chunk == b"\x00":
                break
            chunks.append(chunk)
        return b"".join(chunks)

    async def _send_socks4_reply(self, code: int) -> None:
        self.writer.write(struct.pack("!BBH4s", 0, code, 0, b"\x00\x00\x00\x00"))
        await self.writer.drain()

    async def _handle_socks4(self, cmd: int) -> None:
        port, = await self.readstruct("!H")
        ip_bytes = await self.reader.readexactly(4)
        await self._read_null_terminated()

        ip = socket.inet_ntop(socket.AF_INET, ip_bytes)
        if ip_bytes[:3] == b"\x00\x00\x00" and ip_bytes[3:4] != b"\x00":
            address = (await self._read_null_terminated()).decode(), port
            address_type = Socks5AddressType.DOMAIN
        else:
            address = ip, port
            address_type = Socks5AddressType.IPV4

        if cmd == SOCKS4_CONNECT:
            try:
                connection = await self.server.tcp_connect(address_type, address)
            except Exception as exc:
                await self._send_socks4_reply(SOCKS4_REPLY_REJECT)
                raise exc

            await self._send_socks4_reply(SOCKS4_REPLY_GRANTED)
            await self.tcp_forward(connection)
        elif cmd == SOCKS4_BIND:
            await self._send_socks4_reply(SOCKS4_REPLY_REJECT)
            logger.warning("%s: SOCKS4 BIND not supported", self.log_tag)
        else:
            await self._send_socks4_reply(SOCKS4_REPLY_REJECT)
            logger.warning("%s: invalid SOCKS4 command %d", self.log_tag, cmd)

    async def _handle_socks5(self) -> None:
        (nmethods,) = await self.readstruct("!B")

        methods = await self.reader.readexactly(nmethods)

        if 0 not in methods:
            self.writer.write(struct.pack("!BB", SOCKS_VERSION, 0xFF))
            raise Exception("Unsupported auth methods %s" % str(methods))

        self.writer.write(struct.pack("!BB", SOCKS_VERSION, 0))
        version, cmd, _, address_type = await self.readstruct("!BBBB")
        if version != SOCKS_VERSION:
            raise Exception("Invalid version %r after auth" % chr(version))

        address = await self.read_addrport(address_type)
        if address is None:
            self.send_reply(Socks5Status.EAFNOSUPPORT)
            raise Exception("Unsupported address type %d" % address_type)

        if cmd == 1:
            await self.handle_connect(address_type, address)
        elif cmd == 3:
            client_address = self.writer.get_extra_info("peername")
            if client_address:
                address = (client_address[0], client_address[1])
            await self.handle_udp(address)
        else:
            self.send_reply(Socks5Status.ENOTSUP)
            raise Exception("Command %d unsupported" % cmd)

    async def handle(self) -> None:
        try:
            first = await self.reader.readexactly(1)
            if (65 <= first[0] <= 90) or (97 <= first[0] <= 122):
                from .http_proxy_server import AsyncHTTPProxyHandler

                reader = PrefixedStreamReader(self.reader, first)
                await AsyncHTTPProxyHandler(reader, self.writer, self.server).handle()
                return

            if first[0] == SOCKS_VERSION:
                self.reader = PrefixedStreamReader(self.reader, first)
                await self._handle_socks5()
                return

            if first[0] == SOCKS4_VERSION:
                second = await self.reader.readexactly(1)
                if second[0] not in (SOCKS4_CONNECT, SOCKS4_BIND):
                    http_port = self.server.http_port or 9877
                    logger.warning(
                        "%s: not SOCKS4 (0x04 0x%02x) — misrouted TCP; "
                        "use HTTP proxy :%d or SOCKS5",
                        self.log_tag,
                        second[0],
                        http_port,
                    )
                    return
                await self._handle_socks4(second[0])
                return

            http_port = self.server.http_port or 9877
            raise Exception(
                "Invalid protocol %r (expected SOCKS4, SOCKS5, or HTTP; "
                "HTTP proxy is also on port %d)"
                % (chr(first[0]), http_port)
            )
        except asyncio.IncompleteReadError:
            logger.debug("%s: client closed during handshake", self.log_tag)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.error("%s: %s: %s", self.log_tag, type(e).__name__, e)
        finally:
            if not self.writer.is_closing():
                self.writer.close()
                await self.writer.wait_closed()

    async def read_addrport(self, address_type: int) -> SocketAddress | None:
        if address_type == Socks5AddressType.IPV4:
            ip = await self.reader.readexactly(4)
            address = socket.inet_ntop(socket.AF_INET, ip)
        elif address_type == Socks5AddressType.DOMAIN:
            domain_length = ord(await self.reader.readexactly(1))
            address = (await self.reader.readexactly(domain_length)).decode()
        elif address_type == Socks5AddressType.IPV6:
            ip = await self.reader.readexactly(16)
            address = socket.inet_ntop(socket.AF_INET6, ip)
        else:
            return None

        (port,) = await self.readstruct("!H")
        return address, port

    async def handle_connect(self, address_type: int, address: SocketAddress) -> None:
        try:
            connection = await self.server.tcp_connect(address_type, address)
        except Exception as e:
            self.send_reply(Socks5Status.EHOSTUNREACH)
            raise e

        self.send_reply(Socks5Status.SUCCEEDED)
        await self.tcp_forward(connection)

    async def handle_udp(self, client_address: SocketAddress) -> None:
        csock_addr = self.writer.get_extra_info("sockname")[0]

        # TODO: restrict incoming packets to client address
        try:
            udp_forwarder = UdpForwarder(self.log_tag, self.server, csock_addr)
            await udp_forwarder.start()
        except Exception as e:
            self.send_reply(Socks5Status.ERROR)
            raise e

        csock_port = udp_forwarder.client_conn.get_extra_info("sockname")[1]

        self.send_reply(Socks5Status.SUCCEEDED, (csock_addr, csock_port))
        try:
            while True:
                chunk = await self.reader.read(4096)
                if not chunk:
                    break
        finally:
            udp_forwarder.close()


if __name__ == "__main__":
    # Testing purposes only
    stats = status.StatusMonitor("SOCKS5 Server", interval=1)
    logging.getLogger().addHandler(stats)

    async def main() -> None:
        server = AsyncProxyServer(AsyncSocks5Handler, traffic_stats=stats)
        asyncio.create_task(server.run())
        await stats.render_forever()

    asyncio.run(main())
