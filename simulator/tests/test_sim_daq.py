"""Simulator DAQ engine tests (Phase 3 PR-A).

Drive the SimDaqEngine through its wire-level CTO interface and verify
the resulting DTO packets match the C-side spec (XCP 1.4 §1.4.2).

Cite: ASAM XCP 1.4 Part 2 §1.4.2
Cite: ADR-0010 row 12 (loopback zero-loss budget)
"""

from __future__ import annotations

from tethys_master.protocol.daq import (
    AllocDaqRequest,
    AllocOdtEntryRequest,
    AllocOdtRequest,
    DtoPacket,
    FreeDaqRequest,
    GetDaqProcessorInfoRequest,
    GetDaqProcessorInfoResponse,
    OdtEntry,
    SetDaqListModeRequest,
    SetDaqPtrRequest,
    StartStopSynchMode,
    StartStopSynchRequest,
    WriteDaqRequest,
)
from tethys_master.protocol.frame import XcpError, XcpPacketId, parse_response
from tethys_sim.daq import SimDaqEngine
from tethys_sim.slave import XcpSimSlave, _ramp_memory


def _do_connect(slave: XcpSimSlave) -> None:
    response = slave.dispatch(bytes([0xFF, 0x00]))
    assert response is not None
    pid, _body = parse_response(response)
    assert pid == XcpPacketId.RES


def _send_ok(slave: XcpSimSlave, packet: bytes) -> bytes:
    response = slave.dispatch(packet)
    assert response is not None
    pid, body = parse_response(response)
    assert pid == XcpPacketId.RES, f"unexpected error: {response.hex()}"
    return body


def test_engine_resets_on_construction() -> None:
    engine = SimDaqEngine()
    assert engine.state.allocated_lists == 0
    assert engine.state.any_active is False


def test_alloc_daq_rejects_oversized() -> None:
    engine = SimDaqEngine()
    response = engine.dispatch_cto(AllocDaqRequest(list_count=999).encode())
    assert response is not None
    pid, body = parse_response(response)
    assert pid == XcpPacketId.ERR
    assert body[0] == 0x30


def test_full_setup_via_slave_dispatch() -> None:
    slave = XcpSimSlave()
    _do_connect(slave)
    _send_ok(slave, FreeDaqRequest().encode())
    _send_ok(slave, AllocDaqRequest(list_count=1).encode())
    _send_ok(slave, AllocOdtRequest(daq_list_number=0, odt_count=1).encode())
    _send_ok(slave, AllocOdtEntryRequest(daq_list_number=0, odt_number=0, entry_count=1).encode())
    _send_ok(slave, SetDaqPtrRequest(daq_list_number=0, odt_number=0, entry_number=0).encode())
    _send_ok(slave, WriteDaqRequest(entry=OdtEntry(address=0x10, length=4)).encode())
    _send_ok(slave, SetDaqListModeRequest(mode=0, daq_list_number=0, event_channel=0, prescaler=1).encode())
    _send_ok(slave, StartStopSynchRequest(mode=int(StartStopSynchMode.START_SELECTED)).encode())
    assert slave.daq.state.allocated_lists == 1
    assert slave.daq.state.lists[0].enabled is True


def test_fire_event_emits_dto_with_expected_bytes() -> None:
    slave = XcpSimSlave()
    _do_connect(slave)
    _send_ok(slave, FreeDaqRequest().encode())
    _send_ok(slave, AllocDaqRequest(list_count=1).encode())
    _send_ok(slave, AllocOdtRequest(daq_list_number=0, odt_count=1).encode())
    _send_ok(slave, AllocOdtEntryRequest(daq_list_number=0, odt_number=0, entry_count=1).encode())
    _send_ok(slave, SetDaqPtrRequest(daq_list_number=0, odt_number=0, entry_number=0).encode())
    _send_ok(slave, WriteDaqRequest(entry=OdtEntry(address=0x20, length=4)).encode())
    _send_ok(slave, SetDaqListModeRequest(mode=0, daq_list_number=0, event_channel=0, prescaler=1).encode())
    _send_ok(slave, StartStopSynchRequest(mode=int(StartStopSynchMode.START_SELECTED)).encode())

    dtos = slave.fire_event(0)
    assert len(dtos) == 1
    packet = DtoPacket.parse(dtos[0])
    assert packet.absolute_odt_number == 0
    assert packet.ctr == 0
    assert packet.payload == bytes([0x20, 0x21, 0x22, 0x23])


def test_fire_event_ctr_advances_and_wraps() -> None:
    slave = XcpSimSlave()
    _do_connect(slave)
    _send_ok(slave, AllocDaqRequest(list_count=1).encode())
    _send_ok(slave, AllocOdtRequest(daq_list_number=0, odt_count=1).encode())
    _send_ok(slave, AllocOdtEntryRequest(daq_list_number=0, odt_number=0, entry_count=1).encode())
    _send_ok(slave, SetDaqPtrRequest(daq_list_number=0, odt_number=0, entry_number=0).encode())
    _send_ok(slave, WriteDaqRequest(entry=OdtEntry(address=0, length=1)).encode())
    _send_ok(slave, SetDaqListModeRequest(mode=0, daq_list_number=0, event_channel=0, prescaler=1).encode())
    _send_ok(slave, StartStopSynchRequest(mode=int(StartStopSynchMode.START_SELECTED)).encode())

    for expected in range(0, 3):
        dtos = slave.fire_event(0)
        assert DtoPacket.parse(dtos[0]).ctr == expected

    for _ in range(253):
        slave.fire_event(0)
    assert DtoPacket.parse(slave.fire_event(0)[0]).ctr == 0


