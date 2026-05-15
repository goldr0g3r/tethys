"""UDP transport for XCP-on-IP.

Implements the minimal request/response datagram pattern needed for the
Phase 1 acceptance bench: bidirectional UDP socket bound to ``0.0.0.0:0``
(ephemeral) with a known peer ``(host, port)``.

Cite: ASAM XCP-on-Ethernet 1.0 §3.1 (XCP on UDP framing)
Cite: parent plan section 3.2 (transport_eth.c equivalent on the master side)
Trace: docs/traceability.csv row TETHYS-DES-0030 (lands at PR-10)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tethys_master.logging_setup import get_logger
from tethys_master.transport import TransportId, TransportInfo

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class _UdpProtocol(asyncio.DatagramProtocol):
    """Internal asyncio DatagramProtocol that pushes received datagrams to a queue."""

    def __init__(self, queue: asyncio.Queue[bytes], on_lost: Callable[[Exception | None], None]) -> None:
        self._queue = queue
        self._on_lost = on_lost
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        if not isinstance(transport, asyncio.DatagramTransport):
            msg = f"Unexpected transport type: {type(transport).__name__}"
            raise TypeError(msg)
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        logger.debug("udp.recv", bytes=len(data), peer=f"{addr[0]}:{addr[1]}")
        self._queue.put_nowait(bytes(data))

    def error_received(self, exc: Exception) -> None:
        logger.warning("udp.error", exc=str(exc))

    def connection_lost(self, exc: Exception | None) -> None:
        logger.info("udp.connection_lost", exc=str(exc) if exc else None)
        self._on_lost(exc)


class UdpTransport:
    """UDP point-to-point transport for XCP frames.

    The socket binds to an ephemeral local port. The remote peer is the
    address passed in the constructor.
    """

    # Phase 5 PR-C: declare the TransportInfo per ADR-0004 so the conformance
    # suite can metadata-test UDP without instantiating it. Values mirror
    # ADR-0010 row 1/2/3 (marine UDP CTO/DAQ): unreliable, ordered (modulo
    # IP-level reorder which is rare on a single hop), 1500-byte MTU.
    info: TransportInfo = TransportInfo(
        id=TransportId.UDP,
        name="udp",
        mtu=1500,
        supports_reliable=False,
        supports_ordering=True,
        max_burst_loss=4,
        typical_latency_us=200,
        typical_loss_per_pkt=1e-4,
    )

    def __init__(self, remote_host: str, remote_port: int) -> None:
        if not (1 <= remote_port <= 65535):
            msg = f"port out of range: {remote_port}"
            raise ValueError(msg)
        self._remote_addr = (remote_host, remote_port)
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _UdpProtocol | None = None
        self._lost = asyncio.Event()

    async def open(self) -> None:
        loop = asyncio.get_running_loop()
        protocol = _UdpProtocol(self._rx_queue, lambda _: self._lost.set())
        transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=("0.0.0.0", 0),  # noqa: S104 - intentional bind-any for loopback bench
            remote_addr=self._remote_addr,
        )
        self._transport = transport
        self._protocol = protocol
        local = transport.get_extra_info("sockname")
        logger.info(
            "udp.opened",
            local=f"{local[0]}:{local[1]}",
            remote=f"{self._remote_addr[0]}:{self._remote_addr[1]}",
        )

    async def close(self) -> None:
        if self._transport is not None and not self._transport.is_closing():
            self._transport.close()
            logger.info("udp.closed")

    async def send(self, data: bytes) -> None:
        if self._transport is None:
            msg = "Transport not open; call open() first"
            raise RuntimeError(msg)
        self._transport.sendto(bytes(data))
        logger.debug("udp.send", bytes=len(data))

    async def recv(self, *, timeout: float | None = None) -> bytes:
        """Wait for the next datagram. ``timeout`` in seconds."""
        if self._transport is None:
            msg = "Transport not open; call open() first"
            raise RuntimeError(msg)
        return await asyncio.wait_for(self._rx_queue.get(), timeout=timeout)

    async def __aenter__(self) -> UdpTransport:
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()


class UdpEchoSlave:
    """Tiny UDP server used by tests to imitate a slave for round-trip testing.

    Not part of the public master API. Lives here so tests can construct a
    loopback bench without depending on simulator/.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._host = host
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._handler: Callable[[bytes, tuple[str, int]], bytes | None] | None = None
        self.actual_port: int = 0

    def set_handler(self, handler: Callable[[bytes, tuple[str, int]], bytes | None]) -> None:
        self._handler = handler

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        slave = self  # for the inner protocol class capture

        class _ServerProtocol(asyncio.DatagramProtocol):
            transport: asyncio.DatagramTransport | None = None

            def connection_made(self, t: asyncio.BaseTransport) -> None:
                if not isinstance(t, asyncio.DatagramTransport):
                    msg = f"Unexpected transport type: {type(t).__name__}"
                    raise TypeError(msg)
                self.transport = t

            def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
                if slave._handler is None or self.transport is None:
                    return
                response = slave._handler(bytes(data), addr)
                if response is not None:
                    self.transport.sendto(response, addr)

        transport, _ = await loop.create_datagram_endpoint(
            _ServerProtocol,
            local_addr=(self._host, self._port),
        )
        self._transport = transport
        sockname = transport.get_extra_info("sockname")
        self.actual_port = int(sockname[1])

    async def stop(self) -> None:
        if self._transport is not None and not self._transport.is_closing():
            self._transport.close()
