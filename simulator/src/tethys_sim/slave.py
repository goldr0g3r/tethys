"""posix-sim XCP slave - asyncio UDP server (Phase 1 + Phase 2 + Phase 3 DAQ).

This is a Python-side functional twin of the C dispatcher in
``slave/src/core/xcp_dispatcher.c`` + ``slave/src/core/xcp_daq.c``. Both
must agree on the wire-level behaviour of the supported commands so the
acceptance bench (and the PR-31 differential test against pyxcp) can
swap between them transparently. The Python implementation operates
against a 1 KiB ramp-pattern memory backend.

Phase 3 (PR-3b) extends the simulator with:

- DAQ command set: FREE_DAQ / ALLOC_DAQ / ALLOC_ODT / ALLOC_ODT_ENTRY,
  SET_DAQ_PTR / WRITE_DAQ, SET_DAQ_LIST_MODE / GET_DAQ_LIST_MODE,
  START_STOP_DAQ_LIST / START_STOP_SYNCH, plus the read-only
  GET_DAQ_{PROCESSOR,RESOLUTION}_INFO descriptors.
- Cyclic DTO emission task: when DAQ lists are running, an asyncio
  background task ticks at ``daq_tick_hz`` Hz, packs each ODT into a
  DTO frame, and `sendto`s it to the most recent CTO peer address.

Opcode assignments mirror the C-side constants in
``slave/include/tethys/xcp_daq.h``, which themselves come straight from
ASAM XCP 1.4 Part 2 Table 17 (Standard Command Codes).

Cite: ASAM XCP 1.4 Part 2 §1.3.1..§1.3.4 + §1.4.2.1 + §1.5 (CTO)
Cite: ASAM XCP 1.4 Part 2 §1.4 (DAQ command set + DTO emission)
Cite: parent plan §8 (Phase 2 + Phase 3 acceptance)
"""

from __future__ import annotations

import asyncio
import contextlib
import time
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

# ---- DAQ static sizing (mirrors slave/include/tethys/xcp_odt.h) -------

SIM_DAQ_MAX_LISTS = 4
SIM_DAQ_MAX_ODT_PER_LIST = 8
SIM_DAQ_MAX_ENTRIES_PER_ODT = 16
SIM_DAQ_MAX_DTO_BYTES = 64

# ---- DAQ command codes (mirrors slave/include/tethys/xcp_daq.h) -------
# These line up with ASAM XCP 1.4 Part 2 Table 17 / §1.4.

CMD_FREE_DAQ = 0xD6
CMD_ALLOC_DAQ = 0xD5
CMD_ALLOC_ODT = 0xD4
CMD_ALLOC_ODT_ENTRY = 0xD3
CMD_SET_DAQ_PTR = 0xE2
CMD_WRITE_DAQ = 0xE1
CMD_WRITE_DAQ_MULTIPLE = 0xC7
CMD_SET_DAQ_LIST_MODE = 0xE0
CMD_GET_DAQ_LIST_MODE = 0xDF
CMD_START_STOP_DAQ_LIST = 0xDE
CMD_START_STOP_SYNCH = 0xDD
CMD_GET_DAQ_PROCESSOR_INFO = 0xDA
CMD_GET_DAQ_RESOLUTION_INFO = 0xD9
CMD_GET_DAQ_LIST_INFO = 0xD8
CMD_GET_DAQ_EVENT_INFO = 0xD7
CMD_READ_DAQ = 0xDB

# SET_DAQ_LIST_MODE mode bits (XCP 1.4 Part 2 §1.4.2.6)
DAQ_MODE_DIRECTION_STIM = 0x02
DAQ_MODE_TIMESTAMP = 0x04
DAQ_MODE_PID_OFF = 0x10

# START_STOP_DAQ_LIST modes (XCP 1.4 §1.4.2.4)
DAQ_SS_STOP = 0x00
DAQ_SS_START = 0x01
DAQ_SS_SELECT = 0x02

# START_STOP_SYNCH modes (XCP 1.4 §1.4.2.5)
DAQ_SYNCH_STOP_ALL = 0x00
DAQ_SYNCH_START_SELECTED = 0x01
DAQ_SYNCH_STOP_SELECTED = 0x02
DAQ_SYNCH_PREPARE_START_SELECTED = 0x03

# DAQ-specific error codes (XCP 1.4 Part 2 Table 12)
ERR_MEMORY_OVERFLOW = 0x30
ERR_DAQ_CONFIG = 0x32