def test_fire_event_prescaler_throttles() -> None:
    slave = XcpSimSlave()
    _do_connect(slave)
    _send_ok(slave, AllocDaqRequest(list_count=1).encode())
    _send_ok(slave, AllocOdtRequest(daq_list_number=0, odt_count=1).encode())
    _send_ok(slave, AllocOdtEntryRequest(daq_list_number=0, odt_number=0, entry_count=1).encode())
    _send_ok(slave, SetDaqPtrRequest(daq_list_number=0, odt_number=0, entry_number=0).encode())
    _send_ok(slave, WriteDaqRequest(entry=OdtEntry(address=0, length=1)).encode())
    _send_ok(slave, SetDaqListModeRequest(mode=0, daq_list_number=0, event_channel=0, prescaler=3).encode())
    _send_ok(slave, StartStopSynchRequest(mode=int(StartStopSynchMode.START_SELECTED)).encode())

    assert slave.fire_event(0) == []
    assert slave.fire_event(0) == []
    dtos = slave.fire_event(0)
    assert len(dtos) == 1


def test_fire_event_emits_one_dto_per_odt() -> None:
    slave = XcpSimSlave()
    _do_connect(slave)
    _send_ok(slave, AllocDaqRequest(list_count=1).encode())
    _send_ok(slave, AllocOdtRequest(daq_list_number=0, odt_count=3).encode())
    for odt in range(3):
        _send_ok(slave, AllocOdtEntryRequest(daq_list_number=0, odt_number=odt, entry_count=1).encode())
        _send_ok(slave, SetDaqPtrRequest(daq_list_number=0, odt_number=odt, entry_number=0).encode())
        _send_ok(slave, WriteDaqRequest(entry=OdtEntry(address=0x10 * odt, length=2)).encode())
    _send_ok(slave, SetDaqListModeRequest(mode=0, daq_list_number=0, event_channel=0, prescaler=1).encode())
    _send_ok(slave, StartStopSynchRequest(mode=int(StartStopSynchMode.START_SELECTED)).encode())

    dtos = slave.fire_event(0)
    assert len(dtos) == 3
    assert [DtoPacket.parse(d).absolute_odt_number for d in dtos] == [0, 1, 2]


def test_fire_event_skipped_on_wrong_channel() -> None:
    slave = XcpSimSlave()
    _do_connect(slave)
    _send_ok(slave, AllocDaqRequest(list_count=1).encode())
    _send_ok(slave, AllocOdtRequest(daq_list_number=0, odt_count=1).encode())
    _send_ok(slave, AllocOdtEntryRequest(daq_list_number=0, odt_number=0, entry_count=1).encode())
    _send_ok(slave, SetDaqPtrRequest(daq_list_number=0, odt_number=0, entry_number=0).encode())
    _send_ok(slave, WriteDaqRequest(entry=OdtEntry(address=0, length=1)).encode())
    _send_ok(slave, SetDaqListModeRequest(mode=0, daq_list_number=0, event_channel=5, prescaler=1).encode())
    _send_ok(slave, StartStopSynchRequest(mode=int(StartStopSynchMode.START_SELECTED)).encode())

    assert slave.fire_event(0) == []
    assert len(slave.fire_event(5)) == 1


def test_get_daq_processor_info_response() -> None:
    slave = XcpSimSlave()
    _do_connect(slave)
    response = slave.dispatch(GetDaqProcessorInfoRequest().encode())
    assert response is not None
    pid, body = parse_response(response)
    assert pid == XcpPacketId.RES
    info = GetDaqProcessorInfoResponse.decode(body)
    assert info.daq_properties == 0x11
    assert info.max_daq > 0
    assert info.max_event_channel > 0


def test_daq_command_without_connect_returns_access_denied() -> None:
    slave = XcpSimSlave()
    response = slave.dispatch(FreeDaqRequest().encode())
    assert response is not None
    pid, body = parse_response(response)
    assert pid == XcpPacketId.ERR
    assert body[0] == XcpError.ERR_ACCESS_DENIED


def test_engine_emits_zero_payload_when_memory_misconfigured() -> None:
    engine = SimDaqEngine()
    engine.dispatch_cto(AllocDaqRequest(list_count=1).encode())
    engine.dispatch_cto(AllocOdtRequest(daq_list_number=0, odt_count=1).encode())
    engine.dispatch_cto(AllocOdtEntryRequest(daq_list_number=0, odt_number=0, entry_count=1).encode())
    engine.dispatch_cto(SetDaqPtrRequest(daq_list_number=0, odt_number=0, entry_number=0).encode())
    engine.dispatch_cto(WriteDaqRequest(entry=OdtEntry(address=99999, length=4)).encode())
    engine.dispatch_cto(SetDaqListModeRequest(mode=0, daq_list_number=0, event_channel=0, prescaler=1).encode())
    engine.dispatch_cto(StartStopSynchRequest(mode=int(StartStopSynchMode.START_SELECTED)).encode())
    dtos = engine.fire_event(0, bytes(_ramp_memory()))
    assert len(dtos) == 1
    assert DtoPacket.parse(dtos[0]).payload == b"\x00\x00\x00\x00"
