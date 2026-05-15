"""Unit + integration tests for the posix-sim slave dispatcher.

Validates the slave responds correctly to the 4 Phase-1 commands and
mirrors the C dispatcher's behaviour.
"""

from __future__ import annotations

import pytest
from tethys_master.protocol.client import XcpClient, XcpProtocolError
from tethys_master.protocol.frame import (
    ConnectResponse,
    DisconnectRequest,
    GetStatusRequest,
    GetVersionRequest,
    XcpCommand,
    XcpError,
    XcpPacketId,
    parse_response,
)
from tethys_master.transport.udp import UdpTransport

from tethys_sim.slave import XcpSimSlave


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
