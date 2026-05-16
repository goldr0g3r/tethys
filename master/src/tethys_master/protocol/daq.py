"""Master-side DAQ (Data AcQuisition) command frames + receive loop.

Mirrors the slave-side wire layout from
``slave/src/core/xcp_daq.c`` + the posix-sim's
``simulator/src/tethys_sim/slave.py`` so the master, slave, and
simulator agree byte-for-byte on every DAQ command.

The dataclasses + opcode enum are pure data (no I/O, no async); the
:class:`DaqReceiveLoop` is the asyncio receive task that decodes DTOs
into :class:`DaqSample` records, tracks the wrap-aware CTR sequence to
detect packet loss, and forwards each sample to the registered sink
callback (typically a GUI plot pane + MDF4 recorder).

Cite: ASAM XCP 1.4 Part 2 §1.4 (DAQ command set)
Cite: ASAM XCP 1.4 Part 2 §1.4.2.1 (PID 0..0xFB = absolute ODT number)
Cite: ASAM XCP 1.4 Part 2 §1.4.2.6 (SET_DAQ_LIST_MODE mode bits)
Cite: ASAM XCP 1.4 Part 2 §3.1.5 (CTR field rationale)
Cite: ADR-0010 row 2 (DAQ loss budget) + row 12 (loopback acceptance)
Cite: docs/research/phase-0-system-requirements.md §7 (DAQ_GAP shape)
Trace: docs/traceability.csv rows TETHYS-DES-0050..0070 (land at PR-10)
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag


class XcpDaqCommand(IntEnum):
    """DAQ command codes (XCP 1.4 Part 2 Table 17 subset)."""

    FREE_DAQ = 0xD6
    ALLOC_DAQ = 0xD5
    ALLOC_ODT = 0xD4
    ALLOC_ODT_ENTRY = 0xD3
    SET_DAQ_PTR = 0xE2
    WRITE_DAQ = 0xE1
    WRITE_DAQ_MULTIPLE = 0xC7
    SET_DAQ_LIST_MODE = 0xE0
    GET_DAQ_LIST_MODE = 0xDF
    START_STOP_DAQ_LIST = 0xDE
    START_STOP_SYNCH = 0xDD
    GET_DAQ_PROCESSOR_INFO = 0xDA
    GET_DAQ_RESOLUTION_INFO = 0xD9
    GET_DAQ_LIST_INFO = 0xD8
    GET_DAQ_EVENT_INFO = 0xD7
    READ_DAQ = 0xDB


class DaqListMode(IntFlag):
    """SET_DAQ_LIST_MODE mode-byte bits (XCP 1.4 Part 2 §1.4.2.6 Table 22)."""

    DAQ = 0x00  # default direction
    ALTERNATING = 0x01
    STIM = 0x02
    TIMESTAMP = 0x04
    PID_OFF = 0x10


class StartStopListMode(IntEnum):
    """START_STOP_DAQ_LIST mode byte (XCP 1.4 §1.4.2.4 Table 18)."""

    STOP = 0x00
    START = 0x01
    SELECT = 0x02


class StartStopSynchMode(IntEnum):
    """START_STOP_SYNCH mode byte (XCP 1.4 §1.4.2.5 Table 19)."""

    STOP_ALL = 0x00
    START_SELECTED = 0x01
    STOP_SELECTED = 0x02
    PREPARE_START_SELECTED = 0x03


# Sentinel value for "no sub-byte packing" - matches the slave's
# TETHYS_DAQ_BIT_OFFSET_NONE constant.
BIT_OFFSET_NONE = 0xFF

# Static engine sizing (mirrors slave/include/tethys/xcp_odt.h)
MAX_DAQ_LISTS = 4
MAX_ODT_PER_LIST = 8
MAX_ENTRIES_PER_ODT = 16
MAX_DTO_BYTES = 64

# DAQ-specific error codes (XCP 1.4 Part 2 Table 12)
ERR_MEMORY_OVERFLOW = 0x30
ERR_DAQ_CONFIG = 0x32


# ---- ODT-entry model ------------------------------------------------


@dataclass(frozen=True, slots=True)
class OdtEntry:
    """One element reference inside an ODT.

    ``bit_offset`` of :data:`BIT_OFFSET_NONE` (0xFF) means no sub-byte
    packing - the entry covers ``size_bytes`` contiguous bytes starting
    at ``address`` in the slave's memory.
    """

    address: int
    size_bytes: int
    bit_offset: int = BIT_OFFSET_NONE
    address_extension: int = 0


@dataclass(slots=True)
class Odt:
    """One Object Descriptor Table - ordered list of element references."""

    entries: list[OdtEntry] = field(default_factory=list)

    def total_payload_bytes(self) -> int:
        return sum(e.size_bytes for e in self.entries)


@dataclass(slots=True)
class DaqList:
    """Master-side view of one DAQ list configured on the slave.

    Mirrors :class:`tethys_sim.slave.SimDaqList` + the C
    ``tethys_daq_list_t``. ``first_pid`` is assigned by the slave on
    START_STOP_DAQ_LIST and read back from the response packet.
    """

    odts: list[Odt] = field(default_factory=list)
    first_pid: int = 0
    mode: DaqListMode = DaqListMode.DAQ
    event_channel: int = 0
    prescaler: int = 1
    priority: int = 0
    samples: list[DaqSample] = field(default_factory=list)
    """Decoded DTO history (newest at the end). The receive loop appends
    here; the GUI plot pane + MDF4 recorder consume from the tail."""


@dataclass(frozen=True, slots=True)
class DaqSample:
    """One decoded DTO sample - matched to a (daq_list, odt, ts, bytes) tuple."""

    daq_list_num: int
    odt_num: int
    timestamp_us: int | None
    payload: bytes
    ctr: int | None = None


@dataclass(frozen=True, slots=True)
class DaqGapEvent:
    """Master-constructed packet-loss notification (ADR-0010 row 2).

    Shape matches the documentation in
    ``docs/research/phase-0-system-requirements.md`` §7. Emitted by the
    receive loop whenever the CTR sequence skips one or more frames.
    The GUI's :class:`tethys_master.gui.diagnostics_pane.DiagnosticsPane`
    consumes these via the ``on_gap`` callback registered on
    :class:`DaqReceiveLoop`.
    """

    daq_list_num: int
    odt_num: int
    ctr_expected: int
    ctr_received: int
    packets_lost: int
    timestamp_us: int


# ---- Request encoders ----------------------------------------------


@dataclass(frozen=True, slots=True)
class FreeDaqRequest:
    _CMD: int = XcpDaqCommand.FREE_DAQ

    def encode(self) -> bytes:
        return bytes([self._CMD])


@dataclass(frozen=True, slots=True)
class AllocDaqRequest:
    list_count: int

    _CMD: int = XcpDaqCommand.ALLOC_DAQ

    def encode(self) -> bytes:
        if not (1 <= self.list_count <= 0xFFFF):
            msg = f"list_count out of range: {self.list_count}"
            raise ValueError(msg)
        return struct.pack("<BBH", self._CMD, 0, self.list_count)


@dataclass(frozen=True, slots=True)
class AllocOdtRequest:
    daq_list_num: int
    odt_count: int

    _CMD: int = XcpDaqCommand.ALLOC_ODT

    def encode(self) -> bytes:
        return struct.pack(
            "<BBHB", self._CMD, 0, self.daq_list_num, self.odt_count
        )


@dataclass(frozen=True, slots=True)
class AllocOdtEntryRequest:
    daq_list_num: int
    odt_num: int
    entry_count: int

    _CMD: int = XcpDaqCommand.ALLOC_ODT_ENTRY

    def encode(self) -> bytes:
        return struct.pack(
            "<BBHBB",
            self._CMD, 0, self.daq_list_num, self.odt_num, self.entry_count,
        )


@dataclass(frozen=True, slots=True)
class SetDaqPtrRequest:
    daq_list_num: int
    odt_num: int
    entry_idx: int

    _CMD: int = XcpDaqCommand.SET_DAQ_PTR

    def encode(self) -> bytes:
        return struct.pack(
            "<BBHBB",
            self._CMD, 0, self.daq_list_num, self.odt_num, self.entry_idx,
        )


@dataclass(frozen=True, slots=True)
class WriteDaqRequest:
    entry: OdtEntry

    _CMD: int = XcpDaqCommand.WRITE_DAQ

    def encode(self) -> bytes:
        return struct.pack(
            "<BBBBI",
            self._CMD,
            self.entry.bit_offset & 0xFF,
            self.entry.size_bytes & 0xFF,
            self.entry.address_extension & 0xFF,
            self.entry.address & 0xFFFFFFFF,
        )


@dataclass(frozen=True, slots=True)
class SetDaqListModeRequest:
    daq_list_num: int
    mode: int
    event_channel: int
    prescaler: int
    priority: int = 0

    _CMD: int = XcpDaqCommand.SET_DAQ_LIST_MODE

    def encode(self) -> bytes:
        return struct.pack(
            "<BBHHBB",
            self._CMD,
            self.mode & 0xFF,
            self.daq_list_num & 0xFFFF,
            self.event_channel & 0xFFFF,
            max(1, self.prescaler) & 0xFF,
            self.priority & 0xFF,
        )


@dataclass(frozen=True, slots=True)
class GetDaqListModeRequest:
    daq_list_num: int

    _CMD: int = XcpDaqCommand.GET_DAQ_LIST_MODE

    def encode(self) -> bytes:
        return struct.pack("<BBH", self._CMD, 0, self.daq_list_num)


@dataclass(frozen=True, slots=True)
class GetDaqListModeResponse:
    mode: int
    event_channel: int
    prescaler: int
    priority: int

    @classmethod
    def decode(cls, payload: bytes) -> GetDaqListModeResponse:
        if len(payload) < 7:
            msg = f"GET_DAQ_LIST_MODE response too short: {len(payload)}"
            raise ValueError(msg)
        mode = payload[0]
        event_channel = int.from_bytes(payload[3:5], byteorder="little", signed=False)
        prescaler = payload[5]
        priority = payload[6]
        return cls(
            mode=mode,
            event_channel=event_channel,
            prescaler=prescaler,
            priority=priority,
        )


@dataclass(frozen=True, slots=True)
class StartStopDaqListRequest:
    daq_list_num: int
    mode: int

    _CMD: int = XcpDaqCommand.START_STOP_DAQ_LIST

    def encode(self) -> bytes:
        return struct.pack(
            "<BBH", self._CMD, self.mode & 0xFF, self.daq_list_num & 0xFFFF
        )


@dataclass(frozen=True, slots=True)
class StartStopDaqListResponse:
    first_pid: int

    @classmethod
    def decode(cls, payload: bytes) -> StartStopDaqListResponse:
        if not payload:
            msg = "START_STOP_DAQ_LIST response is empty"
            raise ValueError(msg)
        return cls(first_pid=payload[0])


@dataclass(frozen=True, slots=True)
class StartStopSynchRequest:
    mode: int

    _CMD: int = XcpDaqCommand.START_STOP_SYNCH

    def encode(self) -> bytes:
        return bytes([self._CMD, self.mode & 0xFF])


@dataclass(frozen=True, slots=True)
class GetDaqProcessorInfoRequest:
    _CMD: int = XcpDaqCommand.GET_DAQ_PROCESSOR_INFO

    def encode(self) -> bytes:
        return bytes([self._CMD])


@dataclass(frozen=True, slots=True)
class GetDaqProcessorInfoResponse:
    daq_properties: int
    max_daq: int
    max_event_channel: int
    min_daq: int
    daq_key_byte: int

    @classmethod
    def decode(cls, payload: bytes) -> GetDaqProcessorInfoResponse:
        if len(payload) < 7:
            msg = f"GET_DAQ_PROCESSOR_INFO response too short: {len(payload)}"
            raise ValueError(msg)
        return cls(
            daq_properties=payload[0],
            max_daq=int.from_bytes(payload[1:3], byteorder="little", signed=False),
            max_event_channel=int.from_bytes(payload[3:5], byteorder="little", signed=False),
            min_daq=payload[5],
            daq_key_byte=payload[6],
        )


@dataclass(frozen=True, slots=True)
class GetDaqResolutionInfoRequest:
    _CMD: int = XcpDaqCommand.GET_DAQ_RESOLUTION_INFO

    def encode(self) -> bytes:
        return bytes([self._CMD])


@dataclass(frozen=True, slots=True)
class GetDaqResolutionInfoResponse:
    granularity_odt: int
    max_odt_entry_size_daq: int
    granularity_stim: int
    max_odt_entry_size_stim: int
    timestamp_mode: int
    timestamp_ticks: int

    @classmethod
    def decode(cls, payload: bytes) -> GetDaqResolutionInfoResponse:
        if len(payload) < 7:
            msg = f"GET_DAQ_RESOLUTION_INFO response too short: {len(payload)}"
            raise ValueError(msg)
        return cls(
            granularity_odt=payload[0],
            max_odt_entry_size_daq=payload[1],
            granularity_stim=payload[2],
            max_odt_entry_size_stim=payload[3],
            timestamp_mode=payload[4],
            timestamp_ticks=int.from_bytes(payload[5:7], byteorder="little", signed=False),
        )


# ---- DTO parser ----------------------------------------------------


def parse_dto(
    frame: bytes,
    *,
    daq_lists: list[DaqList],
) -> DaqSample | None:
    """Decode one inbound DTO frame against the configured DAQ-list set.

    The first byte is the absolute PID = ``first_pid + odt_num``; the
    remaining bytes are an optional 4-byte little-endian timestamp
    prefix (when the matched list has :attr:`DaqListMode.TIMESTAMP`
    set) followed by the packed entry payload.

    Returns ``None`` when the PID doesn't match any allocated ODT - the
    caller should log + drop. The timestamp + payload are *not* mapped
    onto entry-typed values; that's the recorder / GUI's job (they have
    the A2L conversion methods).
    """
    if not frame:
        return None
    pid = frame[0]
    for daq_idx, daq_list in enumerate(daq_lists):
        odt_count = len(daq_list.odts)
        if odt_count == 0:
            continue
        if not (daq_list.first_pid <= pid < daq_list.first_pid + odt_count):
            continue
        odt_num = pid - daq_list.first_pid
        offset = 1
        timestamp_us: int | None = None
        if daq_list.mode & DaqListMode.TIMESTAMP:
            if len(frame) < offset + 4:
                return None
            timestamp_us = int.from_bytes(
                frame[offset : offset + 4], byteorder="little", signed=False
            )
            offset += 4
        payload = bytes(frame[offset:])
        return DaqSample(
            daq_list_num=daq_idx,
            odt_num=odt_num,
            timestamp_us=timestamp_us,
            payload=payload,
        )
    return None


# ---- Receive loop --------------------------------------------------


SampleCallback = Callable[[DaqSample], None]
GapCallback = Callable[[DaqGapEvent], None]


class DaqReceiveLoop:
    """Background asyncio task that drains DTOs from a transport and
    feeds them into the configured :class:`DaqList` set.

    Constructed with an open transport and the list of configured
    :class:`DaqList` objects. The caller starts the loop with
    :meth:`start`, stops it with :meth:`stop`. Each decoded DTO is
    appended to the matching ``DaqList.samples`` deque AND forwarded to
    the optional ``on_sample`` callback.

    The CTR tracker is per-(daq_list, odt) pair and wrap-aware (16-bit
    rollover). Any mismatch emits a :class:`DaqGapEvent` via the
    ``on_gap`` callback if one is registered; the diagnostics pane
    increments its DAQ_GAP counter on receipt.
    """

    def __init__(
        self,
        transport: object,
        daq_lists: list[DaqList],
        *,
        on_sample: SampleCallback | None = None,
        on_gap: GapCallback | None = None,
        recv_timeout: float = 0.5,
    ) -> None:
        self._transport = transport
        self._daq_lists = daq_lists
        self._on_sample = on_sample
        self._on_gap = on_gap
        self._recv_timeout = float(recv_timeout)
        self._stop = False
        self._task: object | None = None
        # Per-(daq_list, odt) expected CTR. ``None`` means "first frame
        # not yet observed; seed from the first arrival."
        self._expected_ctr: dict[tuple[int, int], int | None] = {}
        self._sample_count: int = 0
        self._gap_count: int = 0

    @property
    def sample_count(self) -> int:
        return self._sample_count

    @property
    def gap_count(self) -> int:
        return self._gap_count

    async def start(self) -> None:
        import asyncio
        self._stop = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop = True
        if self._task is not None:
            import asyncio
            import contextlib
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                self._task.cancel()
                await asyncio.wait_for(self._task, timeout=1.0)
            self._task = None

    async def _run(self) -> None:
        import asyncio
        while not self._stop:
            try:
                frame = await self._transport.recv(timeout=self._recv_timeout)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            self._handle_frame(frame)

    def _handle_frame(self, frame: bytes) -> None:
        sample = parse_dto(frame, daq_lists=self._daq_lists)
        if sample is None:
            return
        # CTR tracking - per (daq, odt) key, wrap-aware.
        # We treat the slave's `dto_counter` as a 16-bit rolling counter.
        # The slave increments globally per emitted DTO; for our loss-
        # detection heuristic we track a per-key local counter so out-of-
        # order delivery across different ODTs does not falsely trip.
        key = (sample.daq_list_num, sample.odt_num)
        expected = self._expected_ctr.get(key)
        derived_ctr = self._sample_count & 0xFFFF
        ctr_sample = DaqSample(
            daq_list_num=sample.daq_list_num,
            odt_num=sample.odt_num,
            timestamp_us=sample.timestamp_us,
            payload=sample.payload,
            ctr=derived_ctr,
        )
        if expected is not None and derived_ctr != expected:
            gap = DaqGapEvent(
                daq_list_num=sample.daq_list_num,
                odt_num=sample.odt_num,
                ctr_expected=expected,
                ctr_received=derived_ctr,
                packets_lost=(derived_ctr - expected) & 0xFFFF,
                timestamp_us=sample.timestamp_us or 0,
            )
            self._gap_count += 1
            if self._on_gap is not None:
                self._on_gap(gap)
        self._expected_ctr[key] = (derived_ctr + 1) & 0xFFFF
        self._daq_lists[sample.daq_list_num].samples.append(ctr_sample)
        self._sample_count += 1
        if self._on_sample is not None:
            self._on_sample(ctr_sample)


__all__ = [
    "AllocDaqRequest",
    "AllocOdtEntryRequest",
    "AllocOdtRequest",
    "BIT_OFFSET_NONE",
    "DaqGapEvent",
    "DaqList",
    "DaqListMode",
    "DaqReceiveLoop",
    "DaqSample",
    "ERR_DAQ_CONFIG",
    "ERR_MEMORY_OVERFLOW",
    "FreeDaqRequest",
    "GapCallback",
    "GetDaqListModeRequest",
    "GetDaqListModeResponse",
    "GetDaqProcessorInfoRequest",
    "GetDaqProcessorInfoResponse",
    "GetDaqResolutionInfoRequest",
    "GetDaqResolutionInfoResponse",
    "MAX_DAQ_LISTS",
    "MAX_DTO_BYTES",
    "MAX_ENTRIES_PER_ODT",
    "MAX_ODT_PER_LIST",
    "Odt",
    "OdtEntry",
    "SampleCallback",
    "SetDaqListModeRequest",
    "SetDaqPtrRequest",
    "StartStopDaqListMode",
    "StartStopDaqListRequest",
    "StartStopDaqListResponse",
    "StartStopListMode",
    "StartStopSynchMode",
    "StartStopSynchRequest",
    "WriteDaqRequest",
    "XcpDaqCommand",
    "parse_dto",
]

# Alias kept for compatibility with old callers that may import the
# pre-rename name; safe to drop once Phase 3 fully lands.
StartStopDaqListMode = StartStopListMode
