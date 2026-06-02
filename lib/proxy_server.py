""" General base class for proxies """

import asyncio
import logging
import random
import socket
import sys
from asyncio.staggered import staggered_race
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Coroutine, Sequence, Type

from dns.asyncresolver import Resolver
from dns.inet import af_for_address

from . import status

logger = logging.getLogger("socks5")

SocketAddress = tuple[str, int]
Connection = tuple[asyncio.StreamReader, asyncio.StreamWriter]

_RETRIABLE_CONNECT_ERRNOS = frozenset({9, 22, 49, 51, 53, 54, 57, 64, 65})


def _normalize_bind_host(host: str | None) -> str | None:
    if host in (None, "", "0.0.0.0", "::"):
        return None
    return host


def _is_pythonista() -> bool:
    return "Pythonista" in sys.executable


@dataclass
class GenericAddress:
    ipv4: SocketAddress | None = None
    ipv6: SocketAddress | None = None


HAPPY_EYEBALLS_DELAY = 0.05  # seconds
CONNECT_TIMEOUT = 75  # seconds


async def forwarder_loop(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    stat_fn: Callable[[int], None],
) -> None:
    try:
        while 1:
            buf = await reader.read(65536)
            if not buf:
                break
            stat_fn(len(buf))
            writer.write(buf)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


# XXX: should make this a more generic address type enum and convert from socks5
class Socks5AddressType(IntEnum):
    IPV4 = 1
    DOMAIN = 3
    IPV6 = 4


class AsyncProxyHandler:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        server: "AsyncProxyServer",
    ):
        self.reader = reader
        self.writer = writer
        self.server = server

        peer_addr = writer.get_extra_info("peername")
        if peer_addr is None:
            self.log_tag = "<unknown>"
        elif len(peer_addr) == 2:
            # IPv4
            self.log_tag = "%s:%s" % peer_addr
        elif len(peer_addr) == 4:
            # IPv6
            self.log_tag = "[%s]:%s" % peer_addr[:2]
        else:
            self.log_tag = "[%s]" % (peer_addr,)

    async def tcp_forward(self, connection: Connection) -> None:
        s_reader, s_writer = connection
        await asyncio.gather(
            forwarder_loop(
                s_reader, self.writer, self.server.traffic_stats.add_inbound
            ),
            forwarder_loop(
                self.reader, s_writer, self.server.traffic_stats.add_outbound
            ),
            return_exceptions=True,
        )

    async def handle(self) -> None:
        pass


