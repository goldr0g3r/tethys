"""Unit + integration tests for the posix-sim slave dispatcher.

Validates the slave responds correctly to the Phase-1 4 commands plus the
Phase-2 read-path 3 commands (SET_MTA / UPLOAD / SHORT_UPLOAD), mirroring
the C dispatcher's behaviour for the same byte-exact request layouts.
"""

from __future__ import annotations

import pytest
from tethys_master.protocol.client import XcpClient, XcpProtocolError
from tethys_master.protocol.frame import (
    ConnectResponse,
    DisconnectRequest,
    GetStatusRequest,
    GetVersionRequest,
    SetMtaRequest,
    ShortUploadRequest,
    UploadRequest,
    XcpCommand,
    XcpError,
    XcpPacketId,
    parse_response,
)
from tethys_master.transport.udp import UdpTransport

from tethys_sim.slave import SIM_MEMORY_SIZE, XcpSimSlave


class TestDispatchUnit:
    def test_empty_packet_returns_syntax_error(self) -> None:
        slave = XcpSimSlave()
        response = slave.dispatch(b"")
        assert response is not None
        assert response[0] == XcpPacketId.ERR
        assert response[1] == XcpError.ERR_CMD_SYNTAX

    def test_unknown_cmd_returns_cmd_unknown(self) -> None:
        slave = XcpSimSlave()
        response = slave.dispatch(b"\x42")
        assert response is not None
        assert response[0] == XcpPacketId.ERR
        assert response[1] == XcpError.ERR_CMD_UNKNOWN

    def test_get_status_before_connect_denied(self) -> None:
        slave = XcpSimSlave()
        response = slave.dispatch(bytes([XcpCommand.GET_STATUS]))
        assert response is not None
        assert response[0] == XcpPacketId.ERR
        assert response[1] == XcpError.ERR_ACCESS_DENIED

    def test_get_version_before_connect_denied(self) -> None:
        slave = XcpSimSlave()
        response = slave.dispatch(GetVersionRequest().encode())
        assert response is not None
        assert response[0] == XcpPacketId.ERR
        assert response[1] == XcpError.ERR_ACCESS_DENIED

    def test_connect_succeeds(self) -> None:
        slave = XcpSimSlave()
        response = slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        assert response is not None
        assert response[0] == XcpPacketId.RES
        body = response[1:]
        decoded = ConnectResponse.decode(body)
        assert decoded.max_cto == 8
        assert decoded.max_dto == 256
        assert slave.state.connected

    def test_disconnect_after_connect(self) -> None:
        slave = XcpSimSlave()
        slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        response = slave.dispatch(DisconnectRequest().encode())
        assert response is not None
        assert response[0] == XcpPacketId.RES
        assert not slave.state.connected

    def test_get_status_after_connect(self) -> None:
        slave = XcpSimSlave()
        slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        response = slave.dispatch(GetStatusRequest().encode())
        assert response is not None
        packet_id, body = parse_response(response)
        assert packet_id == XcpPacketId.RES
        assert body[0] == 0x80  # session_status bit7 set


@pytest.mark.asyncio
async def test_loopback_full_session() -> None:
    slave = XcpSimSlave(host="127.0.0.1", port=0)
    await slave.start()
    try:
        port = slave.actual_port
        async with XcpClient(UdpTransport("127.0.0.1", port), default_timeout_s=1.0) as client:
            connect_response = await client.connect()
            assert connect_response.max_cto == 8
            assert connect_response.max_dto == 256

            status_response = await client.get_status()
            assert status_response.session_configuration_id == 0xABCD

            version_response = await client.get_version()
            assert (version_response.protocol_major, version_response.protocol_minor) == (1, 4)
            assert (version_response.transport_major, version_response.transport_minor) == (1, 4)

            await client.disconnect()
            assert not client.is_connected
            # The slave should refuse subsequent reads after DISCONNECT.
            with pytest.raises(XcpProtocolError) as exc_info:
                await client.get_status()
            assert exc_info.value.code == XcpError.ERR_ACCESS_DENIED
    finally:
        await slave.stop()


