"""Tests for the in-process loopback transport.

Loopback is the universal baseline that every other transport's correctness
is compared against (Phase 5 conformance suite).
"""

from __future__ import annotations

import asyncio

import pytest

from tethys_master.transport import TransportEventKind, TransportId
from tethys_master.transport.loopback import LOOPBACK_MTU, LoopbackTransport


@pytest.mark.asyncio
async def test_loopback_round_trip() -> None:
    """A.send(x) -> B.recv() == x, and the reverse."""
    a, b = LoopbackTransport.create_pair()
    async with a, b:
        await a.send(b"hello")
        assert await b.recv(timeout=1.0) == b"hello"

        await b.send(b"world")
        assert await a.recv(timeout=1.0) == b"world"


@pytest.mark.asyncio
async def test_loopback_metadata_matches_adr_0010_row_12() -> None:
    """Loopback declares zero loss + zero latency + ordered + reliable per ADR-0010 row 12."""
    a, _b = LoopbackTransport.create_pair()
    info = a.info
    assert info.id == TransportId.LOOPBACK
    assert info.name == "loopback"
    assert info.mtu == LOOPBACK_MTU
    assert info.supports_reliable is True
    assert info.supports_ordering is True
    assert info.max_burst_loss == 0
    assert info.typical_loss_per_pkt == 0.0


@pytest.mark.asyncio
async def test_loopback_close_idempotency() -> None:
    a, b = LoopbackTransport.create_pair()
    await a.open()
    await b.open()
    await a.close()
    await a.close()  # second close is a no-op
    assert not a.is_open
    await b.close()


@pytest.mark.asyncio
async def test_loopback_send_on_closed_raises() -> None:
    a, b = LoopbackTransport.create_pair()
    await a.open()
    await b.open()
    await a.close()
    with pytest.raises(RuntimeError):
        await a.send(b"x")
    await b.close()


@pytest.mark.asyncio
async def test_loopback_oversize_payload_raises() -> None:
    a, b = LoopbackTransport.create_pair()
    async with a, b:
        with pytest.raises(ValueError, match="exceeds MTU"):
            await a.send(b"x" * (LOOPBACK_MTU + 1))


@pytest.mark.asyncio
async def test_loopback_recv_timeout_raises_asyncio_timeout() -> None:
    a, b = LoopbackTransport.create_pair()
    async with a, b:
        with pytest.raises(asyncio.TimeoutError):
            await b.recv(timeout=0.05)


@pytest.mark.asyncio
async def test_inject_loss_fires_event_callback() -> None:
    a, b = LoopbackTransport.create_pair()
    captured: list[tuple[TransportEventKind, int]] = []
    b.set_event_callback(lambda ev: captured.append((ev.kind, ev.count)))
    async with a, b:
        await a.send(b"\x01")
        await a.send(b"\x02")
        await a.send(b"\x03")
        b.inject_loss(count=2)
    assert captured == [(TransportEventKind.LOSS, 2)]


@pytest.mark.asyncio
async def test_pair_does_not_cross_other_pairs() -> None:
    """Two independently created pairs must not see each other's traffic."""
    a, b = LoopbackTransport.create_pair(names=("pair1-a", "pair1-b"))
    c, d = LoopbackTransport.create_pair(names=("pair2-a", "pair2-b"))
    async with a, b, c, d:
        await a.send(b"to-pair1")
        await c.send(b"to-pair2")
        assert await b.recv(timeout=1.0) == b"to-pair1"
        assert await d.recv(timeout=1.0) == b"to-pair2"
        with pytest.raises(asyncio.TimeoutError):
            await b.recv(timeout=0.05)
