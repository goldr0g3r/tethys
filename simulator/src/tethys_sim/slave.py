"""posix-sim XCP slave - asyncio UDP server (Phase 1 + Phase 2 full).

This is a Python-side functional twin of the C dispatcher in
``slave/src/core/xcp_dispatcher.c``. Both must agree on the wire-level
behaviour of the supported commands so the acceptance bench (and the
PR-31 differential test against pyxcp) can swap between them
transparently. The Python implementation operates against a 1 KiB
ramp-pattern memory backend.

Cite: ASAM XCP 1.4 Part 2 §1.3.1..§1.3.4 + §1.4.2.1 + §1.5
Cite: parent plan §8 (Phase 2 acceptance)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from tethys_master.logging_setup import get_logger
from tethys_master.protocol.frame import (
    XCP_MAX_DOWNLOAD_BYTES,
    XCP_MAX_UPLOAD_BYTES,
    BuildChecksumResponse,
    ConnectResponse,
    GetStatusResponse,
    GetVersionResponse,
    ResourceMask,
    XcpChecksumType,
    XcpCommand,
    XcpError,
    encode_error_response,
    encode_positive_response,
)

SIM_MEMORY_SIZE = 1024
"""Size of the simulator's virtual memory backend (1 KiB)."""


def _ramp_memory(size: int = SIM_MEMORY_SIZE) -> bytearray:
    """Generate a deterministic ramp pattern so UPLOAD tests are stable."""
    return bytearray((i & 0xFF) for i in range(size))

logger = get_logger(__name__)


@dataclass(slots=True)
class SlaveState:
    """Volatile slave state (one instance per simulator process)."""

    connected: bool = False
    session_status: int = 0x00
    resource_protection: int = 0x00
    state_number: int = 0x00
    session_configuration_id: int = 0xABCD
    mta_address: int = 0
    mta_extension: int = 0
    memory: bytearray = field(default_factory=_ramp_memory)


