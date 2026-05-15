"""Unit tests for the XCP frame codec.

Cite: ASAM XCP 1.4 Part 2 §1.3.2 (CONNECT/DISCONNECT/GET_STATUS)
Cite: ASAM XCP 1.4 Part 2 §1.4.2.1 (GET_VERSION)
"""

from __future__ import annotations

import pytest

from tethys_master.protocol.frame import (
    ConnectRequest,
    ConnectResponse,
    DisconnectRequest,
    ErrorResponse,
    GetStatusRequest,
    GetStatusResponse,
    GetVersionRequest,
    GetVersionResponse,
    ResourceMask,
    XcpCommand,
    XcpError,
    XcpPacketId,
    encode_error_response,
    encode_positive_response,
    parse_response,
)


class TestConnectRequest:
    def test_encode_default_mode(self) -> None:
        request = ConnectRequest()
        assert request.encode() == bytes([XcpCommand.CONNECT, 0])

    def test_encode_user_defined_mode(self) -> None:
        request = ConnectRequest(mode=1)
        assert request.encode() == bytes([XcpCommand.CONNECT, 1])


class TestConnectResponse:
    def test_roundtrip(self) -> None:
        original = ConnectResponse(
            resource=ResourceMask.DAQ | ResourceMask.CAL_PAG,
            comm_mode_basic=0x80,
            max_cto=8,
            max_dto=256,
            protocol_version=0x01,
            transport_version=0x01,
        )
        body = original.encode_body()
        decoded = ConnectResponse.decode(body)
        assert decoded == original

    def test_decode_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            ConnectResponse.decode(b"\x00\x00\x00")

    def test_max_dto_out_of_range(self) -> None:
        bad = ConnectResponse(
            resource=0,
            comm_mode_basic=0,
            max_cto=8,
            max_dto=0x1_0000,
            protocol_version=0,
            transport_version=0,
        )
        with pytest.raises(ValueError, match="max_dto"):
            bad.encode_body()


class TestDisconnectRequest:
    def test_encode(self) -> None:
        assert DisconnectRequest().encode() == bytes([XcpCommand.DISCONNECT])


class TestGetStatus:
    def test_request_encode(self) -> None:
        assert GetStatusRequest().encode() == bytes([XcpCommand.GET_STATUS])

    def test_response_roundtrip(self) -> None:
        original = GetStatusResponse(
            current_session_status=0x80,
            current_resource_protection=0x00,
            state_number=0x01,
            session_configuration_id=0x1234,
        )
        body = original.encode_body()
        decoded = GetStatusResponse.decode(body)
        assert decoded == original

    def test_response_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            GetStatusResponse.decode(b"\x00\x00")


class TestGetVersion:
    def test_request_encode(self) -> None:
        assert GetVersionRequest().encode() == bytes([XcpCommand.GET_VERSION])

    def test_response_roundtrip(self) -> None:
        original = GetVersionResponse(
            reserved=0,
            protocol_major=1,
            protocol_minor=4,
            transport_major=1,
            transport_minor=4,
        )
        body = original.encode_body()
        decoded = GetVersionResponse.decode(body)
        assert decoded == original

    def test_response_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            GetVersionResponse.decode(b"\x00\x00\x00\x00")


class TestErrorResponse:
    def test_roundtrip(self) -> None:
        original = ErrorResponse(error_code=XcpError.ERR_CMD_UNKNOWN, info=b"")
        body = original.encode_body()
        decoded = ErrorResponse.decode(body)
        assert decoded.error_code == original.error_code
        assert decoded.info == original.info

    def test_roundtrip_with_info(self) -> None:
        original = ErrorResponse(error_code=XcpError.ERR_OUT_OF_RANGE, info=b"\x01\x02\x03")
        body = original.encode_body()
        decoded = ErrorResponse.decode(body)
        assert decoded == original

    def test_decode_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            ErrorResponse.decode(b"")


class TestPacketHelpers:
    def test_encode_positive_prepends_res(self) -> None:
        packet = encode_positive_response(b"\x01\x02")
        assert packet[0] == XcpPacketId.RES
        assert packet[1:] == b"\x01\x02"

    def test_encode_error_prepends_err(self) -> None:
        packet = encode_error_response(XcpError.ERR_ACCESS_DENIED, info=b"\xab")
        assert packet[0] == XcpPacketId.ERR
        assert packet[1] == XcpError.ERR_ACCESS_DENIED
        assert packet[2:] == b"\xab"

    def test_parse_response_splits_id_and_body(self) -> None:
        packet_id, body = parse_response(bytes([XcpPacketId.RES, 0x01, 0x02]))
        assert packet_id == XcpPacketId.RES
        assert body == b"\x01\x02"

    def test_parse_response_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            parse_response(b"")
