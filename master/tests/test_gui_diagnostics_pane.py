"""DiagnosticsPane tests — counters, event log, latency summary."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

from tethys_master.gui.diagnostics_pane import DiagnosticsPane  # noqa: E402

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


@pytest.fixture
def pane(qtbot: QtBot) -> DiagnosticsPane:
    p = DiagnosticsPane()
    qtbot.addWidget(p)
    p.show()
    qtbot.waitExposed(p)
    return p


def test_initial_counters_zero(pane: DiagnosticsPane) -> None:
    assert pane.ctr_mismatches() == 0
    assert pane.gap_events() == 0
    assert pane.event_log_size() == 0
    assert pane.latency_samples() == ()


def test_increment_ctr_mismatch_updates_label(pane: DiagnosticsPane) -> None:
    pane.increment_ctr_mismatch()
    pane.increment_ctr_mismatch(by=3)
    assert pane.ctr_mismatches() == 4
    assert pane._lbl_ctr.text() == "4"


def test_increment_gap_event_updates_label(pane: DiagnosticsPane) -> None:
    pane.increment_gap_event(by=2)
    assert pane.gap_events() == 2
    assert pane._lbl_gaps.text() == "2"


def test_increment_rejects_non_positive(pane: DiagnosticsPane) -> None:
    with pytest.raises(ValueError, match="positive"):
        pane.increment_ctr_mismatch(by=0)
    with pytest.raises(ValueError, match="positive"):
        pane.increment_gap_event(by=-1)


def test_event_log_caps_at_100(pane: DiagnosticsPane) -> None:
    for i in range(150):
        pane.append_event(f"transport event {i}")
    assert pane.event_log_size() == 100
    # Most recent items should still be present.
    last = pane._event_log.item(pane.event_log_size() - 1).text()
    assert last == "transport event 149"


def test_empty_event_is_ignored(pane: DiagnosticsPane) -> None:
    pane.append_event("")
    pane.append_event("   ")
    assert pane.event_log_size() == 0


def test_latency_summary_updates(pane: DiagnosticsPane) -> None:
    for latency in (0.5, 1.0, 1.5, 2.0, 50.0):
        pane.record_latency_ms(latency)
    text = pane._lbl_latency.text()
    assert "p50:" in text
    assert "p99:" in text
    assert "max: 50.00 ms" in text


def test_latency_rejects_negative(pane: DiagnosticsPane) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        pane.record_latency_ms(-0.1)


def test_reset_clears_everything(pane: DiagnosticsPane) -> None:
    pane.increment_ctr_mismatch()
    pane.increment_gap_event()
    pane.append_event("xyz")
    pane.record_latency_ms(10.0)
    pane.reset()
    assert pane.ctr_mismatches() == 0
    assert pane.gap_events() == 0
    assert pane.event_log_size() == 0
    assert pane.latency_samples() == ()
    assert "p50: —" in pane._lbl_latency.text()
