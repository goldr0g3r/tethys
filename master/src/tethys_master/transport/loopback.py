"""In-process loopback transport (universal baseline for conformance suite).

A pair of :class:`LoopbackTransport` instances backed by two
:class:`asyncio.Queue` objects: instance A's ``send`` enqueues onto instance
B's recv queue and vice versa. Used by the Phase 5 conformance suite as the
universal baseline so every other transport's correctness is asserted
against the same shape of tests.

Cite: ADR-0004 (transport-abstraction-layer interface)
Cite: ADR-0010 row 12 (loopback zero-loss budget)
Trace: docs/traceability.csv row TETHYS-DES-0031 (lands at PR-10)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from tethys_master.logging_setup import get_logger
from tethys_master.transport import (
    TransportEvent,
    TransportEventKind,
    TransportId,
    TransportInfo,
)

if TYPE_CHECKING:
    from typing import Self

logger = get_logger(__name__)

LOOPBACK_MTU: int = 256
"""Max payload per loopback frame; matches the XCP default MAX_DTO."""

LOOPBACK_DEFAULT_DEPTH: int = 32
"""Default ring depth — enough for the conformance suite's burst scenarios."""


class LoopbackTransport:
    """One end of a loopback pair.

    Instances are created in pairs via :meth:`create_pair`. Sending on one
    instance enqueues on the partner's recv queue; recv pulls from the local
    queue. ``open`` and ``close`` track the lifecycle so misuse (recv on a
    closed transport) raises predictably.

    Loss / latency-high events are not emitted by this transport in normal
    operation (loopback is zero-loss per ADR-0010 row 12), but the
    :meth:`inject_loss` helper lets the conformance suite verify the event
    callback wiring without needing a real lossy bus.
    """

    info: TransportInfo = TransportInfo(
        id=TransportId.LOOPBACK,
        name="loopback",
        mtu=LOOPBACK_MTU,
        supports_reliable=True,
        supports_ordering=True,
        max_burst_loss=0,
        typical_latency_us=0,
        typical_loss_per_pkt=0.0,
    )

    def __init__(self, *, depth: int = LOOPBACK_DEFAULT_DEPTH, name: str = "loopback") -> None:
        if depth < 1:
            msg = f"depth must be >= 1, got {depth}"
            raise ValueError(msg)
        self._depth = depth
        self._name = name
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=depth)
        self._peer: LoopbackTransport | None = None
        self._opened = False
        self._closed = False
        self._on_event: Callable[[TransportEvent], None] | None = None

    @classmethod
    def create_pair(
        cls,
        *,
        depth: int = LOOPBACK_DEFAULT_DEPTH,
        names: tuple[str, str] = ("loopback-a", "loopback-b"),
    ) -> tuple[Self, Self]:
        """Construct two loopback endpoints wired to each other.

        :param depth: per-endpoint recv queue depth. When the queue fills, the
                      sending side gets a :class:`asyncio.QueueFull` raised
                      as a backpressure signal (mirrors the C-side ring's
                      overwrite-oldest semantics; the conformance suite
                      catches both shapes).
        :param names: human-readable names for logs.
        :returns: ``(a, b)`` where ``a.send(x)`` makes ``b.recv()`` return
                  ``x`` and vice versa.
        """
        a = cls(depth=depth, name=names[0])
        b = cls(depth=depth, name=names[1])
        a._peer = b
        b._peer = a
        return a, b

    @property
    def is_open(self) -> bool:
        return self._opened and not self._closed

    @property
    def name(self) -> str:
        return self._name

    def set_event_callback(self, cb: Callable[[TransportEvent], None] | None) -> None:
        """Register or detach the out-of-band event callback."""
        self._on_event = cb

    async def open(self) -> None:
        if self._closed:
            msg = f"loopback {self._name!r} cannot be reopened after close"
            raise RuntimeError(msg)
        if self._peer is None:
            msg = f"loopback {self._name!r} has no peer; use LoopbackTransport.create_pair()"
            raise RuntimeError(msg)
        self._opened = True
        logger.info("loopback.opened", name=self._name, peer=self._peer._name)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._opened = False
            logger.info("loopback.closed", name=self._name)

    async def send(self, data: bytes) -> None:
        """Enqueue ``data`` onto the peer's recv queue.

        :raises RuntimeError: if the transport is not open.
        :raises ValueError:   if ``data`` is empty or larger than the MTU.
        :raises asyncio.QueueFull: if the peer's queue is full (back-pressure;
                                   mirrors the C-side ring's overwrite-oldest
                                   semantics in the inverse direction).
        """
        if not self.is_open or self._peer is None:
            msg = f"loopback {self._name!r} is not open"
            raise RuntimeError(msg)
        if not data:
            msg = "loopback.send: empty payload"
            raise ValueError(msg)
        if len(data) > LOOPBACK_MTU:
            msg = f"loopback.send: payload {len(data)} bytes exceeds MTU {LOOPBACK_MTU}"
            raise ValueError(msg)
        try:
            self._peer._rx_queue.put_nowait(bytes(data))
        except asyncio.QueueFull:
            self._emit_event(TransportEventKind.LOSS, count=1)
            raise

    async def recv(self, *, timeout: float | None = None) -> bytes:
        if not self.is_open:
            msg = f"loopback {self._name!r} is not open"
            raise RuntimeError(msg)
        if timeout is None:
            return await self._rx_queue.get()
        return await asyncio.wait_for(self._rx_queue.get(), timeout=timeout)

    def inject_loss(self, count: int = 1) -> None:
        """Manually drop ``count`` frames from the local recv queue and emit a
        :class:`TransportEvent` with kind :attr:`TransportEventKind.LOSS`.

        Used by the conformance suite to verify the event-callback wiring
        without needing a real lossy bus. Drops at most as many frames as are
        currently queued.
        """
        if count < 1:
            msg = f"count must be >= 1, got {count}"
            raise ValueError(msg)
        dropped = 0
        while dropped < count and not self._rx_queue.empty():
            try:
                _ = self._rx_queue.get_nowait()
                dropped += 1
            except asyncio.QueueEmpty:  # pragma: no cover - defensive
                break
        self._emit_event(TransportEventKind.LOSS, count=max(dropped, 1))

    def _emit_event(self, kind: TransportEventKind, *, count: int = 1) -> None:
        if self._on_event is None:
            return
        ev = TransportEvent(kind=kind, timestamp_us=0, count=count)
        self._on_event(ev)

    async def __aenter__(self) -> LoopbackTransport:
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
