"""Connection wizard — 3-page transport / params / confirm flow.

Page 1 (:class:`_TransportPage`) picks one of the supported XCP
transports (UDP / TCP / SocketCAN / UART). Page 2
(:class:`_ParametersPage`) shows the form fields appropriate for that
transport via a stacked widget so we never display irrelevant rows.
Page 3 (:class:`_ConfirmPage`) shows the assembled target so the user
can review before hitting Finish.

PR-A scope: collect the user's choice and emit it as a ``dict`` on the
:attr:`ConnectionWizard.connect_requested` signal. PR-B / PR-C wire
that signal up to the real :class:`tethys_master.protocol.client.XcpClient`
backed by Worker B's transport implementations.

Cite: parent plan §3.1 (PySide6 connection wizard) + §8 Phase 6
Cite: ADR-0004 (transport abstraction layer)
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from tethys_master.logging_setup import get_logger

logger = get_logger(__name__)


class TransportKind(str, Enum):
    """XCP-supported transport choices for the GUI (parent §3.1)."""

    UDP = "udp"
    TCP = "tcp"
    CAN = "can"
    UART = "uart"


_TRANSPORT_LABELS: dict[TransportKind, str] = {
    TransportKind.UDP: "UDP (XCP on Ethernet)",
    TransportKind.TCP: "TCP (XCP on Ethernet)",
    TransportKind.CAN: "SocketCAN (Linux, CANable 2.0)",
    TransportKind.UART: "UART / SxI (serial)",
}

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 5555
_DEFAULT_CAN_IFACE = "can0"
_DEFAULT_UART_DEVICE = "/dev/ttyUSB0"
_DEFAULT_UART_BAUD = 115_200

_MIN_PORT = 1
_MAX_PORT = 65_535
_MIN_BAUD = 1_200
_MAX_BAUD = 4_000_000


class _TransportPage(QWizardPage):
    """Page 1 — combo-box selection of the XCP transport."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("wizard_page_transport")
        self.setTitle("Choose transport")
        self.setSubTitle("Select the XCP transport for this session.")

        self.combo = QComboBox()
        self.combo.setObjectName("wizard_transport_combo")
        for kind in TransportKind:
            self.combo.addItem(_TRANSPORT_LABELS[kind], kind.value)
        self.combo.setCurrentIndex(0)  # UDP default
        self.combo.setAccessibleName("Transport kind")

        form = QFormLayout(self)
        label = QLabel("&Transport:")
        label.setBuddy(self.combo)
        form.addRow(label, self.combo)

    def selected_transport(self) -> TransportKind:
        return TransportKind(self.combo.currentData())


