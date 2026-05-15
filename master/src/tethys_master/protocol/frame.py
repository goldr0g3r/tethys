"""XCP CTO frame encoding / decoding.

This module implements the XCP 1.4 Part 2 Standard Command set Tethys
supports today (parent plan §8 Phase 1 + Phase 2 read path):
CONNECT, DISCONNECT, GET_STATUS, GET_VERSION, SET_MTA, UPLOAD,
SHORT_UPLOAD, plus the corresponding response frame parsing.

Phase 2 PR-29 extends this to DOWNLOAD, BUILD_CHECKSUM, SYNCH.

Cite: ASAM XCP 1.4 Part 2 §1.3.2.4 CONNECT
Cite: ASAM XCP 1.4 Part 2 §1.3.2.5 DISCONNECT
Cite: ASAM XCP 1.4 Part 2 §1.3.2.6 GET_STATUS
Cite: ASAM XCP 1.4 Part 2 §1.4.2.1 GET_VERSION
Cite: ASAM XCP 1.4 Part 2 §1.3.3.1 SET_MTA
Cite: ASAM XCP 1.4 Part 2 §1.3.3.2 UPLOAD
Cite: ASAM XCP 1.4 Part 2 §1.3.3.6 SHORT_UPLOAD
Trace: docs/traceability.csv row TETHYS-DES-0001..0007 (lands at PR-10)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar


class XcpCommand(IntEnum):
    """XCP Standard Command codes (Phase 1 + Phase 2 read path).

    Reference: ASAM XCP 1.4 Part 2 Table 5 (Standard Command codes).
    """

    CONNECT = 0xFF
    DISCONNECT = 0xFE
    GET_STATUS = 0xFD
    SYNCH = 0xFC
    GET_VERSION = 0xC0
    SET_MTA = 0xF6
    UPLOAD = 0xF5
    SHORT_UPLOAD = 0xF4


class XcpPacketId(IntEnum):
    """First byte of any response packet (XCP 1.4 Part 2 §3.1)."""

    RES = 0xFF  # positive response
    ERR = 0xFE  # error response
    EV = 0xFD  # event
    SERV = 0xFC  # service request


class XcpError(IntEnum):
    """XCP error codes (XCP 1.4 Part 2 Table 12; subset Tethys handles today)."""

    ERR_CMD_SYNCH = 0x00
    ERR_CMD_BUSY = 0x10
    ERR_DAQ_ACTIVE = 0x11
    ERR_PGM_ACTIVE = 0x12
    ERR_CMD_UNKNOWN = 0x20
    ERR_CMD_SYNTAX = 0x21
    ERR_OUT_OF_RANGE = 0x22
    ERR_WRITE_PROTECTED = 0x23
    ERR_ACCESS_DENIED = 0x24
    ERR_ACCESS_LOCKED = 0x25
    ERR_PAGE_NOT_VALID = 0x26


XCP_MAX_UPLOAD_BYTES = 7
"""Maximum number of payload bytes the slave can return in one UPLOAD response.

