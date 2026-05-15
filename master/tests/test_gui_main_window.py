"""MainWindow tests: signals, status bar mutators, action enablement.

Drives every menu / toolbar action and every status mutator to satisfy
the Phase 6 acceptance criterion ("all critical actions reachable;
smoke test runs headless in CI via pytest-qt").
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

# E402: pytest.importorskip MUST run before any PySide6 import so the suite
# skips cleanly in headless-CLI-only checkouts. The `noqa` is intentional.
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolBar  # noqa: E402

from tethys_master.gui.main_window import MainWindow  # noqa: E402

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot: QtBot) -> MainWindow:
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_main_window_title_includes_version_and_xcp_marker(window: MainWindow) -> None:
    title = window.windowTitle()
    assert "Tethys master" in title
    assert "XCP 1.4" in title


def test_menus_present_and_named(window: MainWindow) -> None:
    menu_bar = window.menuBar()
    assert menu_bar is not None
    action_titles = [a.text().replace("&", "") for a in menu_bar.actions()]
    for expected in ("File", "Connect", "View", "Help"):
        assert expected in action_titles, f"menu bar missing {expected!r}; got {action_titles}"


def test_toolbar_contains_all_critical_actions(window: MainWindow) -> None:
    toolbars = window.findChildren(QToolBar)
    main_toolbar = next(tb for tb in toolbars if tb.objectName() == "main_toolbar")
    action_names = [a.objectName() for a in main_toolbar.actions() if a.objectName()]
    for expected in (
        "action_connect",
        "action_disconnect",
        "action_start_daq",
        "action_stop_daq",
        "action_record",
    ):
        assert expected in action_names, f"toolbar missing {expected!r}; got {action_names}"


def test_status_bar_initially_disconnected_idle_no_gaps(window: MainWindow) -> None:
    conn, daq, gaps = window.status_labels()
    assert conn.text() == "Disconnected"
    assert daq.text() == "DAQ: idle"
    assert gaps.text() == "Gaps: 0"


def test_disconnect_action_disabled_initially(window: MainWindow) -> None:
    assert not window.action_disconnect.isEnabled()
    assert not window.action_start_daq.isEnabled()
    assert not window.action_stop_daq.isEnabled()
    assert not window.action_record.isEnabled()
    # Connect is always enabled.
    assert window.action_connect.isEnabled()


def test_set_connection_state_updates_status_and_enables_actions(window: MainWindow) -> None:
    window.set_connection_state(connected=True, peer="udp://127.0.0.1:5555")
    conn, _, _ = window.status_labels()
    assert "udp://127.0.0.1:5555" in conn.text()
    assert window.is_connected()
    assert window.action_disconnect.isEnabled()
    assert window.action_start_daq.isEnabled()  # DAQ not yet active
    assert not window.action_stop_daq.isEnabled()
    assert window.action_record.isEnabled()


def test_set_connection_state_disconnect_resets_daq(window: MainWindow) -> None:
    window.set_connection_state(connected=True, peer="udp://x")
    window.set_daq_rate_hz(1000.0)
    assert window.is_daq_active()
    window.set_connection_state(connected=False)
    assert not window.is_connected()
    assert not window.is_daq_active()
    _, daq, _ = window.status_labels()
    assert daq.text() == "DAQ: idle"


def test_set_daq_rate_hz_formats_and_toggles_actions(window: MainWindow) -> None:
    window.set_connection_state(connected=True, peer="udp://x")
    window.set_daq_rate_hz(1000.0)
    _, daq, _ = window.status_labels()
    assert daq.text() == "DAQ: 1000.0 Hz"
    assert window.is_daq_active()
    assert not window.action_start_daq.isEnabled()
    assert window.action_stop_daq.isEnabled()
    window.set_daq_rate_hz(None)
    assert daq.text() == "DAQ: idle"
    assert not window.is_daq_active()


def test_set_gap_count_updates_label(window: MainWindow) -> None:
    window.set_gap_count(7)
    _, _, gaps = window.status_labels()
    assert gaps.text() == "Gaps: 7"


def test_set_gap_count_rejects_negative(window: MainWindow) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        window.set_gap_count(-1)


def test_connect_action_emits_signal_and_opens_wizard(qtbot: QtBot, window: MainWindow) -> None:
    with qtbot.waitSignal(window.connect_requested, timeout=1000):
        window.action_connect.trigger()
    wizard = getattr(window, "_active_wizard", None)
    assert wizard is not None, "Connect action did not stash an active wizard"
    assert wizard.objectName() == "connection_wizard_modal"
    wizard.close()


def test_disconnect_start_stop_record_actions_emit_signals(qtbot: QtBot, window: MainWindow) -> None:
    window.set_connection_state(connected=True, peer="udp://x")

    with qtbot.waitSignal(window.disconnect_requested, timeout=1000):
        window.action_disconnect.trigger()

    with qtbot.waitSignal(window.start_daq_requested, timeout=1000):
        window.action_start_daq.trigger()

    window.set_daq_rate_hz(500.0)
    with qtbot.waitSignal(window.stop_daq_requested, timeout=1000):
        window.action_stop_daq.trigger()

    with qtbot.waitSignal(window.record_mdf4_requested, timeout=1000):
        window.action_record.trigger()


def test_central_widget_is_plot_pane(window: MainWindow) -> None:
    """PR-B: the central widget is now the PlotPane (PR-A placeholder is gone)."""
    central = window.centralWidget()
    assert central is not None
    assert central.objectName() == "plot_pane"
    assert central is window.plot_pane()


def test_a2l_dock_and_diagnostics_dock_attached(window: MainWindow) -> None:
    """PR-B: A2L tree + diagnostics docks attach on construction."""
    from PySide6.QtCore import Qt

    a2l_dock = window.a2l_dock()
    diag_dock = window.diagnostics_dock()
    assert a2l_dock.objectName() == "a2l_dock"
    assert diag_dock.objectName() == "diagnostics_dock"
    assert window.dockWidgetArea(a2l_dock) == Qt.DockWidgetArea.LeftDockWidgetArea
    assert window.dockWidgetArea(diag_dock) == Qt.DockWidgetArea.BottomDockWidgetArea


def test_view_menu_lists_dock_toggles(window: MainWindow) -> None:
    """PR-B: the View menu exposes A2L tree + Diagnostics toggles."""
    menu_bar = window.menuBar()
    assert menu_bar is not None
    view_action = next(a for a in menu_bar.actions() if a.text().replace("&", "") == "View")
    view_menu = view_action.menu()
    assert view_menu is not None
    toggle_names = {a.objectName() for a in view_menu.actions() if a.objectName()}
    assert "action_view_a2l" in toggle_names
    assert "action_view_diagnostics" in toggle_names


def test_record_daq_gap_updates_pane_diagnostics_and_status(window: MainWindow) -> None:
    """PR-B: a DAQ_GAP event drives plot markers, diag counter, status counter together."""
    window.record_daq_gap(at_seconds=3.5)
    window.record_daq_gap(at_seconds=7.25)
    assert window.plot_pane().gap_count() == 2
    assert window.diagnostics_pane().gap_events() == 2
    _, _, gaps_label = window.status_labels()
    assert gaps_label.text() == "Gaps: 2"


def test_calibration_mdf4_profile_docks_attached(window: MainWindow) -> None:
    """PR-C: calibration + MDF4 + profile docks attach on construction."""
    from PySide6.QtCore import Qt

    cal_dock = window.calibration_dock()
    mdf_dock = window.mdf4_dock()
    prof_dock = window.profile_dock()
    assert cal_dock.objectName() == "calibration_dock"
    assert mdf_dock.objectName() == "mdf4_dock"
    assert prof_dock.objectName() == "profile_dock"
    # All three are right-area docks (tabified together).
    for dock in (cal_dock, mdf_dock, prof_dock):
        assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea


def test_view_menu_lists_all_five_dock_toggles(window: MainWindow) -> None:
    """PR-C: View menu carries A2L + Diagnostics + Calibration + MDF4 + Profile toggles."""
    menu_bar = window.menuBar()
    assert menu_bar is not None
    view_action = next(a for a in menu_bar.actions() if a.text().replace("&", "") == "View")
    view_menu = view_action.menu()
    assert view_menu is not None
    toggle_names = {a.objectName() for a in view_menu.actions() if a.objectName()}
    for expected in (
        "action_view_a2l",
        "action_view_diagnostics",
        "action_view_calibration",
        "action_view_mdf4",
        "action_view_profile",
    ):
        assert expected in toggle_names


def test_profile_change_updates_status_label(window: MainWindow) -> None:
    """PR-C: switching profile updates the status-bar Profile label."""
    from tethys_master.gui.profile_selector import Profile

    window.profile_selector().set_profile(Profile.SPACE)
    label = window._status_profile  # type: ignore[attr-defined]
    assert label.text() == "Profile: space"


def test_a2l_measurement_select_loads_characteristics_into_editor(
    window: MainWindow,
) -> None:
    """PR-C: clicking a measurement also seeds the calibration editor."""
    from tethys_master.protocol.a2l import A2LFile, Characteristic, CharacteristicType

    a2l = A2LFile(
        project_name="p",
        project_long_identifier="",
        module_name="m",
        module_long_identifier="",
        characteristics={
            "k": Characteristic(
                name="k",
                long_identifier="",
                characteristic_type=CharacteristicType.VALUE,
                address=0x100,
                record_layout="rl",
                maxdiff=0.0,
                conversion="",
                lower_limit=0.0,
                upper_limit=10.0,
            )
        },
    )
    window.a2l_tree().set_a2l(a2l)
    window._on_a2l_measurement_selected("ignored")  # type: ignore[attr-defined]
    assert window.calibration_editor().model().rowCount() == 1


def test_show_about_dialog_does_not_crash(qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    """``QMessageBox.about`` is modal; we intercept it to keep the test non-blocking."""
    from PySide6.QtWidgets import QMessageBox

    invocations: list[str] = []

    def _fake_about(*args: object, **kwargs: object) -> None:
        invocations.append("about-called")

    monkeypatch.setattr(QMessageBox, "about", staticmethod(_fake_about))
    window.action_about.trigger()
    qtbot.wait(50)
    assert invocations == ["about-called"]


def test_close_event_does_not_crash(qtbot: QtBot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    win.close()
    app = QApplication.instance()
    assert app is not None
    _ = Qt.Key.Key_F1  # touch Qt to ensure module is still importable
