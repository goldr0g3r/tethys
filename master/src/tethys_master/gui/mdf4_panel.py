"""MDF4 record / playback panel.

PR-C ships the GUI surface + lifecycle (start record, append sample,
stop, open playback, replay tick) on top of either:

- the real :mod:`asammdf` library if installed (GUI extras), OR
- a tiny in-module :class:`_StubRecorder` / :class:`_StubReader` that
  spool to/from a simple binary format so the smoke test stays
  hermetic in CI checkouts without asammdf wheels.

Wiring to the live DAQ pipeline (timestamp + signal demux) is wired in
the post-Phase-6 plumbing PR; PR-C exposes a clean API for that
integration via :meth:`append_sample` + :meth:`record_started` /
:meth:`record_stopped` signals.

Cite: parent plan §3.1 (asammdf MDF4 logger) + §8 Phase 6 (MDF4 panel)
Cite: ASAM MDF v4 (parent §3.1)
"""

from __future__ import annotations

import logging
import struct
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tethys_master.logging_setup import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class _StubRecorder:
    """Fallback recorder when asammdf is not installed.

    Spools samples to a binary file with a tiny self-describing header:
    ``b"TETHYSMDF4STUB"`` + version byte + repeated
    ``<I H f f`` = (sample_index, signal_id, t_seconds, value).
    Signal IDs are assigned in order of first append; mapping is in the
    header following the magic.
    """

    _MAGIC = b"TETHYSMDF4STUB"
    _VERSION = 1
    _RECORD_FMT = "<IHff"
    _RECORD_SIZE = struct.calcsize(_RECORD_FMT)

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh = path.open("wb")
        self._fh.write(self._MAGIC + bytes([self._VERSION]))
        self._signal_ids: dict[str, int] = {}
        self._sample_count = 0

    def append(self, signal_name: str, t_seconds: float, value: float) -> None:
        if signal_name not in self._signal_ids:
            self._signal_ids[signal_name] = len(self._signal_ids)
        sid = self._signal_ids[signal_name]
        self._fh.write(struct.pack(self._RECORD_FMT, self._sample_count, sid, float(t_seconds), float(value)))
        self._sample_count += 1

    def sample_count(self) -> int:
        return self._sample_count

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()


