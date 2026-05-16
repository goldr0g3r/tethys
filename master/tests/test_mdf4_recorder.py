"""MDF4 recorder round-trip tests (asammdf-driven third-party-reader proxy).

The parent §8 Phase 3 acceptance reads:

    "MDF4 file opens in third-party tool (Vector free MDF Viewer)"

asammdf is the reference open-source reader for MDF v4 and is
independent of the Vector Viewer code base; this test asserts that
every recorder-written .mf4 file re-opens in a *fresh* asammdf
instance with the same channel set + sample-count contract. The full
manual smoke test against the Vector Viewer is documented in
``docs/runbooks/demo-recording.md`` for the v1.0 release demo.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

asammdf = pytest.importorskip(
    "asammdf",
    reason="asammdf not installed (only ships with master[gui] extras)",
)

from tethys_master.protocol.daq import DaqSample
from tethys_master.protocol.mdf4_recorder import (
    Mdf4Recorder,
    Mdf4ReopenResult,
    SignalBinding,
)


def _make_sample(
    *, ts_us: int, value_f32: float, value_u16: int
) -> DaqSample:
    """One DAQ sample with a 4-byte float + 2-byte uint16 payload."""
    payload = struct.pack("<f", value_f32) + struct.pack("<H", value_u16)
    return DaqSample(
        daq_list_num=0,
        odt_num=0,
        timestamp_us=ts_us,
        payload=payload,
    )


def test_recorder_round_trip(tmp_path: Path) -> None:
    recorder = Mdf4Recorder()
    recorder.bind_signal(
        SignalBinding(
            name="engine_rpm",
            daq_list_num=0,
            odt_num=0,
            byte_offset=0,
            struct_format="<f",
            unit="rpm",
        )
    )
    recorder.bind_signal(
        SignalBinding(
            name="coolant_temp",
            daq_list_num=0,
            odt_num=0,
            byte_offset=4,
            struct_format="<H",
            unit="degC",
        )
    )
    recorder.start()
    # Feed 100 samples at 1 ms spacing.
    for i in range(100):
        recorder.feed_sample(
            _make_sample(ts_us=i * 1000, value_f32=float(i), value_u16=i)
        )
    recorder.stop()
    assert recorder.sample_count == 100

    mf4_path = recorder.save(tmp_path / "session.mf4")
    assert mf4_path.exists()
    assert mf4_path.stat().st_size > 0

    # Re-open in a fresh asammdf instance + assert channel set / counts.
    result: Mdf4ReopenResult = Mdf4Recorder.reopen(mf4_path)
    assert "engine_rpm" in result.channel_names
    assert "coolant_temp" in result.channel_names
    assert result.channels["engine_rpm"] == 100
    assert result.channels["coolant_temp"] == 100
    assert result.total_samples == 200


def test_recorder_ignores_unbound_samples(tmp_path: Path) -> None:
    recorder = Mdf4Recorder()
    recorder.bind_signal(
        SignalBinding(
            name="rpm",
            daq_list_num=0,
            odt_num=0,
            byte_offset=0,
            struct_format="<f",
        )
    )
    recorder.start()
    # Feed a sample with the right list/odt - counted.
    recorder.feed_sample(_make_sample(ts_us=0, value_f32=1.0, value_u16=0))
    # Feed a sample for a different ODT - sample_count increments but
    # the bound channel does not gain a row.
    recorder.feed_sample(
        DaqSample(
            daq_list_num=0,
            odt_num=1,
            timestamp_us=1000,
            payload=b"\x00\x00\x00\x00",
        )
    )
    recorder.stop()
    assert recorder.sample_count == 2
    path = recorder.save(tmp_path / "single.mf4")
    result = Mdf4Recorder.reopen(path)
    assert result.channels["rpm"] == 1


def test_recorder_save_without_bindings_raises(tmp_path: Path) -> None:
    recorder = Mdf4Recorder()
    with pytest.raises(ValueError, match="no channels bound"):
        recorder.save(tmp_path / "empty.mf4")


def test_recorder_start_clears_previous_session(tmp_path: Path) -> None:
    recorder = Mdf4Recorder()
    recorder.bind_signal(
        SignalBinding(
            name="rpm",
            daq_list_num=0,
            odt_num=0,
            byte_offset=0,
            struct_format="<f",
        )
    )
    recorder.start()
    recorder.feed_sample(_make_sample(ts_us=0, value_f32=1.0, value_u16=0))
    assert recorder.sample_count == 1
    recorder.stop()
    recorder.start()  # second session - must zero the buffers
    assert recorder.sample_count == 0
    recorder.feed_sample(_make_sample(ts_us=0, value_f32=2.0, value_u16=0))
    assert recorder.sample_count == 1
    path = recorder.save(tmp_path / "session2.mf4")
    result = Mdf4Recorder.reopen(path)
    assert result.channels["rpm"] == 1
