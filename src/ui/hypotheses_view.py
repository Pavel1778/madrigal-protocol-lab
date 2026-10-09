"""Hypotheses panel.

Lists every field the rule marks as a hypothesis, together with the alternative
readings the engine tested for it. Each candidate is coloured by how well it
fits: a high score is green, a middle score yellow, a low score grey. Selecting a
candidate asks the window to reveal a message that supports it, so a reading can
be checked against the bytes behind it.

This is evidence, not a verdict: the declared meaning is one candidate among the
others and may score lower. Nothing here proves a field's meaning.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from . import theme

# Score bands for the colour code: high, middle, low.
HIGH_SCORE = 0.9
MID_SCORE = 0.5

_COLUMNS = ("field", "reading", "support", "contradict", "score")

# The readings added for value shape; shown with the same colour code as the
# rest but named here so the panel can label them.
_SHAPE_READINGS = (
    "entropy_random",
    "entropy_parameter",
    "entropy_enum",
    "periodicity",
    "bit_pattern_2",
    "bit_pattern_4",
    "bit_pattern_6",
    "delta_correlation",
)


def score_colour(score: float) -> str:
    """Colour for a candidate score: green, yellow or grey.

    Args:
        score: The candidate's ``support / (support + contradict)`` in [0, 1].

    Returns:
        One of the theme's text colours.
    """
    if score >= HIGH_SCORE:
        return theme.MATCHED_TEXT
    if score >= MID_SCORE:
        return theme.INCOMPLETE_TEXT
    return theme.TEXT_SECONDARY


class HypothesesView(QtWidgets.QWidget):
    """Hypothesis fields with their alternative readings."""

    messageSelected = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.header = QtWidgets.QLabel("no rule applied")
        self.header.setProperty("role", "secondary")
        self.header.setFont(theme.body_font(9))
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        self.table = QtWidgets.QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setFont(theme.body_font(9))
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selected)
        layout.addWidget(self.table, 1)

        self._offsets: list[int] = []

    def show_fields(self, fields: list) -> None:
        """Fill the panel from a list of ``FieldAlternatives``.

        Args:
            fields: Per-field alternatives, as returned by
                ``suggest_alternatives``. Each candidate is drawn as one row.
        """
        self.table.setRowCount(0)
        self._offsets = []
        rows = []
        for field in fields:
            candidates = field.alternatives or []
            if not candidates:
                rows.append((field.field_name, "(no candidate fits)", None, None))
                continue
            for candidate in candidates:
                rows.append((field.field_name, candidate.name, candidate, candidate.score))

        self.table.setRowCount(len(rows))
        for row, (field_name, reading, candidate, score) in enumerate(rows):
            self._fill_row(row, field_name, reading, candidate, score)

        total_candidates = sum(1 for _, _, candidate, _ in rows if candidate is not None)
        self.header.setText(
            f"{len(fields)} hypothesis field(s), {total_candidates} candidate reading(s)"
        )

    def clear(self) -> None:
        """Empty the panel."""
        self.table.setRowCount(0)
        self._offsets = []
        self.header.setText("no rule applied")

    def _fill_row(self, row: int, field_name: str, reading: str, candidate, score) -> None:
        support = "" if candidate is None else f"{candidate.support}"
        contradict = "" if candidate is None else f"{candidate.contradict}"
        score_text = "" if score is None else f"{score:.2f}"
        cells = [field_name, reading, support, contradict, score_text]
        colour = None if score is None else score_colour(score)
        for column, text in enumerate(cells):
            item = QtWidgets.QTableWidgetItem(text)
            if column == 1 and reading in _SHAPE_READINGS:
                item.setToolTip("value-shape reading")
            if colour is not None and column >= 2:
                item.setForeground(QtGui.QColor(colour))
            self.table.setItem(row, column, item)
        offset = _first_evidence_offset(candidate)
        self._offsets.append(offset)
        if offset is not None:
            self.table.item(row, 0).setData(QtCore.Qt.ItemDataRole.UserRole, offset)
            self.table.item(row, 0).setToolTip(f"reveal message at offset {offset}")

    def _on_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._offsets) and self._offsets[row] is not None:
            self.messageSelected.emit(int(self._offsets[row]))


def _first_evidence_offset(candidate) -> int | None:
    """Offset of the first evidence message for a candidate, if any."""
    if candidate is None:
        return None
    for entry in candidate.evidence or []:
        offset = entry.get("message_offset")
        if isinstance(offset, int):
            return offset
    return None
