"""Loopback roundtrip tests for DOWNLOAD / BUILD_CHECKSUM / SYNCH.

Re-uses the memory-backed loopback slave pattern from
``test_client_upload.py`` so the master + simulator wire-level contract
is exercised end-to-end on the master side without standing up the C
dispatcher.

Cite: ASAM XCP 1.4 Part 2 §1.3.4.1 DOWNLOAD
Cite: ASAM XCP 1.4 Part 2 §1.5.1 BUILD_CHECKSUM
Cite: ASAM XCP 1.4 Part 2 §1.3.1.2 SYNCH
"""

from __future__ import annotations

import pytest

from tethys_master.protocol.client import XcpClient, XcpProtocolError
from tethys_master.protocol.frame import (
    XCP_MAX_DOWNLOAD_BYTES,
    BuildChecksumResponse,
    ConnectResponse,
    ResourceMask,
    XcpChecksumType,
    XcpCommand,
    XcpError,
    encode_error_response,
    encode_positive_response,
)
from tethys_master.transport.udp import UdpEchoSlave, UdpTransport

MEMORY_SIZE = 256


def _build_full_handler():  # type: ignore[no-untyped-def]
    """Build a memory-backed slave handler implementing every Phase-2 command."""
    state = {
        "connected": False,
        "mta_address": 0,
        "mta_extension": 0,
        "memory": bytearray((i & 0xFF) for i in range(MEMORY_SIZE)),
    }

    def handler(packet: bytes, _addr: tuple[str, int]) -> bytes | None:  # noqa: PLR0911 - one branch per XCP command
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
            state["mta_extension"] = packet[3]
            state["mta_address"] = int.from_bytes(packet[4:8], "little", signed=False)
            return encode_positive_response(b"")
        if cmd == XcpCommand.DOWNLOAD:
            num = packet[1]
            if num < 1 or num > XCP_MAX_DOWNLOAD_BYTES:
                return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
            start = state["mta_address"]
            if start + num > MEMORY_SIZE:
                return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
            state["memory"][start : start + num] = packet[2 : 2 + num]
            state["mta_address"] += num
            return encode_positive_response(b"")
        if cmd == XcpCommand.BUILD_CHECKSUM:
            block_size = int.from_bytes(packet[4:8], "little", signed=False)
            if block_size == 0:
                return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
            start = state["mta_address"]
            if start + block_size > MEMORY_SIZE:
                return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
            checksum = sum(state["memory"][start : start + block_size]) & 0xFFFFFFFF
            state["mta_address"] += block_size
            response = BuildChecksumResponse(
                checksum_type=XcpChecksumType.ADD_44, checksum=checksum
            )
            return encode_positive_response(response.encode_body())
        if cmd == XcpCommand.SYNCH:
            return encode_error_response(XcpError.ERR_CMD_SYNCH)
        return encode_error_response(XcpError.ERR_CMD_UNKNOWN)

    return handler, state


@pytest.mark.asyncio
async def test_set_mta_download_roundtrip_then_upload_returns_written_value() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    handler, state = _build_full_handler()
    slave.set_handler(handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.set_mta(address=0x40, address_extension=0)
            await client.download(b"\xde\xad\xbe\xef")
            assert bytes(state["memory"][0x40:0x44]) == b"\xde\xad\xbe\xef"
            assert state["mta_address"] == 0x44
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_build_checksum_returns_sum_of_ramp_window() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    handler, _state = _build_full_handler()
    slave.set_handler(handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.set_mta(address=0x10, address_extension=0)
            # Sum of ramp bytes 0x10..0x13 = 0x46.
            response = await client.build_checksum(block_size=4)
            assert response.checksum == 0x46
            assert response.checksum_type == XcpChecksumType.ADD_44
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_download_too_large_raises_protocol_error() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    handler, _state = _build_full_handler()
    slave.set_handler(handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.set_mta(address=MEMORY_SIZE - 2, address_extension=0)
            with pytest.raises(XcpProtocolError) as exc_info:
                await client.download(b"\x01\x02\x03\x04")
            assert exc_info.value.code == XcpError.ERR_OUT_OF_RANGE
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_synch_returns_ok_on_err_cmd_synch() -> None:
    """SYNCH is the only command where ERR_CMD_SYNCH is the success case."""
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    handler, _state = _build_full_handler()
    slave.set_handler(handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.synch()  # must not raise
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_synch_raises_on_unexpected_error_code() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)

    def odd_synch_handler(packet: bytes, _addr: tuple[str, int]) -> bytes | None:
        if packet and packet[0] == XcpCommand.SYNCH:
            return encode_error_response(XcpError.ERR_ACCESS_DENIED)
        if packet and packet[0] == XcpCommand.CONNECT:
            return encode_positive_response(
                ConnectResponse(
                    resource=0, comm_mode_basic=0x80, max_cto=8, max_dto=256,
                    protocol_version=0x01, transport_version=0x01,
                ).encode_body()
            )
        return encode_error_response(XcpError.ERR_CMD_UNKNOWN)

    slave.set_handler(odd_synch_handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            with pytest.raises(XcpProtocolError) as exc_info:
                await client.synch()
            assert exc_info.value.code == XcpError.ERR_ACCESS_DENIED
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_download_then_build_checksum_verifies_write() -> None:
    """Real-world CAL flow: DOWNLOAD a known pattern, then BUILD_CHECKSUM to verify."""
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    handler, _state = _build_full_handler()
    slave.set_handler(handler)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.set_mta(address=0x80, address_extension=0)
            await client.download(b"\x01\x02\x03\x04")
            # Re-position MTA and verify
            await client.set_mta(address=0x80, address_extension=0)
            response = await client.build_checksum(block_size=4)
            assert response.checksum == 0x01 + 0x02 + 0x03 + 0x04  # = 10
    finally:
        await slave.stop()
