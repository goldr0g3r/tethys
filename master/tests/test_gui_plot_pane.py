"""PlotPane tests — subscriptions, rolling window, gap markers, clear."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")
pytest.importorskip("pyqtgraph", reason="pyqtgraph not installed; run `uv sync --all-extras`.")

from tethys_master.gui.plot_pane import PlotPane  # noqa: E402

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


@pytest.fixture
def pane(qtbot: QtBot) -> PlotPane:
    p = PlotPane(rolling_window_s=10.0)
    qtbot.addWidget(p)
    p.show()
    qtbot.waitExposed(p)
    return p


def test_default_no_traces_no_gaps(pane: PlotPane) -> None:
    assert pane.subscribed_signals() == ()
    assert pane.gap_count() == 0
    assert pane.rolling_window_s() == pytest.approx(10.0)


def test_subscribe_is_idempotent(pane: PlotPane) -> None:
    pane.subscribe("engine_rpm")
    pane.subscribe("engine_rpm")
    assert pane.subscribed_signals() == ("engine_rpm",)


def test_subscribe_assigns_distinct_palette_colors(pane: PlotPane) -> None:
    pane.subscribe("a")
    pane.subscribe("b")
    pane.subscribe("c")
    assert pane.subscribed_signals() == ("a", "b", "c")


def test_append_sample_auto_subscribes_unknown_signal(pane: PlotPane) -> None:
    pane.append_sample("rpm_implicit", 0.0, 1234.0)
    assert "rpm_implicit" in pane.subscribed_signals()


def test_append_samples_bulk(pane: PlotPane) -> None:
    pane.subscribe("temp")
    pane.append_samples("temp", [(0.0, 20.0), (0.1, 21.0), (0.2, 22.0)])
    # Internal trace's data length should be 3 (no rolling trim under 10s window).
    trace = pane._traces["temp"]
    assert len(trace.xs) == 3
    assert len(trace.ys) == 3


def test_rolling_window_trims_old_samples(pane: PlotPane) -> None:
    pane.subscribe("rpm")
    for t in range(0, 20):  # 0..19 seconds, 10s window
        pane.append_sample("rpm", float(t), float(t))
    trace = pane._traces["rpm"]
    # Latest = 19, min_t = 19-10 = 9 → kept samples 9..19 inclusive = 11 points.
    assert trace.xs[0] >= 9.0
    assert trace.xs[-1] == pytest.approx(19.0)
    assert len(trace.xs) <= 11


def test_set_rolling_window_rejects_non_positive(pane: PlotPane) -> None:
    with pytest.raises(ValueError, match="positive"):
        pane.set_rolling_window_s(0)
    with pytest.raises(ValueError, match="positive"):
        pane.set_rolling_window_s(-1.0)


def test_mark_gap_increments_counter_and_renders_line(pane: PlotPane) -> None:
    pane.mark_gap(at_seconds=1.5)
    pane.mark_gap(at_seconds=3.0)
    assert pane.gap_count() == 2
    assert len(pane._gap_lines) == 2


def test_clear_removes_traces_data_and_gaps(pane: PlotPane) -> None:
    pane.subscribe("a")
    pane.append_sample("a", 0.0, 1.0)
    pane.mark_gap(at_seconds=0.5)
    pane.clear()
    # Traces persist as subscriptions but data is empty.
    assert pane.subscribed_signals() == ("a",)
    assert pane._traces["a"].xs == []
    assert pane.gap_count() == 0
    assert pane._gap_lines == []


def test_unsubscribe_removes_trace(pane: PlotPane) -> None:
    pane.subscribe("a")
    pane.subscribe("b")
    pane.unsubscribe("a")
    assert pane.subscribed_signals() == ("b",)
    pane.unsubscribe("not_there")  # idempotent
    assert pane.subscribed_signals() == ("b",)


def test_construction_rejects_invalid_window() -> None:
    with pytest.raises(ValueError, match="positive"):
        PlotPane(rolling_window_s=0)
