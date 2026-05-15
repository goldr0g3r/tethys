"""Main window — menus, toolbar, status bar, central dock area.

PR-A scaffold: every menu entry, toolbar button, and status-bar field
has a keyboard shortcut so the Phase 6 acceptance criterion
("keyboard-only navigation passes, all critical actions reachable")
holds from the first commit. PR-B replaces the placeholder central
widget with the A2L tree + plot pane dock area; PR-C adds the
calibration editor + MDF4 record/playback panes.

State semantics (see :meth:`MainWindow.set_connection_state`,
:meth:`set_daq_rate_hz`, :meth:`set_gap_count`) are the contract the
PR-B / PR-C panels mutate when the underlying
:mod:`tethys_master.protocol.client` reports activity.

Cite: parent plan §8 Phase 6 (master GUI deliverables + acceptance)
Cite: ADR-0010 (packet-loss tolerance budget — gap counter semantics)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QToolBar,
    QWidget,
)

from tethys_master import __version__
from tethys_master.gui.a2l_tree import A2LTreeView
from tethys_master.gui.connection_wizard import ConnectionWizard
from tethys_master.gui.diagnostics_pane import DiagnosticsPane
from tethys_master.gui.plot_pane import PlotPane
from tethys_master.logging_setup import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Tethys master GUI top-level window.

    Signals expose every critical user action so PR-B / PR-C panels (and
    tests) can react without rummaging through Qt internals. Each signal
    is fired by the matching QAction.triggered slot; the action is
    reachable via menu, toolbar, AND keyboard shortcut to satisfy the
    Phase 6 acceptance criterion.
    """

    connect_requested = Signal()
    """Emitted when the user picks File / Connect, the toolbar button, or Ctrl+K."""

    disconnect_requested = Signal()
    """Emitted by the matching menu / toolbar action / Ctrl+Shift+K."""

    start_daq_requested = Signal()
    """Emitted by Start DAQ (Ctrl+R)."""

    stop_daq_requested = Signal()
    """Emitted by Stop DAQ (Ctrl+T)."""

    record_mdf4_requested = Signal()
    """Emitted by Record MDF4 (Ctrl+M)."""

    connection_target_chosen = Signal(dict)
    """Emitted with the wizard's selected target dict after Finish."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tethys_main_window")
        self.setWindowTitle(f"Tethys master {__version__} — XCP 1.4")
        self.resize(1200, 800)

        self._connected: bool = False
        self._daq_active: bool = False

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_status_bar()
        self._build_central_widget()
        self._populate_view_menu()
        self._update_actions_enabled()

        self.connect_requested.connect(self._open_connection_wizard)

    # ---- Construction helpers -----------------------------------------

    def _build_actions(self) -> None:
        # File. NOTE: ``QKeySequence.StandardKey.Quit`` resolves to an empty
        # sequence on Windows (where Alt+F4 is the OS-level window-close
        # idiom and Qt declines to bind a duplicate). We force ``Ctrl+Q``
        # so the keyboard-nav acceptance test passes on every matrix leg.
        self.action_quit = QAction("&Quit", self)
        self.action_quit.setObjectName("action_quit")
        self.action_quit.setShortcut("Ctrl+Q")
        self.action_quit.setStatusTip("Exit Tethys master (Ctrl+Q)")
        self.action_quit.triggered.connect(self.close)

        # Connect / Disconnect
        self.action_connect = QAction("&Connect…", self)
        self.action_connect.setObjectName("action_connect")
        self.action_connect.setShortcut("Ctrl+K")
        self.action_connect.setStatusTip("Open the connection wizard (Ctrl+K)")
        self.action_connect.triggered.connect(self.connect_requested)

        self.action_disconnect = QAction("&Disconnect", self)
        self.action_disconnect.setObjectName("action_disconnect")
        self.action_disconnect.setShortcut("Ctrl+Shift+K")
        self.action_disconnect.setStatusTip("Disconnect from the slave (Ctrl+Shift+K)")
        self.action_disconnect.triggered.connect(self.disconnect_requested)

        # DAQ
        self.action_start_daq = QAction("Start D&AQ", self)
        self.action_start_daq.setObjectName("action_start_daq")
        self.action_start_daq.setShortcut("Ctrl+R")
        self.action_start_daq.setStatusTip("Start data acquisition (Ctrl+R)")
        self.action_start_daq.triggered.connect(self.start_daq_requested)

        self.action_stop_daq = QAction("S&top DAQ", self)
        self.action_stop_daq.setObjectName("action_stop_daq")
        self.action_stop_daq.setShortcut("Ctrl+T")
        self.action_stop_daq.setStatusTip("Stop data acquisition (Ctrl+T)")
        self.action_stop_daq.triggered.connect(self.stop_daq_requested)

        # Record
        self.action_record = QAction("&Record MDF4…", self)
        self.action_record.setObjectName("action_record")
        self.action_record.setShortcut("Ctrl+M")
        self.action_record.setStatusTip("Record DAQ samples to an MDF4 file (Ctrl+M)")
        self.action_record.triggered.connect(self.record_mdf4_requested)

        # Help
        self.action_about = QAction("&About Tethys master", self)
        self.action_about.setObjectName("action_about")
        self.action_about.setShortcut("F1")
        self.action_about.setStatusTip("Show version and license info (F1)")
        self.action_about.triggered.connect(self._show_about)

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        assert menu_bar is not None

        file_menu = menu_bar.addMenu("&File")
        assert file_menu is not None
        file_menu.setObjectName("menu_file")
        file_menu.addAction(self.action_quit)

        conn_menu = menu_bar.addMenu("&Connect")
        assert conn_menu is not None
        conn_menu.setObjectName("menu_connect")
        conn_menu.addAction(self.action_connect)
        conn_menu.addAction(self.action_disconnect)
        conn_menu.addSeparator()
        conn_menu.addAction(self.action_start_daq)
        conn_menu.addAction(self.action_stop_daq)
        conn_menu.addAction(self.action_record)

        # View menu — populated with dock toggles in :meth:`_populate_view_menu`
        # after the central + dock widgets are constructed.
        view_menu = menu_bar.addMenu("&View")
        assert view_menu is not None
        view_menu.setObjectName("menu_view")
        self._view_menu = view_menu

        help_menu = menu_bar.addMenu("&Help")
        assert help_menu is not None
        help_menu.setObjectName("menu_help")
        help_menu.addAction(self.action_about)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Tethys", self)
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        toolbar.addAction(self.action_connect)
        toolbar.addAction(self.action_disconnect)
        toolbar.addSeparator()
        toolbar.addAction(self.action_start_daq)
        toolbar.addAction(self.action_stop_daq)
        toolbar.addSeparator()
        toolbar.addAction(self.action_record)
        self._toolbar = toolbar

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        bar.setObjectName("status_bar")
        self.setStatusBar(bar)

        self._status_connection = QLabel("Disconnected")
        self._status_connection.setObjectName("status_connection")
        self._status_daq_rate = QLabel("DAQ: idle")
        self._status_daq_rate.setObjectName("status_daq_rate")
        self._status_gap_count = QLabel("Gaps: 0")
        self._status_gap_count.setObjectName("status_gap_count")

        bar.addPermanentWidget(self._status_connection)
        bar.addPermanentWidget(self._status_daq_rate)
        bar.addPermanentWidget(self._status_gap_count)

    def _build_central_widget(self) -> None:
        # PR-B layout: real-time plot occupies the centre; A2L tree on the
        # left dock; diagnostics on the bottom dock. Every pane is
        # toggleable from the View menu via the dock's built-in
        # toggleViewAction() so keyboard-only navigation still passes.
        self._plot_pane = PlotPane(self)
        self._plot_pane.setObjectName("plot_pane")
        self.setCentralWidget(self._plot_pane)

        # A2L tree dock (left)
        self._a2l_tree = A2LTreeView(self)
        self._a2l_dock = QDockWidget("A2L tree", self)
        self._a2l_dock.setObjectName("a2l_dock")
        self._a2l_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._a2l_dock.setWidget(self._a2l_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._a2l_dock)

        # Diagnostics dock (bottom)
        self._diagnostics_pane = DiagnosticsPane(self)
        self._diagnostics_dock = QDockWidget("Diagnostics", self)
        self._diagnostics_dock.setObjectName("diagnostics_dock")
        self._diagnostics_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self._diagnostics_dock.setWidget(self._diagnostics_pane)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._diagnostics_dock)

        # Wire A2L → plot: subscribing a measurement adds a trace.
        self._a2l_tree.measurement_selected.connect(self._plot_pane.subscribe)

    def _populate_view_menu(self) -> None:
        """Hook dock-widget toggle actions into the View menu (PR-B)."""
        # ``QDockWidget.toggleViewAction()`` returns a checkable QAction that
        # shows / hides the dock and stays in sync if the user closes it via
        # the dock's title-bar X. Adding it to the View menu is the Qt-idiomatic
        # way to make every pane keyboard-reachable.
        a2l_toggle = self._a2l_dock.toggleViewAction()
        a2l_toggle.setText("&A2L tree")
        a2l_toggle.setObjectName("action_view_a2l")
        a2l_toggle.setShortcut("Ctrl+Shift+A")
        diag_toggle = self._diagnostics_dock.toggleViewAction()
        diag_toggle.setText("&Diagnostics")
        diag_toggle.setObjectName("action_view_diagnostics")
        diag_toggle.setShortcut("Ctrl+Shift+D")
        self._view_menu.addAction(a2l_toggle)
        self._view_menu.addAction(diag_toggle)

    # ---- Pane accessors (PR-C, tests) --------------------------------

    def a2l_tree(self) -> A2LTreeView:
        return self._a2l_tree

    def plot_pane(self) -> PlotPane:
        return self._plot_pane

    def diagnostics_pane(self) -> DiagnosticsPane:
        return self._diagnostics_pane

    def a2l_dock(self) -> QDockWidget:
        return self._a2l_dock

    def diagnostics_dock(self) -> QDockWidget:
        return self._diagnostics_dock

    # ---- State mutators (called by PR-B / PR-C panels and tests) ------

    def is_connected(self) -> bool:
        return self._connected

    def is_daq_active(self) -> bool:
        return self._daq_active

    def set_connection_state(self, *, connected: bool, peer: str = "") -> None:
        """Update the status bar + action enablement after a state change."""
        self._connected = connected
        if connected:
            text = f"Connected → {peer}" if peer else "Connected"
        else:
            text = "Disconnected"
            self._daq_active = False
            self._status_daq_rate.setText("DAQ: idle")
        self._status_connection.setText(text)
        self._update_actions_enabled()
        logger.info("gui.connection_state", connected=connected, peer=peer or None)

    def set_daq_rate_hz(self, rate_hz: float | None) -> None:
        """``None`` or ``0`` means idle; positive values format as ``DAQ: NN.N Hz``."""
        if rate_hz is not None and rate_hz > 0:
            self._daq_active = True
            self._status_daq_rate.setText(f"DAQ: {rate_hz:.1f} Hz")
        else:
            self._daq_active = False
            self._status_daq_rate.setText("DAQ: idle")
        self._update_actions_enabled()

    def set_gap_count(self, count: int) -> None:
        """Update the DAQ_GAP counter shown in the status bar (ADR-0010)."""
        if count < 0:
            msg = f"gap count must be non-negative, got {count}"
            raise ValueError(msg)
        self._status_gap_count.setText(f"Gaps: {count}")

    def record_daq_gap(self, at_seconds: float) -> None:
        """Record a DAQ_GAP event: draws a marker, bumps diagnostics + status."""
        self._plot_pane.mark_gap(at_seconds)
        self._diagnostics_pane.increment_gap_event()
        self.set_gap_count(self._diagnostics_pane.gap_events())

    def status_labels(self) -> tuple[QLabel, QLabel, QLabel]:
        """Test hook — returns (connection, daq_rate, gap_count) labels."""
        return self._status_connection, self._status_daq_rate, self._status_gap_count

    # ---- Action plumbing ----------------------------------------------

    def _update_actions_enabled(self) -> None:
        self.action_disconnect.setEnabled(self._connected)
        self.action_start_daq.setEnabled(self._connected and not self._daq_active)
        self.action_stop_daq.setEnabled(self._connected and self._daq_active)
        self.action_record.setEnabled(self._connected)

    def _open_connection_wizard(self) -> None:
        wizard = ConnectionWizard(self)
        wizard.setObjectName("connection_wizard_modal")
        wizard.connect_requested.connect(self._on_wizard_finished)
        wizard.open()  # non-blocking show; the dialog drives via signals
        self._active_wizard = wizard  # keep a reference so it is not GC'd

    def _on_wizard_finished(self, target: dict[str, object]) -> None:
        # PR-A: just update status + re-emit. PR-B/C wires the real CONNECT.
        transport = str(target.get("transport", "?"))
        if "host" in target:
            peer = f"{target['host']}:{target.get('port', '?')}"
        elif "interface" in target:
            peer = str(target["interface"])
        elif "device" in target:
            peer = f"{target['device']}@{target.get('baud', '?')}"
        else:
            peer = "?"
        self.set_connection_state(connected=True, peer=f"{transport}://{peer}")
        self.connection_target_chosen.emit(target)

    # ---- Dialogs ------------------------------------------------------

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Tethys master",
            f"<h3>Tethys master {__version__}</h3>"
            "<p>License-free XCP 1.4 calibration and measurement tool.</p>"
            "<p>MIT licensed. See <code>LICENSE</code> at the repo root.</p>"
            "<p>XCP primer: <code>docs/learn/xcp-101.md</code>.</p>",
        )
