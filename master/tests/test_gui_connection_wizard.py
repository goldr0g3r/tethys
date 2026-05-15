"""Connection wizard tests — pages, fields, target-dict shape."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

# E402: pytest.importorskip must precede the PySide6 import; see header.
from PySide6.QtWidgets import QWizard  # noqa: E402

from tethys_master.gui.connection_wizard import (  # noqa: E402
    ConnectionWizard,
    TransportKind,
)

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


@pytest.fixture
def wizard(qtbot: QtBot) -> ConnectionWizard:
    w = ConnectionWizard()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


def test_wizard_has_three_pages_in_order(wizard: ConnectionWizard) -> None:
    page_ids = wizard.pageIds()
    assert len(page_ids) == 3
    titles = [wizard.page(pid).title() for pid in page_ids]
    assert titles == [
        "Choose transport",
        "Connection parameters",
        "Confirm and connect",
    ]


def test_transport_combo_lists_all_four_kinds(wizard: ConnectionWizard) -> None:
    combo = wizard.page_transport.combo
    data_values = [combo.itemData(i) for i in range(combo.count())]
    assert data_values == [k.value for k in TransportKind]


def test_default_target_is_udp_localhost_5555(wizard: ConnectionWizard) -> None:
    target = wizard.selected_target()
    assert target == {"transport": "udp", "host": "127.0.0.1", "port": 5555}


def test_changing_transport_to_can_yields_interface_only_target(qtbot: QtBot, wizard: ConnectionWizard) -> None:
    can_index = next(
        i for i in range(wizard.page_transport.combo.count())
        if wizard.page_transport.combo.itemData(i) == TransportKind.CAN.value
    )
    wizard.page_transport.combo.setCurrentIndex(can_index)
    wizard.next()  # advance to parameters page (triggers initializePage)
    qtbot.wait(20)
    target = wizard.selected_target()
    assert target == {"transport": "can", "interface": "can0"}


def test_changing_transport_to_uart_yields_device_baud_target(qtbot: QtBot, wizard: ConnectionWizard) -> None:
    uart_index = next(
        i for i in range(wizard.page_transport.combo.count())
        if wizard.page_transport.combo.itemData(i) == TransportKind.UART.value
    )
    wizard.page_transport.combo.setCurrentIndex(uart_index)
    wizard.next()
    qtbot.wait(20)
    target = wizard.selected_target()
    assert target["transport"] == "uart"
    assert target["device"] == "/dev/ttyUSB0"
    assert target["baud"] == 115_200


def test_editing_host_and_port_reflected_in_target(qtbot: QtBot, wizard: ConnectionWizard) -> None:
    wizard.next()  # navigate to parameters page
    qtbot.wait(20)
    wizard.page_params.host_field.setText("10.0.0.5")
    wizard.page_params.port_field.setValue(54321)
    target = wizard.selected_target()
    assert target == {"transport": "udp", "host": "10.0.0.5", "port": 54321}


def test_port_field_clamps_to_valid_range(qtbot: QtBot, wizard: ConnectionWizard) -> None:
    wizard.next()
    qtbot.wait(20)
    wizard.page_params.port_field.setValue(0)  # below the minimum
    assert wizard.page_params.port_field.value() >= 1
    wizard.page_params.port_field.setValue(70_000)  # above the maximum
    assert wizard.page_params.port_field.value() <= 65_535


def test_empty_host_falls_back_to_default(qtbot: QtBot, wizard: ConnectionWizard) -> None:
    wizard.next()
    qtbot.wait(20)
    wizard.page_params.host_field.setText("   ")
    target = wizard.selected_target()
    assert target["host"] == "127.0.0.1"


def test_accept_emits_connect_requested_with_target(qtbot: QtBot, wizard: ConnectionWizard) -> None:
    with qtbot.waitSignal(wizard.connect_requested, timeout=1000) as blocker:
        wizard.accept()
    assert blocker.args is not None
    target = blocker.args[0]
    assert isinstance(target, dict)
    assert target["transport"] == "udp"


def test_confirm_page_summary_lists_target_fields(qtbot: QtBot, wizard: ConnectionWizard) -> None:
    wizard.next()  # to parameters
    qtbot.wait(20)
    wizard.next()  # to confirm
    qtbot.wait(20)
    summary_text = wizard.page_confirm.summary.text()
    assert "transport" in summary_text
    assert "udp" in summary_text
    assert "127.0.0.1" in summary_text
    assert "5555" in summary_text


def test_no_back_button_on_first_page(wizard: ConnectionWizard) -> None:
    """Per Qt option NoBackButtonOnStartPage — keyboard nav doesn't expose Back here."""
    assert wizard.testOption(QWizard.WizardOption.NoBackButtonOnStartPage)