@dataclass(slots=True)
class SimOdtEntry:
    """One ODT entry - mirrors C struct ``tethys_daq_entry_t``."""

    bit_offset: int = 0xFF
    size_bytes: int = 0
    addr_extension: int = 0
    address: int = 0
    in_use: bool = False


@dataclass(slots=True)
class SimOdt:
    """One ODT - fixed-size entry array."""

    entries: list[SimOdtEntry] = field(
        default_factory=lambda: [
            SimOdtEntry() for _ in range(SIM_DAQ_MAX_ENTRIES_PER_ODT)
        ]
    )
    entry_count: int = 0


@dataclass(slots=True)
class SimDaqList:
    """One DAQ list - fixed-size ODT array + mode bits + runtime state."""

    odts: list[SimOdt] = field(
        default_factory=lambda: [SimOdt() for _ in range(SIM_DAQ_MAX_ODT_PER_LIST)]
    )
    odt_count: int = 0
    first_pid: int = 0
    mode: int = 0
    event_channel: int = 0
    prescaler: int = 1
    prescaler_counter: int = 0
    priority: int = 0
    allocated: bool = False
    running: bool = False
    selected: bool = False


@dataclass(slots=True)
class SimDaqEngine:
    """Functional twin of the C ``tethys_daq_engine_t``."""

    lists: list[SimDaqList] = field(
        default_factory=lambda: [SimDaqList() for _ in range(SIM_DAQ_MAX_LISTS)]
    )
    list_count: int = 0
    ptr_daq: int = 0
    ptr_odt: int = 0
    ptr_entry: int = 0
    ptr_valid: bool = False
    dto_counter: int = 0

    def reset(self) -> None:
        for daq_list in self.lists:
            daq_list.odt_count = 0
            daq_list.first_pid = 0
            daq_list.mode = 0
            daq_list.event_channel = 0
            daq_list.prescaler = 1
            daq_list.prescaler_counter = 0
            daq_list.priority = 0
            daq_list.allocated = False
            daq_list.running = False
            daq_list.selected = False
            for odt in daq_list.odts:
                odt.entry_count = 0
                for entry in odt.entries:
                    entry.in_use = False
                    entry.size_bytes = 0
                    entry.address = 0
                    entry.addr_extension = 0
                    entry.bit_offset = 0xFF
        self.list_count = 0
        self.ptr_valid = False
        self.ptr_daq = 0
        self.ptr_odt = 0
        self.ptr_entry = 0
        self.dto_counter = 0

    def recompute_first_pids(self) -> None:
        """PID 0..0xFB = absolute ODT number (XCP 1.4 §1.4.2.1)."""
        cursor = 0
        for daq_list in self.lists[: self.list_count]:
            if not daq_list.allocated:
                continue
            daq_list.first_pid = cursor
            cursor = min(0xFC, cursor + daq_list.odt_count)


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
    daq: SimDaqEngine = field(default_factory=SimDaqEngine)


