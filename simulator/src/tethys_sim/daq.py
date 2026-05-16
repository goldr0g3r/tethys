"""Simulator DAQ engine - Python twin of ``slave/src/core/xcp_daq.c``.

Used by :class:`tethys_sim.slave.XcpSimSlave` to handle every DAQ
command on the wire-byte level and to emit DTOs when the master fires a
tick.

Cite: ASAM XCP 1.4 Part 2 §1.4.2
Cite: parent plan §8 (Phase 3 acceptance)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tethys_master.protocol.daq import (
    DaqListMode,
    StartStopDaqListMode,
    StartStopSynchMode,
    XcpDaqCommand,
)
from tethys_master.protocol.frame import (
    XcpError,
    encode_error_response,
    encode_positive_response,
)

# Sizing mirrors slave/include/tethys/tethys_static_memory.h.
SIM_MAX_DAQ_LISTS = 8
SIM_MAX_ODTS_PER_LIST = 16
SIM_MAX_ODT_ENTRIES = 16
SIM_MAX_DAQ_EVENTS = 16


@dataclass(slots=True)
class SimOdtEntry:
    address: int = 0
    address_extension: int = 0
    length: int = 0
    bit_offset: int = 0xFF


@dataclass(slots=True)
class SimDaqOdt:
    entry_count: int = 0
    entries: list[SimOdtEntry] = field(
        default_factory=lambda: [SimOdtEntry() for _ in range(SIM_MAX_ODT_ENTRIES)]
    )


@dataclass(slots=True)
class SimDaqList:
    odt_count: int = 0
    event_channel: int = 0
    prescaler: int = 0
    prescale_count: int = 0
    mode: int = 0
    ctr: int = 0
    enabled: bool = False
    odts: list[SimDaqOdt] = field(
        default_factory=lambda: [SimDaqOdt() for _ in range(SIM_MAX_ODTS_PER_LIST)]
    )


@dataclass(slots=True)
class SimDaqState:
    """Mutable state mirrored from the C ``tethys_daq_state_t``."""

    allocated_lists: int = 0
    any_active: bool = False
    daq_ptr_list: int = 0
    daq_ptr_odt: int = 0
    daq_ptr_entry: int = 0
    lists: list[SimDaqList] = field(
        default_factory=lambda: [SimDaqList() for _ in range(SIM_MAX_DAQ_LISTS)]
    )


class SimDaqEngine:
    """Pure-Python DAQ engine for the posix-sim slave."""

    def __init__(self, *, max_dto: int = 256) -> None:
        self._state = SimDaqState()
        self._max_dto = int(max_dto)

    @property
    def state(self) -> SimDaqState:
        return self._state

    def reset(self) -> None:
        self._state = SimDaqState()

    # ---- Wire dispatch ----------------------------------------------

    def dispatch_cto(self, packet: bytes) -> bytes | None:
        """Handle one DAQ CTO. Returns the response bytes, or None if the
        packet's first byte is not a DAQ command (caller routes elsewhere)."""
        if not packet:
            return None
        cmd = packet[0]
        if cmd == int(XcpDaqCommand.FREE_DAQ):
            self._state = SimDaqState()
            return encode_positive_response(b"")
        if cmd == int(XcpDaqCommand.ALLOC_DAQ):
            return self._handle_alloc_daq(packet)
        if cmd == int(XcpDaqCommand.ALLOC_ODT):
            return self._handle_alloc_odt(packet)
        if cmd == int(XcpDaqCommand.ALLOC_ODT_ENTRY):
            return self._handle_alloc_odt_entry(packet)
        if cmd == int(XcpDaqCommand.SET_DAQ_PTR):
            return self._handle_set_daq_ptr(packet)
        if cmd == int(XcpDaqCommand.WRITE_DAQ):
            return self._handle_write_daq(packet)
        if cmd == int(XcpDaqCommand.SET_DAQ_LIST_MODE):
            return self._handle_set_daq_list_mode(packet)
        if cmd == int(XcpDaqCommand.GET_DAQ_LIST_MODE):
            return self._handle_get_daq_list_mode(packet)
        if cmd == int(XcpDaqCommand.START_STOP_DAQ_LIST):
            return self._handle_start_stop_daq_list(packet)
        if cmd == int(XcpDaqCommand.START_STOP_SYNCH):
            return self._handle_start_stop_synch(packet)
        if cmd == int(XcpDaqCommand.CLEAR_DAQ_LIST):
            return self._handle_clear_daq_list(packet)
        if cmd == int(XcpDaqCommand.GET_DAQ_PROCESSOR_INFO):
            return self._handle_get_daq_processor_info()
        if cmd == int(XcpDaqCommand.GET_DAQ_RESOLUTION_INFO):
            return self._handle_get_daq_resolution_info()
        if cmd == int(XcpDaqCommand.GET_DAQ_LIST_INFO):
            return self._handle_get_daq_list_info(packet)
        if cmd == int(XcpDaqCommand.GET_DAQ_EVENT_INFO):
            return self._handle_get_daq_event_info(packet)
        return None

    # ---- Helpers ----------------------------------------------------

    @staticmethod
    def _u16(p: bytes, idx: int) -> int:
        return int.from_bytes(p[idx : idx + 2], byteorder="little", signed=False)

    @staticmethod
    def _u32(p: bytes, idx: int) -> int:
        return int.from_bytes(p[idx : idx + 4], byteorder="little", signed=False)

    def _list_in_range(self, daq_num: int) -> bool:
        return 0 <= daq_num < self._state.allocated_lists

    def _odt_in_range(self, daq_num: int, odt_num: int) -> bool:
        if not self._list_in_range(daq_num):
            return False
        return 0 <= odt_num < self._state.lists[daq_num].odt_count

    def _entry_in_range(self, daq_num: int, odt_num: int, entry_num: int) -> bool:
        if not self._odt_in_range(daq_num, odt_num):
            return False
        return 0 <= entry_num < self._state.lists[daq_num].odts[odt_num].entry_count

    # ---- Allocation / configuration ---------------------------------

    def _handle_alloc_daq(self, packet: bytes) -> bytes:
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        count = self._u16(packet, 2)
        if count > SIM_MAX_DAQ_LISTS:
            return encode_error_response(0x30)  # ERR_MEMORY_OVERFLOW
        self._state = SimDaqState(allocated_lists=count)
        return encode_positive_response(b"")

    def _handle_alloc_odt(self, packet: bytes) -> bytes:
        if len(packet) < 5:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = self._u16(packet, 2)
        odt_count = packet[4]
        if not self._list_in_range(daq_num):
            return encode_error_response(0x30)
        if odt_count > SIM_MAX_ODTS_PER_LIST:
            return encode_error_response(0x30)
        lst = self._state.lists[daq_num]
        lst.odt_count = odt_count
        for j in range(SIM_MAX_ODTS_PER_LIST):
            lst.odts[j].entry_count = 0
        return encode_positive_response(b"")

    def _handle_alloc_odt_entry(self, packet: bytes) -> bytes:
        if len(packet) < 6:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = self._u16(packet, 2)
        odt_num = packet[4]
        entry_count = packet[5]
        if not self._odt_in_range(daq_num, odt_num):
            return encode_error_response(0x30)
        if entry_count > SIM_MAX_ODT_ENTRIES:
            return encode_error_response(0x30)
        self._state.lists[daq_num].odts[odt_num].entry_count = entry_count
        return encode_positive_response(b"")

    def _handle_set_daq_ptr(self, packet: bytes) -> bytes:
        if len(packet) < 6:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = self._u16(packet, 2)
        odt_num = packet[4]
        entry_num = packet[5]
        if not self._entry_in_range(daq_num, odt_num, entry_num):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        self._state.daq_ptr_list = daq_num
        self._state.daq_ptr_odt = odt_num
        self._state.daq_ptr_entry = entry_num
        return encode_positive_response(b"")

    def _handle_write_daq(self, packet: bytes) -> bytes:
        if len(packet) < 8:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        bit_offset = packet[1]
        size_bytes = packet[2]
        ext = packet[3]
        address = self._u32(packet, 4)
        if size_bytes == 0:
            return encode_error_response(0x32)  # ERR_DAQ_CONFIG
        if not self._entry_in_range(
            self._state.daq_ptr_list,
            self._state.daq_ptr_odt,
            self._state.daq_ptr_entry,
        ):
            return encode_error_response(0x32)
        entry = (
            self._state.lists[self._state.daq_ptr_list]
            .odts[self._state.daq_ptr_odt]
            .entries[self._state.daq_ptr_entry]
        )
        entry.bit_offset = bit_offset
        entry.length = size_bytes
        entry.address_extension = ext
        entry.address = address
        ec = self._state.lists[self._state.daq_ptr_list].odts[self._state.daq_ptr_odt].entry_count
        if self._state.daq_ptr_entry + 1 < ec:
            self._state.daq_ptr_entry += 1
        return encode_positive_response(b"")

    def _handle_set_daq_list_mode(self, packet: bytes) -> bytes:
        if len(packet) < 8:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        mode = packet[1]
        daq_num = self._u16(packet, 2)
        event_ch = self._u16(packet, 4)
        prescaler = packet[6]
        if not self._list_in_range(daq_num):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        if event_ch >= SIM_MAX_DAQ_EVENTS:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        if prescaler == 0:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        lst = self._state.lists[daq_num]
        lst.mode = mode
        lst.event_channel = event_ch
        lst.prescaler = prescaler
        lst.prescale_count = prescaler
        return encode_positive_response(b"")

    def _handle_get_daq_list_mode(self, packet: bytes) -> bytes:
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = self._u16(packet, 2)
        if not self._list_in_range(daq_num):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        lst = self._state.lists[daq_num]
        body = (
            bytes([lst.mode, 0, 0])
            + (lst.event_channel & 0xFFFF).to_bytes(2, "little", signed=False)
            + bytes([lst.prescaler, 0])
        )
        return encode_positive_response(body)

    def _handle_start_stop_daq_list(self, packet: bytes) -> bytes:
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        mode = packet[1]
        daq_num = self._u16(packet, 2)
        if not self._list_in_range(daq_num):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        lst = self._state.lists[daq_num]
        if mode == int(StartStopDaqListMode.START):
            lst.enabled = True
            self._state.any_active = True
        elif mode == int(StartStopDaqListMode.STOP):
            lst.enabled = False
            self._state.any_active = any(
                self._state.lists[i].enabled for i in range(self._state.allocated_lists)
            )
        elif mode == int(StartStopDaqListMode.SELECT):
            lst.prescale_count = lst.prescaler
        else:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        return encode_positive_response(b"\x00")

    def _handle_start_stop_synch(self, packet: bytes) -> bytes:
        if len(packet) < 2:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        mode = packet[1]
        if mode in (int(StartStopSynchMode.STOP_ALL), int(StartStopSynchMode.STOP_SELECTED)):
            for i in range(self._state.allocated_lists):
                self._state.lists[i].enabled = False
            self._state.any_active = False
        elif mode == int(StartStopSynchMode.START_SELECTED):
            for i in range(self._state.allocated_lists):
                self._state.lists[i].enabled = True
            self._state.any_active = self._state.allocated_lists > 0
        return encode_positive_response(b"")

    def _handle_clear_daq_list(self, packet: bytes) -> bytes:
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = self._u16(packet, 2)
        if not self._list_in_range(daq_num):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        lst = self._state.lists[daq_num]
        for j in range(lst.odt_count):
            lst.odts[j].entry_count = 0
        return encode_positive_response(b"")

    # ---- Info queries -----------------------------------------------

    def _handle_get_daq_processor_info(self) -> bytes:
        body = bytes(
            [
                0x11,
                SIM_MAX_DAQ_LISTS, 0,
                SIM_MAX_DAQ_EVENTS, 0,
                0, 0,
            ]
        )
        return encode_positive_response(body)

    def _handle_get_daq_resolution_info(self) -> bytes:
        body = bytes(
            [
                1,
                0xFF,
                1,
                0xFF,
                0x8A,
                1, 0,
            ]
        )
        return encode_positive_response(body)

    def _handle_get_daq_list_info(self, packet: bytes) -> bytes:
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        daq_num = self._u16(packet, 2)
        if not self._list_in_range(daq_num):
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        lst = self._state.lists[daq_num]
        props = 0x04 if (lst.mode & int(DaqListMode.STIM)) != 0 else 0x00
        body = bytes(
            [
                props,
                SIM_MAX_ODTS_PER_LIST,
                SIM_MAX_ODT_ENTRIES,
            ]
        ) + (lst.event_channel & 0xFFFF).to_bytes(2, "little", signed=False)
        return encode_positive_response(body)

    def _handle_get_daq_event_info(self, packet: bytes) -> bytes:
        if len(packet) < 4:
            return encode_error_response(XcpError.ERR_CMD_SYNTAX)
        event_ch = self._u16(packet, 2)
        if event_ch >= SIM_MAX_DAQ_EVENTS:
            return encode_error_response(XcpError.ERR_OUT_OF_RANGE)
        body = bytes([0x05, SIM_MAX_DAQ_LISTS, 11, 1, 6, 0])
        return encode_positive_response(body)

    # ---- Runtime DTO emission ---------------------------------------

    def fire_event(self, event_id: int, memory: bytes) -> list[bytes]:
        """Tick the engine. Returns the DTOs that should be sent."""
        if not self._state.any_active:
            return []
        dtos: list[bytes] = []
        for i in range(self._state.allocated_lists):
            lst = self._state.lists[i]
            if not lst.enabled:
                continue
            if lst.event_channel != event_id:
                continue
            if lst.prescale_count > 1:
                lst.prescale_count -= 1
                continue
            lst.prescale_count = lst.prescaler
            abs_odt_base = sum(self._state.lists[k].odt_count for k in range(i))
            for j in range(lst.odt_count):
                abs_odt = (abs_odt_base + j) & 0xFF
                payload = bytearray()
                for k in range(lst.odts[j].entry_count):
                    e = lst.odts[j].entries[k]
                    if e.length == 0:
                        continue
                    end = e.address + e.length
                    if e.address < 0 or end > len(memory):
                        payload.extend(b"\x00" * e.length)
                    else:
                        payload.extend(memory[e.address : end])
                    if len(payload) + 2 > self._max_dto:
                        break
                dtos.append(bytes([abs_odt, lst.ctr]) + bytes(payload))
            lst.ctr = (lst.ctr + 1) & 0xFF
        return dtos
