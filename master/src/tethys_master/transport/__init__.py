"""Transport layer implementations for the Tethys master.

Phase 1 shipped UDP. Phase 5 (parent §8) adds the TAL freeze, loopback,
SocketCAN, and UART/SxI. The :class:`Transport` protocol is the frozen
interface contract per `ADR-0004 Transport abstraction layer
<../../../../docs/adr/0004-transport-abstraction-layer.md>`_; metadata is
surfaced through :class:`TransportInfo` instances (mirrors the C-side
``tethys_tr_descriptor_t`` field set).

Out-of-band events (loss, latency, bus-off, reconnect) are delivered via the
``on_event`` callback registration on transports that observe them.

The Python ``Transport`` ``runtime_checkable`` protocol intentionally does
not include ``info`` directly so that compile-time type checks against
single-purpose mocks don't break; concrete transports expose ``info`` as a
class or instance attribute.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Protocol, runtime_checkable

__all__ = [
    "Transport",
    "TransportEvent",
    "TransportEventCallback",
    "TransportEventKind",
    "TransportId",
    "TransportInfo",
]


class TransportId(IntEnum):
    """Stable transport identifier; mirrors the C ``tethys_tr_id_t`` enum.

    Values are kept in lockstep with ``slave/include/tethys/tethys_transport.h``
    so MDF4 headers written by the master decode identically to logs emitted
    by the C slave.
    """

    UNDEFINED = 0
    LOOPBACK = 1
    UDP = 2
    TCP = 3
    CAN_FD = 4
    SOCKETCAN = 5
    UART_SXI = 6
    CCSDS_COP1_AD = 7
    CCSDS_TM = 8
    CAN_1WIRE = 9


class TransportEventKind(IntEnum):
    """Out-of-band event categories; mirrors the C ``tethys_tr_evt_kind_t``."""

    LOSS = 0
    LATENCY_HIGH = 1
    BUS_OFF = 2
    BUS_RECOVERED = 3
    RECONNECTED = 4


@dataclass(frozen=True, slots=True)
class TransportEvent:
    """Structured event handed to event callbacks.

    Mirrors the C ``tethys_tr_event_t`` layout. ``timestamp_us`` is the
    monotonic time at event observation; ``count`` is the number of frames
    affected (e.g. burst-loss length).
    """

    kind: TransportEventKind
    timestamp_us: int
    count: int = 1


TransportEventCallback = "callable[[TransportEvent], None]"


@dataclass(frozen=True, slots=True)
class TransportInfo:
    """Metadata declared by each concrete transport at registration time.

    These fields drive ODT buffer sizing (``max_burst_loss``), CTO timeout
    selection (``typical_latency_us``), DAQ_GAP alert thresholds
    (``typical_loss_per_pkt``), and the MDF4 header. They are immutable for
    the lifetime of the transport instance — switching transports requires
    constructing a new :class:`Transport` object.

    The ``typical_loss_per_pkt`` field is a fraction (0.0 .. 1.0); the C-side
    descriptor expresses the same number in parts-per-billion (PPB) to avoid
    floating point in the slave (see ``tethys_transport.h``).
    """

    id: TransportId
    name: str
    mtu: int
    supports_reliable: bool
    supports_ordering: bool
    max_burst_loss: int = 0
    typical_latency_us: int = 0
    typical_loss_per_pkt: float = 0.0
    extra: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class Transport(Protocol):
    """Minimal transport interface every concrete transport implements.

    See `ADR-0004 Transport abstraction layer <../../../../docs/adr/0004-transport-abstraction-layer.md>`_.

    Concrete transports additionally expose:

    - ``info``: a :class:`TransportInfo` instance with the capability flags.
    - ``on_event``: optional ``Callable[[TransportEvent], None]`` setter for
      out-of-band event delivery.
    """

    async def open(self) -> None: ...

    async def close(self) -> None: ...

    async def send(self, data: bytes) -> None: ...

    async def recv(self, *, timeout: float | None = None) -> bytes: ...


def _validate_timeout(timeout: float | None) -> None:
    """Common timeout validation used by every transport's ``recv``.

    Negative timeouts are a programming error; raise ``ValueError`` so the
    bug surfaces at the caller, not as a silently-mis-scheduled wait. None
    means "wait forever" and is encouraged for the highest-level callers
    that wrap timeouts in :func:`asyncio.wait_for`.
    """
    if timeout is None:
        return
    if timeout < 0.0:
        msg = f"timeout must be >= 0, got {timeout}"
        raise ValueError(msg)


async def _await_with_optional_timeout(future: asyncio.Future[bytes], timeout: float | None) -> bytes:
    """Internal helper: await a future with an optional asyncio timeout.

    Used by ``recv`` on transports backed by an :class:`asyncio.Queue`.
    Raises :class:`asyncio.TimeoutError` on deadline expiry.
    """
    if timeout is None:
        return await future
    return await asyncio.wait_for(future, timeout=timeout)
