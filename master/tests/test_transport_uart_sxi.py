"""Tests for the raw UART/SxI transport (framer + pyserial backend).

Framer-only tests run on every platform (pure Python). pyserial round-trip
tests use a POSIX ``pty`` pair and skip on Windows.

Cite: ADR-0004 (transport-abstraction-layer interface)
Cite: ADR-0010 row 8 (UART/SxI raw budget)
"""

from __future__ import annotations

import sys

import pytest

from tethys_master.transport import TransportId
from tethys_master.transport.uart_sxi import (
    UART_FRAME_OVERHEAD,
    UART_MTU,
    UART_START_BYTE,
    UartSxiTransport,
    _Framer,
    encode_frame,
)


def test_encode_frame_layout() -> None:
    frame = encode_frame(b"\x01\x02\x03")
    assert frame[0] == UART_START_BYTE
    assert frame[1] == 3
    assert frame[2:5] == b"\x01\x02\x03"
    # checksum = XOR of [start, len, payload]
    assert frame[5] == (UART_START_BYTE ^ 3 ^ 0x01 ^ 0x02 ^ 0x03)
    assert len(frame) == 3 + UART_FRAME_OVERHEAD


def test_encode_frame_empty_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        encode_frame(b"")


def test_encode_frame_oversize_rejected() -> None:
    with pytest.raises(ValueError, match="exceeds MTU"):
        encode_frame(b"x" * (UART_MTU + 1))


def test_framer_decodes_a_clean_frame() -> None:
    framer = _Framer()
    payload = b"hello"
    decoded = framer.feed(encode_frame(payload))
    assert decoded == [payload]


def test_framer_resyncs_after_garbage_prefix() -> None:
    framer = _Framer()
    junk = b"\x00\x11\x22"
    payload = b"abc"
    decoded = framer.feed(junk + encode_frame(payload))
    assert decoded == [payload]


def test_framer_checksum_mismatch_reports_loss_and_drops_frame() -> None:
    framer = _Framer()
    losses: list[int] = []
    framer.set_on_loss(lambda c: losses.append(c))
    frame = bytearray(encode_frame(b"abc"))
    frame[-1] ^= 0xFF  # corrupt the checksum
    decoded = framer.feed(bytes(frame))
    assert decoded == []
    assert losses == [1]


def test_framer_invalid_length_byte_reports_loss() -> None:
    framer = _Framer()
    losses: list[int] = []
    framer.set_on_loss(lambda c: losses.append(c))
    # start + len=0 - illegal
    framer.feed(bytes([UART_START_BYTE, 0]))
    assert losses == [1]
    # start + len > MTU - illegal
    framer.feed(bytes([UART_START_BYTE, UART_MTU + 1]))
    assert losses == [1, 1]


def test_framer_decodes_multiple_frames_in_one_chunk() -> None:
    framer = _Framer()
    payloads = [b"one", b"two", b"three"]
    blob = b"".join(encode_frame(p) for p in payloads)
    decoded = framer.feed(blob)
    assert decoded == payloads


def test_uart_metadata_fields() -> None:
    tr = UartSxiTransport("/dev/null", baud=115200)
    info = tr.info
    assert info.id == TransportId.UART_SXI
    assert info.name == "uart_sxi"
    assert info.mtu == UART_MTU
    assert info.supports_reliable is False
    assert info.supports_ordering is True


def test_uart_rejects_empty_port() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        UartSxiTransport("")


def test_uart_rejects_non_positive_baud() -> None:
    with pytest.raises(ValueError, match="baud must"):
        UartSxiTransport("/dev/null", baud=0)


# ---- pyserial round-trip over a POSIX pty pair ------------------


pytestmark_pty = pytest.mark.skipif(
    not sys.platform.startswith(("linux", "darwin")),
    reason="POSIX pty pair required for UART loopback test",
)


@pytestmark_pty
@pytest.mark.asyncio
async def test_uart_pty_round_trip() -> None:
    """End-to-end: send a payload, recv it back on the paired endpoint."""
    from tethys_sim.transport.uart_pty import uart_pty_pair  # type: ignore[import-not-found]

    async with uart_pty_pair() as (a, b):
        payload = b"\xde\xad\xbe\xef"
        await a.send(payload)
        got = await b.recv(timeout=2.0)
        assert got == payload
