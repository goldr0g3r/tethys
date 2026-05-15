"""High-level XCP client (master side).

Wraps a :class:`Transport` with the request/response orchestration for
the Phase 1 + Phase 2 read-path command set. Phase 2 PR-29 extends to
DOWNLOAD / BUILD_CHECKSUM / SYNCH.

Cite: ASAM XCP 1.4 Part 2 §1.3 (Standard Command set)
Cite: ADR-0004 (transport abstraction layer)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tethys_master.logging_setup import get_logger
from tethys_master.protocol.frame import (
    ConnectRequest,
    ConnectResponse,
    DisconnectRequest,
    ErrorResponse,
    GetStatusRequest,
    GetStatusResponse,
    GetVersionRequest,
    GetVersionResponse,
    SetMtaRequest,
    ShortUploadRequest,
    UploadRequest,
    UploadResponse,
    XcpPacketId,
    parse_response,
)

if TYPE_CHECKING:
    from tethys_master.transport import Transport

logger = get_logger(__name__)


class XcpProtocolError(Exception):
    """Raised when the slave returns an ERR packet."""

    def __init__(self, code: int, info: bytes = b"") -> None:
        super().__init__(f"XCP error 0x{code:02X} (info={info!r})")
        self.code = code
        self.info = info


class XcpClient:
    """Async XCP client - one transport, one logical session."""

    def __init__(self, transport: Transport, *, default_timeout_s: float = 0.5) -> None:
        self._transport = transport
        self._timeout = default_timeout_s
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def __aenter__(self) -> XcpClient:
        await self._transport.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._connected:
            try:
                await self.disconnect()
            except Exception:
                logger.warning("xcp.disconnect.failed_during_aexit")
        await self._transport.close()

    async def _request(self, payload: bytes, *, timeout: float | None = None) -> bytes:
        await self._transport.send(payload)
        return await self._transport.recv(timeout=timeout if timeout is not None else self._timeout)

    @staticmethod
    def _ensure_positive(packet: bytes) -> bytes:
        packet_id, body = parse_response(packet)
        if packet_id == XcpPacketId.RES:
            return body
        if packet_id == XcpPacketId.ERR:
            err = ErrorResponse.decode(body)
            raise XcpProtocolError(err.error_code, err.info)
        raise XcpProtocolError(packet_id, body)

    async def connect(self, *, mode: int = 0) -> ConnectResponse:
        logger.info("xcp.connect.start", mode=mode)
        request = ConnectRequest(mode=mode).encode()
        body = self._ensure_positive(await self._request(request))
        response = ConnectResponse.decode(body)
        self._connected = True
        logger.info(
            "xcp.connect.ok",
            resource=hex(response.resource),
            max_cto=response.max_cto,
            max_dto=response.max_dto,
            protocol_v=hex(response.protocol_version),
            transport_v=hex(response.transport_version),
        )
        return response

    async def disconnect(self) -> None:
        logger.info("xcp.disconnect.start")
        request = DisconnectRequest().encode()
        self._ensure_positive(await self._request(request))
        self._connected = False
        logger.info("xcp.disconnect.ok")

    async def get_status(self) -> GetStatusResponse:
        request = GetStatusRequest().encode()
        body = self._ensure_positive(await self._request(request))
        response = GetStatusResponse.decode(body)
        logger.info(
            "xcp.get_status.ok",
            session=hex(response.current_session_status),
            protection=hex(response.current_resource_protection),
        )
        return response

    async def get_version(self) -> GetVersionResponse:
        request = GetVersionRequest().encode()
        body = self._ensure_positive(await self._request(request))
        response = GetVersionResponse.decode(body)
        logger.info(
            "xcp.get_version.ok",
            protocol=f"{response.protocol_major}.{response.protocol_minor}",
            transport=f"{response.transport_major}.{response.transport_minor}",
        )
        return response

    # ---- Phase 2 read path ------------------------------------------

    async def set_mta(self, address: int, address_extension: int = 0) -> None:
        """SET_MTA - position the slave's Memory Transfer Address.

        Cite: ASAM XCP 1.4 Part 2 §1.3.3.1
        """
        logger.info("xcp.set_mta.start", address=hex(address), extension=address_extension)
        request = SetMtaRequest(address=address, address_extension=address_extension).encode()
        body = self._ensure_positive(await self._request(request))
        if body:
            logger.warning("xcp.set_mta.unexpected_body", bytes=len(body))
        logger.info("xcp.set_mta.ok")

    async def upload(self, num_bytes: int) -> bytes:
        """UPLOAD ``num_bytes`` bytes from the current MTA (auto-increments).

        Cite: ASAM XCP 1.4 Part 2 §1.3.3.2
        """
        logger.info("xcp.upload.start", num_bytes=num_bytes)
        request = UploadRequest(num_bytes=num_bytes).encode()
        body = self._ensure_positive(await self._request(request))
        response = UploadResponse.decode(body)
        if len(response.data) < num_bytes:
            logger.warning("xcp.upload.short_response", got=len(response.data), want=num_bytes)
        logger.info("xcp.upload.ok", got=len(response.data))
        return response.data[:num_bytes]

    async def short_upload(self, num_bytes: int, address: int, address_extension: int = 0) -> bytes:
        """SHORT_UPLOAD - stateless read of ``num_bytes`` from ``address``.

        Does not modify the slave's MTA. Cite: ASAM XCP 1.4 Part 2 §1.3.3.6
        """
        logger.info(
            "xcp.short_upload.start",
            num_bytes=num_bytes,
            address=hex(address),
            extension=address_extension,
        )
        request = ShortUploadRequest(
            num_bytes=num_bytes, address=address, address_extension=address_extension
        ).encode()
        body = self._ensure_positive(await self._request(request))
        response = UploadResponse.decode(body)
        logger.info("xcp.short_upload.ok", got=len(response.data))
        return response.data[:num_bytes]