class _ParametersPage(QWizardPage):
    """Page 2 — transport-specific connection parameters."""

    def __init__(self, transport_page: _TransportPage) -> None:
        super().__init__()
        self.setObjectName("wizard_page_parameters")
        self.setTitle("Connection parameters")
        self.setSubTitle("Configure the chosen transport.")
        self._transport_page = transport_page

        self.host_field = QLineEdit(_DEFAULT_HOST)
        self.host_field.setObjectName("wizard_param_host")
        self.port_field = QSpinBox()
        self.port_field.setObjectName("wizard_param_port")
        self.port_field.setRange(_MIN_PORT, _MAX_PORT)
        self.port_field.setValue(_DEFAULT_PORT)

        self.can_iface_field = QLineEdit(_DEFAULT_CAN_IFACE)
        self.can_iface_field.setObjectName("wizard_param_can_iface")

        self.uart_device_field = QLineEdit(_DEFAULT_UART_DEVICE)
        self.uart_device_field.setObjectName("wizard_param_uart_device")
        self.uart_baud_field = QSpinBox()
        self.uart_baud_field.setObjectName("wizard_param_uart_baud")
        self.uart_baud_field.setRange(_MIN_BAUD, _MAX_BAUD)
        self.uart_baud_field.setValue(_DEFAULT_UART_BAUD)

        self._panel_ip = self._build_panel_ip()
        self._panel_can = self._build_panel_can()
        self._panel_uart = self._build_panel_uart()

        self._stack = QStackedWidget()
        self._stack.setObjectName("wizard_param_stack")
        self._stack.addWidget(self._panel_ip)
        self._stack.addWidget(self._panel_can)
        self._stack.addWidget(self._panel_uart)

        layout = QVBoxLayout(self)
        layout.addWidget(self._stack)

    def _build_panel_ip(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("wizard_panel_ip")
        form = QFormLayout(panel)
        host_label = QLabel("&Host:")
        host_label.setBuddy(self.host_field)
        port_label = QLabel("&Port:")
        port_label.setBuddy(self.port_field)
        form.addRow(host_label, self.host_field)
        form.addRow(port_label, self.port_field)
        return panel

    def _build_panel_can(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("wizard_panel_can")
        form = QFormLayout(panel)
        iface_label = QLabel("&Interface:")
        iface_label.setBuddy(self.can_iface_field)
        form.addRow(iface_label, self.can_iface_field)
        return panel

    def _build_panel_uart(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("wizard_panel_uart")
        form = QFormLayout(panel)
        device_label = QLabel("&Device:")
        device_label.setBuddy(self.uart_device_field)
        baud_label = QLabel("&Baud:")
        baud_label.setBuddy(self.uart_baud_field)
        form.addRow(device_label, self.uart_device_field)
        form.addRow(baud_label, self.uart_baud_field)
        return panel

    def initializePage(self) -> None:
        kind = self._transport_page.selected_transport()
        if kind in (TransportKind.UDP, TransportKind.TCP):
            self._stack.setCurrentWidget(self._panel_ip)
        elif kind == TransportKind.CAN:
            self._stack.setCurrentWidget(self._panel_can)
        else:
            self._stack.setCurrentWidget(self._panel_uart)


class _ConfirmPage(QWizardPage):
    """Page 3 — read-only summary of the assembled target."""

    def __init__(
        self,
        transport_page: _TransportPage,
        params_page: _ParametersPage,
    ) -> None:
        super().__init__()
        self.setObjectName("wizard_page_confirm")
        self.setTitle("Confirm and connect")
        self.setSubTitle("Review the target; Finish triggers CONNECT.")
        self._transport_page = transport_page
        self._params_page = params_page

        self.summary = QLabel("")
        self.summary.setObjectName("wizard_summary")
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)

    def initializePage(self) -> None:
        target = _target_from(self._transport_page, self._params_page)
        rows = [f"<b>{key}</b>: {value}" for key, value in target.items()]
        self.summary.setText("<br/>".join(rows))


def _target_from(
    transport_page: _TransportPage,
    params_page: _ParametersPage,
) -> dict[str, Any]:
    kind = transport_page.selected_transport()
    if kind in (TransportKind.UDP, TransportKind.TCP):
        return {
            "transport": kind.value,
            "host": params_page.host_field.text().strip() or _DEFAULT_HOST,
            "port": int(params_page.port_field.value()),
        }
    if kind == TransportKind.CAN:
        return {
            "transport": kind.value,
            "interface": params_page.can_iface_field.text().strip() or _DEFAULT_CAN_IFACE,
        }
    return {
        "transport": kind.value,
        "device": params_page.uart_device_field.text().strip() or _DEFAULT_UART_DEVICE,
        "baud": int(params_page.uart_baud_field.value()),
    }


class ConnectionWizard(QWizard):
    """3-page transport / params / confirm wizard.

    Emits :attr:`connect_requested` with a dict describing the chosen
    target after the user presses Finish. The dict shape is one of:

    - ``{"transport": "udp" | "tcp", "host": str, "port": int}``
    - ``{"transport": "can", "interface": str}``
    - ``{"transport": "uart", "device": str, "baud": int}``
    """

    connect_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("connection_wizard")
        self.setWindowTitle("Tethys master — Connect")
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

        self.page_transport = _TransportPage()
        self.page_params = _ParametersPage(self.page_transport)
        self.page_confirm = _ConfirmPage(self.page_transport, self.page_params)

        self.addPage(self.page_transport)
        self.addPage(self.page_params)
        self.addPage(self.page_confirm)

        self.accepted.connect(self._on_accept)

    def selected_target(self) -> dict[str, Any]:
        """Return the assembled target dict for the current widget state."""
        return _target_from(self.page_transport, self.page_params)

    def _on_accept(self) -> None:
        target = self.selected_target()
        logger.info("gui.connection_wizard.accepted", **target)
        self.connect_requested.emit(target)