# ---- Phase 2 read-path tests -----------------------------------------


class TestPhase2DispatchUnit:
    def test_set_mta_before_connect_denied(self) -> None:
        slave = XcpSimSlave()
        response = slave.dispatch(SetMtaRequest(address=0x10).encode())
        assert response is not None
        assert response[0] == XcpPacketId.ERR
        assert response[1] == XcpError.ERR_ACCESS_DENIED

    def test_set_mta_updates_state(self) -> None:
        slave = XcpSimSlave()
        slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        response = slave.dispatch(SetMtaRequest(address=0xCAFEBABE, address_extension=2).encode())
        assert response is not None
        assert response[0] == XcpPacketId.RES
        assert slave.state.mta_address == 0xCAFEBABE
        assert slave.state.mta_extension == 2

    def test_upload_zero_bytes_returns_out_of_range(self) -> None:
        slave = XcpSimSlave()
        slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        response = slave.dispatch(bytes([XcpCommand.UPLOAD, 0]))
        assert response is not None
        assert response[0] == XcpPacketId.ERR
        assert response[1] == XcpError.ERR_OUT_OF_RANGE

    def test_upload_increments_mta(self) -> None:
        slave = XcpSimSlave()
        slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        slave.dispatch(SetMtaRequest(address=0x10).encode())
        response = slave.dispatch(UploadRequest(num_bytes=4).encode())
        assert response is not None
        assert response[0] == XcpPacketId.RES
        assert response[1:5] == bytes([0x10, 0x11, 0x12, 0x13])
        assert slave.state.mta_address == 0x14

    def test_short_upload_leaves_mta_unchanged(self) -> None:
        slave = XcpSimSlave()
        slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        slave.dispatch(SetMtaRequest(address=0x80).encode())
        response = slave.dispatch(ShortUploadRequest(num_bytes=3, address=0x20).encode())
        assert response is not None
        assert response[0] == XcpPacketId.RES
        assert response[1:4] == bytes([0x20, 0x21, 0x22])
        assert slave.state.mta_address == 0x80

    def test_upload_out_of_range_address(self) -> None:
        slave = XcpSimSlave()
        slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        slave.dispatch(SetMtaRequest(address=SIM_MEMORY_SIZE - 2).encode())
        response = slave.dispatch(UploadRequest(num_bytes=4).encode())
        assert response is not None
        assert response[0] == XcpPacketId.ERR
        assert response[1] == XcpError.ERR_OUT_OF_RANGE

    def test_short_upload_truncated_returns_syntax(self) -> None:
        slave = XcpSimSlave()
        slave.dispatch(bytes([XcpCommand.CONNECT, 0]))
        response = slave.dispatch(bytes([XcpCommand.SHORT_UPLOAD, 4, 0]))  # short by 5 bytes
        assert response is not None
        assert response[0] == XcpPacketId.ERR
        assert response[1] == XcpError.ERR_CMD_SYNTAX


@pytest.mark.asyncio
async def test_loopback_set_mta_upload_short_upload() -> None:
    slave = XcpSimSlave(host="127.0.0.1", port=0)
    await slave.start()
    try:
        port = slave.actual_port
        async with XcpClient(UdpTransport("127.0.0.1", port), default_timeout_s=1.0) as client:
            await client.connect()
            await client.set_mta(address=0x00, address_extension=0)
            chunk_a = await client.upload(num_bytes=4)
            assert chunk_a == bytes([0x00, 0x01, 0x02, 0x03])
            chunk_b = await client.upload(num_bytes=3)
            assert chunk_b == bytes([0x04, 0x05, 0x06])

            chunk_c = await client.short_upload(num_bytes=5, address=0x40)
            assert chunk_c == bytes([0x40, 0x41, 0x42, 0x43, 0x44])

            await client.disconnect()
    finally:
        await slave.stop()
