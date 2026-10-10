"""User preferences and their dialog.

Preferences are grouped in ``general``, ``editor``, ``paths`` and ``advanced``
inside ``QSettings`` (organisation ``madrigal``, application ``protocol-lab``),
next to the theme and interface-language keys the window already uses. The
defaults are declared in one place so a fresh install, a dialog and the tests
all agree on them.

The dialog is edit-and-preview: switching theme or language applies
immediately, while the remaining values are collected and published once, as a
plain dictionary, when the user accepts. ``Cancel`` restores whatever was
active when the dialog opened.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets

ORGANISATION = "madrigal"
APPLICATION = "protocol-lab"

# group -> (key, default). One table so the dialog, the loader and the tests
# share a single definition of "unset".
DEFAULTS: dict[str, dict[str, Any]] = {
    "general": {
        "theme": "system",
        "language": "system",
    },
    "editor": {
        "hex_font_size": 13,
        "tree_font_size": 11,
        "zoom": 100,
        "show_offset": True,
    },
    "paths": {
        "project_dir": "",
        "capture_dir": "",
        "relative_paths": True,
    },
    "advanced": {
        "log_level": "INFO",
        "show_diagnostics": True,
    },
}

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
THEME_MODES = ("dark", "light", "system")
LANGUAGE_CODES = ("ru", "en", "system")


def _key(group: str, name: str) -> str:
    return f"{group}/{name}"


def read_settings(settings: QtCore.QSettings | None = None) -> dict[str, dict[str, Any]]:
    """Return every preference with its default filled in.

    Values come back from ``QSettings`` typed; a boolean stored as ``true`` is
    normalised back to ``bool`` here so callers never compare against a string.
    """
    store = settings or QtCore.QSettings(ORGANISATION, APPLICATION)
    result: dict[str, dict[str, Any]] = {}
    for group, entries in DEFAULTS.items():
        section: dict[str, Any] = {}
        for name, default in entries.items():
            stored = store.value(_key(group, name), default)
            if isinstance(default, bool):
                section[name] = _as_bool(stored)
            elif isinstance(default, int) and not isinstance(default, bool):
                section[name] = int(str(stored))
            else:
                section[name] = str(stored)
        result[group] = section
    return result


def write_settings(
    values: dict[str, dict[str, Any]],
    settings: QtCore.QSettings | None = None,
) -> None:
    """Persist *values*, keeping only keys that are known."""
    store = settings or QtCore.QSettings(ORGANISATION, APPLICATION)
    for group, entries in values.items():
        if group not in DEFAULTS:
            continue
        for name, value in entries.items():
            if name in DEFAULTS[group]:
                store.setValue(_key(group, name), value)
    store.sync()


def get(groups: dict[str, dict[str, Any]], group: str, name: str) -> Any:
    """Read ``group/name`` from a settings mapping, falling back to the default."""
    return groups.get(group, {}).get(name, DEFAULTS[group][name])


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class SettingsDialog(QtWidgets.QDialog):
    """Tabbed preferences dialog with OK, Cancel and Apply."""

    settingsChanged = QtCore.Signal(dict)

    def __init__(
        self,
        current: dict[str, dict[str, Any]] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))
        self.setModal(True)
        self._initial = current if current is not None else read_settings()
        # A heterogeneous registry: combo boxes, spin boxes, check boxes and
        # line edits by name. Each accessor below knows its own widget type.
        self._widgets: dict[str, dict[str, Any]] = {}

        tabs = QtWidgets.QTabWidget(self)
        tabs.addTab(self._build_general(), self.tr("General"))
        tabs.addTab(self._build_editor(), self.tr("Editor"))
        tabs.addTab(self._build_paths(), self.tr("Paths"))
        tabs.addTab(self._build_advanced(), self.tr("Advanced"))

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self._on_cancel)
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(tabs, 1)
        layout.addWidget(buttons)

    # -- tabs --------------------------------------------------------------

    def _build_general(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        theme = QtWidgets.QComboBox()
        for mode, label in (("dark", "Dark"), ("light", "Light"), ("system", "System")):
            theme.addItem(self.tr(label), mode)
        language = QtWidgets.QComboBox()
        language.addItem("Русский", "ru")
        language.addItem("English", "en")
        language.addItem(self.tr("System"), "system")
        self._set_combo(theme, get(self._initial, "general", "theme"))
        self._set_combo(language, get(self._initial, "general", "language"))
        form.addRow(self.tr("Theme"), theme)
        form.addRow(self.tr("Language"), language)
        self._widgets["general"] = {"theme": theme, "language": language}
        return page

    def _build_editor(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        hex_size = QtWidgets.QSpinBox()
        hex_size.setRange(6, 48)
        hex_size.setValue(int(get(self._initial, "editor", "hex_font_size")))
        tree_size = QtWidgets.QSpinBox()
        tree_size.setRange(6, 48)
        tree_size.setValue(int(get(self._initial, "editor", "tree_font_size")))
        zoom = QtWidgets.QSpinBox()
        zoom.setRange(60, 300)
        zoom.setSingleStep(10)
        zoom.setSuffix(" %")
        zoom.setValue(int(get(self._initial, "editor", "zoom")))
        show_offset = QtWidgets.QCheckBox()
        show_offset.setChecked(bool(get(self._initial, "editor", "show_offset")))
        form.addRow(self.tr("Hex font size"), hex_size)
        form.addRow(self.tr("Tree font size"), tree_size)
        form.addRow(self.tr("Interface zoom"), zoom)
        form.addRow(self.tr("Show offset column"), show_offset)
        self._widgets["editor"] = {
            "hex_font_size": hex_size,
            "tree_font_size": tree_size,
            "zoom": zoom,
            "show_offset": show_offset,
        }
        return page

    def _build_paths(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        layout: dict[str, QtWidgets.QWidget] = {}
        for name, label in (
            ("project_dir", self.tr("Projects directory")),
            ("capture_dir", self.tr("Captures directory")),
        ):
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            field = QtWidgets.QLineEdit(str(get(self._initial, "paths", name)))
            browse = QtWidgets.QPushButton(self.tr("Browse..."))
            browse.clicked.connect(lambda _checked=False, f=field: self._pick_dir(f))
            row_layout.addWidget(field, 1)
            row_layout.addWidget(browse)
            form.addRow(label, row)
            layout[name] = field
        relative = QtWidgets.QCheckBox()
        relative.setChecked(bool(get(self._initial, "paths", "relative_paths")))
        form.addRow(self.tr("Relative paths in manifest"), relative)
        self._widgets["paths"] = {**layout, "relative_paths": relative}
        return page

    def _build_advanced(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        level = QtWidgets.QComboBox()
        for name in LOG_LEVELS:
            level.addItem(name, name)
        self._set_combo(level, get(self._initial, "advanced", "log_level"))
        show_diagnostics = QtWidgets.QCheckBox()
        show_diagnostics.setChecked(bool(get(self._initial, "advanced", "show_diagnostics")))
        form.addRow(self.tr("Logging level"), level)
        form.addRow(self.tr("Show diagnostics in UI"), show_diagnostics)
        self._widgets["advanced"] = {
            "log_level": level,
            "show_diagnostics": show_diagnostics,
        }
        return page

    # -- values ------------------------------------------------------------

    def values(self) -> dict[str, dict[str, Any]]:
        """Collect the widgets into the settings mapping."""
        theme = self._widgets["general"]["theme"]
        language = self._widgets["general"]["language"]
        hex_size = self._widgets["editor"]["hex_font_size"]
        tree_size = self._widgets["editor"]["tree_font_size"]
        zoom = self._widgets["editor"]["zoom"]
        show_offset = self._widgets["editor"]["show_offset"]
        project = self._widgets["paths"]["project_dir"]
        capture = self._widgets["paths"]["capture_dir"]
        relative = self._widgets["paths"]["relative_paths"]
        level = self._widgets["advanced"]["log_level"]
        diagnostics = self._widgets["advanced"]["show_diagnostics"]
        return {
            "general": {
                "theme": theme.currentData(),
                "language": language.currentData(),
            },
            "editor": {
                "hex_font_size": hex_size.value(),
                "tree_font_size": tree_size.value(),
                "zoom": zoom.value(),
                "show_offset": show_offset.isChecked(),
            },
            "paths": {
                "project_dir": project.text(),
                "capture_dir": capture.text(),
                "relative_paths": relative.isChecked(),
            },
            "advanced": {
                "log_level": level.currentData(),
                "show_diagnostics": diagnostics.isChecked(),
            },
        }

    # -- buttons -----------------------------------------------------------

    def _on_ok(self) -> None:
        self._emit()
        self.accept()

    def _on_cancel(self) -> None:
        # Re-publish the values the dialog opened with, so a live theme or
        # language preview is rolled back, then close.
        self.settingsChanged.emit(self._initial)
        self.reject()

    def _on_apply(self) -> None:
        self._emit()

    def _emit(self) -> None:
        self.settingsChanged.emit(self.values())

    # -- helpers -----------------------------------------------------------

    def _pick_dir(self, field: QtWidgets.QLineEdit) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, self.tr("Choose directory"), field.text()
        )
        if chosen:
            field.setText(chosen)

    @staticmethod
    def _set_combo(combo: QtWidgets.QComboBox, value: Any) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
