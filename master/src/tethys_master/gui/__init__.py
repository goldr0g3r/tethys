"""Tethys master PySide6 GUI (parent plan §3.1, Phase 6).

The GUI runs on top of the existing protocol + transport stack
(:mod:`tethys_master.protocol`, :mod:`tethys_master.transport`); it does
NOT reimplement the wire protocol. PR-A (this file's introducing PR)
ships the application skeleton, main window, and connection wizard.
PR-B adds the A2L tree + plot pane + diagnostics pane; PR-C adds the
calibration editor + MDF4 record/playback + profile selector.

PySide6 and pyqtgraph are pulled in by the ``[gui]`` optional-dependency
group in ``pyproject.toml``; pip-installing ``tethys-master`` alone
keeps the headless CLI lightweight. The ``tethys-master gui`` CLI
subcommand and the ``tethys-master-gui`` direct entry point both error
out cleanly when PySide6 is missing.

Cite: parent plan §3.1 (PC master tool — PySide6 + pyqtgraph)
Cite: parent plan §8 Phase 6 (master GUI deliverables + acceptance)
Cite: ADR-0007 (Python master tool, MATLAB is consumer not driver)
Trace: docs/traceability.csv row TETHYS-DES-0050 (lands at PR-10)
"""

from __future__ import annotations

__all__: list[str] = []
