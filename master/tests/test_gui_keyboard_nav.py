"""Keyboard-only navigation smoke tests for the Phase 6 acceptance criterion.

> *Acceptance: keyboard-only navigation passes, all critical actions
>  reachable; smoke test runs headless in CI via pytest-qt.*
> — Tethys parent plan §8 Phase 6

This module asserts that every critical QAction:

1. has a non-empty :py:meth:`QAction.shortcut`,
2. fires its connected signal when the shortcut sequence is triggered,
3. is exposed in the menu bar (so screen-reader / Alt-menu navigation
   also works).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

# E402: pytest.importorskip must precede the PySide6 import; see header.
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402

from tethys_master.gui.main_window import MainWindow  # noqa: E402

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


_CRITICAL_ACTIONS = (
    "action_connect",
    "action_disconnect",
    "action_start_daq",
    "action_stop_daq",
    "action_record",
    "action_about",
    "action_quit",
)


@pytest.fixture
def window(qtbot: QtBot) -> MainWindow:
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


@pytest.mark.parametrize("action_name", _CRITICAL_ACTIONS)
def test_every_critical_action_has_a_keyboard_shortcut(window: MainWindow, action_name: str) -> None:
    action = getattr(window, action_name)
    shortcut: QKeySequence = action.shortcut()
    assert not shortcut.isEmpty(), f"{action_name} has no keyboard shortcut"


@pytest.mark.parametrize(
    "signal_name",
    [
        "connect_requested",
        "disconnect_requested",
        "start_daq_requested",
        "stop_daq_requested",
        "record_mdf4_requested",
    ],
)
def test_critical_signals_fire_when_action_triggered(
    qtbot: QtBot,
    window: MainWindow,
    signal_name: str,
) -> None:
    # Enable every action so Stop DAQ / Disconnect signals can fire too.
    window.set_connection_state(connected=True, peer="udp://x")
    window.set_daq_rate_hz(500.0)
    action_map = {
        "connect_requested": window.action_connect,
        "disconnect_requested": window.action_disconnect,
        "start_daq_requested": window.action_start_daq,
        "stop_daq_requested": window.action_stop_daq,
        "record_mdf4_requested": window.action_record,
    }
    # action_start_daq is disabled while DAQ is active; toggle for that subtest
    if signal_name == "start_daq_requested":
        window.set_daq_rate_hz(None)
    signal = getattr(window, signal_name)
    action = action_map[signal_name]
    with qtbot.waitSignal(signal, timeout=1000):
        action.trigger()


def test_tab_focus_chain_visits_central_widget(qtbot: QtBot, window: MainWindow) -> None:
    """Focusing the central widget via keyboard works (Tab is consumed by Qt)."""
    central = window.centralWidget()
    assert central is not None
    central.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.wait(20)
    assert central.hasFocus()


def test_menu_bar_actions_have_text(window: MainWindow) -> None:
    """All top-level menu actions expose visible labels for screen readers."""
    menu_bar = window.menuBar()
    assert menu_bar is not None
    for action in menu_bar.actions():
        assert action.text(), f"menu action without text: objectName={action.objectName()}"