class XcpSimSlave:
    """asyncio UDP server emulating the Tethys C slave."""

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",  # noqa: S104 - intentional bind-any in dev / loopback bench
        port: int = 5555,
        profile: str = "marine",
    ) -> None:
        self._host = host
        self._port = port
        self._profile = profile
        self._state = SlaveState()
        self._transport: asyncio.DatagramTransport | None = None

    @property
    def actual_port(self) -> int:
        if self._transport is None:
            return 0
        sockname = self._transport.get_extra_info("sockname")
        return int(sockname[1])

    @property
    def state(self) -> SlaveState:
        return self._state

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        slave = self

        class _Protocol(asyncio.DatagramProtocol):
            transport: asyncio.DatagramTransport | None = None

            def connection_made(self, t: asyncio.BaseTransport) -> None:
                if not isinstance(t, asyncio.DatagramTransport):
                    msg = f"Unexpected transport type: {type(t).__name__}"
                    raise TypeError(msg)
                self.transport = t

            def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
                response = slave.dispatch(bytes(data))
                if response is not None and self.transport is not None:
                    self.transport.sendto(response, addr)

        transport, _ = await loop.create_datagram_endpoint(
            _Protocol,
            local_addr=(self._host, self._port),
        )
        self._transport = transport
        sockname = transport.get_extra_info("sockname")
        logger.info(
            "sim.listen",
            host=sockname[0],
            port=sockname[1],
            profile=self._profile,
        )

    async def stop(self) -> None:
        if self._transport is not None and not self._transport.is_closing():
            self._transport.close()
            logger.info("sim.stopped")

    def dispatch(self, packet: bytes) -> bytes | None:  # noqa: PLR0911, PLR0912 - one branch per XCP command
        """Dispatch a single inbound CTO request and return the response body.

        Mirrors the slave C dispatcher's behaviour.
        """
        if not packet:
            logger.warning("sim.recv.empty")
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        cmd = packet[0]
        if cmd == XcpCommand.CONNECT:
            self._state.connected = True
            self._state.session_status = 0x80  # bit7 = SESSION_CONFIG_VALID
            connect_response = ConnectResponse(
                resource=ResourceMask.DAQ | ResourceMask.CAL_PAG,
                comm_mode_basic=0x80,
                max_cto=8,
                max_dto=256,
                protocol_version=0x01,
                transport_version=0x01,
            )
            logger.info("sim.cmd.connect")
            return encode_positive_response(connect_response.encode_body())
        if cmd == XcpCommand.DISCONNECT:
            self._state.connected = False
            self._state.session_status = 0x00
            logger.info("sim.cmd.disconnect")
            return encode_positive_response(b"")
        if cmd == XcpCommand.GET_STATUS:
            if not self._state.connected:
                logger.warning("sim.cmd.get_status.not_connected")
                return encode_error_response(XcpError.ERR_ACCESS_DENIED)
            status_response = GetStatusResponse(
                current_session_status=self._state.session_status,
                current_resource_protection=self._state.resource_protection,
                state_number=self._state.state_number,
                session_configuration_id=self._state.session_configuration_id,
            )
            logger.info("sim.cmd.get_status")
            return encode_positive_response(status_response.encode_body())
        if cmd == XcpCommand.GET_VERSION:
            if not self._state.connected:
                logger.warning("sim.cmd.get_version.not_connected")
                return encode_error_response(XcpError.ERR_ACCESS_DENIED)
            version_response = GetVersionResponse(
                reserved=0,
                protocol_major=1,
                protocol_minor=4,
                transport_major=1,
                transport_minor=4,
            )
            logger.info("sim.cmd.get_version")
            return encode_positive_response(version_response.encode_body())
        if cmd == XcpCommand.SET_MTA:
            return self._handle_set_mta(packet)
        if cmd == XcpCommand.UPLOAD:
            return self._handle_upload(packet)
        if cmd == XcpCommand.SHORT_UPLOAD:
            return self._handle_short_upload(packet)
        if cmd == XcpCommand.DOWNLOAD:
            return self._handle_download(packet)
        if cmd == XcpCommand.BUILD_CHECKSUM:
            return self._handle_build_checksum(packet)
        if cmd == XcpCommand.SYNCH:
            return self._handle_synch()
        logger.warning("sim.cmd.unknown", cmd=hex(cmd))
        return encode_error_response(XcpError.ERR_CMD_UNKNOWN)

    # ---- Phase 2 read-path handlers -------------------------------

    def _handle_set_mta(self, packet: bytes) -> bytes:
        if not self._state.connected:
            logger.warning("sim.cmd.set_mta.not_connected")
            return encode_error_response(XcpError.ERR_ACCESS_DENIED)
        if len(packet) < 8:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        self._state.mta_extension = packet[3]
        self._state.mta_address = int.from_bytes(packet[4:8], byteorder="little", signed=False)
        logger.info(
            "sim.cmd.set_mta",
            address=hex(self._state.mta_address),
            extension=self._state.mta_extension,
        )
        return encode_positive_response(b"")

    def _handle_upload(self, packet: bytes) -> bytes:
        if not self._state.connected:
            logger.warning("sim.cmd.upload.not_connected")
            return encode_error_response(XcpError.ERR_ACCESS_DENIED)
        if len(packet) < 2:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        num = packet[1]
        if num < 1 or num > XCP_MAX_UPLOAD_BYTES:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        start = self._state.mta_address
        if start + num > len(self._state.memory):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        chunk = bytes(self._state.memory[start : start + num])
        self._state.mta_address += num
        logger.info("sim.cmd.upload", start=hex(start), num=num)
        return encode_positive_response(chunk)

    def _handle_short_upload(self, packet: bytes) -> bytes:
        if not self._state.connected:
            logger.warning("sim.cmd.short_upload.not_connected")
            return encode_error_response(XcpError.ERR_ACCESS_DENIED)
        if len(packet) < 8:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        num = packet[1]
        if num < 1 or num > XCP_MAX_UPLOAD_BYTES:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        address = int.from_bytes(packet[4:8], byteorder="little", signed=False)
        if address + num > len(self._state.memory):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        chunk = bytes(self._state.memory[address : address + num])
        logger.info("sim.cmd.short_upload", address=hex(address), num=num)
        return encode_positive_response(chunk)

    def _handle_download(self, packet: bytes) -> bytes:
        if not self._state.connected:
            logger.warning("sim.cmd.download.not_connected")
            return encode_error_response(XcpError.ERR_ACCESS_DENIED)
        if len(packet) < 2:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        num = packet[1]
        if num < 1 or num > XCP_MAX_DOWNLOAD_BYTES:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        if len(packet) < 2 + num:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        start = self._state.mta_address
        if start + num > len(self._state.memory):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        payload = packet[2 : 2 + num]
        self._state.memory[start : start + num] = payload
        self._state.mta_address += num
        logger.info("sim.cmd.download", start=hex(start), num=num)
        return encode_positive_response(b"")

    def _handle_build_checksum(self, packet: bytes) -> bytes:
        if not self._state.connected:
            logger.warning("sim.cmd.build_checksum.not_connected")
            return encode_error_response(XcpError.ERR_ACCESS_DENIED)
        if len(packet) < 8:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        block_size = int.from_bytes(packet[4:8], byteorder="little", signed=False)
        if block_size == 0:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        start = self._state.mta_address
        if start + block_size > len(self._state.memory):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        checksum = sum(self._state.memory[start : start + block_size]) & 0xFFFFFFFF
        self._state.mta_address += block_size
        response = BuildChecksumResponse(
            checksum_type=XcpChecksumType.ADD_44, checksum=checksum
        )
        logger.info(
            "sim.cmd.build_checksum",
            start=hex(start),
            block_size=block_size,
            checksum=hex(checksum),
        )
        return encode_positive_response(response.encode_body())

    def _handle_synch(self) -> bytes:
        """SYNCH always responds with ERR_CMD_SYNCH per XCP 1.4 Part 2 §1.3.1.2."""
        logger.info("sim.cmd.synch")
        return encode_error_response(XcpError.ERR_CMD_SYNCH)
