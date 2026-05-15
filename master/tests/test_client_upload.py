"""Loopback roundtrip tests for SET_MTA / UPLOAD / SHORT_UPLOAD.

These extend test_client_loopback.py with a memory-backed loopback slave
so the XCP read-path commands can be exercised end-to-end on the master
side without standing up the C dispatcher.

Cite: ASAM XCP 1.4 Part 2 §1.3.3.1 SET_MTA
Cite: ASAM XCP 1.4 Part 2 §1.3.3.2 UPLOAD
Cite: ASAM XCP 1.4 Part 2 §1.3.3.6 SHORT_UPLOAD
"""

from __future__ import annotations

import pytest

from tethys_master.protocol.client import XcpClient, XcpProtocolError
from tethys_master.protocol.frame import (
    XCP_MAX_UPLOAD_BYTES,
    ConnectResponse,
    ResourceMask,
    XcpCommand,
    XcpError,
    encode_error_response,
    encode_positive_response,
)
from tethys_master.transport.udp import UdpEchoSlave, UdpTransport

MEMORY_SIZE = 256


def _build_handler():  # type: ignore[no-untyped-def]
    """Build a memory-backed slave handler.

    Returns (handler, state_view) so tests can read back the MTA the handler
    saw without parsing protocol frames again.
    """
    state = {
        "connected": False,
        "mta_address": 0,
        "mta_extension": 0,
        "memory": bytearray((i & 0xFF) for i in range(MEMORY_SIZE)),
    }

    def handler(packet: bytes, _addr: tuple[str, int]) -> bytes | None:  # noqa: PLR0911, PLR0912 - one branch per XCP command + per-error-class return
        if not packet:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        cmd = packet[0]
        if cmd == XcpCommand.CONNECT:
            state["connected"] = True
            response = ConnectResponse(
                resource=ResourceMask.DAQ | ResourceMask.CAL_PAG,
                comm_mode_basic=0x80,
                max_cto=8,
                max_dto=256,
                protocol_version=0x01,
                transport_version=0x01,
            )
            return encode_positive_response(response.encode_body())
        if cmd == XcpCommand.DISCONNECT:
            state["connected"] = False
            return encode_positive_response(b"")
        if cmd == XcpCommand.SET_MTA:
            if not state["connected"]:
                return encode_error_response(XcpError.ERR_ACCESS_DENIED)
            if len(packet) < 8:
                return encode_error_response(XcpError.ERR_CMD_SYNTAX)
            state["mta_extension"] = packet[3]
            state["mta_address"] = int.from_bytes(packet[4:8], "little", signed=False)
            return encode_positive_response(b"")
        if cmd == XcpCommand.UPLOAD:
            if not state["connected"]:
                return encode_error_response(XcpError.ERR_ACCESS_DENIED)
            if len(packet) < 2:
                return encode_error_response(XcpError.ERR_CMD_SYNTAX)
            num = packet[1]
            if num < 1 or num > XCP_MAX_UPLOAD_BYTES:
                return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
            start = state["mta_address"]
            if start + num > MEMORY_SIZE:
                return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
            chunk = bytes(state["memory"][start : start + num])
            state["mta_address"] += num
            return encode_positive_response(chunk)
        if cmd == XcpCommand.SHORT_UPLOAD:
            if not state["connected"]:
                return encode_error_response(XcpError.ERR_ACCESS_DENIED)
            if len(packet) < 8:
                return encode_error_response(XcpError.ERR_CMD_SYNTAX)
            num = packet[1]
            if num < 1 or num > XCP_MAX_UPLOAD_BYTES:
                return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
            address = int.from_bytes(packet[4:8], "little", signed=False)
            if address + num > MEMORY_SIZE:
                return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
            return encode_positive_response(bytes(state["memory"][address : address + num]))
        return encode_error_response(XcpError.ERR_CMD_UNKNOWN)

    return handler, state


@pytest.mark.asyncio
async def test_set_mta_then_upload_returns_ramp_pattern() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    handler, state = _build_handler()
    slave.set_handler(handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.set_mta(address=0x10, address_extension=0)
            assert state["mta_address"] == 0x10
            assert state["mta_extension"] == 0

            chunk = await client.upload(num_bytes=4)
            assert chunk == bytes([0x10, 0x11, 0x12, 0x13])
            assert state["mta_address"] == 0x14  # auto-incremented

            chunk2 = await client.upload(num_bytes=2)
            assert chunk2 == bytes([0x14, 0x15])
            assert state["mta_address"] == 0x16
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_short_upload_does_not_change_mta() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    handler, state = _build_handler()
    slave.set_handler(handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.set_mta(address=0x80, address_extension=0)
            assert state["mta_address"] == 0x80

            chunk = await client.short_upload(num_bytes=3, address=0x20)
            assert chunk == bytes([0x20, 0x21, 0x22])
            assert state["mta_address"] == 0x80  # unchanged
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_upload_out_of_range_raises_protocol_error() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    handler, _state = _build_handler()
    slave.set_handler(handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.set_mta(address=MEMORY_SIZE - 2, address_extension=0)
            with pytest.raises(XcpProtocolError) as exc_info:
                await client.upload(num_bytes=4)
            assert exc_info.value.code == XcpError.ERR_OUT_OF_RANGE
    finally:
        await slave.stop()
