"""Message comparison.

Two messages from the current rule application, shown byte by byte with their
common prefix aligned. Bytes that agree are plain, bytes that differ are marked,
and a run present in only one message is marked as inserted or deleted. The
comparison is over observed bytes only.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtGui, QtWidgets

from . import theme
from .model import RuleApplication

EQUAL = "equal"
CHANGED = "changed"
INSERTED = "inserted"
DELETED = "deleted"


def _colours() -> dict[object, str]:
    """Diff colours for the active theme.

    Agreeing bytes stay plain (no highlight); a changed byte is red, an
    inserted byte green, a deleted byte grey.
    """
    token = theme.current()
    return {
        EQUAL: token.text_primary,
        CHANGED: token.status_mismatched_text,
        INSERTED: token.status_matched_text,
        DELETED: token.text_secondary,
    }


_LEGEND_NAMES = (
    ("equal", EQUAL),
    ("changed", CHANGED),
    ("inserted", INSERTED),
    ("deleted", DELETED),
)


@dataclass
class DiffRow:
    """One aligned row of the byte comparison.

    Attributes:
        offset: Offset of the row's first byte in the messages.
        left: Hex of the left byte, or ``"--"`` when absent.
        right: Hex of the right byte, or ``"--"`` when absent.
        kind: ``EQUAL``, ``CHANGED``, ``INSERTED`` or ``DELETED``.
    """

    offset: int
    left: str
    right: str
    kind: str


def diff_bytes(left: bytes, right: bytes) -> list[DiffRow]:
    """Align *left* and *right* by their common prefix, then pair the rest.

    This is a deliberately simple alignment: a shared prefix, then a shared
    suffix, with the differing middle shown side by side. It is enough to read
    one message against another; it is not a general diff.
    """
    prefix = 0
    limit = min(len(left), len(right))
    while prefix < limit and left[prefix] == right[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < limit - prefix
        and left[len(left) - 1 - suffix] == right[len(right) - 1 - suffix]
    ):
        suffix += 1

    rows: list[DiffRow] = []
    for index in range(prefix):
        rows.append(DiffRow(index, f"{left[index]:02x}", f"{right[index]:02x}", EQUAL))

    left_mid = left[prefix : len(left) - suffix]
    right_mid = right[prefix : len(right) - suffix]
    for index in range(max(len(left_mid), len(right_mid))):
        offset = prefix + index
        left_byte = f"{left_mid[index]:02x}" if index < len(left_mid) else "--"
        right_byte = f"{right_mid[index]:02x}" if index < len(right_mid) else "--"
        if index >= len(left_mid):
            kind = INSERTED
        elif index >= len(right_mid):
            kind = DELETED
        else:
            kind = CHANGED
        rows.append(DiffRow(offset, left_byte, right_byte, kind))

    # The shared tail sits at a different absolute offset in each message when
    # the two lengths differ, so the two indices are computed separately. Using
    # one offset for both read past the end of the shorter message.
    for index in range(suffix):
        left_offset = len(left) - suffix + index
        right_offset = len(right) - suffix + index
        rows.append(
            DiffRow(
                left_offset,
                f"{left[left_offset]:02x}",
                f"{right[right_offset]:02x}",
                EQUAL,
            )
        )
    return rows


class CompareView(QtWidgets.QWidget):
    """Two message selectors and the byte comparison between them."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        selectors = QtWidgets.QHBoxLayout()
        self.left_combo = QtWidgets.QComboBox()
        self.right_combo = QtWidgets.QComboBox()
        self.left_combo.setFont(theme.body_font(9))
        self.right_combo.setFont(theme.body_font(9))
        selectors.addWidget(QtWidgets.QLabel("A"))
        selectors.addWidget(self.left_combo, 1)
        selectors.addWidget(QtWidgets.QLabel("B"))
        selectors.addWidget(self.right_combo, 1)
        layout.addLayout(selectors)

        legend = QtWidgets.QHBoxLayout()
        self._legend_chips: dict[object, QtWidgets.QLabel] = {}
        for name, kind in _LEGEND_NAMES:
            chip = QtWidgets.QLabel(name)
            chip.setFont(theme.mono_font(8))
            legend.addWidget(chip)
            self._legend_chips[kind] = chip
        legend.addStretch(1)
        layout.addLayout(legend)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["offset", "A", "B"])
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFont(theme.mono_font(9))
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.table, 1)

        self._application: RuleApplication | None = None
        self.left_combo.currentIndexChanged.connect(self._refresh)
        self.right_combo.currentIndexChanged.connect(self._refresh)

    def show_application(self, application: RuleApplication) -> None:
        """Load *application*'s messages into the two selectors."""
        self._application = application
        self.left_combo.blockSignals(True)
        self.right_combo.blockSignals(True)
        self.left_combo.clear()
        self.right_combo.clear()
        for message in application.messages:
            label = f"{message.offset}: {message.status.value}"
            self.left_combo.addItem(label, message.offset)
            self.right_combo.addItem(label, message.offset)
        if self.right_combo.count() > 1:
            self.right_combo.setCurrentIndex(1)
        self.left_combo.blockSignals(False)
        self.right_combo.blockSignals(False)
        self._refresh()

    def _refresh(self) -> None:
        self.table.setRowCount(0)
        if self._application is None:
            return
        if self.left_combo.currentData() is None or self.right_combo.currentData() is None:
            return
        left = self._application.message_at(int(self.left_combo.currentData()))
        right = self._application.message_at(int(self.right_combo.currentData()))
        if left is None or right is None:
            return
        rows = diff_bytes(bytes.fromhex(left.bytes_hex), bytes.fromhex(right.bytes_hex))
        colours = _colours()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            colour = QtGui.QColor(colours[row.kind])
            for column, text in enumerate(
                (f"{row.offset:04x}", row.left, row.right)
            ):
                item = QtWidgets.QTableWidgetItem(text)
                item.setForeground(colour)
                self.table.setItem(index, column, item)

    def apply_theme(self) -> None:
        """Recolour the diff table and its legend in the active theme."""
        colours = _colours()
        for kind, chip in self._legend_chips.items():
            chip.setStyleSheet(f"color: {colours[kind]};")
        self._refresh()
