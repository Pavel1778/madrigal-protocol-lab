"""Visual rule builder.

The declarative rule is the heart of the tool, but writing its JSON by hand is
the single biggest barrier for a new user. This panel replaces that: the reader
selects a run of bytes in the hex view, names the field, picks a type from a
short list, and the panel writes the rule document. The generated JSON is shown
so the result is never a black box, and it can still be edited by hand in the
Rule tab.

The panel only ever *builds* a rule document; the engine remains the single
authority on what a rule means. When a field cannot be built (a name is missing,
a length is zero) the panel says so in one line instead of raising.
"""

from __future__ import annotations

import json

from PySide6 import QtCore, QtWidgets

from . import theme
from .constants import FONT_SIZE_BODY
from .layout import FlowLayout

# The field types a person is likely to want, in plain words. The value is the
# engine's type name; the key is what the combo shows.
FIELD_TYPES: tuple[tuple[str, str], ...] = (
    ("Unsigned byte (uint8)", "uint8"),
    ("Unsigned 16-bit (uint16)", "uint16"),
    ("Unsigned 32-bit (uint32)", "uint32"),
    ("Signed byte (int8)", "int8"),
    ("Signed 16-bit (int16)", "int16"),
    ("Signed 32-bit (int32)", "int32"),
    ("Raw bytes", "bytes"),
    ("Named choice (enum)", "enum"),
)

# The framing strategies a person can pick, in plain words.
FRAMING_TYPES: tuple[tuple[str, str], ...] = (
    ("Each message starts with its own length", "length_prefixed"),
    ("Fixed-size messages", "fixed_size"),
    ("Messages between start and end markers", "marker_based"),
)