class XcpSimSlave:
    """asyncio UDP server emulating the Tethys C slave."""

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",  # noqa: S104 - intentional bind-any in dev / loopback bench
        port: int = 5555,
        profile: str = "marine",
        daq_tick_hz: float = 1000.0,
        daq_event_channel: int = 1,
    ) -> None:
        self._host = host
        self._port = port
        self._profile = profile
        self._state = SlaveState()
        self._transport: asyncio.DatagramTransport | None = None
        self._peer_addr: tuple[str, int] | None = None
        self._daq_tick_hz = float(daq_tick_hz)
        self._daq_event_channel = int(daq_event_channel)
        self._daq_task: asyncio.Task[None] | None = None
        self._t0_ns: int = 0

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
                slave._peer_addr = addr
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
        self._t0_ns = time.monotonic_ns()
        self._daq_task = asyncio.create_task(self._daq_emitter_loop())

    async def stop(self) -> None:
        if self._daq_task is not None and not self._daq_task.done():
            self._daq_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._daq_task
            self._daq_task = None
        if self._transport is not None and not self._transport.is_closing():
            self._transport.close()
            logger.info("sim.stopped")

    # ---- DAQ tick driver --------------------------------------------

    async def _daq_emitter_loop(self) -> None:
        """Tick the engine at ``daq_tick_hz`` and emit DTOs to the active peer.

        The loop is best-effort: if no peer has connected yet, ticks are
        a no-op. Once a peer is registered (any CTO received), every
        running DAQ list whose event channel matches the simulator's
        tick channel emits one DTO per ODT per tick.
        """
        period_s = 1.0 / self._daq_tick_hz if self._daq_tick_hz > 0 else 0.001
        try:
            while True:
                await asyncio.sleep(period_s)
                if self._peer_addr is None or self._transport is None:
                    continue
                if self._transport.is_closing():
                    return
                timestamp_us = (time.monotonic_ns() - self._t0_ns) // 1000
                self._tick(self._daq_event_channel, timestamp_us & 0xFFFFFFFF)
        except asyncio.CancelledError:
            raise

    def _tick(self, event_channel: int, timestamp_us: int) -> int:
        """Drive one event-tick. Returns the number of DTOs emitted."""
        engine = self._state.daq
        emitted = 0
        for i in range(engine.list_count):
            daq_list = engine.lists[i]
            if not daq_list.allocated or not daq_list.running:
                continue
            if daq_list.mode & DAQ_MODE_DIRECTION_STIM:
                continue
            if daq_list.event_channel != event_channel:
                continue
            daq_list.prescaler_counter += 1
            if daq_list.prescaler_counter < daq_list.prescaler:
                continue
            daq_list.prescaler_counter = 0
            for odt_num in range(daq_list.odt_count):
                payload = self._pack_dto(i, odt_num, timestamp_us)
                if payload is None:
                    continue
                if self._transport is not None and self._peer_addr is not None:
                    self._transport.sendto(payload, self._peer_addr)
                engine.dto_counter = (engine.dto_counter + 1) & 0xFFFF
                emitted += 1
        return emitted

    def _pack_dto(self, daq_list_num: int, odt_num: int, timestamp_us: int) -> bytes | None:
        engine = self._state.daq
        daq_list = engine.lists[daq_list_num]
        odt = daq_list.odts[odt_num]
        out = bytearray()
        if not (daq_list.mode & DAQ_MODE_PID_OFF):
            out.append((daq_list.first_pid + odt_num) & 0xFF)
        if daq_list.mode & DAQ_MODE_TIMESTAMP:
            out.extend(int(timestamp_us & 0xFFFFFFFF).to_bytes(4, byteorder="little"))
        for entry in odt.entries[: odt.entry_count]:
            if not entry.in_use:
                continue
            end = entry.address + entry.size_bytes
            if end > len(self._state.memory):
                return None
            out.extend(self._state.memory[entry.address : end])
        return bytes(out)

    def tick_once(self, event_channel: int | None = None, timestamp_us: int = 0) -> int:
        """Public test hook: drive one event-tick synchronously.

        Returns the number of DTOs emitted to the registered peer
        (0 if no peer is registered yet).
        """
        return self._tick(
            self._daq_event_channel if event_channel is None else event_channel,
            timestamp_us,
        )

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
        if cmd == CMD_FREE_DAQ:
            return self._handle_free_daq()
        if cmd == CMD_ALLOC_DAQ:
            return self._handle_alloc_daq(packet)
        if cmd == CMD_ALLOC_ODT:
            return self._handle_alloc_odt(packet)
        if cmd == CMD_ALLOC_ODT_ENTRY:
            return self._handle_alloc_odt_entry(packet)
        if cmd == CMD_SET_DAQ_PTR:
            return self._handle_set_daq_ptr(packet)
        if cmd == CMD_WRITE_DAQ:
            return self._handle_write_daq(packet)
        if cmd == CMD_SET_DAQ_LIST_MODE:
            return self._handle_set_daq_list_mode(packet)
        if cmd == CMD_GET_DAQ_LIST_MODE:
            return self._handle_get_daq_list_mode(packet)
        if cmd == CMD_START_STOP_DAQ_LIST:
            return self._handle_start_stop_daq_list(packet)
        if cmd == CMD_START_STOP_SYNCH:
            return self._handle_start_stop_synch(packet)
        if cmd == CMD_GET_DAQ_PROCESSOR_INFO:
            return self._handle_get_daq_processor_info()
        if cmd == CMD_GET_DAQ_RESOLUTION_INFO:
            return self._handle_get_daq_resolution_info()
        logger.warning("sim.cmd.unknown", cmd=hex(cmd))
        return encode_error_response(XcpError.ERR_CMD_UNKNOWN)

    # ---- Phase 2 read-path handlers -------------------------------

    def _handle_set_mta(self, packet: bytes) -> bytes:
        if not self._state.connected:
            return encode_error_response(XcpError.ERR_ACCESS_DENIED)
        if len(packet) < 8:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        self._state.mta_extension = packet[3]
        self._state.mta_address = int.from_bytes(packet[4:8], byteorder="little", signed=False)
        return encode_positive_response(b"")

    def _handle_upload(self, packet: bytes) -> bytes:
        if not self._state.connected:
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
        return encode_positive_response(chunk)

    def _handle_short_upload(self, packet: bytes) -> bytes:
        if not self._state.connected:
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
        return encode_positive_response(chunk)

    def _handle_download(self, packet: bytes) -> bytes:
        if not self._state.connected:
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
        return encode_positive_response(b"")

    def _handle_build_checksum(self, packet: bytes) -> bytes:
        if not self._state.connected:
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
        return encode_positive_response(response.encode_body())

    def _handle_synch(self) -> bytes:
        """SYNCH always responds with ERR_CMD_SYNCH per XCP 1.4 Part 2 §1.3.1.2."""
        return encode_error_response(XcpError.ERR_CMD_SYNCH)

    # ---- Phase 3 DAQ command handlers --------------------------------

    def _check_daq_connected(self) -> bytes | None:
        if not self._state.connected:
            return encode_error_response(XcpError.ERR_ACCESS_DENIED)
        return None

    @staticmethod
    def _res_only() -> bytes:
        return encode_positive_response(b"")

    def _handle_free_daq(self) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        self._state.daq.reset()
        return self._res_only()

    def _handle_alloc_daq(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        list_count = int.from_bytes(packet[2:4], byteorder="little", signed=False)
        if list_count == 0 or list_count > SIM_DAQ_MAX_LISTS:
            return encode_error_response(ERR_MEMORY_OVERFLOW)
        self._state.daq.reset()
        self._state.daq.list_count = list_count
        for i in range(list_count):
            self._state.daq.lists[i].allocated = True
            self._state.daq.lists[i].prescaler = 1
        self._state.daq.recompute_first_pids()
        return self._res_only()

    def _handle_alloc_odt(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if len(packet) < 5:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = int.from_bytes(packet[2:4], byteorder="little", signed=False)
        odt_count = packet[4]
        if daq_num >= self._state.daq.list_count:
            return encode_error_response(ERR_MEMORY_OVERFLOW)
        if odt_count == 0 or odt_count > SIM_DAQ_MAX_ODT_PER_LIST:
            return encode_error_response(ERR_MEMORY_OVERFLOW)
        daq_list = self._state.daq.lists[daq_num]
        if not daq_list.allocated:
            return encode_error_response(ERR_MEMORY_OVERFLOW)
        daq_list.odt_count = odt_count
        for odt in daq_list.odts:
            odt.entry_count = 0
            for e in odt.entries:
                e.in_use = False
        self._state.daq.recompute_first_pids()
        return self._res_only()

    def _handle_alloc_odt_entry(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if len(packet) < 6:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = int.from_bytes(packet[2:4], byteorder="little", signed=False)
        odt_num = packet[4]
        entry_count = packet[5]
        if daq_num >= self._state.daq.list_count:
            return encode_error_response(ERR_MEMORY_OVERFLOW)
        daq_list = self._state.daq.lists[daq_num]
        if odt_num >= daq_list.odt_count:
            return encode_error_response(ERR_MEMORY_OVERFLOW)
        if entry_count == 0 or entry_count > SIM_DAQ_MAX_ENTRIES_PER_ODT:
            return encode_error_response(ERR_MEMORY_OVERFLOW)
        odt = daq_list.odts[odt_num]
        odt.entry_count = entry_count
        for e in odt.entries:
            e.in_use = False
        return self._res_only()

    def _handle_set_daq_ptr(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if len(packet) < 6:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = int.from_bytes(packet[2:4], byteorder="little", signed=False)
        odt_num = packet[4]
        entry_idx = packet[5]
        if daq_num >= self._state.daq.list_count:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        daq_list = self._state.daq.lists[daq_num]
        if odt_num >= daq_list.odt_count:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        if entry_idx >= daq_list.odts[odt_num].entry_count:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        self._state.daq.ptr_daq = daq_num
        self._state.daq.ptr_odt = odt_num
        self._state.daq.ptr_entry = entry_idx
        self._state.daq.ptr_valid = True
        return self._res_only()

    def _handle_write_daq(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if not self._state.daq.ptr_valid:
            return encode_error_response(ERR_DAQ_CONFIG)
        if len(packet) < 8:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        bit_offset = packet[1]
        size_bytes = packet[2]
        ext = packet[3]
        address = int.from_bytes(packet[4:8], byteorder="little", signed=False)
        if size_bytes == 0:
            return encode_error_response(ERR_DAQ_CONFIG)
        daq_list = self._state.daq.lists[self._state.daq.ptr_daq]
        odt = daq_list.odts[self._state.daq.ptr_odt]
        if self._state.daq.ptr_entry >= odt.entry_count:
            return encode_error_response(ERR_DAQ_CONFIG)
        entry = odt.entries[self._state.daq.ptr_entry]
        entry.bit_offset = bit_offset
        entry.size_bytes = size_bytes
        entry.addr_extension = ext
        entry.address = address
        entry.in_use = True
        if self._state.daq.ptr_entry < odt.entry_count - 1:
            self._state.daq.ptr_entry += 1
        return self._res_only()

    def _handle_set_daq_list_mode(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if len(packet) < 8:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        mode = packet[1]
        daq_num = int.from_bytes(packet[2:4], byteorder="little", signed=False)
        event_channel = int.from_bytes(packet[4:6], byteorder="little", signed=False)
        prescaler = packet[6] if packet[6] != 0 else 1
        priority = packet[7]
        if daq_num >= self._state.daq.list_count:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        daq_list = self._state.daq.lists[daq_num]
        if not daq_list.allocated:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        daq_list.mode = mode
        daq_list.event_channel = event_channel
        daq_list.prescaler = prescaler
        daq_list.priority = priority
        daq_list.prescaler_counter = 0
        return self._res_only()

    def _handle_get_daq_list_mode(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = int.from_bytes(packet[2:4], byteorder="little", signed=False)
        if daq_num >= self._state.daq.list_count:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        daq_list = self._state.daq.lists[daq_num]
        body = bytes([
            daq_list.mode, 0, 0,
            daq_list.event_channel & 0xFF,
            (daq_list.event_channel >> 8) & 0xFF,
            daq_list.prescaler, daq_list.priority,
        ])
        return encode_positive_response(body)

    def _handle_start_stop_daq_list(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        mode = packet[1]
        daq_num = int.from_bytes(packet[2:4], byteorder="little", signed=False)
        if daq_num >= self._state.daq.list_count:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        daq_list = self._state.daq.lists[daq_num]
        if mode == DAQ_SS_STOP:
            daq_list.running = False
            daq_list.selected = False
        elif mode == DAQ_SS_START:
            daq_list.running = True
            daq_list.selected = False
            daq_list.prescaler_counter = 0
        elif mode == DAQ_SS_SELECT:
            daq_list.selected = True
        else:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        return encode_positive_response(bytes([daq_list.first_pid]))

    def _handle_start_stop_synch(self, packet: bytes) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        if len(packet) < 2:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        mode = packet[1]
        if mode == DAQ_SYNCH_STOP_ALL:
            for daq_list in self._state.daq.lists[: self._state.daq.list_count]:
                daq_list.running = False
                daq_list.selected = False
        elif mode == DAQ_SYNCH_START_SELECTED:
            for daq_list in self._state.daq.lists[: self._state.daq.list_count]:
                if daq_list.selected:
                    daq_list.running = True
                    daq_list.selected = False
                    daq_list.prescaler_counter = 0
        elif mode == DAQ_SYNCH_STOP_SELECTED:
            for daq_list in self._state.daq.lists[: self._state.daq.list_count]:
                if daq_list.selected:
                    daq_list.running = False
                    daq_list.selected = False
        elif mode == DAQ_SYNCH_PREPARE_START_SELECTED:
            pass  # no-op per XCP 1.4 §1.4.2.5
        else:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        return self._res_only()

    def _handle_get_daq_processor_info(self) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        # daq_properties: OVERLOAD_INDICATION_PID | DYNAMIC; max_daq; max_event=0xFFFF
        return encode_positive_response(bytes([
            0x41, SIM_DAQ_MAX_LISTS, 0x00, 0xFF, 0xFF, 0x00, 0x00,
        ]))

    def _handle_get_daq_resolution_info(self) -> bytes:
        if (err := self._check_daq_connected()) is not None:
            return err
        # granularity=1, max=255, granularity_stim=1, max_stim=255, ts mode=DLONG+1us
        return encode_positive_response(bytes([
            0x01, 0xFF, 0x01, 0xFF, 0x34, 0x01, 0x00,
        ]))
