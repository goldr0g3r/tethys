"""Calibration editor — QTableView over A2L CHARACTERISTICs with limit checks.

Each row is one CHARACTERISTIC: name, current value, units (conversion
field), lower limit, upper limit, status (in / out of range). Edits to
the "Value" column trigger an A2L limit check; the cell renders red
when the entered value falls outside ``[lower_limit, upper_limit]``.

A ``Commit`` button emits :attr:`CalibrationEditor.commit_requested`
with the pending edits as a dict so the master can issue ``DOWNLOAD``
+ ``BUILD_CHECKSUM`` against the slave. PR-C scope: just emit the
signal; the actual wire transaction is wired in a later phase.

Cite: parent plan §8 Phase 6 (calibration editor with A2L limit checks)
Cite: ASAM XCP 1.4 Part 2 §1.3.4.1 DOWNLOAD; §1.5.1 BUILD_CHECKSUM
Cite: ASAM MCD-2 MC v1.7 §4.4.10 CHARACTERISTIC
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from tethys_master.logging_setup import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Qt 6 model methods accept either flavour of index — the persistent
# variant is the one Qt's editor delegates hand to ``setData`` for
# long-lived edits. Aliasing keeps the model signatures Liskov-clean.
_QIndex = QModelIndex | QPersistentModelIndex


class _A2LCharacteristicLike(Protocol):
    """Structural subset of :class:`tethys_master.protocol.a2l.Characteristic`."""

    name: str
    long_identifier: str
    conversion: str
    lower_limit: float
    upper_limit: float
    address: int

    @property
    def characteristic_type(self) -> Any: ...


@dataclass(slots=True)
class _Row:
    """One calibration row — characteristic + current + pending value."""

    char: _A2LCharacteristicLike
    current_value: float
    pending_value: float | None = None

    @property
    def effective(self) -> float:
        return self.pending_value if self.pending_value is not None else self.current_value

    def is_in_range(self) -> bool:
        v = self.effective
        return self.char.lower_limit <= v <= self.char.upper_limit

    def has_pending_edit(self) -> bool:
        return self.pending_value is not None and self.pending_value != self.current_value


_COL_NAME = 0
_COL_VALUE = 1
_COL_UNITS = 2
_COL_MIN = 3
_COL_MAX = 4
_COL_STATUS = 5

_HEADERS = ("Name", "Value", "Units", "Min", "Max", "Status")

_OUT_OF_RANGE_BG = QColor(255, 80, 80, 160)
_PENDING_BG = QColor(255, 255, 0, 110)


class CalibrationModel(QAbstractTableModel):
    """Read/write Qt model: one row per A2L CHARACTERISTIC."""

    def __init__(
        self,
        characteristics: dict[str, _A2LCharacteristicLike] | None = None,
        initial_values: dict[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows: list[_Row] = []
        if characteristics is not None:
            self.set_characteristics(characteristics, initial_values or {})

    def set_characteristics(
        self,
        characteristics: dict[str, _A2LCharacteristicLike],
        initial_values: dict[str, float] | None = None,
    ) -> None:
        initial = initial_values or {}
        self.beginResetModel()
        self._rows = [
            _Row(
                char=char,
                current_value=float(initial.get(name, char.lower_limit)),
            )
            for name, char in sorted(characteristics.items())
        ]
        self.endResetModel()

    def row_at(self, row: int) -> _Row:
        return self._rows[row]

    def pending_edits(self) -> dict[str, float]:
        return {
            r.char.name: float(r.pending_value)
            for r in self._rows
            if r.has_pending_edit() and r.pending_value is not None
        }

    def commit_pending(self) -> None:
        """Promote every pending edit to current value and clear pending."""
        for row in self._rows:
            if row.has_pending_edit() and row.pending_value is not None:
                row.current_value = float(row.pending_value)
            row.pending_value = None
        if self._rows:
            self.dataChanged.emit(
                self.index(0, _COL_VALUE),
                self.index(len(self._rows) - 1, _COL_STATUS),
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole],
            )

    def discard_pending(self) -> None:
        for row in self._rows:
            row.pending_value = None
        if self._rows:
            self.dataChanged.emit(
                self.index(0, _COL_VALUE),
                self.index(len(self._rows) - 1, _COL_STATUS),
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole],
            )

    # ---- Qt model API -----------------------------------------------

    def rowCount(self, parent: _QIndex = QModelIndex()) -> int:  # noqa: B008 - Qt API
        _ = parent
        return len(self._rows)

    def columnCount(self, parent: _QIndex = QModelIndex()) -> int:  # noqa: B008 - Qt API
        _ = parent
        return len(_HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(_HEADERS):
            return _HEADERS[section]
        return None

    def flags(self, index: _QIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == _COL_VALUE:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def data(  # noqa: PLR0911 - Qt model data() is naturally branchy
        self,
        index: _QIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return self._display(row, col)

        if role == Qt.ItemDataRole.BackgroundRole and col == _COL_VALUE:
            if not row.is_in_range():
                return _OUT_OF_RANGE_BG
            if row.has_pending_edit():
                return _PENDING_BG
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            return row.char.long_identifier or row.char.name

        return None

    def setData(
        self,
        index: _QIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        if index.column() != _COL_VALUE:
            return False
        try:
            new_value = float(value)
        except (TypeError, ValueError):
            return False
        row = self._rows[index.row()]
        if new_value == row.current_value:
            row.pending_value = None
        else:
            row.pending_value = new_value
        # The status + background of the whole row may have changed.
        self.dataChanged.emit(
            self.index(index.row(), _COL_VALUE),
            self.index(index.row(), _COL_STATUS),
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole],
        )
        return True

    # ---- Display helpers --------------------------------------------

    @staticmethod
    def _display(row: _Row, col: int) -> Any:  # noqa: PLR0911 - column dispatch
        if col == _COL_NAME:
            return row.char.name
        if col == _COL_VALUE:
            return f"{row.effective:.6g}"
        if col == _COL_UNITS:
            return row.char.conversion
        if col == _COL_MIN:
            return f"{row.char.lower_limit:.6g}"
        if col == _COL_MAX:
            return f"{row.char.upper_limit:.6g}"
        if col == _COL_STATUS:
            if not row.is_in_range():
                return "OUT OF RANGE"
            if row.has_pending_edit():
                return "PENDING"
            return "OK"
        return None


class CalibrationEditor(QWidget):
    """QTableView over A2L CHARACTERISTICs + Commit / Discard buttons.

    Emits :attr:`commit_requested` with a dict of ``{name: new_value}``
    when the user presses Commit and all pending edits are in range.
    Out-of-range pending edits block the commit (button disabled, row
    highlighted red).
    """

    commit_requested = Signal(dict)
    edits_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("calibration_editor")

        self._model = CalibrationModel(parent=self)
        self._table = QTableView()
        self._table.setObjectName("calibration_table")
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self._table.setAlternatingRowColors(True)
        h_header = self._table.horizontalHeader()
        assert h_header is not None
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h_header.setStretchLastSection(True)

        self._commit_btn = QPushButton("&Commit")
        self._commit_btn.setObjectName("calibration_commit_btn")
        self._commit_btn.setShortcut("Ctrl+Return")
        self._commit_btn.clicked.connect(self._on_commit_clicked)
        self._discard_btn = QPushButton("&Discard")
        self._discard_btn.setObjectName("calibration_discard_btn")
        self._discard_btn.clicked.connect(self._on_discard_clicked)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._discard_btn)
        button_row.addWidget(self._commit_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(button_row)

        self._model.dataChanged.connect(self._on_data_changed)
        self._refresh_buttons()

    # ---- Public API --------------------------------------------------

    def set_characteristics(
        self,
        characteristics: dict[str, _A2LCharacteristicLike],
        initial_values: dict[str, float] | None = None,
    ) -> None:
        self._model.set_characteristics(characteristics, initial_values)
        self._refresh_buttons()

    def model(self) -> CalibrationModel:
        return self._model

    def pending_edits(self) -> dict[str, float]:
        return self._model.pending_edits()

    def has_pending_edits(self) -> bool:
        return bool(self._model.pending_edits())

    def has_out_of_range_edits(self) -> bool:
        return any(
            not self._model.row_at(i).is_in_range()
            for i in range(self._model.rowCount())
        )

    # ---- Slots -------------------------------------------------------

    def _on_data_changed(self, *_args: object) -> None:
        self._refresh_buttons()
        self.edits_changed.emit()

    def _on_commit_clicked(self) -> None:
        edits = self._model.pending_edits()
        if not edits:
            return
        if self.has_out_of_range_edits():
            logger.warning("calibration.commit_blocked.out_of_range", edits=list(edits))
            return
        logger.info("calibration.commit_requested", edits=edits)
        self.commit_requested.emit(edits)
        self._model.commit_pending()
        self._refresh_buttons()

    def _on_discard_clicked(self) -> None:
        self._model.discard_pending()
        self._refresh_buttons()
        self.edits_changed.emit()

    def _refresh_buttons(self) -> None:
        has_edits = self.has_pending_edits()
        out_of_range = self.has_out_of_range_edits()
        self._commit_btn.setEnabled(has_edits and not out_of_range)
        self._discard_btn.setEnabled(has_edits)
