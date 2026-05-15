"""posix-sim XCP slave - asyncio UDP server implementing the Phase-1 command set.

This is a Python-side functional twin of the C dispatcher in
``slave/src/core/xcp_dispatcher.c``. Both must agree on the wire-level
behaviour of the supported commands so the acceptance bench can swap
between them transparently.

Cite: ASAM XCP 1.4 Part 2 §1.3.2 + §1.4.2.1
Cite: parent plan section 7 (Phase 1 acceptance)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tethys_master.logging_setup import get_logger
from tethys_master.protocol.frame import (
    ConnectResponse,
    GetStatusResponse,
    GetVersionResponse,
    ResourceMask,
    XcpCommand,
    XcpError,
    encode_error_response,
    encode_positive_response,
)

logger = get_logger(__name__)


@dataclass(slots=True)
class SlaveState:
    """Volatile slave state (one instance per simulator process)."""

    connected: bool = False
    session_status: int = 0x00
    resource_protection: int = 0x00
    state_number: int = 0x00
    session_configuration_id: int = 0xABCD


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

    def dispatch(self, packet: bytes) -> bytes | None:  # noqa: PLR0911 - one return per XCP command branch
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
        logger.warning("sim.cmd.unknown", cmd=hex(cmd))
        return encode_error_response(XcpError.ERR_CMD_UNKNOWN)
