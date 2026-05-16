"""End-to-end tests for the master XcpClient's DAQ command surface.

Drives the simulator (out-of-process not required - we instantiate it
in the same event loop) through the full ALLOC -> WRITE -> START
sequence, then runs the :class:`DaqReceiveLoop` against the live UDP
peer to assert decoded samples arrive in the expected ODTs.
"""

from __future__ import annotations

import asyncio

import pytest
from tethys_master.protocol.client import XcpClient
from tethys_master.protocol.daq import (
    BIT_OFFSET_NONE,
    DaqList,
    DaqListMode,
    DaqReceiveLoop,
    Odt,
    OdtEntry,
    StartStopListMode,
)
from tethys_master.transport.udp import UdpTransport

# Defer the simulator import behind a fixture so pytest-collect does
# not fail in environments where tethys_sim is not installed.
tethys_sim = pytest.importorskip(
    "tethys_sim.slave",
    reason="tethys-sim editable install required for end-to-end DAQ tests",
)


@pytest.fixture
async def sim() -> tethys_sim.XcpSimSlave:  # type: ignore[name-defined]
    slave = tethys_sim.XcpSimSlave(host="127.0.0.1", port=0, daq_tick_hz=200.0)
    await slave.start()
    yield slave
    await slave.stop()


@pytest.mark.asyncio
async def test_alloc_pipeline_via_client(sim: tethys_sim.XcpSimSlave) -> None:  # type: ignore[name-defined]
    async with XcpClient(
        UdpTransport("127.0.0.1", sim.actual_port), default_timeout_s=1.0
    ) as client:
        await client.connect()
        await client.alloc_daq(list_count=1)
        await client.alloc_odt(daq_list_num=0, odt_count=1)
        await client.alloc_odt_entry(daq_list_num=0, odt_num=0, entry_count=1)
        await client.set_daq_ptr(daq_list_num=0, odt_num=0, entry_idx=0)
        await client.write_daq(OdtEntry(address=0, size_bytes=4))
        await client.set_daq_list_mode(
            daq_list_num=0, mode=DaqListMode.DAQ, event_channel=1, prescaler=1
        )
        resp = await client.start_stop_daq_list(0, StartStopListMode.START)
        assert resp.first_pid == 0


@pytest.mark.asyncio
async def test_configure_daq_list_helper(sim: tethys_sim.XcpSimSlave) -> None:  # type: ignore[name-defined]
    async with XcpClient(
        UdpTransport("127.0.0.1", sim.actual_port), default_timeout_s=1.0
    ) as client:
        await client.connect()
        await client.alloc_daq(list_count=1)
        daq_list = await client.configure_daq_list(
            0,
            odts=[
                [
                    OdtEntry(address=0, size_bytes=4),
                    OdtEntry(address=4, size_bytes=2),
                ]
            ],
            mode=DaqListMode.TIMESTAMP,
            event_channel=1,
            prescaler=1,
        )
        assert len(daq_list.odts) == 1
        assert len(daq_list.odts[0].entries) == 2

        # Confirm via GET_DAQ_LIST_MODE that the slave saw what we sent.
        readback = await client.get_daq_list_mode(0)
        assert readback.event_channel == 1
        assert readback.mode == DaqListMode.TIMESTAMP


@pytest.mark.asyncio
async def test_receive_loop_decodes_dtos(sim: tethys_sim.XcpSimSlave) -> None:  # type: ignore[name-defined]
    async with XcpClient(
        UdpTransport("127.0.0.1", sim.actual_port), default_timeout_s=1.0
    ) as client:
        await client.connect()
        await client.alloc_daq(list_count=1)
        daq_list = await client.configure_daq_list(
            0,
            odts=[[OdtEntry(address=0, size_bytes=2)]],
            mode=DaqListMode.DAQ,
            event_channel=1,
            prescaler=1,
        )
        first_pid_resp = await client.start_stop_daq_list(0, StartStopListMode.START)
        daq_list.first_pid = first_pid_resp.first_pid

        receive_loop = DaqReceiveLoop(
            transport=client._transport,  # noqa: SLF001 - intentional
            daq_lists=[daq_list],
            recv_timeout=0.1,
        )
        await receive_loop.start()
        try:
            # Wait long enough for the 200 Hz emitter to produce ~20 frames.
            await asyncio.sleep(0.25)
        finally:
            await receive_loop.stop()
        # >=10 to absorb scheduling jitter; the exact-count nightly
        # acceptance test lives in PR-3e.
        assert receive_loop.sample_count >= 10, (
            f"expected >=10 samples, got {receive_loop.sample_count}"
        )
        # All decoded samples land in DaqList 0, ODT 0 with 2-byte payload.
        for sample in daq_list.samples[:10]:
            assert sample.daq_list_num == 0
            assert sample.odt_num == 0
            assert len(sample.payload) == 2


@pytest.mark.asyncio
async def test_processor_info_reports_static_max(sim: tethys_sim.XcpSimSlave) -> None:  # type: ignore[name-defined]
    async with XcpClient(
        UdpTransport("127.0.0.1", sim.actual_port), default_timeout_s=1.0
    ) as client:
        await client.connect()
        info = await client.get_daq_processor_info()
        # Simulator reports max_daq = SIM_DAQ_MAX_LISTS = 4.
        assert info.max_daq == 4
        assert info.max_event_channel == 0xFFFF
