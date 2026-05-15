"""Real-time plot pane — pyqtgraph multi-trace with DAQ_GAP markers.

Each subscribed signal gets a line in a single :class:`pg.PlotWidget`.
The plot keeps a rolling window of ``rolling_window_s`` seconds
(default 60 s; configurable per-instance) and auto-downsamples for
display when a trace exceeds ``_DOWNSAMPLE_THRESHOLD`` points (delegated
to pyqtgraph's built-in downsampling).

DAQ_GAP markers (ADR-0010) are drawn as semi-transparent vertical lines
on the time axis so operators can visually correlate signal-value
discontinuities with the underlying packet loss.

Cite: parent plan §8 Phase 6 (real-time plot pane)
Cite: ADR-0010 (packet-loss tolerance budget — DAQ_GAP event)
Cite: pyqtgraph 0.13.7 PlotWidget API
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import cycle
from typing import TYPE_CHECKING

import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from tethys_master.logging_setup import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


_DEFAULT_ROLLING_WINDOW_S = 60.0
_DOWNSAMPLE_THRESHOLD = 10_000
_GAP_LINE_ALPHA = 90  # 0..255

# Colour-blind-friendly palette (Wong 2011) — assigned in order of subscribe().
_TRACE_PALETTE: tuple[str, ...] = (
    "#0072B2",  # blue
    "#E69F00",  # orange
    "#009E73",  # green
    "#CC79A7",  # pink
    "#56B4E9",  # sky blue
    "#D55E00",  # vermilion
    "#F0E442",  # yellow
    "#000000",  # black
)


class _Trace:
    """One signal trace inside the plot pane."""

    __slots__ = ("name", "color", "curve", "xs", "ys")

    def __init__(self, name: str, color: str, curve: pg.PlotDataItem) -> None:
        self.name = name
        self.color = color
        self.curve = curve
        self.xs: list[float] = []
        self.ys: list[float] = []

    def append(self, t: float, value: float) -> None:
        self.xs.append(float(t))
        self.ys.append(float(value))

    def trim(self, min_t: float) -> None:
        if not self.xs or self.xs[0] >= min_t:
            return
        i = 0
        for i, x in enumerate(self.xs):  # noqa: B007 - we want the index even when loop exits naturally
            if x >= min_t:
                break
        else:
            i = len(self.xs)
        del self.xs[:i]
        del self.ys[:i]

    def refresh(self) -> None:
        self.curve.setData(self.xs, self.ys)

    def clear(self) -> None:
        self.xs.clear()
        self.ys.clear()
        self.curve.setData([], [])


class PlotPane(QWidget):
    """Real-time multi-trace plot pane with DAQ_GAP visual markers.

    Typical usage:

    .. code-block:: python

        pane = PlotPane()
        pane.subscribe("engine_rpm")
        pane.subscribe("coolant_temp")
        for t, rpm, temp in samples:
            pane.append_sample("engine_rpm", t, rpm)
            pane.append_sample("coolant_temp", t, temp)
        pane.mark_gap(at=12.5)  # vertical line at 12.5 s
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        rolling_window_s: float = _DEFAULT_ROLLING_WINDOW_S,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("plot_pane")
        if rolling_window_s <= 0:
            msg = f"rolling_window_s must be positive, got {rolling_window_s}"
            raise ValueError(msg)
        self._rolling_window_s = float(rolling_window_s)

        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        pg.setConfigOption("antialias", True)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setObjectName("plot_widget")
        self._plot_widget.setLabel("bottom", "Time", units="s")
        self._plot_widget.setLabel("left", "Value")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._plot_widget.addLegend()
        self._plot_widget.getPlotItem().setDownsampling(auto=True, mode="peak")
        self._plot_widget.getPlotItem().setClipToView(True)
        self._plot_widget.enableAutoRange(axis="y")

        self._status = QLabel("0 traces, 0 gaps")
        self._status.setObjectName("plot_status")
        self._clear_btn = QPushButton("&Clear")
        self._clear_btn.setObjectName("plot_clear_btn")
        self._clear_btn.clicked.connect(self.clear)

        top_row = QHBoxLayout()
        top_row.addWidget(self._status)
        top_row.addStretch(1)
        top_row.addWidget(self._clear_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self._plot_widget)

        self._traces: dict[str, _Trace] = {}
        self._gaps: list[float] = []
        self._gap_lines: list[pg.InfiniteLine] = []
        self._color_iter = cycle(_TRACE_PALETTE)

    # ---- Configuration ----------------------------------------------

    def rolling_window_s(self) -> float:
        return self._rolling_window_s

    def set_rolling_window_s(self, seconds: float) -> None:
        if seconds <= 0:
            msg = f"rolling_window_s must be positive, got {seconds}"
            raise ValueError(msg)
        self._rolling_window_s = float(seconds)
        self._enforce_window()

    # ---- Subscriptions ----------------------------------------------

    def subscribe(self, signal_name: str) -> None:
        """Register ``signal_name`` as a trace. Idempotent."""
        if signal_name in self._traces:
            return
        color = next(self._color_iter)
        pen = pg.mkPen(color=QColor(color), width=2)
        curve = self._plot_widget.plot(pen=pen, name=signal_name)
        self._traces[signal_name] = _Trace(signal_name, color, curve)
        self._refresh_status()
        logger.info("plot.subscribed", signal=signal_name, color=color)

    def unsubscribe(self, signal_name: str) -> None:
        trace = self._traces.pop(signal_name, None)
        if trace is None:
            return
        self._plot_widget.removeItem(trace.curve)
        self._refresh_status()
        logger.info("plot.unsubscribed", signal=signal_name)

    def subscribed_signals(self) -> tuple[str, ...]:
        return tuple(self._traces.keys())

    # ---- Data ingest -------------------------------------------------

    def append_sample(self, signal_name: str, t_seconds: float, value: float) -> None:
        """Append one ``(t, value)`` sample to ``signal_name``'s trace.

        Calls :meth:`subscribe` lazily if the trace doesn't exist so
        callers can ingest data before declaring the signal layout.
        """
        if signal_name not in self._traces:
            self.subscribe(signal_name)
        self._traces[signal_name].append(t_seconds, value)
        self._enforce_window()
        self._traces[signal_name].refresh()

    def append_samples(
        self,
        signal_name: str,
        samples: Iterable[tuple[float, float]],
    ) -> None:
        """Bulk append; refreshes the trace once at the end."""
        if signal_name not in self._traces:
            self.subscribe(signal_name)
        trace = self._traces[signal_name]
        for t, v in samples:
            trace.append(t, v)
        self._enforce_window()
        trace.refresh()

    # ---- Gap markers -------------------------------------------------

    def mark_gap(self, at_seconds: float) -> None:
        """Draw a vertical marker at ``at_seconds`` representing a DAQ_GAP."""
        self._gaps.append(float(at_seconds))
        pen = pg.mkPen(color=QColor(204, 102, 0, _GAP_LINE_ALPHA), width=2, style=Qt.PenStyle.DashLine)
        line = pg.InfiniteLine(pos=at_seconds, angle=90, pen=pen)
        self._plot_widget.addItem(line)
        self._gap_lines.append(line)
        self._refresh_status()
        logger.info("plot.gap_marked", at=at_seconds, total_gaps=len(self._gaps))

    def gap_count(self) -> int:
        return len(self._gaps)

    # ---- Lifecycle ---------------------------------------------------

    def clear(self) -> None:
        """Drop every trace's data and every gap marker."""
        for trace in self._traces.values():
            trace.clear()
        for line in self._gap_lines:
            self._plot_widget.removeItem(line)
        self._gap_lines.clear()
        self._gaps.clear()
        self._refresh_status()
        logger.info("plot.cleared")

    # ---- Internals ---------------------------------------------------

    def _enforce_window(self) -> None:
        if not self._traces:
            return
        latest = max((t.xs[-1] for t in self._traces.values() if t.xs), default=0.0)
        min_t = latest - self._rolling_window_s
        if min_t <= 0:
            return
        for trace in self._traces.values():
            trace.trim(min_t)

    def _refresh_status(self) -> None:
        self._status.setText(f"{len(self._traces)} traces, {len(self._gaps)} gaps")