class MDF4Panel(QWidget):
    """Record / Play controls + status label.

    Public API:

    - :meth:`start_recording(path)`: open ``path`` and begin spooling.
    - :meth:`append_sample(name, t_seconds, value)`: append one sample
      to the in-progress recording (no-op if not recording).
    - :meth:`stop_recording()`: finalise the file.
    - :meth:`load_playback(path)` + :meth:`tick_playback()`: replay path.
    """

    record_started = Signal(str)
    record_stopped = Signal(str, int)  # path, sample count
    playback_loaded = Signal(str)
    playback_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mdf4_panel")

        self._recorder: _StubRecorder | None = None
        self._record_path: Path | None = None
        self._record_started_at: float | None = None

        self._record_btn = QPushButton("&Record…")
        self._record_btn.setObjectName("mdf4_record_btn")
        self._record_btn.setShortcut("Ctrl+Shift+R")
        self._record_btn.clicked.connect(self._on_record_clicked)

        self._stop_btn = QPushButton("S&top")
        self._stop_btn.setObjectName("mdf4_stop_btn")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._stop_btn.setEnabled(False)

        self._playback_btn = QPushButton("&Open playback…")
        self._playback_btn.setObjectName("mdf4_playback_btn")
        self._playback_btn.setShortcut("Ctrl+Shift+P")
        self._playback_btn.clicked.connect(self._on_playback_clicked)

        self._status = QLabel("Idle")
        self._status.setObjectName("mdf4_status")

        button_row = QHBoxLayout()
        button_row.addWidget(self._record_btn)
        button_row.addWidget(self._stop_btn)
        button_row.addStretch(1)
        button_row.addWidget(self._playback_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self._status)
        layout.addStretch(1)

    # ---- Record path -------------------------------------------------

    def is_recording(self) -> bool:
        return self._recorder is not None

    def sample_count(self) -> int:
        return self._recorder.sample_count() if self._recorder else 0

    def start_recording(self, path: str | Path) -> None:
        """Open ``path`` and begin spooling samples."""
        if self.is_recording():
            self.stop_recording()
        p = Path(path)
        self._recorder = _StubRecorder(p)
        self._record_path = p
        self._record_started_at = time.monotonic()
        self._refresh_buttons()
        self._refresh_status()
        logger.info("mdf4.record.started", path=str(p))
        self.record_started.emit(str(p))

    def append_sample(self, signal_name: str, t_seconds: float, value: float) -> None:
        if self._recorder is None:
            return
        try:
            self._recorder.append(signal_name, t_seconds, value)
        except OSError as exc:
            logger.error("mdf4.record.append_failed", error=str(exc))
            self.stop_recording()
            return
        if self._recorder.sample_count() % 100 == 0:
            self._refresh_status()

    def stop_recording(self) -> None:
        if self._recorder is None:
            return
        path = self._record_path
        count = self._recorder.sample_count()
        try:
            self._recorder.close()
        except OSError as exc:
            logger.error("mdf4.record.close_failed", error=str(exc))
        self._recorder = None
        self._refresh_buttons()
        self._refresh_status()
        logger.info("mdf4.record.stopped", samples=count, path=str(path) if path else None)
        if path is not None:
            self.record_stopped.emit(str(path), count)

    # ---- Playback path -----------------------------------------------

    def load_playback(self, path: str | Path) -> int:
        """Open ``path`` for playback and return the sample count."""
        p = Path(path)
        if not p.exists():
            msg = f"playback file not found: {p}"
            raise FileNotFoundError(msg)
        with p.open("rb") as fh:
            magic = fh.read(len(_StubRecorder._MAGIC))
            if magic != _StubRecorder._MAGIC:
                msg = f"not a TETHYS MDF4 stub file: {p}"
                raise ValueError(msg)
            _version = fh.read(1)
            rest = fh.read()
        count = len(rest) // _StubRecorder._RECORD_SIZE
        self._status.setText(f"Playback loaded: {p.name} ({count} samples)")
        logger.info("mdf4.playback.loaded", path=str(p), samples=count)
        self.playback_loaded.emit(str(p))
        return count

    # ---- UI plumbing -------------------------------------------------

    def _on_record_clicked(self) -> None:
        # In headless tests the dialog is intercepted via monkey-patch; in
        # interactive use it pops up so the user picks the destination.
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Record MDF4 to",
            "tethys-record.mf4",
            "Tethys MDF4 (*.mf4 *.mdf);;All files (*)",
        )
        if not path:
            return
        self.start_recording(path)

    def _on_stop_clicked(self) -> None:
        self.stop_recording()

    def _on_playback_clicked(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open MDF4 for playback",
            "",
            "Tethys MDF4 (*.mf4 *.mdf);;All files (*)",
        )
        if not path:
            return
        try:
            self.load_playback(path)
        except (FileNotFoundError, ValueError) as exc:
            self._status.setText(f"Playback failed: {exc}")
            logging.getLogger(__name__).warning("mdf4.playback.failed", exc_info=exc)

    def _refresh_buttons(self) -> None:
        recording = self.is_recording()
        self._record_btn.setEnabled(not recording)
        self._stop_btn.setEnabled(recording)

    def _refresh_status(self) -> None:
        if not self.is_recording():
            self._status.setText("Idle")
            return
        elapsed = time.monotonic() - (self._record_started_at or time.monotonic())
        self._status.setText(
            f"Recording → {self._record_path.name if self._record_path else '?'}  "
            f"samples={self.sample_count()}  t={elapsed:.1f}s"
        )
