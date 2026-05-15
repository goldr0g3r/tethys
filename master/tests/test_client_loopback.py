"""Loopback round-trip test for the XCP client.

Uses :class:`UdpEchoSlave` to emulate the slave's CONNECT/DISCONNECT/
GET_VERSION/GET_STATUS responses. Validates the full request -> wire ->
response -> decode path on the master side.
"""

from __future__ import annotations

import asyncio

import pytest

from tethys_master.protocol.client import XcpClient, XcpProtocolError
from tethys_master.protocol.frame import (
    ConnectResponse,
    GetStatusResponse,
    GetVersionResponse,
    ResourceMask,
    XcpCommand,
    XcpError,
    XcpPacketId,
    encode_error_response,
    encode_positive_response,
)
from tethys_master.transport.udp import UdpEchoSlave, UdpTransport


def _handler_factory(custom_status: int = 0x80) -> callable:  # type: ignore[name-defined]
    """Build a slave-side handler that responds to the 4 supported commands."""

    def handler(packet: bytes, _addr: tuple[str, int]) -> bytes | None:
        if not packet:
            return None
        cmd = packet[0]
        if cmd == XcpCommand.CONNECT:
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
            return encode_positive_response(b"")
        if cmd == XcpCommand.GET_STATUS:
            response = GetStatusResponse(
                current_session_status=custom_status,
                current_resource_protection=0x00,
                state_number=0x01,
                session_configuration_id=0xABCD,
            )
            return encode_positive_response(response.encode_body())
        if cmd == XcpCommand.GET_VERSION:
            response = GetVersionResponse(
                reserved=0,
                protocol_major=1,
                protocol_minor=4,
                transport_major=1,
                transport_minor=4,
            )
            return encode_positive_response(response.encode_body())
        return encode_error_response(XcpError.ERR_CMD_UNKNOWN)

    return handler


@pytest.mark.asyncio
async def test_connect_disconnect_roundtrip() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    slave.set_handler(_handler_factory())
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            connect_response = await client.connect()
            assert connect_response.max_cto == 8
            assert connect_response.max_dto == 256
            assert client.is_connected

            status_response = await client.get_status()
            assert status_response.session_configuration_id == 0xABCD

            version_response = await client.get_version()
            assert version_response.protocol_major == 1
            assert version_response.protocol_minor == 4

            await client.disconnect()
            assert not client.is_connected
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_error_response_raises_protocol_error() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)

    def always_error(packet: bytes, _addr: tuple[str, int]) -> bytes | None:
        del packet
        return encode_error_response(XcpError.ERR_ACCESS_DENIED, info=b"locked")

    slave.set_handler(always_error)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            with pytest.raises(XcpProtocolError) as exc_info:
                await client.connect()
            assert exc_info.value.code == XcpError.ERR_ACCESS_DENIED
            assert exc_info.value.info == b"locked"
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_timeout_raises_asyncio_timeout() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)
    slave.set_handler(lambda _p, _a: None)  # never respond
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=0.1) as client:
            with pytest.raises(asyncio.TimeoutError):
                await client.connect()
    finally:
        await slave.stop()


@pytest.mark.asyncio
async def test_unexpected_packet_id() -> None:
    slave = UdpEchoSlave(host="127.0.0.1", port=0)

    def garbage_response(_p: bytes, _a: tuple[str, int]) -> bytes | None:
        return bytes([XcpPacketId.EV, 0x42])  # event packet where we expected RES/ERR

    slave.set_handler(garbage_response)
    await slave.start()
    try:
        async with XcpClient(UdpTransport("127.0.0.1", slave.actual_port), default_timeout_s=1.0) as client:
            with pytest.raises(XcpProtocolError):
                await client.connect()
    finally:
        await slave.stop()
