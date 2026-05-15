"""SocketCAN-specific transport tests (Linux + vcan0 required).

These tests verify that the Linux SocketCAN transport's wire-level behaviour
matches the abstract conformance contract. Non-Linux hosts skip everything
here automatically; Linux hosts without a ``vcan0`` interface also skip and
print an instructive reason so the contributor knows what to set up.

To enable on Linux:

.. code-block:: shell

    sudo modprobe vcan
    sudo ip link add dev vcan0 type vcan
    sudo ip link set up vcan0

Cite: ADR-0004 (transport-abstraction-layer interface)
Cite: ADR-0010 row 7 (SocketCAN host-side budget)
Cite: ISO 11898-1:2024 (CAN data-link layer)
"""

from __future__ import annotations

import socket
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="SocketCAN is a Linux-only kernel feature",
)


def _vcan0_available() -> tuple[bool, str]:
    """Return ``(available, reason)`` for vcan0 bind."""
    if not sys.platform.startswith("linux"):
        return False, "non-Linux host"
    try:
        sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        try:
            sock.bind(("vcan0",))
        finally:
            sock.close()
    except OSError as exc:
        return (
            False,
            f"vcan0 unavailable: {exc} - run 'sudo modprobe vcan && "
            f"sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0'",
        )
    return True, ""


@pytest.fixture()
def _require_vcan0() -> Iterator[None]:
    available, reason = _vcan0_available()
    if not available:
        pytest.skip(reason)
    yield


@pytest.mark.asyncio
async def test_socketcan_metadata_marine_defaults(_require_vcan0: None) -> None:
    from tethys_master.transport import TransportId
    from tethys_master.transport.socketcan import (
        SOCKETCAN_MTU_CLASSIC,
        SocketCanTransport,
    )

    tr = SocketCanTransport("vcan0")
    info = tr.info
    assert info.id == TransportId.SOCKETCAN
    assert info.name == "socketcan"
    assert info.mtu == SOCKETCAN_MTU_CLASSIC
    assert info.supports_reliable is False
    assert info.supports_ordering is True


@pytest.mark.asyncio
async def test_socketcan_send_recv_vcan0(_require_vcan0: None) -> None:
    from tethys_master.transport.socketcan import SocketCanTransport

    sender = SocketCanTransport("vcan0", can_id=0x100)
    receiver = SocketCanTransport("vcan0", can_id=0x101)
    await sender.open()
    await receiver.open()
    try:
        payload = bytes([0xDE, 0xAD, 0xBE, 0xEF])
        await sender.send(payload)
        # vcan loops everything to every reader on the interface
        got = await receiver.recv(timeout=1.0)
        assert got == payload
    finally:
        await sender.close()
        await receiver.close()


def test_socketcan_rejects_empty_ifname() -> None:
    """Even on Linux, constructing with an empty ifname is rejected."""
    from tethys_master.transport.socketcan import SocketCanTransport

    with pytest.raises(ValueError, match="non-empty"):
        SocketCanTransport("")


def test_socketcan_rejects_out_of_range_can_id() -> None:
    from tethys_master.transport.socketcan import SocketCanTransport

    with pytest.raises(ValueError, match="out of CAN"):
        SocketCanTransport("vcan0", can_id=0x80000000)
