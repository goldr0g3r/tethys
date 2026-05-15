"""A2LTreeView tests — loading, model shape, selection signals."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

# E402: pytest.importorskip must precede the PySide6 import (see header).
from PySide6.QtCore import Qt  # noqa: E402

from tethys_master.gui.a2l_tree import A2LTreeView, _StubA2LFile  # noqa: E402
from tethys_master.protocol.a2l import (  # noqa: E402
    A2LDatatype,
    A2LFile,
    Characteristic,
    CharacteristicType,
    Measurement,
)

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_DIR = _REPO_ROOT / "slave" / "tests" / "fixtures"


def _toy_a2l() -> A2LFile:
    return A2LFile(
        project_name="toy",
        project_long_identifier="Toy A2L for PR-B tests",
        module_name="ecu_a",
        module_long_identifier="",
        measurements={
            "engine_rpm": Measurement(
                name="engine_rpm",
                long_identifier="Engine RPM",
                datatype=A2LDatatype.FLOAT32_IEEE,
                conversion="rpm",
                resolution=1,
                accuracy=0.5,
                lower_limit=0.0,
                upper_limit=8000.0,
                address=0x20001000,
            ),
            "coolant_temp": Measurement(
                name="coolant_temp",
                long_identifier="Coolant temperature",
                datatype=A2LDatatype.SWORD,
                conversion="degC",
                resolution=1,
                accuracy=0.25,
                lower_limit=-40.0,
                upper_limit=125.0,
                address=0x20001010,
            ),
        },
        characteristics={
            "fuel_map": Characteristic(
                name="fuel_map",
                long_identifier="16x16 fuel map",
                characteristic_type=CharacteristicType.MAP,
                address=0x20002000,
                record_layout="RL_BYTE",
                maxdiff=0.0,
                conversion="ms",
                lower_limit=0.0,
                upper_limit=20.0,
            ),
        },
    )


@pytest.fixture
def tree(qtbot: QtBot) -> A2LTreeView:
    view = A2LTreeView()
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)
    return view


def test_default_construction_uses_stub(tree: A2LTreeView) -> None:
    assert isinstance(tree.current_a2l(), _StubA2LFile)
    assert tree.measurement_count() == 0
    assert tree.characteristic_count() == 0


def test_set_a2l_builds_two_root_nodes(tree: A2LTreeView) -> None:
    tree.set_a2l(_toy_a2l())
    model = tree.model()
    assert model is not None
    assert model.rowCount() == 2
    root_labels = [model.item(r, 0).text() for r in range(model.rowCount())]
    assert root_labels == ["MEASUREMENTS", "CHARACTERISTICS"]


def test_measurement_rows_sorted_and_formatted(tree: A2LTreeView) -> None:
    tree.set_a2l(_toy_a2l())
    model = tree.model()
    assert model is not None
    meas_root = model.item(0, 0)
    names = [meas_root.child(r, 0).text() for r in range(meas_root.rowCount())]
    assert names == sorted(names)  # alpha sort
    addresses = [meas_root.child(r, 2).text() for r in range(meas_root.rowCount())]
    assert all(addr.startswith("0x") for addr in addresses)
    types = [meas_root.child(r, 1).text() for r in range(meas_root.rowCount())]
    assert set(types) == {"FLOAT32_IEEE", "SWORD"}


def test_characteristic_row_renders_type_and_address(tree: A2LTreeView) -> None:
    tree.set_a2l(_toy_a2l())
    char_root = tree.model().item(1, 0)
    assert char_root.rowCount() == 1
    assert char_root.child(0, 0).text() == "fuel_map"
    assert char_root.child(0, 1).text() == "MAP"
    assert char_root.child(0, 2).text() == "0x20002000"


def test_selecting_measurement_emits_signal(qtbot: QtBot, tree: A2LTreeView) -> None:
    tree.set_a2l(_toy_a2l())
    meas_root = tree.model().item(0, 0)
    target_index = meas_root.child(0, 0).index()
    with qtbot.waitSignal(tree.measurement_selected, timeout=1000) as blocker:
        tree.clicked.emit(target_index)
    assert blocker.args == [meas_root.child(0, 0).text()]


def test_selecting_characteristic_emits_signal(qtbot: QtBot, tree: A2LTreeView) -> None:
    tree.set_a2l(_toy_a2l())
    char_root = tree.model().item(1, 0)
    target_index = char_root.child(0, 0).index()
    with qtbot.waitSignal(tree.characteristic_selected, timeout=1000) as blocker:
        tree.clicked.emit(target_index)
    assert blocker.args == ["fuel_map"]


@pytest.mark.skipif(
    not (_FIXTURE_DIR / "trivial.a2l").exists(),
    reason="A2L fixtures (PR #31) not present in this checkout",
)
def test_loads_real_fixture_from_disk(tree: A2LTreeView) -> None:
    tree.load(_FIXTURE_DIR / "trivial.a2l")
    a2l = tree.current_a2l()
    assert a2l.project_name  # fixture should at least have a PROJECT name
    # Sanity: tree model has the two roots and they reflect the file.
    model = tree.model()
    assert model.rowCount() == 2
    meas_root = model.item(0, 0)
    char_root = model.item(1, 0)
    assert meas_root.rowCount() == tree.measurement_count()
    assert char_root.rowCount() == tree.characteristic_count()


def test_alignment_flags_accessible(tree: A2LTreeView) -> None:
    """Touch a Qt enum to ensure the module is still importable post-test."""
    assert Qt.AlignmentFlag.AlignLeft.value >= 0
