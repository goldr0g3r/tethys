"""End-to-end DAQ emission test against the in-process posix-sim slave.

Drives the slave's DAQ configuration commands over UDP loopback, kicks
``tick_once()`` synchronously, and verifies the simulator emits DTOs
matching the configured ODT layout.

The full 60 s × 1 kHz acceptance test runs slave-side (Unity
``test_xcp_dto_emission.c::test_acceptance_1khz_quickrun_zero_loss``);
this test asserts the same wire behaviour from the *master* perspective
so the PR-3c receive-loop work has a known-good baseline to consume.

Cite: ASAM XCP 1.4 Part 2 §1.4 (DAQ configuration + DTO emission)
Cite: ADR-0010 row 12 (loopback zero-loss budget)
"""

from __future__ import annotations

import asyncio

import pytest
from tethys_master.transport.udp import UdpTransport

from tethys_sim.slave import (
    CMD_ALLOC_DAQ,
    CMD_ALLOC_ODT,
    CMD_ALLOC_ODT_ENTRY,
    CMD_FREE_DAQ,
    CMD_SET_DAQ_LIST_MODE,
    CMD_SET_DAQ_PTR,
    CMD_START_STOP_DAQ_LIST,
    CMD_WRITE_DAQ,
    DAQ_MODE_TIMESTAMP,
    DAQ_SS_START,
    XcpSimSlave,
)


async def _connect(client: UdpTransport) -> None:
    """Issue CONNECT so the slave registers our peer address + transitions."""
    await client.send(bytes([0xFF, 0x00]))
    response = await client.recv(timeout=1.0)
    assert response[0] == 0xFF, f"expected RES, got {response[:2].hex()}"


async def _send_cto(client: UdpTransport, payload: bytes) -> bytes:
    await client.send(payload)
    return await client.recv(timeout=1.0)


@pytest.mark.asyncio
async def test_alloc_daq_pipeline_responds_res() -> None:
    """ALLOC_DAQ -> ALLOC_ODT -> ALLOC_ODT_ENTRY -> SET_DAQ_PTR happy path."""
    sim = XcpSimSlave(host="127.0.0.1", port=0, daq_tick_hz=100.0)
    await sim.start()
    try:
        async with UdpTransport("127.0.0.1", sim.actual_port) as client:
            await _connect(client)
            resp = await _send_cto(client, bytes([CMD_ALLOC_DAQ, 0x00, 0x01, 0x00]))
            assert resp == bytes([0xFF])
            resp = await _send_cto(
                client, bytes([CMD_ALLOC_ODT, 0x00, 0x00, 0x00, 0x02])
            )
            assert resp == bytes([0xFF])
            resp = await _send_cto(
                client, bytes([CMD_ALLOC_ODT_ENTRY, 0x00, 0x00, 0x00, 0x00, 0x03])
            )
            assert resp == bytes([0xFF])
            resp = await _send_cto(
                client, bytes([CMD_SET_DAQ_PTR, 0x00, 0x00, 0x00, 0x00, 0x00])
            )
            assert resp == bytes([0xFF])
    finally:
        await sim.stop()


@pytest.mark.asyncio
async def test_tick_emits_dto_after_configuration() -> None:
    """Configure 1 list / 1 ODT / 1 entry, start, tick, read DTO from loopback."""
    sim = XcpSimSlave(host="127.0.0.1", port=0, daq_tick_hz=10.0)
    await sim.start()
    try:
        async with UdpTransport("127.0.0.1", sim.actual_port) as client:
            await _connect(client)
            await _send_cto(client, bytes([CMD_ALLOC_DAQ, 0x00, 0x01, 0x00]))
            await _send_cto(client, bytes([CMD_ALLOC_ODT, 0x00, 0x00, 0x00, 0x01]))
            await _send_cto(
                client, bytes([CMD_ALLOC_ODT_ENTRY, 0x00, 0x00, 0x00, 0x00, 0x01])
            )
            await _send_cto(
                client, bytes([CMD_SET_DAQ_PTR, 0x00, 0x00, 0x00, 0x00, 0x00])
            )
            await _send_cto(
                client,
                bytes([CMD_WRITE_DAQ, 0xFF, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]),
            )
            await _send_cto(
                client,
                bytes(
                    [
                        CMD_SET_DAQ_LIST_MODE,
                        DAQ_MODE_TIMESTAMP,
                        0x00, 0x00,
                        0x01, 0x00,
                        0x01, 0x00,
                    ]
                ),
            )
            resp = await _send_cto(
                client,
                bytes([CMD_START_STOP_DAQ_LIST, DAQ_SS_START, 0x00, 0x00]),
            )
            assert resp == bytes([0xFF, 0x00])

            sim.tick_once(event_channel=1, timestamp_us=0xAABBCCDD)
            dto = await client.recv(timeout=1.0)
            assert len(dto) == 9
            assert dto[0] == 0x00
            assert dto[1:5] == bytes.fromhex("DDCCBBAA")
            assert dto[5:9] == bytes([0x00, 0x01, 0x02, 0x03])
    finally:
        await sim.stop()


