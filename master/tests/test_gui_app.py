"""Smoke tests for the QApplication bootstrap (Phase 6, PR-A).

These tests are skipped automatically when PySide6 is not installed
(``importorskip`` on the first ``PySide6.QtWidgets`` import).
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


def test_offscreen_platform_active() -> None:
    """conftest.py sets ``QT_QPA_PLATFORM=offscreen`` for headless CI."""
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"


def test_main_returns_pyside6_missing_exit_code_when_qt_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``main()`` exits cleanly with code 2 (and a hint) when PySide6 is absent.

    We simulate the missing-PySide6 path by stashing ``None`` into
    ``sys.modules`` for the QtWidgets sub-module — Python's import
    machinery treats that sentinel as "module deliberately unavailable"
    and raises ``ImportError`` on subsequent imports.
    """
    from tethys_master.gui import app as gui_app

    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", None)
    exit_code = gui_app.main(argv=["tethys-master-gui-test"])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "PySide6" in captured.err
    assert "tethys-master[gui]" in captured.err


def test_main_launches_and_exits_cleanly(qtbot: QtBot) -> None:
    """``main()`` returns 0 when the window is shown and the app is told to quit."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from tethys_master.gui.app import main as gui_main

    # Schedule a quit before invoking main so the event loop returns on its own.
    QTimer.singleShot(0, lambda: QApplication.instance().quit() if QApplication.instance() else None)
    exit_code = gui_main(argv=["tethys-master-gui-test"])
    assert exit_code == 0
    _ = qtbot  # keep the fixture so QApplication stays alive for sibling tests


def test_main_cli_no_arg_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    """``main_cli()`` delegates to :func:`main` without forwarding any args."""
    from tethys_master.gui import app as gui_app

    seen: dict[str, object] = {}

    def _fake_main(argv: list[str] | None = None) -> int:
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(gui_app, "main", _fake_main)
    monkeypatch.setattr(sys, "argv", ["tethys-master-gui", "--ignored"])

    assert gui_app.main_cli() == 0
    assert seen["argv"] is None
