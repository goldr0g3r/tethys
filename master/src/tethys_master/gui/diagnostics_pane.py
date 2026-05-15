"""Diagnostics pane — counters + transport event log + latency summary.

PR-B implementation: numeric counters for the two error classes the
protocol layer surfaces (CTR mismatches, DAQ_GAP events) plus a
capped-FIFO event log for transport-layer events and a text summary
(p50 / p99 / max) of recently-measured round-trip latencies.

Cite: parent plan §8 Phase 6 (diagnostics pane deliverable)
Cite: ADR-0010 (packet-loss tolerance budget — counter semantics)
Cite: docs/research/phase-0-system-requirements.md §4.2 (CTR field)
"""

from __future__ import annotations

import statistics
from collections import deque
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tethys_master.logging_setup import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


_EVENT_LOG_CAPACITY = 100
_LATENCY_WINDOW = 1_000


class DiagnosticsPane(QWidget):
    """Counters, transport event log, and latency summary.

    All mutators are thread-safe in the GIL sense (single increments /
    appends); callers from a DAQ thread should still wrap them in
    ``QMetaObject.invokeMethod`` if they need cross-thread delivery,
    but that wiring is PR-C scope.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("diagnostics_pane")

        self._ctr_mismatches = 0
        self._gap_events = 0
        self._latencies_ms: deque[float] = deque(maxlen=_LATENCY_WINDOW)

        # Counters group
        self._lbl_ctr = QLabel("0")
        self._lbl_ctr.setObjectName("diag_lbl_ctr")
        self._lbl_gaps = QLabel("0")
        self._lbl_gaps.setObjectName("diag_lbl_gaps")
        self._lbl_latency = QLabel("p50: —  p99: —  max: —")
        self._lbl_latency.setObjectName("diag_lbl_latency")

        counters_box = QGroupBox("Counters")
        counters_form = QFormLayout(counters_box)
        counters_form.addRow("CTR mismatches:", self._lbl_ctr)
        counters_form.addRow("DAQ_GAP events:", self._lbl_gaps)
        counters_form.addRow("Round-trip latency:", self._lbl_latency)

        # Event log
        self._event_log = QListWidget()
        self._event_log.setObjectName("diag_event_log")
        self._event_log.setAlternatingRowColors(True)
        self._event_log.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        # textInteractionFlags is not on QListWidget; configure word wrap instead.
        self._event_log.setWordWrap(True)
        log_box = QGroupBox(f"Transport event log (last {_EVENT_LOG_CAPACITY})")
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self._event_log)

        # Reset button
        self._reset_btn = QPushButton("&Reset diagnostics")
        self._reset_btn.setObjectName("diag_reset_btn")
        self._reset_btn.clicked.connect(self.reset)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._reset_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(counters_box)
        layout.addWidget(log_box, stretch=1)
        layout.addLayout(button_row)

    # ---- Mutators ----------------------------------------------------

    def increment_ctr_mismatch(self, by: int = 1) -> None:
        if by <= 0:
            msg = f"increment must be positive, got {by}"
            raise ValueError(msg)
        self._ctr_mismatches += by
        self._lbl_ctr.setText(str(self._ctr_mismatches))

    def increment_gap_event(self, by: int = 1) -> None:
        if by <= 0:
            msg = f"increment must be positive, got {by}"
            raise ValueError(msg)
        self._gap_events += by
        self._lbl_gaps.setText(str(self._gap_events))

    def append_event(self, message: str) -> None:
        """Append a transport-event message; oldest entries fall off at 100."""
        text = message.strip()
        if not text:
            return
        self._event_log.addItem(text)
        while self._event_log.count() > _EVENT_LOG_CAPACITY:
            taken = self._event_log.takeItem(0)
            del taken
        self._event_log.scrollToBottom()

    def record_latency_ms(self, latency_ms: float) -> None:
        if latency_ms < 0:
            msg = f"latency must be non-negative, got {latency_ms}"
            raise ValueError(msg)
        self._latencies_ms.append(float(latency_ms))
        self._refresh_latency_label()

    def reset(self) -> None:
        """Zero every counter and clear the event log + latency window."""
        self._ctr_mismatches = 0
        self._gap_events = 0
        self._latencies_ms.clear()
        self._lbl_ctr.setText("0")
        self._lbl_gaps.setText("0")
        self._lbl_latency.setText("p50: —  p99: —  max: —")
        self._event_log.clear()
        logger.info("diagnostics.reset")

    # ---- Accessors (test hooks) -------------------------------------

    def ctr_mismatches(self) -> int:
        return self._ctr_mismatches

    def gap_events(self) -> int:
        return self._gap_events

    def event_log_size(self) -> int:
        return self._event_log.count()

    def latency_samples(self) -> tuple[float, ...]:
        return tuple(self._latencies_ms)

    # ---- Internals ---------------------------------------------------

    def _refresh_latency_label(self) -> None:
        if not self._latencies_ms:
            self._lbl_latency.setText("p50: —  p99: —  max: —")
            return
        samples = sorted(self._latencies_ms)
        p50 = statistics.median(samples)
        # p99 — exact rank for small N, interpolated would be needless precision here.
        idx_p99 = max(0, int(round(0.99 * (len(samples) - 1))))
        p99 = samples[idx_p99]
        max_v = samples[-1]
        self._lbl_latency.setText(
            f"p50: {p50:.2f} ms  p99: {p99:.2f} ms  max: {max_v:.2f} ms"
        )

    # Keep Qt namespace warm so the test harness can introspect alignment etc.
    _ALIGNMENT_LEFT = Qt.AlignmentFlag.AlignLeft
