"""Timeline of operator actions next to the messages they line up with.

The researcher's own log ("at 12:00 I set parameter 21") is the strongest clue
for what a message means. This panel puts each logged action next to the
messages that happened at the same moment, so a value seen on the wire can be
compared with the value the operator intended. Selecting a row asks the window
to jump to the message bytes.

The pairing is a temporal suggestion, never a proof: an action with no message
in range, or a message with no action, is shown as such rather than guessed at.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import theme
from .constants import FONT_SIZE_BODY

_COLUMNS = ("time", "action", "message", "agreement")


class TimelineView(QtWidgets.QWidget):
    """Operator actions aligned with decoded messages."""

    messageSelected = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.header = QtWidgets.QLabel()
        self.header.setWordWrap(True)
        self.header.setProperty("role", "secondary")
        self.header.setFont(theme.body_font(FONT_SIZE_BODY))
        layout.addWidget(self.header)

        self.table = QtWidgets.QTableWidget(0, len(_COLUMNS))
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setFont(theme.body_font(FONT_SIZE_BODY))
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selected)
        layout.addWidget(self.table, 1)

        self._offsets: list[int] = []
        self._column_labels = _COLUMNS
        self._report = None
        self.retranslate_ui()

    def show_correlation(self, report) -> None:
        """Fill the table from a :class:`CorrelationReport`.

        One row per paired action and message; a note row states the counts of
        anything left unpaired on either side.
        """
        self._report = report
        self._offsets = []
        rows: list[tuple[str, str, str, str]] = []
        for correlation in report.correlated:
            agreement = self.tr("matches")
            if correlation.value_conflicts:
                agreement = self.tr("conflicts: {0}").format("; ".join(correlation.value_conflicts))
            elif not correlation.value_agreements:
                agreement = self.tr("no shared field")
            rows.append(
                (
                    _format_time(correlation.message_timestamp),
                    correlation.entry.action or "",
                    f"offset {correlation.message_offset}",
                    agreement,
                )
            )
        self.table.setRowCount(len(rows))
        for row, cells in enumerate(rows):
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column == 3 and text.startswith("conflicts"):
                    item.setForeground(QtCore.Qt.GlobalColor.red)
                self.table.setItem(row, column, item)
            offset = report.correlated[row].message_offset
            self._offsets.append(offset)
            self.table.item(row, 0).setData(QtCore.Qt.ItemDataRole.UserRole, offset)
        self.header.setText(
            self.tr("{0} action(s) matched a message, {1} left unpaired.").format(
                len(report.correlated),
                len(report.entries_without_message) + report.messages_without_entry,
            )
        )

    def clear(self) -> None:
        """Empty the panel."""
        self.table.setRowCount(0)
        self._offsets = []
        self.header.setText(
            self.tr("Load an action journal to line your actions up with the messages.")
        )

    def _on_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._offsets):
            self.messageSelected.emit(int(self._offsets[row]))

    def apply_theme(self) -> None:
        """Re-read the theme so the conflict colour follows the palette."""
        self.header.setFont(theme.body_font(FONT_SIZE_BODY))
        self.table.setFont(theme.body_font(FONT_SIZE_BODY))
        if self._report is not None:
            self.show_correlation(self._report)

    def retranslate_ui(self) -> None:
        """Apply the captions in the active interface language."""
        self.table.setHorizontalHeaderLabels([self.tr(c) for c in self._column_labels])
        if not self.table.rowCount():
            self.clear()


def _format_time(timestamp: float | None) -> str:
    """Render a timestamp as ``HH:MM:SS.mmm``, or a dash when absent."""
    if timestamp is None:
        return "-"
    import datetime

    moment = datetime.datetime.fromtimestamp(timestamp, datetime.UTC)
    return moment.strftime("%H:%M:%S.") + f"{moment.microsecond // 1000:03d}"
