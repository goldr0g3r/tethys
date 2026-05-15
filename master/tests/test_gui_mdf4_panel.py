"""MDF4Panel tests — record / stop lifecycle + playback round-trip."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

from tethys_master.gui.mdf4_panel import MDF4Panel  # noqa: E402

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


@pytest.fixture
def panel(qtbot: QtBot) -> MDF4Panel:
    p = MDF4Panel()
    qtbot.addWidget(p)
    p.show()
    qtbot.waitExposed(p)
    return p


def test_initial_state_idle(panel: MDF4Panel) -> None:
    assert not panel.is_recording()
    assert panel.sample_count() == 0
    assert panel._record_btn.isEnabled()
    assert not panel._stop_btn.isEnabled()
    assert panel._status.text() == "Idle"


def test_start_recording_opens_file_and_emits_signal(
    qtbot: QtBot,
    panel: MDF4Panel,
    tmp_path: Path,
) -> None:
    out = tmp_path / "session.mf4"
    with qtbot.waitSignal(panel.record_started, timeout=1000) as blocker:
        panel.start_recording(out)
    assert blocker.args == [str(out)]
    assert panel.is_recording()
    assert out.exists()
    assert not panel._record_btn.isEnabled()
    assert panel._stop_btn.isEnabled()


def test_append_sample_buffers_into_file(
    panel: MDF4Panel,
    tmp_path: Path,
) -> None:
    out = tmp_path / "samples.mf4"
    panel.start_recording(out)
    panel.append_sample("engine_rpm", 0.0, 1000.0)
    panel.append_sample("engine_rpm", 0.001, 1010.0)
    panel.append_sample("coolant_temp", 0.0, 80.0)
    assert panel.sample_count() == 3


def test_stop_recording_flushes_and_emits(
    qtbot: QtBot,
    panel: MDF4Panel,
    tmp_path: Path,
) -> None:
    out = tmp_path / "session2.mf4"
    panel.start_recording(out)
    panel.append_sample("rpm", 0.0, 1.0)
    with qtbot.waitSignal(panel.record_stopped, timeout=1000) as blocker:
        panel.stop_recording()
    assert blocker.args[0] == str(out)
    assert blocker.args[1] == 1
    assert not panel.is_recording()
    # File should still exist + have at least the magic header.
    assert out.stat().st_size > 14


def test_append_sample_noop_when_not_recording(panel: MDF4Panel) -> None:
    panel.append_sample("rpm", 0.0, 1.0)
    assert panel.sample_count() == 0


def test_load_playback_returns_sample_count(
    qtbot: QtBot,
    panel: MDF4Panel,
    tmp_path: Path,
) -> None:
    rec_path = tmp_path / "round-trip.mf4"
    panel.start_recording(rec_path)
    for i in range(5):
        panel.append_sample("x", float(i) * 0.01, float(i))
    panel.stop_recording()

    play_panel = MDF4Panel()
    qtbot.addWidget(play_panel)
    with qtbot.waitSignal(play_panel.playback_loaded, timeout=1000):
        sample_count = play_panel.load_playback(rec_path)
    assert sample_count == 5


def test_load_playback_rejects_missing_file(panel: MDF4Panel, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        panel.load_playback(tmp_path / "nope.mf4")


def test_load_playback_rejects_wrong_magic(panel: MDF4Panel, tmp_path: Path) -> None:
    bad = tmp_path / "bad.mf4"
    bad.write_bytes(b"NOT_TETHYS_MDF4")
    with pytest.raises(ValueError, match="not a TETHYS MDF4 stub"):
        panel.load_playback(bad)


def test_starting_recording_twice_replaces_previous(
    panel: MDF4Panel,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.mf4"
    second = tmp_path / "second.mf4"
    panel.start_recording(first)
    panel.append_sample("a", 0.0, 1.0)
    panel.start_recording(second)
    # second start_recording should have closed first.
    assert panel.sample_count() == 0
    assert first.exists()
    assert second.exists()
