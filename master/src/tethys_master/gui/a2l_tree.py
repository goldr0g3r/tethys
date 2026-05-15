"""A2L tree view — MEASUREMENT / CHARACTERISTIC browser.

Wraps an :class:`tethys_master.protocol.a2l.A2LFile` (Worker A's
BSD-3-style facade, landed in PR #38) in a Qt model + tree view. The
tree has two top-level nodes (MEASUREMENTS, CHARACTERISTICS); each
child carries the name, type, and address in three columns.

When :class:`tethys_master.protocol.a2l` is unavailable (e.g. in a
checkout that predates PR #38) a tiny :class:`_StubA2LFile` is used so
the GUI still starts; the stub returns an empty model.

Selection: clicking a measurement / characteristic emits
:attr:`A2LTreeView.measurement_selected` or
:attr:`A2LTreeView.characteristic_selected` with the symbol name so the
plot pane (PR-B) and the calibration editor (PR-C) can subscribe.

Cite: parent plan §8 Phase 6 (A2L tree view deliverable)
Cite: ASAM MCD-2 MC v1.7 §4.4.10 CHARACTERISTIC + §4.4.18 MEASUREMENT
Cite: ADR-0007 (Python master tool — Sauci/pya2l-style facade)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTreeView, QWidget

from tethys_master.logging_setup import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class _A2LMeasurementLike(Protocol):
    """Structural subset of :class:`tethys_master.protocol.a2l.Measurement` we need."""

    name: str
    long_identifier: str
    address: int

    @property
    def datatype(self) -> Any: ...


class _A2LCharacteristicLike(Protocol):
    """Structural subset of :class:`tethys_master.protocol.a2l.Characteristic`."""

    name: str
    long_identifier: str
    address: int

    @property
    def characteristic_type(self) -> Any: ...


class _A2LFileLike(Protocol):
    """Structural subset of :class:`tethys_master.protocol.a2l.A2LFile`."""

    project_name: str
    module_name: str
    measurements: dict[str, _A2LMeasurementLike]
    characteristics: dict[str, _A2LCharacteristicLike]


@dataclass(slots=True)
class _StubA2LFile:
    """Fallback used when :mod:`tethys_master.protocol.a2l` is not importable.

    Carries the same minimal surface the tree view consumes so the GUI
    keeps loading in dev environments that predate Worker A's PR #38.
    """

    project_name: str = "(no A2L loaded)"
    module_name: str = ""
    measurements: dict[str, _A2LMeasurementLike] = field(default_factory=dict)
    characteristics: dict[str, _A2LCharacteristicLike] = field(default_factory=dict)


def _load_a2l(path: str | Path) -> _A2LFileLike:
    """Load an A2L file via Worker A's facade or fall back to the stub.

    The stub path is taken only on ``ImportError``; any other parse error
    propagates so the GUI surfaces it.
    """
    try:
        from tethys_master.protocol.a2l import A2LFile
    except ImportError:
        logger.warning("a2l.facade_missing", path=str(path))
        return _StubA2LFile()
    # ``A2LFile`` satisfies ``_A2LFileLike`` structurally; mypy can't see it
    # through dict's invariance in the value type so we cast at the boundary.
    return A2LFile.load(path)  # type: ignore[return-value]


_COL_NAME = 0
_COL_TYPE = 1
_COL_ADDRESS = 2

_HEADERS = ("Name", "Type", "Address")


def _datatype_label(datatype: Any) -> str:
    """Render the datatype field whether it is an enum or a plain string."""
    return getattr(datatype, "value", str(datatype))


def _format_address(address: int) -> str:
    return f"0x{address:08X}" if address else "—"


def _build_model(a2l: _A2LFileLike) -> QStandardItemModel:
    """Translate an :class:`A2LFile` into a 3-column :class:`QStandardItemModel`."""
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(list(_HEADERS))

    measurements_root = QStandardItem("MEASUREMENTS")
    measurements_root.setEditable(False)
    measurements_root.setData("__root_measurements__", Qt.ItemDataRole.UserRole)
    for name in sorted(a2l.measurements):
        m = a2l.measurements[name]
        name_item = QStandardItem(m.name)
        name_item.setEditable(False)
        name_item.setData(("measurement", m.name), Qt.ItemDataRole.UserRole)
        name_item.setToolTip(m.long_identifier or m.name)
        type_item = QStandardItem(_datatype_label(m.datatype))
        type_item.setEditable(False)
        addr_item = QStandardItem(_format_address(m.address))
        addr_item.setEditable(False)
        measurements_root.appendRow([name_item, type_item, addr_item])
    model.appendRow(measurements_root)

    characteristics_root = QStandardItem("CHARACTERISTICS")
    characteristics_root.setEditable(False)
    characteristics_root.setData("__root_characteristics__", Qt.ItemDataRole.UserRole)
    for name in sorted(a2l.characteristics):
        c = a2l.characteristics[name]
        name_item = QStandardItem(c.name)
        name_item.setEditable(False)
        name_item.setData(("characteristic", c.name), Qt.ItemDataRole.UserRole)
        name_item.setToolTip(c.long_identifier or c.name)
        type_item = QStandardItem(_datatype_label(c.characteristic_type))
        type_item.setEditable(False)
        addr_item = QStandardItem(_format_address(c.address))
        addr_item.setEditable(False)
        characteristics_root.appendRow([name_item, type_item, addr_item])
    model.appendRow(characteristics_root)

    return model


class A2LTreeView(QTreeView):
    """QTreeView over the MODULE → MEASUREMENT / CHARACTERISTIC tree.

    Set an A2L file via :meth:`set_a2l` (instance) or :meth:`load`
    (file path). Selecting a leaf emits :attr:`measurement_selected` or
    :attr:`characteristic_selected` with the symbol name.
    """

    measurement_selected = Signal(str)
    characteristic_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("a2l_tree_view")
        self.setHeaderHidden(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self._a2l: _A2LFileLike = _StubA2LFile()
        self._reload_model()
        self.clicked.connect(self._on_clicked)

    def set_a2l(self, a2l: _A2LFileLike) -> None:
        """Replace the displayed A2L file with the given instance."""
        self._a2l = a2l
        self._reload_model()
        logger.info(
            "a2l_tree.loaded",
            project=a2l.project_name,
            module=getattr(a2l, "module_name", ""),
            measurements=len(a2l.measurements),
            characteristics=len(a2l.characteristics),
        )

    def load(self, path: str | Path) -> None:
        """Load an A2L file from ``path`` and refresh the tree."""
        self.set_a2l(_load_a2l(path))

    def current_a2l(self) -> _A2LFileLike:
        return self._a2l

    def measurement_count(self) -> int:
        return len(self._a2l.measurements)

    def characteristic_count(self) -> int:
        return len(self._a2l.characteristics)

    def _reload_model(self) -> None:
        model = _build_model(self._a2l)
        self.setModel(model)
        self.expandAll()
        for col in range(model.columnCount()):
            self.resizeColumnToContents(col)

    def _on_clicked(self, index: object) -> None:
        # ``index`` is a QModelIndex; use the role-payload from the name column.
        idx_name = index.siblingAtColumn(_COL_NAME) if hasattr(index, "siblingAtColumn") else index
        payload = idx_name.data(Qt.ItemDataRole.UserRole) if hasattr(idx_name, "data") else None
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        kind, name = payload
        if kind == "measurement":
            logger.info("a2l_tree.measurement_selected", name=name)
            self.measurement_selected.emit(name)
        elif kind == "characteristic":
            logger.info("a2l_tree.characteristic_selected", name=name)
            self.characteristic_selected.emit(name)