class AsyncProxyServer:
    def __init__(
        self,
        handler_class: Type[AsyncProxyHandler],
        listen_hosts: str | Sequence[str] = ("::", "0.0.0.0"),
        listen_port: int = 9876,
        traffic_stats: status.TrafficStats | None = None,
        resolver: Resolver | None = None,
        connect_host_ipv4: str | None = None,
        connect_host_ipv6: str | None = None,
        prefer_system_dns: bool = False,
        http_port: int | None = None,
        access_log: bool = False,
        pac_body: bytes | None = None,
    ):
        self.handler_class = handler_class
        self.listen_hosts = listen_hosts
        self.listen_port = listen_port
        self.http_port = http_port
        self.traffic_stats = traffic_stats or status.SimpleTrafficStats()
        self.prefer_system_dns = prefer_system_dns
        self.access_log = access_log
        self.pac_body = pac_body
        self.connect_host_ipv4 = _normalize_bind_host(connect_host_ipv4)
        self.connect_host_ipv6 = _normalize_bind_host(connect_host_ipv6)
        if resolver is not None:
            self.resolver = resolver
        elif not prefer_system_dns:
            self.resolver = Resolver()
        else:
            self.resolver = None
        self.resolver_source: str | None = None
        self._async_server: asyncio.Server | None = None
        if (
            not self.prefer_system_dns
            and self.resolver is not None
            and (
                self.connect_host_ipv4 is not None
                or self.connect_host_ipv6 is not None
            )
        ):
            resolver_afs = [af_for_address(ns) for ns in self.resolver.nameservers]
            if (
                any(af == socket.AF_INET for af in resolver_afs)
                and self.connect_host_ipv4 is not None
            ):
                self.resolver_source = self.connect_host_ipv4
                self.resolver.nameservers = [
                    ns
                    for ns in self.resolver.nameservers
                    if af_for_address(ns) == socket.AF_INET
                ]
            elif (
                any(af == socket.AF_INET6 for af in resolver_afs)
                and self.connect_host_ipv6 is not None
            ):
                self.resolver_source = self.connect_host_ipv6
                self.resolver.nameservers = [
                    ns
                    for ns in self.resolver.nameservers
                    if af_for_address(ns) == socket.AF_INET6
                ]
            else:
                raise Exception("Resolver does not have any suitable nameservers!")

    def _want_ipv4(self) -> bool:
        return not (
            self.connect_host_ipv4 is None and self.connect_host_ipv6 is not None
        )

    def _want_ipv6(self) -> bool:
        return not (
            self.connect_host_ipv4 is not None and self.connect_host_ipv6 is None
        )

    def _domain_name(self, address: SocketAddress) -> str:
        return address[0] if isinstance(address, tuple) else str(address)

    def _resolution_failed(self, domain: str, detail: str = "") -> Exception:
        msg = "Host %s could not be resolved" % domain
        if detail:
            msg += " (%s)" % detail
        return Exception(msg)

    async def run(self) -> None:
        self._async_server = await asyncio.start_server(
            self.client_connected,
            host=self.listen_hosts,
            port=self.listen_port,
            reuse_address=True,
        )
        await self._async_server.serve_forever()

    async def close(self) -> None:
        server = self._async_server
        if server is None:
            return
        server.close()
        await server.wait_closed()
        self._async_server = None

    async def client_connected(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        handler = self.handler_class(reader, writer, server=self)
        self.traffic_stats.add_connection()
        try:
            await handler.handle()
        finally:
            self.traffic_stats.remove_connection()

    def _local_addr_ipv4(self) -> tuple[str, int] | None:
        if self.connect_host_ipv4 is None:
            return None
        return (self.connect_host_ipv4, 0)

    def _local_addr_ipv6(self) -> tuple[str, int] | None:
        if self.connect_host_ipv6 is None:
            return None
        return (self.connect_host_ipv6, 0)

    async def _open_connection_inner(
        self, host: str, port: int, local_addr: tuple[str, int] | None
    ) -> Connection:
        connect = asyncio.open_connection(host, port, local_addr=local_addr)
        try:
            return await asyncio.wait_for(connect, timeout=CONNECT_TIMEOUT)
        except OSError as exc:
            if local_addr is None or exc.errno not in _RETRIABLE_CONNECT_ERRNOS:
                raise
            logger.warning(
                "Connect via %s failed (%s); retrying default route",
                local_addr[0],
                exc,
            )
            return await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=CONNECT_TIMEOUT,
            )

    async def _open_connection(
        self, host: str, port: int, local_addr: tuple[str, int] | None
    ) -> Connection:
        return await self._open_connection_inner(host, port, local_addr)

    async def ipv4_connect(self, address: SocketAddress) -> Connection:
        return await self._open_connection(
            address[0], address[1], self._local_addr_ipv4()
        )

    async def ipv6_connect(self, address: SocketAddress) -> Connection:
        return await self._open_connection(
            address[0], address[1], self._local_addr_ipv6()
        )

    async def tcp_connect(
        self, address_type: int, address: SocketAddress
    ) -> Connection:
        resolved = await self.resolve_address(address_type, address)

        if resolved.ipv4 is not None and resolved.ipv6 is not None:
            if _is_pythonista():
                errors: list[BaseException] = []
                for connect in (
                    lambda: self.ipv4_connect(resolved.ipv4),
                    lambda: self.ipv6_connect(resolved.ipv6),
                ):
                    try:
                        return await connect()
                    except BaseException as exc:
                        errors.append(exc)
                if errors:
                    raise errors[0]
                raise Exception("connect failed")
            ipv6_addr = resolved.ipv6
            ipv4_addr = resolved.ipv4
            result, result_index, exceptions = await staggered_race(
                [
                    lambda: self.ipv6_connect(ipv6_addr),
                    lambda: self.ipv4_connect(ipv4_addr),
                ],
                delay=HAPPY_EYEBALLS_DELAY,
            )
            if not result:
                raise exceptions[0]
            return result
        elif resolved.ipv4 is not None:
            return await self.ipv4_connect(resolved.ipv4)
        elif resolved.ipv6 is not None:
            return await self.ipv6_connect(resolved.ipv6)
        else:
            raise self._resolution_failed(self._domain_name(address))

    async def dummy_resolve(self):
        raise Exception("address family not supported")

    async def _resolve_domain_system(self, domain: str, port: int) -> GenericAddress:
        loop = asyncio.get_running_loop()
        families: list[int] = []
        if self._want_ipv4():
            families.append(socket.AF_INET)
        if self._want_ipv6():
            families.append(socket.AF_INET6)
        if not families:
            families = [socket.AF_INET, socket.AF_INET6]

        result = GenericAddress()
        errors: list[str] = []
        for family in families:
            label = "IPv4" if family == socket.AF_INET else "IPv6"
            try:
                infos = await loop.getaddrinfo(
                    domain,
                    port,
                    family=family,
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror as exc:
                errors.append("%s: %s" % (label, exc))
                continue
            if infos:
                addr = (infos[0][4][0], port)
                if family == socket.AF_INET:
                    result.ipv4 = addr
                else:
                    result.ipv6 = addr

        if not result.ipv4 and not result.ipv6 and errors:
            raise self._resolution_failed(
                domain, "system getaddrinfo: " + "; ".join(errors)
            )
        return result

    async def _resolve_domain_custom(self, domain: str, port: int) -> GenericAddress:
        if self.resolver is None:
            raise self._resolution_failed(domain, "no custom resolver")

        result = GenericAddress()
        dns_errors: list[str] = []

        if self._want_ipv4():
            if self.connect_host_ipv4 is None and self.connect_host_ipv6 is not None:
                ipv4_resolver = self.dummy_resolve()
            else:
                ipv4_resolver = self.resolver.resolve(
                    domain, "A", source=self.resolver_source
                )
        else:
            ipv4_resolver = self.dummy_resolve()

        if self._want_ipv6():
            if self.connect_host_ipv4 is not None and self.connect_host_ipv6 is None:
                ipv6_resolver = self.dummy_resolve()
            else:
                ipv6_resolver = self.resolver.resolve(
                    domain, "AAAA", source=self.resolver_source
                )
        else:
            ipv6_resolver = self.dummy_resolve()

        ipv4, ipv6 = await asyncio.gather(
            ipv4_resolver,
            ipv6_resolver,
            return_exceptions=True,
        )
        if isinstance(ipv4, BaseException):
            dns_errors.append("A: %s" % ipv4)
        elif ipv4:
            result.ipv4 = (random.choice(ipv4).address, port)
        if isinstance(ipv6, BaseException):
            dns_errors.append("AAAA: %s" % ipv6)
        elif ipv6:
            result.ipv6 = (random.choice(ipv6).address, port)

        if result.ipv4 is None and result.ipv6 is None and dns_errors:
            raise self._resolution_failed(domain, "; ".join(dns_errors))
        return result

    async def _resolve_domain(self, address: SocketAddress) -> GenericAddress:
        domain, port = address

        result = GenericAddress()
        try:
            socket.inet_pton(socket.AF_INET, domain)
            result.ipv4 = address
            return result
        except Exception:
            pass

        try:
            socket.inet_pton(socket.AF_INET6, domain)
            result.ipv6 = address
            return result
        except Exception:
            pass

        dns_errors: list[str] = []
        resolvers: list[tuple[str, Callable[[], Coroutine]]] = []
        if self.prefer_system_dns:
            resolvers.append(
                ("system", lambda: self._resolve_domain_system(domain, port))
            )
            resolvers.append(
                ("custom", lambda: self._resolve_domain_custom(domain, port))
            )
        else:
            resolvers.append(
                ("custom", lambda: self._resolve_domain_custom(domain, port))
            )
            resolvers.append(
                ("system", lambda: self._resolve_domain_system(domain, port))
            )

        for label, resolve in resolvers:
            try:
                candidate = await resolve()
                if candidate.ipv4 or candidate.ipv6:
                    if label == "system" and len(resolvers) > 1:
                        logger.info("DNS via system resolver for %s", domain)
                    return candidate
            except Exception as exc:
                dns_errors.append("%s: %s" % (label, exc))

        raise self._resolution_failed(domain, "; ".join(dns_errors) or "no answer")

    async def resolve_address(
        self, address_type: int, address: SocketAddress
    ) -> GenericAddress:
        if address_type == Socks5AddressType.IPV4:
            result = GenericAddress(ipv4=address)
        elif address_type == Socks5AddressType.DOMAIN:
            result = await self._resolve_domain(address)
        elif address_type == Socks5AddressType.IPV6:
            result = GenericAddress(ipv6=address)

        if self.connect_host_ipv4 is None and self.connect_host_ipv6 is not None:
            result.ipv4 = None
        elif self.connect_host_ipv4 is not None and self.connect_host_ipv6 is None:
            result.ipv6 = None

        if (
            address_type == Socks5AddressType.DOMAIN
            and not result.ipv4
            and not result.ipv6
        ):
            raise self._resolution_failed(self._domain_name(address))

        return result
