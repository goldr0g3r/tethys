"""High-level XCP client (master side).

Wraps a :class:`Transport` with the request/response orchestration for
the Phase 1 + Phase 2 command set (CONNECT, DISCONNECT, GET_STATUS,
GET_VERSION, SYNCH, SET_MTA, UPLOAD, SHORT_UPLOAD, DOWNLOAD,
BUILD_CHECKSUM).

Cite: ASAM XCP 1.4 Part 2 §1.3 (Standard Command set)
Cite: ADR-0004 (transport abstraction layer)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tethys_master.logging_setup import get_logger
from tethys_master.protocol.daq import (
    AllocDaqRequest,
    AllocOdtEntryRequest,
    AllocOdtRequest,
    DaqList,
    DaqListMode,
    FreeDaqRequest,
    GetDaqListModeRequest,
    GetDaqListModeResponse,
    GetDaqProcessorInfoRequest,
    GetDaqProcessorInfoResponse,
    GetDaqResolutionInfoRequest,
    GetDaqResolutionInfoResponse,
    Odt,
    OdtEntry,
    SetDaqListModeRequest,
    SetDaqPtrRequest,
    StartStopDaqListRequest,
    StartStopDaqListResponse,
    StartStopListMode,
    StartStopSynchMode,
    StartStopSynchRequest,
    WriteDaqRequest,
)
from tethys_master.protocol.frame import (
    BuildChecksumRequest,
    BuildChecksumResponse,
    ConnectRequest,
    ConnectResponse,
    DisconnectRequest,
    DownloadRequest,
    ErrorResponse,
    GetStatusRequest,
    GetStatusResponse,
    GetVersionRequest,
    GetVersionResponse,
    SetMtaRequest,
    ShortUploadRequest,
    SynchRequest,
    UploadRequest,
    UploadResponse,
    XcpError,
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

    # ---- Phase 2 write / checksum / sync ----------------------------

    async def download(self, data: bytes) -> None:
        """DOWNLOAD - write ``data`` to the current MTA (auto-increments).

        Cite: ASAM XCP 1.4 Part 2 §1.3.4.1
        """
        logger.info("xcp.download.start", num_bytes=len(data))
        request = DownloadRequest(data=bytes(data)).encode()
        body = self._ensure_positive(await self._request(request))
        if body:
            logger.warning("xcp.download.unexpected_body", bytes=len(body))
        logger.info("xcp.download.ok")

    async def build_checksum(self, block_size: int) -> BuildChecksumResponse:
        """BUILD_CHECKSUM - sum ``block_size`` bytes starting at MTA.

        Cite: ASAM XCP 1.4 Part 2 §1.5.1
        """
        logger.info("xcp.build_checksum.start", block_size=block_size)
        request = BuildChecksumRequest(block_size=block_size).encode()
        body = self._ensure_positive(await self._request(request))
        response = BuildChecksumResponse.decode(body)
        logger.info(
            "xcp.build_checksum.ok",
            checksum=hex(response.checksum),
            checksum_type=hex(response.checksum_type),
        )
        return response

    async def synch(self) -> None:
        """SYNCH - reset the slave's protocol state machine.

        The slave is required to respond with ERR_CMD_SYNCH; this is the
        documented synchronisation handshake, not an error. The client
        absorbs the ERR_CMD_SYNCH response silently.

        Cite: ASAM XCP 1.4 Part 2 §1.3.1.2
        """
        logger.info("xcp.synch.start")
        request = SynchRequest().encode()
        packet = await self._request(request)
        packet_id, body = parse_response(packet)
        if packet_id == XcpPacketId.ERR and body and body[0] == XcpError.ERR_CMD_SYNCH:
            logger.info("xcp.synch.ok")
            return
        # Any other response is unexpected; surface it as a protocol error.
        if packet_id == XcpPacketId.ERR:
            err = ErrorResponse.decode(body)
            raise XcpProtocolError(err.error_code, err.info)
        raise XcpProtocolError(packet_id, body)

    # ---- Phase 3 DAQ command surface ---------------------------------

    async def free_daq(self) -> None:
        """FREE_DAQ - drop the slave's entire DAQ configuration.

        Cite: ASAM XCP 1.4 Part 2 §1.4.2.7
        """
        logger.info("xcp.free_daq")
        self._ensure_positive(await self._request(FreeDaqRequest().encode()))

    async def alloc_daq(self, list_count: int) -> None:
        """ALLOC_DAQ - allocate ``list_count`` empty DAQ lists.

        Cite: ASAM XCP 1.4 Part 2 §1.4.2.7
        """
        logger.info("xcp.alloc_daq.start", count=list_count)
        self._ensure_positive(
            await self._request(AllocDaqRequest(list_count=list_count).encode())
        )

    async def alloc_odt(self, daq_list_num: int, odt_count: int) -> None:
        """ALLOC_ODT - allocate ``odt_count`` ODTs inside an already-allocated list."""
        self._ensure_positive(
            await self._request(
                AllocOdtRequest(
                    daq_list_num=daq_list_num, odt_count=odt_count
                ).encode()
            )
        )

    async def alloc_odt_entry(
        self, daq_list_num: int, odt_num: int, entry_count: int
    ) -> None:
        """ALLOC_ODT_ENTRY - allocate ``entry_count`` entry slots inside an ODT."""
        self._ensure_positive(
            await self._request(
                AllocOdtEntryRequest(
                    daq_list_num=daq_list_num,
                    odt_num=odt_num,
                    entry_count=entry_count,
                ).encode()
            )
        )

    async def set_daq_ptr(
        self, daq_list_num: int, odt_num: int, entry_idx: int
    ) -> None:
        """SET_DAQ_PTR - position the slave's WRITE_DAQ pointer.

        Cite: ASAM XCP 1.4 Part 2 §1.4.2.2
        """
        self._ensure_positive(
            await self._request(
                SetDaqPtrRequest(
                    daq_list_num=daq_list_num,
                    odt_num=odt_num,
                    entry_idx=entry_idx,
                ).encode()
            )
        )

    async def write_daq(self, entry: OdtEntry) -> None:
        """WRITE_DAQ - define one ODT element at the current SET_DAQ_PTR position.

        Cite: ASAM XCP 1.4 Part 2 §1.4.2.2
        """
        self._ensure_positive(
            await self._request(WriteDaqRequest(entry=entry).encode())
        )

    async def write_odt(
        self, daq_list_num: int, odt_num: int, entries: list[OdtEntry]
    ) -> None:
        """Convenience: SET_DAQ_PTR then WRITE_DAQ for each entry in order.

        The slave auto-advances the pointer after each WRITE_DAQ so we
        only need one SET_DAQ_PTR call per ODT.
        """
        await self.set_daq_ptr(daq_list_num, odt_num, 0)
        for entry in entries:
            await self.write_daq(entry)

    async def set_daq_list_mode(
        self,
        daq_list_num: int,
        *,
        mode: int = 0,
        event_channel: int = 0,
        prescaler: int = 1,
        priority: int = 0,
    ) -> None:
        """SET_DAQ_LIST_MODE - configure direction / timestamp / event-channel.

        Cite: ASAM XCP 1.4 Part 2 §1.4.2.6
        """
        self._ensure_positive(
            await self._request(
                SetDaqListModeRequest(
                    daq_list_num=daq_list_num,
                    mode=mode,
                    event_channel=event_channel,
                    prescaler=prescaler,
                    priority=priority,
                ).encode()
            )
        )

    async def get_daq_list_mode(self, daq_list_num: int) -> GetDaqListModeResponse:
        body = self._ensure_positive(
            await self._request(
                GetDaqListModeRequest(daq_list_num=daq_list_num).encode()
            )
        )
        return GetDaqListModeResponse.decode(body)

    async def start_stop_daq_list(
        self, daq_list_num: int, mode: StartStopListMode | int
    ) -> StartStopDaqListResponse:
        """START_STOP_DAQ_LIST - per-list start / stop / select.

        Cite: ASAM XCP 1.4 Part 2 §1.4.2.4
        """
        body = self._ensure_positive(
            await self._request(
                StartStopDaqListRequest(
                    daq_list_num=daq_list_num, mode=int(mode)
                ).encode()
            )
        )
        return StartStopDaqListResponse.decode(body)

    async def start_stop_synch(self, mode: StartStopSynchMode | int) -> None:
        """START_STOP_SYNCH - all-lists race-fix variant.

        Cite: ASAM XCP 1.4 Part 2 §1.4.2.5
        """
        self._ensure_positive(
            await self._request(StartStopSynchRequest(mode=int(mode)).encode())
        )

    async def get_daq_processor_info(self) -> GetDaqProcessorInfoResponse:
        body = self._ensure_positive(
            await self._request(GetDaqProcessorInfoRequest().encode())
        )
        return GetDaqProcessorInfoResponse.decode(body)

    async def get_daq_resolution_info(self) -> GetDaqResolutionInfoResponse:
        body = self._ensure_positive(
            await self._request(GetDaqResolutionInfoRequest().encode())
        )
        return GetDaqResolutionInfoResponse.decode(body)

    # ---- DAQ-list orchestration helper -------------------------------

    async def configure_daq_list(
        self,
        daq_list_num: int,
        *,
        odts: list[list[OdtEntry]],
        mode: int = 0,
        event_channel: int = 0,
        prescaler: int = 1,
        priority: int = 0,
    ) -> DaqList:
        """End-to-end ALLOC + WRITE + SET_DAQ_LIST_MODE for one list.

        Assumes ALLOC_DAQ has already been issued. Returns a populated
        :class:`DaqList` snapshot (with ``first_pid=0`` until the caller
        calls :meth:`start_stop_daq_list` and stamps the response in).
        """
        await self.alloc_odt(daq_list_num, len(odts))
        daq_list = DaqList(mode=DaqListMode(mode), event_channel=event_channel,
                           prescaler=prescaler, priority=priority)
        for odt_num, entries in enumerate(odts):
            await self.alloc_odt_entry(daq_list_num, odt_num, len(entries))
            await self.write_odt(daq_list_num, odt_num, entries)
            daq_list.odts.append(Odt(entries=list(entries)))
        await self.set_daq_list_mode(
            daq_list_num,
            mode=mode,
            event_channel=event_channel,
            prescaler=prescaler,
            priority=priority,
        )
        return daq_list
