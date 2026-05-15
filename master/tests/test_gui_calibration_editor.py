"""CalibrationEditor tests — model, limit checks, commit / discard signals."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

from PySide6.QtCore import Qt  # noqa: E402

from tethys_master.gui.calibration_editor import (  # noqa: E402
    CalibrationEditor,
    CalibrationModel,
)
from tethys_master.protocol.a2l import (  # noqa: E402
    Characteristic,
    CharacteristicType,
)

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


def _toy_characteristics() -> dict[str, Characteristic]:
    return {
        "fuel_offset": Characteristic(
            name="fuel_offset",
            long_identifier="Fuel injection offset (ms)",
            characteristic_type=CharacteristicType.VALUE,
            address=0x20002000,
            record_layout="RL_FLOAT",
            maxdiff=0.0,
            conversion="ms",
            lower_limit=-1.0,
            upper_limit=1.0,
        ),
        "boost_gain": Characteristic(
            name="boost_gain",
            long_identifier="Boost pressure gain",
            characteristic_type=CharacteristicType.VALUE,
            address=0x20002010,
            record_layout="RL_FLOAT",
            maxdiff=0.0,
            conversion="",
            lower_limit=0.5,
            upper_limit=2.0,
        ),
    }


@pytest.fixture
def editor(qtbot: QtBot) -> CalibrationEditor:
    e = CalibrationEditor()
    qtbot.addWidget(e)
    e.show()
    qtbot.waitExposed(e)
    e.set_characteristics(_toy_characteristics(), initial_values={"fuel_offset": 0.0, "boost_gain": 1.0})
    return e


def test_initial_state_no_edits_buttons_disabled(editor: CalibrationEditor) -> None:
    assert not editor.has_pending_edits()
    assert not editor.has_out_of_range_edits()
    assert not editor._commit_btn.isEnabled()
    assert not editor._discard_btn.isEnabled()


def test_model_renders_two_rows_sorted(editor: CalibrationEditor) -> None:
    model = editor.model()
    assert model.rowCount() == 2
    # Sorted alphabetically — boost_gain comes before fuel_offset.
    name_col_0 = model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole)
    name_col_1 = model.data(model.index(1, 0), Qt.ItemDataRole.DisplayRole)
    assert (name_col_0, name_col_1) == ("boost_gain", "fuel_offset")


def test_in_range_edit_enables_commit_and_emits_edits_changed(
    qtbot: QtBot,
    editor: CalibrationEditor,
) -> None:
    model = editor.model()
    value_index = model.index(0, 1)  # boost_gain value
    with qtbot.waitSignal(editor.edits_changed, timeout=1000):
        model.setData(value_index, 1.5, Qt.ItemDataRole.EditRole)
    assert editor.has_pending_edits()
    assert not editor.has_out_of_range_edits()
    assert editor._commit_btn.isEnabled()
    assert editor._discard_btn.isEnabled()


def test_out_of_range_edit_blocks_commit(
    qtbot: QtBot,
    editor: CalibrationEditor,
) -> None:
    model = editor.model()
    fuel_value_index = model.index(1, 1)  # fuel_offset value
    with qtbot.waitSignal(editor.edits_changed, timeout=1000):
        model.setData(fuel_value_index, 5.0, Qt.ItemDataRole.EditRole)  # upper limit 1.0
    assert editor.has_pending_edits()
    assert editor.has_out_of_range_edits()
    assert not editor._commit_btn.isEnabled()
    # background colour goes red on out-of-range value
    bg = model.data(fuel_value_index, Qt.ItemDataRole.BackgroundRole)
    assert bg is not None


def test_commit_emits_signal_and_clears_pending(
    qtbot: QtBot,
    editor: CalibrationEditor,
) -> None:
    model = editor.model()
    model.setData(model.index(0, 1), 1.25, Qt.ItemDataRole.EditRole)  # boost_gain
    model.setData(model.index(1, 1), 0.5, Qt.ItemDataRole.EditRole)  # fuel_offset

    with qtbot.waitSignal(editor.commit_requested, timeout=1000) as blocker:
        editor._commit_btn.click()
    edits = blocker.args[0]
    assert isinstance(edits, dict)
    assert edits == {"boost_gain": 1.25, "fuel_offset": 0.5}
    # After commit, pending is cleared and the buttons disable.
    assert not editor.has_pending_edits()
    assert not editor._commit_btn.isEnabled()


def test_discard_drops_pending_without_emitting_commit(
    qtbot: QtBot,
    editor: CalibrationEditor,
) -> None:
    model = editor.model()
    model.setData(model.index(0, 1), 1.75, Qt.ItemDataRole.EditRole)
    assert editor.has_pending_edits()

    # Discard should NOT emit commit_requested.
    with qtbot.assertNotEmitted(editor.commit_requested):
        editor._discard_btn.click()
    assert not editor.has_pending_edits()
    assert not editor._discard_btn.isEnabled()


def test_invalid_string_input_rejected(editor: CalibrationEditor) -> None:
    model = editor.model()
    ok = model.setData(model.index(0, 1), "not a number", Qt.ItemDataRole.EditRole)
    assert ok is False
    assert not editor.has_pending_edits()


def test_status_column_reflects_state(editor: CalibrationEditor) -> None:
    model = editor.model()
    # All OK initially
    status_initial = model.data(model.index(0, 5), Qt.ItemDataRole.DisplayRole)
    assert status_initial == "OK"
    # Make a pending in-range edit
    model.setData(model.index(0, 1), 1.5, Qt.ItemDataRole.EditRole)
    status_pending = model.data(model.index(0, 5), Qt.ItemDataRole.DisplayRole)
    assert status_pending == "PENDING"
    # Take it out of range
    model.setData(model.index(0, 1), 99.0, Qt.ItemDataRole.EditRole)
    status_bad = model.data(model.index(0, 5), Qt.ItemDataRole.DisplayRole)
    assert status_bad == "OUT OF RANGE"


def test_model_can_be_constructed_empty() -> None:
    model = CalibrationModel()
    assert model.rowCount() == 0
    assert model.columnCount() == 6