class RuleBuilder(QtWidgets.QWidget):
    """Build a rule document from selected bytes.

    Emits :attr:`ruleBuilt` with the new rule JSON whenever the document
    changes, so the window can offer it for applying or saving.
    """

    ruleBuilt = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.intro = QtWidgets.QLabel()
        self.intro.setWordWrap(True)
        self.intro.setProperty("role", "secondary")
        self.intro.setFont(theme.body_font(FONT_SIZE_BODY))
        layout.addWidget(self.intro)

        self._fields: list[dict] = []
        self._rule_id = "new_rule"
        self._framing: dict = {
            "type": "length_prefixed",
            "length_offset": 2,
            "length_size": 2,
            "byte_order": "big",
            "length_covers": "payload",
        }

        framing_row = QtWidgets.QHBoxLayout()
        self.framing_label = QtWidgets.QLabel()
        self.framing_label.setFont(theme.body_font(FONT_SIZE_BODY))
        self.framing_combo = QtWidgets.QComboBox()
        # The captions are long; letting the combo size to its longest entry
        # would set a floor on the whole window's minimum width. A fixed
        # contents length keeps the window able to shrink on a small screen.
        self.framing_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.framing_combo.setMinimumContentsLength(10)
        for caption, _value in FRAMING_TYPES:
            self.framing_combo.addItem(caption)
        self.framing_combo.currentIndexChanged.connect(self._on_framing_changed)
        framing_row.addWidget(self.framing_label)
        framing_row.addWidget(self.framing_combo, 1)
        layout.addLayout(framing_row)

        add_row = QtWidgets.QHBoxLayout()
        self.name_label = QtWidgets.QLabel()
        self.name_label.setFont(theme.body_font(FONT_SIZE_BODY))
        self.name_edit = QtWidgets.QLineEdit()
        self.type_label = QtWidgets.QLabel()
        self.type_label.setFont(theme.body_font(FONT_SIZE_BODY))
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.type_combo.setMinimumContentsLength(8)
        for caption, _value in FIELD_TYPES:
            self.type_combo.addItem(caption)
        self.add_button = QtWidgets.QPushButton()
        self.add_button.setProperty("accent", "true")
        self.add_button.clicked.connect(self._on_add_field)
        add_row.addWidget(self.name_label)
        add_row.addWidget(self.name_edit, 1)
        add_row.addWidget(self.type_label)
        add_row.addWidget(self.type_combo)
        add_row.addWidget(self.add_button)
        layout.addLayout(add_row)

        self.selection_label = QtWidgets.QLabel()
        self.selection_label.setWordWrap(True)
        self.selection_label.setProperty("role", "secondary")
        self.selection_label.setFont(theme.body_font(FONT_SIZE_BODY))
        layout.addWidget(self.selection_label)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setFont(theme.body_font(FONT_SIZE_BODY))
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        button_row = FlowLayout()
        self.remove_button = QtWidgets.QPushButton()
        self.remove_button.clicked.connect(self._on_remove_field)
        self.clear_button = QtWidgets.QPushButton()
        self.clear_button.clicked.connect(self.clear)
        self.use_button = QtWidgets.QPushButton()
        self.use_button.setProperty("accent", "true")
        self.use_button.clicked.connect(self._on_use)
        button_row.addWidget(self.remove_button)
        button_row.addWidget(self.clear_button)
        button_row.addWidget(self.use_button)
        layout.addLayout(button_row)

        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(theme.mono_font(FONT_SIZE_BODY))
        self.preview.setMaximumHeight(150)
        layout.addWidget(self.preview)

        self._selection_start = 0
        self._selection_length = 0
        self._column_labels = ("name", "type", "offset", "length")
        self.retranslate_ui()

    # -- selection ---------------------------------------------------------

    def set_selection(self, offset: int, length: int) -> None:
        """Record the bytes the user selected in the hex view."""
        self._selection_start = max(0, int(offset))
        self._selection_length = max(0, int(length))
        self._update_selection_label()

    def _update_selection_label(self) -> None:
        if self._selection_length <= 0:
            self.selection_label.setText(
                self.tr("Select bytes in the hex view, then name the field here.")
            )
            self.add_button.setEnabled(False)
            return
        self.selection_label.setText(
            self.tr("Selected bytes {0}..{1} ({2} byte(s)).").format(
                self._selection_start,
                self._selection_start + self._selection_length - 1,
                self._selection_length,
            )
        )
        self.add_button.setEnabled(True)

    # -- building ----------------------------------------------------------

    def _on_framing_changed(self, index: int) -> None:
        _caption, value = FRAMING_TYPES[index]
        if value == "fixed_size":
            self._framing = {"type": "fixed_size", "size": 16}
        elif value == "marker_based":
            self._framing = {
                "type": "marker_based",
                "start_bytes": "aa55",
                "end_bytes": "0d0a",
            }
        else:
            self._framing = {
                "type": "length_prefixed",
                "length_offset": 2,
                "length_size": 2,
                "byte_order": "big",
                "length_covers": "payload",
            }
        self._emit()

    def _on_add_field(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.selection_label.setText(self.tr("Give the field a name first."))
            return
        if self._selection_length <= 0:
            self.selection_label.setText(self.tr("Select bytes in the hex view first."))
            return
        if any(f["name"] == name for f in self._fields):
            self.selection_label.setText(
                self.tr("A field named {0} already exists.").format(name)
            )
            return
        _caption, ftype = FIELD_TYPES[self.type_combo.currentIndex()]
        spec: dict = {
            "name": name,
            "offset": self._selection_start,
            "type": ftype,
            "hypothesis": True,
        }
        if ftype in ("uint16", "uint32", "int16", "int32"):
            spec["byte_order"] = "big"
        if ftype == "bytes":
            spec["length"] = self._selection_length
        self._fields.append(spec)
        self.name_edit.clear()
        self._refresh_table()
        self._emit()

    def _on_remove_field(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        index = rows[0].row()
        if 0 <= index < len(self._fields):
            del self._fields[index]
            self._refresh_table()
            self._emit()

    def _on_use(self) -> None:
        self.ruleBuilt.emit(self.rule_json())

    def clear(self) -> None:
        """Start a new, empty rule."""
        self._fields = []
        self._refresh_table()
        self._emit()

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._fields))
        for row, spec in enumerate(self._fields):
            cells = (
                str(spec.get("name", "")),
                str(spec.get("type", "")),
                str(spec.get("offset", "")),
                str(spec.get("length", "")),
            )
            for column, text in enumerate(cells):
                self.table.setItem(row, column, QtWidgets.QTableWidgetItem(text))

    def rule_document(self) -> dict:
        """Return the rule document the panel currently describes."""
        return {
            "schema_version": 1,
            "rule_id": self._rule_id,
            "rule_version": 1,
            "name": self._rule_id,
            "scope": {"direction": "A_to_B"},
            "framing": dict(self._framing),
            "fields": [dict(f) for f in self._fields],
        }

    def rule_json(self) -> str:
        """Return the rule document as pretty-printed JSON."""
        return json.dumps(self.rule_document(), indent=2)

    def _emit(self) -> None:
        text = self.rule_json()
        self.preview.setPlainText(text)
        self.use_button.setEnabled(bool(self._fields))
        self.ruleBuilt.emit(text)

    # -- language ----------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Apply the captions in the active interface language."""
        self.intro.setText(
            self.tr(
                "Build a rule without writing JSON: select bytes in the hex view, "
                "name the field and pick its type."
            )
        )
        self.framing_label.setText(self.tr("Messages are framed by"))
        self.name_label.setText(self.tr("Name"))
        self.type_label.setText(self.tr("Type"))
        self.add_button.setText(self.tr("Add field"))
        self.remove_button.setText(self.tr("Remove selected"))
        self.clear_button.setText(self.tr("Clear"))
        self.use_button.setText(self.tr("Use this rule"))
        self.table.setHorizontalHeaderLabels([self.tr(c) for c in self._column_labels])
        self.framing_combo.setItemText(0, self.tr(FRAMING_TYPES[0][0]))
        self.framing_combo.setItemText(1, self.tr(FRAMING_TYPES[1][0]))
        self.framing_combo.setItemText(2, self.tr(FRAMING_TYPES[2][0]))
        for index, (caption, _value) in enumerate(FIELD_TYPES):
            self.type_combo.setItemText(index, self.tr(caption))
        self._update_selection_label()

    def apply_theme(self) -> None:
        """Re-read the theme fonts for the panel's widgets."""
        for label in (
            self.intro,
            self.framing_label,
            self.name_label,
            self.type_label,
            self.selection_label,
        ):
            label.setFont(theme.body_font(FONT_SIZE_BODY))
        self.table.setFont(theme.body_font(FONT_SIZE_BODY))
        self.preview.setFont(theme.mono_font(FONT_SIZE_BODY))