XCP CTO is 8 bytes by default; one byte is the response PID, leaving 7 bytes
of payload. Multi-CTO block-transfer reads are deferred to a later phase.
"""


class ResourceMask(IntEnum):
    """CONNECT response resource availability bitmask (XCP 1.4 Part 2 §1.3.2.4 Table 6)."""

    NONE = 0x00
    CAL_PAG = 0x01
    DAQ = 0x04
    STIM = 0x08
    PGM = 0x10


class CommModeBasic(IntEnum):
    """CONNECT response communication mode basic (XCP 1.4 Part 2 §1.3.2.4 Table 7)."""

    BYTE_ORDER_MOTOROLA = 0x01
    ADDRESS_GRANULARITY_BYTE = 0x00
    ADDRESS_GRANULARITY_WORD = 0x02
    ADDRESS_GRANULARITY_DWORD = 0x04
    OPTIONAL = 0x80


XCP_DEFAULT_MAX_CTO = 8
XCP_DEFAULT_MAX_DTO = 256
XCP_PROTOCOL_VERSION_MAJOR = 1
XCP_TRANSPORT_VERSION_MAJOR = 1
XCP_PROTOCOL_VERSION = 0x0104  # XCP 1.4
XCP_TRANSPORT_VERSION = 0x0104  # XCP-on-UDP 1.4


@dataclass(frozen=True, slots=True)
class ConnectRequest:
    """XCP CONNECT request packet (XCP 1.4 Part 2 §1.3.2.4)."""

    mode: int = 0  # 0 = normal mode, 1 = user-defined

    _CMD: ClassVar[int] = XcpCommand.CONNECT

    def encode(self) -> bytes:
        return struct.pack("<BB", self._CMD, self.mode)


@dataclass(frozen=True, slots=True)
class ConnectResponse:
    """CONNECT positive response (XCP 1.4 Part 2 §1.3.2.4)."""

    resource: int
    comm_mode_basic: int
    max_cto: int
    max_dto: int
    protocol_version: int  # high byte = major, low byte = minor
    transport_version: int

    @classmethod
    def decode(cls, payload: bytes) -> ConnectResponse:
        """Decode the 7-byte body that follows the 0xFF RES byte.

        Wire layout (XCP 1.4 Part 2 §1.3.2.4 Table 5):
          [0] resource (1 byte)
          [1] commModeBasic (1 byte)
          [2] maxCto (1 byte)
          [3..4] maxDto (2 bytes, big-endian per Motorola flag - we treat as little-endian for Phase 1 default)
          [5] protocolLayerVersion (1 byte major)
          [6] transportLayerVersion (1 byte major)
        """
        if len(payload) < 7:
            msg = f"CONNECT response body too short: {len(payload)} bytes (expected >=7)"
            raise ValueError(msg)
        resource = payload[0]
        comm = payload[1]
        max_cto = payload[2]
        max_dto = int.from_bytes(payload[3:5], byteorder="little", signed=False)
        protocol_version = payload[5]
        transport_version = payload[6]
        return cls(
            resource=resource,
            comm_mode_basic=comm,
            max_cto=max_cto,
            max_dto=max_dto,
            protocol_version=protocol_version,
            transport_version=transport_version,
        )

    def encode_body(self) -> bytes:
        """Slave-side helper - encode the 7-byte body (no leading RES byte)."""
        if not (0 <= self.max_dto <= 0xFFFF):
            msg = f"max_dto out of u16 range: {self.max_dto}"
            raise ValueError(msg)
        return (
            bytes(
                [
                    self.resource & 0xFF,
                    self.comm_mode_basic & 0xFF,
                    self.max_cto & 0xFF,
                ]
            )
            + self.max_dto.to_bytes(2, byteorder="little", signed=False)
            + bytes([self.protocol_version & 0xFF, self.transport_version & 0xFF])
        )


@dataclass(frozen=True, slots=True)
class DisconnectRequest:
    """XCP DISCONNECT request (XCP 1.4 Part 2 §1.3.2.5)."""

    _CMD: ClassVar[int] = XcpCommand.DISCONNECT

    def encode(self) -> bytes:
        return bytes([self._CMD])


@dataclass(frozen=True, slots=True)
class GetStatusRequest:
    """XCP GET_STATUS request (XCP 1.4 Part 2 §1.3.2.6)."""

    _CMD: ClassVar[int] = XcpCommand.GET_STATUS

    def encode(self) -> bytes:
        return bytes([self._CMD])


@dataclass(frozen=True, slots=True)
class GetStatusResponse:
    """GET_STATUS positive response."""

    current_session_status: int
    current_resource_protection: int
    state_number: int
    session_configuration_id: int

    @classmethod
    def decode(cls, payload: bytes) -> GetStatusResponse:
        if len(payload) < 5:
            msg = f"GET_STATUS response body too short: {len(payload)}"
            raise ValueError(msg)
        session_id = int.from_bytes(payload[3:5], byteorder="little", signed=False)
        return cls(
            current_session_status=payload[0],
            current_resource_protection=payload[1],
            state_number=payload[2],
            session_configuration_id=session_id,
        )

    def encode_body(self) -> bytes:
        return bytes(
            [
                self.current_session_status & 0xFF,
                self.current_resource_protection & 0xFF,
                self.state_number & 0xFF,
            ]
        ) + (self.session_configuration_id & 0xFFFF).to_bytes(2, byteorder="little", signed=False)


@dataclass(frozen=True, slots=True)
class GetVersionRequest:
    """XCP GET_VERSION request (XCP 1.4 Part 2 §1.4.2.1)."""

    _CMD: ClassVar[int] = XcpCommand.GET_VERSION

    def encode(self) -> bytes:
        return bytes([self._CMD])


@dataclass(frozen=True, slots=True)
class GetVersionResponse:
    """GET_VERSION positive response."""

    reserved: int
    protocol_major: int
    protocol_minor: int
    transport_major: int
    transport_minor: int

    @classmethod
    def decode(cls, payload: bytes) -> GetVersionResponse:
        if len(payload) < 5:
            msg = f"GET_VERSION response body too short: {len(payload)}"
            raise ValueError(msg)
        return cls(
            reserved=payload[0],
            protocol_major=payload[1],
            protocol_minor=payload[2],
            transport_major=payload[3],
            transport_minor=payload[4],
        )

    def encode_body(self) -> bytes:
        return bytes(
            [
                self.reserved & 0xFF,
                self.protocol_major & 0xFF,
                self.protocol_minor & 0xFF,
                self.transport_major & 0xFF,
                self.transport_minor & 0xFF,
            ]
        )


@dataclass(frozen=True, slots=True)
class ErrorResponse:
    """XCP error response (XCP 1.4 Part 2 §3.1 Table 12)."""

    error_code: int
    info: bytes = field(default=b"")

    @classmethod
    def decode(cls, payload: bytes) -> ErrorResponse:
        if not payload:
            msg = "Error response body is empty"
            raise ValueError(msg)
        return cls(error_code=payload[0], info=bytes(payload[1:]))

    def encode_body(self) -> bytes:
        return bytes([self.error_code & 0xFF]) + bytes(self.info)


def encode_positive_response(body: bytes) -> bytes:
    """Prepend the RES (0xFF) packet-id byte to a response body."""
    return bytes([XcpPacketId.RES]) + bytes(body)


def encode_error_response(code: int, info: bytes = b"") -> bytes:
    """Build an error response packet (ERR byte + code + optional info)."""
    return bytes([XcpPacketId.ERR, code & 0xFF]) + bytes(info)


def parse_response(packet: bytes) -> tuple[int, bytes]:
    """Split a packet into (packet_id, body) tuple.

    Returns:
        packet_id: first byte (one of XcpPacketId values).
        body: remainder of the packet.
    """
    if not packet:
        msg = "Empty packet"
        raise ValueError(msg)
    return packet[0], bytes(packet[1:])


# ---- Phase 2 read-path commands ---------------------------------------


@dataclass(frozen=True, slots=True)
class SetMtaRequest:
    """XCP SET_MTA request (XCP 1.4 Part 2 §1.3.3.1).

    Wire layout (8 bytes):
        [0]    PID = 0xF6
        [1..2] reserved (zero)
        [3]    address_extension
        [4..7] address (4 bytes, little-endian)
    """

    address: int
    address_extension: int = 0

    _CMD: ClassVar[int] = XcpCommand.SET_MTA

    def encode(self) -> bytes:
        if not (0 <= self.address <= 0xFFFFFFFF):
            msg = f"address out of u32 range: {self.address}"
            raise ValueError(msg)
        if not (0 <= self.address_extension <= 0xFF):
            msg = f"address_extension out of u8 range: {self.address_extension}"
            raise ValueError(msg)
        return struct.pack("<BBBBI", self._CMD, 0, 0, self.address_extension, self.address)


@dataclass(frozen=True, slots=True)
class UploadRequest:
    """XCP UPLOAD request (XCP 1.4 Part 2 §1.3.3.2).

    Wire layout (2 bytes):
        [0] PID = 0xF5
        [1] N - number of bytes to upload (1..MAX_CTO-1 = 1..7)
    """

    num_bytes: int

    _CMD: ClassVar[int] = XcpCommand.UPLOAD

    def encode(self) -> bytes:
        if not (1 <= self.num_bytes <= XCP_MAX_UPLOAD_BYTES):
            msg = f"num_bytes out of range [1, {XCP_MAX_UPLOAD_BYTES}]: {self.num_bytes}"
            raise ValueError(msg)
        return struct.pack("<BB", self._CMD, self.num_bytes)


@dataclass(frozen=True, slots=True)
class ShortUploadRequest:
    """XCP SHORT_UPLOAD request (XCP 1.4 Part 2 §1.3.3.6).

    Wire layout (8 bytes):
        [0]    PID = 0xF4
        [1]    N - number of bytes (1..MAX_CTO-1)
        [2]    reserved (zero)
        [3]    address_extension
        [4..7] address (4 bytes, little-endian)
    """

    num_bytes: int
    address: int
    address_extension: int = 0

    _CMD: ClassVar[int] = XcpCommand.SHORT_UPLOAD

    def encode(self) -> bytes:
        if not (1 <= self.num_bytes <= XCP_MAX_UPLOAD_BYTES):
            msg = f"num_bytes out of range [1, {XCP_MAX_UPLOAD_BYTES}]: {self.num_bytes}"
            raise ValueError(msg)
        if not (0 <= self.address <= 0xFFFFFFFF):
            msg = f"address out of u32 range: {self.address}"
            raise ValueError(msg)
        if not (0 <= self.address_extension <= 0xFF):
            msg = f"address_extension out of u8 range: {self.address_extension}"
            raise ValueError(msg)
        return struct.pack(
            "<BBBBI", self._CMD, self.num_bytes, 0, self.address_extension, self.address
        )


@dataclass(frozen=True, slots=True)
class UploadResponse:
    """UPLOAD / SHORT_UPLOAD positive response.

    The slave returns the requested data inline after the RES PID; the
    master-side decoder strips the PID byte and exposes the raw bytes.
    """

    data: bytes

    @classmethod
    def decode(cls, payload: bytes) -> UploadResponse:
        return cls(data=bytes(payload))

    def encode_body(self) -> bytes:
        return bytes(self.data)