@pytest.mark.asyncio
async def test_free_daq_clears_engine() -> None:
    sim = XcpSimSlave(host="127.0.0.1", port=0, daq_tick_hz=10.0)
    await sim.start()
    try:
        async with UdpTransport("127.0.0.1", sim.actual_port) as client:
            await _connect(client)
            await _send_cto(client, bytes([CMD_ALLOC_DAQ, 0x00, 0x02, 0x00]))
            assert sim.state.daq.list_count == 2
            await _send_cto(client, bytes([CMD_FREE_DAQ]))
            assert sim.state.daq.list_count == 0
    finally:
        await sim.stop()


@pytest.mark.asyncio
async def test_alloc_overflow_returns_memory_overflow() -> None:
    sim = XcpSimSlave(host="127.0.0.1", port=0, daq_tick_hz=10.0)
    await sim.start()
    try:
        async with UdpTransport("127.0.0.1", sim.actual_port) as client:
            await _connect(client)
            resp = await _send_cto(
                client, bytes([CMD_ALLOC_DAQ, 0x00, 99, 0x00])
            )
            assert resp[0] == 0xFE
            assert resp[1] == 0x30
    finally:
        await sim.stop()


@pytest.mark.asyncio
async def test_emitter_loop_streams_at_target_rate() -> None:
    """The asyncio emitter task fires DTOs at the configured tick rate.

    Configure a list at 100 Hz, sleep 200 ms, count datagrams that
    arrived back. Expect roughly 20 frames - we accept >=10 to absorb
    scheduling jitter (the 1 kHz nightly soak in PR-3e is the exact-
    count acceptance criterion).
    """
    sim = XcpSimSlave(host="127.0.0.1", port=0, daq_tick_hz=100.0)
    await sim.start()
    try:
        async with UdpTransport("127.0.0.1", sim.actual_port) as client:
            await _connect(client)
            await _send_cto(client, bytes([CMD_ALLOC_DAQ, 0x00, 0x01, 0x00]))
            await _send_cto(client, bytes([CMD_ALLOC_ODT, 0x00, 0x00, 0x00, 0x01]))
            await _send_cto(
                client, bytes([CMD_ALLOC_ODT_ENTRY, 0x00, 0x00, 0x00, 0x00, 0x01])
            )
            await _send_cto(
                client, bytes([CMD_SET_DAQ_PTR, 0x00, 0x00, 0x00, 0x00, 0x00])
            )
            await _send_cto(
                client,
                bytes([CMD_WRITE_DAQ, 0xFF, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00]),
            )
            await _send_cto(
                client,
                bytes(
                    [
                        CMD_SET_DAQ_LIST_MODE,
                        0x00,
                        0x00, 0x00,
                        0x01, 0x00,
                        0x01, 0x00,
                    ]
                ),
            )
            await _send_cto(
                client,
                bytes([CMD_START_STOP_DAQ_LIST, DAQ_SS_START, 0x00, 0x00]),
            )
            await asyncio.sleep(0.2)
            received = 0
            while True:
                try:
                    dto = await client.recv(timeout=0.05)
                except asyncio.TimeoutError:
                    break
                assert len(dto) == 3
                assert dto[0] == 0x00
                received += 1
            assert received >= 10, f"expected >=10 DTOs, got {received}"
    finally:
        await sim.stop()
