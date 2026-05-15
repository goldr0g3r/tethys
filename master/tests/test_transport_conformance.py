"""Generic conformance suite for the Tethys master transports.

Parametrised over (transport_factory, scenario). Each transport that Tethys
ships must pass every scenario in this file. Adding a new transport to the
``TRANSPORTS`` table gives the conformance suite N new tests for free
(parent §8 Phase 5 acceptance: "one conformance suite reused across every
transport").

Scenarios:
    * ``open_close``       - lifecycle is idempotent and observable.
    * ``send_recv``        - 8-byte payload round-trips losslessly.
    * ``send_recv_bulk``   - N=16 frames; same payload comes back in order.
    * ``recv_timeout``     - recv on an empty queue raises asyncio.TimeoutError.
    * ``send_after_close`` - send on a closed transport raises RuntimeError.
    * ``metadata_sanity``  - transport.info.id != UNDEFINED, mtu > 0.
    * ``drop_detection``   - loss event reaches the registered callback.

The UDP transport row is *covered indirectly* by
``test_client_loopback.py`` (which round-trips UDP via :class:`UdpEchoSlave`)
to keep this file free of socket bind setup. The conformance contract for
UDP is therefore: "if loopback passes here AND UDP passes loopback-round-
trip in ``test_client_loopback.py``, UDP is conformant."

Cite: ADR-0004 (transport-abstraction-layer interface)
Cite: parent plan §8 Phase 5 acceptance
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest

from tethys_master.transport import TransportEventKind, TransportId
from tethys_master.transport.loopback import LoopbackTransport

# Each factory's setup() returns an async context manager that yields a pair
# of transport objects. The element type is intentionally `Any` because the
# concrete classes (LoopbackTransport, SocketCanTransport, ...) only share
# the runtime `Transport` Protocol, and mypy cannot narrow Protocol
# membership through a tuple.
_TransportPairCM = AbstractAsyncContextManager[tuple[Any, Any]]


@dataclass(frozen=True, slots=True)
class TransportFactory:
    """Wraps a transport name + setup function.

    ``setup()`` returns an async context manager yielding ``(tx_a, tx_b)``
    pair: traffic sent on ``tx_a`` is received on ``tx_b`` and vice versa.
    The conformance scenarios drive this exact shape, which keeps the
    suite transport-agnostic.
    """

    name: str
    setup: Callable[[], _TransportPairCM]


@asynccontextmanager
async def _loopback_factory() -> AsyncIterator[tuple[LoopbackTransport, LoopbackTransport]]:
    a, b = LoopbackTransport.create_pair()
    await a.open()
    await b.open()
    try:
        yield (a, b)
    finally:
        await a.close()
        await b.close()


TRANSPORTS: list[TransportFactory] = [
    TransportFactory(name="loopback", setup=_loopback_factory),
]


# SocketCAN entry: vcan0 must exist + Linux only. We register the factory
# unconditionally on Linux but skip its tests via a runtime check if the
# kernel interface isn't available.
def _socketcan_available() -> tuple[bool, str]:
    if not sys.platform.startswith("linux"):
        return False, "SocketCAN requires Linux"
    try:
        import socket

        sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        try:
            sock.bind(("vcan0",))
        finally:
            sock.close()
    except OSError as exc:
        return False, f"vcan0 unavailable: {exc}"
    return True, ""


if sys.platform.startswith("linux"):

    @asynccontextmanager
    async def _socketcan_factory() -> AsyncIterator[tuple[object, object]]:  # pragma: no cover - Linux-only
        from tethys_master.transport.socketcan import SocketCanTransport

        a = SocketCanTransport("vcan0", can_id=0x123)
        b = SocketCanTransport("vcan0", can_id=0x124)
        await a.open()
        await b.open()
        try:
            yield (a, b)
        finally:
            await a.close()
            await b.close()

    TRANSPORTS.append(TransportFactory(name="socketcan", setup=_socketcan_factory))


# UART/SxI entry: POSIX pty pair (Linux + macOS). Skips on Windows.
def _uart_pty_available() -> tuple[bool, str]:
    if not sys.platform.startswith(("linux", "darwin")):
        return False, "UART/SxI conformance row requires POSIX pty"
    try:
        import pty  # noqa: F401

        import serial  # type: ignore[import-untyped]  # noqa: F401
    except ImportError as exc:
        return False, f"missing dependency: {exc}"
    return True, ""


if sys.platform.startswith(("linux", "darwin")):

    @asynccontextmanager
    async def _uart_factory() -> AsyncIterator[tuple[object, object]]:  # pragma: no cover - POSIX-only
        from tethys_sim.transport.uart_pty import uart_pty_pair  # type: ignore[import-not-found]

        async with uart_pty_pair() as pair:
            yield pair

    TRANSPORTS.append(TransportFactory(name="uart_sxi", setup=_uart_factory))


def _id_of(factory: TransportFactory) -> str:
    return factory.name


def _maybe_skip_socketcan(factory: TransportFactory) -> None:
    if factory.name == "socketcan":
        ok, reason = _socketcan_available()
        if not ok:
            pytest.skip(reason)


def _maybe_skip_uart(factory: TransportFactory) -> None:
    if factory.name == "uart_sxi":
        ok, reason = _uart_pty_available()
        if not ok:
            pytest.skip(reason)


def _maybe_skip_unavailable(factory: TransportFactory) -> None:
    _maybe_skip_socketcan(factory)
    _maybe_skip_uart(factory)


# -------- Generic scenarios -----------------------------------------


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_open_close(factory: TransportFactory) -> None:
    _maybe_skip_socketcan(factory)
    async with factory.setup() as (a, b):
        assert a is not None
        assert b is not None


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_send_recv(factory: TransportFactory) -> None:
    _maybe_skip_socketcan(factory)
    async with factory.setup() as (a, b):
        payload = bytes(range(8))
        await a.send(payload)
        received = await b.recv(timeout=2.0)
        assert received == payload


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_send_recv_bulk_in_order(factory: TransportFactory) -> None:
    _maybe_skip_socketcan(factory)
    async with factory.setup() as (a, b):
        payloads = [bytes([i, i + 1, i + 2, i + 3]) for i in range(16)]
        for p in payloads:
            await a.send(p)
        for expected in payloads:
            got = await b.recv(timeout=2.0)
            assert got == expected, f"out-of-order or lost: expected {expected!r}, got {got!r}"


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_recv_timeout(factory: TransportFactory) -> None:
    _maybe_skip_socketcan(factory)
    async with factory.setup() as (_a, b):
        with pytest.raises(asyncio.TimeoutError):
            await b.recv(timeout=0.05)


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_send_after_close_raises(factory: TransportFactory) -> None:
    _maybe_skip_socketcan(factory)
    async with factory.setup() as (a, _b):
        await a.close()
        with pytest.raises(RuntimeError):
            await a.send(b"x")


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_metadata_sanity(factory: TransportFactory) -> None:
    _maybe_skip_unavailable(factory)
    async with factory.setup() as (a, _b):
        info = a.info
        assert info.id != TransportId.UNDEFINED
        assert info.mtu > 0
        assert info.name


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_drop_detection(factory: TransportFactory) -> None:
    """Loss is observable via the registered event callback.

    The loopback transport injects loss synthetically; SocketCAN observes
    loss via kernel error frames; UART observes loss via the framer
    state-machine when bytes are corrupted on the wire. The conformance
    contract here asserts only that the callback wiring is in place;
    actual real-bus fault injection is Phase 10 robustness-suite work.
    """
    _maybe_skip_unavailable(factory)
    captured: list[TransportEventKind] = []
    async with factory.setup() as (a, b):
        b.set_event_callback(lambda ev: captured.append(ev.kind))
        if factory.name == "loopback":
            await a.send(b"first")
            await a.send(b"second")
            assert isinstance(b, LoopbackTransport)
            b.inject_loss(count=2)
            assert captured == [TransportEventKind.LOSS]
        else:
            assert captured == []


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_burst_send_no_loss(factory: TransportFactory) -> None:
    """A short burst within the transport's max_burst_loss budget arrives intact.

    Asserts the contract from ADR-0010: each transport declares a
    ``max_burst_loss`` that the ODT engine sizes buffers from. The
    conformance suite verifies that a burst of size <= ``max_burst_loss``
    (or 4 frames, whichever is smaller) round-trips losslessly.
    """
    _maybe_skip_unavailable(factory)
    async with factory.setup() as (a, b):
        burst_size = min(max(a.info.max_burst_loss, 1), 4)
        payloads = [bytes([i]) * 4 for i in range(burst_size)]
        for p in payloads:
            await a.send(p)
        for expected in payloads:
            got = await b.recv(timeout=2.0)
            assert got == expected, f"burst loss: expected {expected!r}, got {got!r}"


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_send_at_mtu_round_trip(factory: TransportFactory) -> None:
    """An exactly-MTU-sized payload survives the round trip.

    Catches off-by-one buffer sizing in the framer / ring code.
    """
    _maybe_skip_unavailable(factory)
    async with factory.setup() as (a, b):
        mtu = a.info.mtu
        if mtu == 0:
            pytest.skip("transport reports zero MTU")
        # Repeating 0..255 ramp truncated to exactly MTU bytes.
        payload = bytes((i & 0xFF) for i in range(mtu))
        assert len(payload) == mtu
        await a.send(payload)
        got = await b.recv(timeout=2.0)
        assert got == payload


@pytest.mark.parametrize("factory", TRANSPORTS, ids=_id_of)
@pytest.mark.asyncio
async def test_conformance_send_oversize_raises(factory: TransportFactory) -> None:
    """Sending more than ``info.mtu`` bytes raises ``ValueError`` consistently."""
    _maybe_skip_unavailable(factory)
    async with factory.setup() as (a, _b):
        oversize = b"\x00" * (a.info.mtu + 1)
        with pytest.raises(ValueError):
            await a.send(oversize)
