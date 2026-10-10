"""Interpretation panel.

Three tabs: the rule (editable text with an apply button), the decoded messages
of the current direction, and the counterexamples. A field that the rule marks
as a hypothesis is labelled as such, so an assumption is never shown as a fact.
Selecting a counterexample asks the window to reveal its bytes.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from . import theme
from .model import (
    MISMATCHED,
    RuleApplication,
)

_STATUS_RANK = {
    "mismatched": 0,
    "incomplete": 1,
    "ambiguous": 2,
    "unknown": 3,
    "uncovered": 4,
    "not_applicable": 5,
    "outdated": 6,
    "matched": 7,
}


def _field_summary(message) -> str:
    parts = []
    for field in message.fields:
        if field.status.value == "not_applicable":
            continue
        value = field.value
        marker = " (hypothesis)" if field.hypothesis else ""
        if value is None:
            parts.append(f"{field.field_name}: {field.reason or field.status.value}{marker}")
        else:
            parts.append(f"{field.field_name}={value}{marker}")
    return "  ".join(parts)


class ValidationView(QtWidgets.QWidget):
    """Rule editor, message table and counterexample list."""

    applyRequested = QtCore.Signal()
    counterexampleSelected = QtCore.Signal(int)
    ruleLoaded = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._context = QtWidgets.QLabel("no capture open")
        self._context.setProperty("role", "secondary")
        self._context.setFont(theme.body_font(9))
        layout.addWidget(self._context)

        self._tabs = QtWidgets.QTabWidget()
        layout.addWidget(self._tabs, 1)

        # Rule tab.
        rule_page = QtWidgets.QWidget()
        rule_layout = QtWidgets.QVBoxLayout(rule_page)
        rule_layout.setContentsMargins(0, 0, 0, 0)
        self.rule_edit = QtWidgets.QPlainTextEdit()
        self.rule_edit.setFont(theme.mono_font(9))
        self.rule_edit.setPlaceholderText("rule JSON or YAML")
        rule_layout.addWidget(self.rule_edit, 1)
        rule_buttons = QtWidgets.QHBoxLayout()
        self.apply_button = QtWidgets.QPushButton("Apply to current direction")
        self.apply_button.setProperty("accent", "true")
        self.apply_button.clicked.connect(self.applyRequested.emit)
        rule_buttons.addWidget(self.apply_button)
        rule_buttons.addStretch(1)
        rule_layout.addLayout(rule_buttons)
        self.rule_status = QtWidgets.QLabel("")
        self.rule_status.setProperty("role", "secondary")
        self.rule_status.setFont(theme.body_font(9))
        self.rule_status.setWordWrap(True)
        rule_layout.addWidget(self.rule_status)
        self._tabs.addTab(rule_page, "Rule")

        # Messages tab.
        self.messages_table = QtWidgets.QTableWidget(0, 4)
        self.messages_table.setHorizontalHeaderLabels(["offset", "len", "status", "fields"])
        self.messages_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.messages_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.messages_table.setFont(theme.body_font(9))
        self.messages_table.verticalHeader().setVisible(False)
        header = self.messages_table.horizontalHeader()
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.messages_table.itemSelectionChanged.connect(self._on_message_selected)
        self._tabs.addTab(self.messages_table, "Messages")

        # Counterexamples tab.
        counter_page = QtWidgets.QWidget()
        counter_layout = QtWidgets.QVBoxLayout(counter_page)
        counter_layout.setContentsMargins(0, 0, 0, 0)
        self.counter_list = QtWidgets.QListWidget()
        self.counter_list.setFont(theme.body_font(9))
        self.counter_list.itemSelectionChanged.connect(self._on_counter_selected)
        counter_layout.addWidget(self.counter_list, 1)
        self._tabs.addTab(counter_page, "Counterexamples")

        self._application: RuleApplication | None = None
        self._status_error = False

    # -- rule --------------------------------------------------------------

    def set_rule_text(self, text: str) -> None:
        """Replace the rule editor contents with ``text``."""
        self.rule_edit.setPlainText(text)

    def rule_text(self) -> str:
        """The current rule editor contents."""
        return self.rule_edit.toPlainText()

    def set_rule_status(self, text: str, error: bool = False) -> None:
        """Show ``text`` in the rule status line, red when ``error``."""
        self._status_error = error
        self._style_status()
        self.rule_status.setText(text)

    def _style_status(self) -> None:
        colour = (
            theme.current().status_mismatched_text
            if self._status_error
            else theme.current().text_secondary
        )
        self.rule_status.setStyleSheet(f"color: {colour};")

    def set_context(self, session_id: str, direction: str) -> None:
        """Show which session and direction the panel is working on."""
        self._context.setText(f"session {session_id}   {direction}")

    # -- results -----------------------------------------------------------

    def show_application(self, application: RuleApplication) -> None:
        """Fill the message table and counterexample list from *application*."""
        self._application = application
        self.messages_table.setRowCount(0)
        ordered = sorted(
            application.messages,
            key=lambda m: (_STATUS_RANK.get(m.status.value, 9), m.offset),
        )
        self.messages_table.setRowCount(len(ordered))
        for row, message in enumerate(ordered):
            self._fill_row(row, message)

        self.counter_list.clear()
        counterexamples = sorted(application.counterexamples, key=lambda m: m.offset)
        for message in counterexamples:
            item = QtWidgets.QListWidgetItem(
                f"offset {message.offset}  {message.bytes_hex}  {message.reason or ''}"
            )
            item.setForeground(QtGui.QColor(theme.current().status_mismatched_text))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, message.offset)
            item.setToolTip(_provenance_tooltip(message))
            self.counter_list.addItem(item)

        counts = application.counts
        summary = "  ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        self._tabs.setTabText(1, f"Messages ({len(ordered)})")
        self._tabs.setTabText(2, f"Counterexamples ({len(counterexamples)})")
        if not self.rule_status.text():
            self.set_rule_status(f"rule v{application.rule.rule_version}  {summary}")

    def _fill_row(self, row: int, message) -> None:
        cells = [
            f"{message.offset}",
            f"{message.length}",
            message.status.value,
            _field_summary(message),
        ]
        for column, text in enumerate(cells):
            item = QtWidgets.QTableWidgetItem(text)
            if column == 3:
                item.setFont(theme.mono_font(9))
            if message.status.value == MISMATCHED:
                item.setForeground(QtGui.QColor(theme.current().status_mismatched_text))
            elif message.status.value == "matched":
                item.setForeground(QtGui.QColor(theme.current().status_matched_text))
            self.messages_table.setItem(row, column, item)
        self.messages_table.item(row, 0).setData(
            QtCore.Qt.ItemDataRole.UserRole, message.offset
        )

    def _on_message_selected(self) -> None:
        rows = self.messages_table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.messages_table.item(rows[0].row(), 0)
        if item is not None:
            self.counterexampleSelected.emit(int(item.data(QtCore.Qt.ItemDataRole.UserRole)))

    def _on_counter_selected(self) -> None:
        items = self.counter_list.selectedItems()
        if items:
            self.counterexampleSelected.emit(int(items[0].data(QtCore.Qt.ItemDataRole.UserRole)))

    def show_message_count(self, count: int) -> None:
        """Show that the rule was applied to ``count`` messages."""
        self.set_rule_status(f"rule applied to {count} messages")

    def apply_theme(self) -> None:
        """Recolour the status line and rebuild the table in the active theme."""
        self._style_status()
        if self._application is not None:
            self.show_application(self._application)


def _provenance_tooltip(message) -> str:
    for field in message.fields:
        provenance = field.provenance_range
        if provenance:
            packets = provenance.get("packets")
            label = f"packets {packets}" if packets else ""
            if provenance.get("seq") is not None:
                label += f"  seq {provenance['seq']}"
            if provenance.get("ts") is not None:
                label += f"  ts {provenance['ts']}"
            label += f"\n{message.bytes_hex}"
            return label.strip()
    return message.bytes_hex
