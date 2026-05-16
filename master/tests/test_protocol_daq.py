"""Unit tests for the master-side DAQ command frames + DTO parser.

Exercises every encoder against its byte-exact wire layout, then the
:class:`tethys_master.protocol.daq.parse_dto` helper end-to-end with
representative DTOs (no timestamp, with timestamp, multi-list set).

Cite: ASAM XCP 1.4 Part 2 §1.4 (DAQ command set + DTO layout)
"""

from __future__ import annotations

import struct

import pytest
from tethys_master.protocol.daq import (
    BIT_OFFSET_NONE,
    AllocDaqRequest,
    AllocOdtEntryRequest,
    AllocOdtRequest,
    DaqList,
    DaqListMode,
    FreeDaqRequest,
    GetDaqListModeResponse,
    GetDaqProcessorInfoResponse,
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
    XcpDaqCommand,
    parse_dto,
)


class TestEncoders:
    def test_free_daq_is_pid_only(self) -> None:
        assert FreeDaqRequest().encode() == bytes([XcpDaqCommand.FREE_DAQ])

    def test_alloc_daq_le16(self) -> None:
        wire = AllocDaqRequest(list_count=4).encode()
        assert wire == bytes([XcpDaqCommand.ALLOC_DAQ, 0, 0x04, 0x00])

    def test_alloc_daq_rejects_zero(self) -> None:
        with pytest.raises(ValueError):
            AllocDaqRequest(list_count=0).encode()

    def test_alloc_odt(self) -> None:
        wire = AllocOdtRequest(daq_list_num=1, odt_count=3).encode()
        assert wire == bytes(
            [XcpDaqCommand.ALLOC_ODT, 0, 0x01, 0x00, 0x03]
        )

    def test_alloc_odt_entry(self) -> None:
        wire = AllocOdtEntryRequest(daq_list_num=2, odt_num=1, entry_count=4).encode()
        assert wire == bytes(
            [XcpDaqCommand.ALLOC_ODT_ENTRY, 0, 0x02, 0x00, 0x01, 0x04]
        )

    def test_set_daq_ptr(self) -> None:
        wire = SetDaqPtrRequest(daq_list_num=0, odt_num=0, entry_idx=2).encode()
        assert wire == bytes(
            [XcpDaqCommand.SET_DAQ_PTR, 0, 0x00, 0x00, 0x00, 0x02]
        )

    def test_write_daq(self) -> None:
        entry = OdtEntry(address=0x20001000, size_bytes=4)
        wire = WriteDaqRequest(entry=entry).encode()
        assert wire[:4] == bytes(
            [XcpDaqCommand.WRITE_DAQ, BIT_OFFSET_NONE, 4, 0]
        )
        assert wire[4:8] == struct.pack("<I", 0x20001000)

    def test_set_daq_list_mode(self) -> None:
        wire = SetDaqListModeRequest(
            daq_list_num=1,
            mode=DaqListMode.TIMESTAMP,
            event_channel=7,
            prescaler=1,
            priority=0,
        ).encode()
        assert wire == bytes(
            [
                XcpDaqCommand.SET_DAQ_LIST_MODE,
                DaqListMode.TIMESTAMP,
                0x01, 0x00,
                0x07, 0x00,
                0x01, 0x00,
            ]
        )

    def test_start_stop_daq_list(self) -> None:
        wire = StartStopDaqListRequest(
            daq_list_num=2, mode=StartStopListMode.START
        ).encode()
        assert wire == bytes(
            [XcpDaqCommand.START_STOP_DAQ_LIST, StartStopListMode.START, 0x02, 0x00]
        )

    def test_start_stop_synch(self) -> None:
        wire = StartStopSynchRequest(mode=StartStopSynchMode.START_SELECTED).encode()
        assert wire == bytes(
            [XcpDaqCommand.START_STOP_SYNCH, StartStopSynchMode.START_SELECTED]
        )


class TestResponses:
    def test_start_stop_daq_list_response(self) -> None:
        resp = StartStopDaqListResponse.decode(bytes([0x05]))
        assert resp.first_pid == 0x05

    def test_get_daq_list_mode_response(self) -> None:
        body = bytes(
            [DaqListMode.TIMESTAMP, 0, 0, 0x07, 0x00, 0x02, 0x00]
        )
        resp = GetDaqListModeResponse.decode(body)
        assert resp.mode == DaqListMode.TIMESTAMP
        assert resp.event_channel == 7
        assert resp.prescaler == 2
        assert resp.priority == 0

    def test_get_daq_processor_info_response(self) -> None:
        body = bytes([0x41, 0x04, 0x00, 0xFF, 0xFF, 0x00, 0x00])
        resp = GetDaqProcessorInfoResponse.decode(body)
        assert resp.daq_properties == 0x41
        assert resp.max_daq == 4
        assert resp.max_event_channel == 0xFFFF
        assert resp.min_daq == 0

    def test_get_daq_resolution_info_response(self) -> None:
        body = bytes([0x01, 0xFF, 0x01, 0xFF, 0x34, 0x01, 0x00])
        resp = GetDaqResolutionInfoResponse.decode(body)
        assert resp.granularity_odt == 1
        assert resp.max_odt_entry_size_daq == 0xFF
        assert resp.timestamp_mode == 0x34
        assert resp.timestamp_ticks == 1

    def test_short_response_raises(self) -> None:
        with pytest.raises(ValueError):
            GetDaqListModeResponse.decode(bytes([0]))


class TestParseDto:
    def _setup_list(self, *, mode: DaqListMode = DaqListMode.DAQ) -> list[DaqList]:
        daq_list = DaqList(
            first_pid=0,
            mode=mode,
            event_channel=1,
            prescaler=1,
            odts=[
                Odt(entries=[OdtEntry(address=0, size_bytes=4)]),
                Odt(entries=[OdtEntry(address=4, size_bytes=2)]),
            ],
        )
        return [daq_list]

    def test_pid_0_no_timestamp(self) -> None:
        lists = self._setup_list()
        sample = parse_dto(bytes([0x00, 0x11, 0x22, 0x33, 0x44]), daq_lists=lists)
        assert sample is not None
        assert sample.daq_list_num == 0
        assert sample.odt_num == 0
        assert sample.timestamp_us is None
        assert sample.payload == bytes([0x11, 0x22, 0x33, 0x44])

    def test_pid_1_no_timestamp(self) -> None:
        lists = self._setup_list()
        sample = parse_dto(bytes([0x01, 0xAA, 0xBB]), daq_lists=lists)
        assert sample is not None
        assert sample.odt_num == 1
        assert sample.payload == bytes([0xAA, 0xBB])

    def test_timestamp_prefix_stripped(self) -> None:
        lists = self._setup_list(mode=DaqListMode.TIMESTAMP)
        frame = bytes([0x00]) + (0xDEADBEEF).to_bytes(4, "little") + bytes([1, 2, 3, 4])
        sample = parse_dto(frame, daq_lists=lists)
        assert sample is not None
        assert sample.timestamp_us == 0xDEADBEEF
        assert sample.payload == bytes([1, 2, 3, 4])

    def test_unknown_pid_returns_none(self) -> None:
        lists = self._setup_list()
        assert parse_dto(bytes([0x05, 0x00, 0x00]), daq_lists=lists) is None

    def test_empty_frame_returns_none(self) -> None:
        assert parse_dto(b"", daq_lists=[]) is None

    def test_multi_list_dispatch(self) -> None:
        daq_list_0 = DaqList(
            first_pid=0,
            event_channel=1,
            odts=[Odt(entries=[OdtEntry(address=0, size_bytes=2)])],
        )
        daq_list_1 = DaqList(
            first_pid=1,
            event_channel=2,
            odts=[
                Odt(entries=[OdtEntry(address=10, size_bytes=4)]),
                Odt(entries=[OdtEntry(address=20, size_bytes=2)]),
            ],
        )
        lists = [daq_list_0, daq_list_1]
        # PID = 1 -> daq_list_1 odt 0
        sample = parse_dto(bytes([0x01, 0xAA, 0xBB, 0xCC, 0xDD]), daq_lists=lists)
        assert sample is not None
        assert sample.daq_list_num == 1
        assert sample.odt_num == 0
        # PID = 2 -> daq_list_1 odt 1
        sample = parse_dto(bytes([0x02, 0xEE, 0xFF]), daq_lists=lists)
        assert sample is not None
        assert sample.daq_list_num == 1
        assert sample.odt_num == 1
