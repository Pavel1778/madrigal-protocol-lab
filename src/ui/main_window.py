"""Application main window.

Layout: a menu bar, a horizontal splitter with the session tree on the left, the
hex view in the centre and the interpretation panel on the right, and a status
bar carrying the byte provenance, a progress indicator and a message area.

The window holds a :class:`CaptureModel` and a :class:`RuleModel`. It opens a
normalized capture (the contract JSON), never a pcap; the capture module is a
separate concern.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..protocol.result import build_result, write_result
from . import theme
from .compare_view import CompareView
from .hex_view import (
    LEGEND_KINDS,
    HexView,
    annotations_from_application,
    annotations_from_stream,
    legend_label,
    legend_swatch,
)
from .hypotheses_view import HypothesesView
from .i18n import LanguageManager
from .model import CaptureModel, RuleModel, verify_rule_on_corpus
from .session_tree import SessionTree
from .settings import SettingsDialog, read_settings, write_settings
from .validation_view import ValidationView

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / "REPORT.md"
APP_ICON = REPO_ROOT / "assets" / "icons" / "app" / "madrigal-protocol-lab.svg"
# The desktop id, without the ``.desktop`` suffix Qt expects. The installed file
# keeps the suffix: /usr/share/applications/madrigal-protocol-lab.desktop.
APP_DESKTOP_FILE = "madrigal-protocol-lab"

logger = logging.getLogger(__name__)


def app_icon() -> QtGui.QIcon:
    """Return the application icon, or an empty icon when the asset is absent."""
    return QtGui.QIcon(str(APP_ICON)) if APP_ICON.is_file() else QtGui.QIcon()


def associate_with_desktop_entry(app: QtGui.QGuiApplication | None = None) -> None:
    """Tie the running application to its installed desktop entry.

    A Linux dock resolves a window icon from the desktop entry whose id matches
    the application, not from :meth:`setWindowIcon`. Without this the taskbar
    shows a generic icon even though the title bar carries the right one. The id
    is the desktop file basename without the ``.desktop`` suffix, so the daemon
    finds ``/usr/share/applications/madrigal-protocol-lab.desktop``.
    """
    application = app or QtGui.QGuiApplication.instance()
    if application is not None:
        application.setDesktopFileName(APP_DESKTOP_FILE)


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._base_title = self.tr("Madrigal protocol laboratory")
        self.setWindowTitle(self._base_title)
        self.setWindowIcon(app_icon())
        self.resize(1400, 860)

        self._capture: CaptureModel | None = None
        self._rule: RuleModel | None = None
        self._session_id: str = ""
        self._direction: str = ""
        self._corpus_report = None
        self._last_dir: Path | None = None
        self._theme_manager = None
        self._language_manager: LanguageManager | None = None
        self._capture_name: str = ""
        self._settings: dict = read_settings()

        self._build_menu()
        self._build_central()
        self._build_status()
        self._wire()
        self._show_empty_state()
        self._install_theme()
        self._install_language()
        self._apply_stored_settings(adopt_from_managers=True)

    def _show_empty_state(self) -> None:
        """Explain the first-run window before a capture is opened."""
        self.hex_view.show_hint(
            self.tr(
                "no capture loaded\n\n"
                "Open a normalized capture (Ctrl+O), pick a session and a direction,\n"
                "then load a rule (Ctrl+R) or press Load example in the Rule tab."
            )
        )
        self.validation_view.set_rule_status(self.tr("no rule applied yet"))

    # -- construction ------------------------------------------------------

    def _build_menu(self) -> None:
        bar = self.menuBar()

        # Menus and actions are kept so :meth:`retranslate_ui` can relabel them
        # in place when the interface language changes, without rebuilding the
        # window or losing the loaded state.
        self._menus: dict[str, QtWidgets.QMenu] = {}
        self._actions: dict[str, QtGui.QAction] = {}

        file_menu = bar.addMenu("")
        self._menus["file"] = file_menu
        self._actions["open_capture"] = self._action(
            file_menu,
            "Open &normalized capture...",
            self.open_capture_dialog,
            "Ctrl+O",
            tip="Open a capture already normalized by src.capture.cli; a raw .pcap/.pcapng is not read here",
        )
        self._actions["open_rule"] = self._action(file_menu, "Open &rule...", self.open_rule_dialog, "Ctrl+R")
        self._actions["save_result"] = self._action(file_menu, "&Save result...", self.save_result_dialog, "Ctrl+S")
        file_menu.addSeparator()
        self._actions["quit"] = self._action(file_menu, "&Quit", self.close, "Ctrl+Q")

        rule_menu = bar.addMenu("")
        self._menus["rule"] = rule_menu
        self._actions["apply_direction"] = self._action(rule_menu, "&Apply to current direction", self.apply_rule, "F5")
        self._actions["apply_capture"] = self._action(rule_menu, "Apply to &whole capture", self.apply_to_capture, "F6")
        self._actions["compare_versions"] = self._action(rule_menu, "&Compare versions", self.show_version_diff)

        report_menu = bar.addMenu("")
        self._menus["report"] = report_menu
        self._actions["show_report"] = self._action(report_menu, "Show &REPORT.md", self.show_report)
        self._actions["export_markdown"] = self._action(report_menu, "&Export Markdown...", self.export_markdown)
        self._actions["export_html"] = self._action(report_menu, "Export &HTML...", self.export_html)

        view_menu = bar.addMenu("")
        self._menus["view"] = view_menu
        self._actions["theme_dark"] = self._action(view_menu, "&Dark theme", lambda: self.set_theme_mode("dark"), "Ctrl+1")
        self._actions["theme_light"] = self._action(view_menu, "&Light theme", lambda: self.set_theme_mode("light"), "Ctrl+2")
        self._actions["theme_system"] = self._action(view_menu, "&System theme", lambda: self.set_theme_mode("system"), "Ctrl+3")
        view_menu.addSeparator()

        self._actions["settings"] = self._action(
            view_menu, "&Settings...", self.open_settings_dialog, "Ctrl+,"
        )
        view_menu.addSeparator()

        self._language_menu = view_menu.addMenu("")
        self._menus["language"] = self._language_menu
        self._language_group = QtGui.QActionGroup(self)
        self._language_group.setExclusive(True)
        self._language_actions: dict[str, QtGui.QAction] = {}
        for code, label in (
            ("ru", "Русский"),
            ("en", "English"),
            ("system", "System"),
        ):
            action = QtGui.QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, c=code: self.set_language(c))
            self._language_group.addAction(action)
            self._language_menu.addAction(action)
            self._language_actions[code] = action

        help_menu = bar.addMenu("")
        self._menus["help"] = help_menu
        self._actions["quick_help"] = self._action(help_menu, "&Quick help", self.show_help, "F1")
        self._actions["about"] = self._action(help_menu, "&About", self.show_about)

        self._relabel_menu()

    def _action(self, menu, text, slot, shortcut: str | None = None, tip: str | None = None) -> QtGui.QAction:
        action = QtGui.QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _relabel_menu(self) -> None:
        """Translate every menu, action and language item in place."""
        labels = {
            "file": self.tr("&File"),
            "rule": self.tr("&Rule"),
            "report": self.tr("&Report"),
            "view": self.tr("&View"),
            "help": self.tr("&Help"),
            "language": self.tr("&Language"),
        }
        for key, label in labels.items():
            self._menus[key].setTitle(label)
        sources = {
            "open_capture": self.tr("Open &normalized capture..."),
            "open_rule": self.tr("Open &rule..."),
            "save_result": self.tr("&Save result..."),
            "quit": self.tr("&Quit"),
            "apply_direction": self.tr("&Apply to current direction"),
            "apply_capture": self.tr("Apply to &whole capture"),
            "compare_versions": self.tr("&Compare versions"),
            "show_report": self.tr("Show &REPORT.md"),
            "export_markdown": self.tr("&Export Markdown..."),
            "export_html": self.tr("Export &HTML..."),
            "theme_dark": self.tr("&Dark theme"),
            "theme_light": self.tr("&Light theme"),
            "theme_system": self.tr("&System theme"),
            "settings": self.tr("&Settings..."),
            "quick_help": self.tr("&Quick help"),
            "about": self.tr("&About"),
        }
        for key, label in sources.items():
            action = self._actions.get(key)
            if action is not None:
                action.setText(label)
        system_label = self.tr("System")
        for code, action in self._language_actions.items():
            action.setText(system_label if code == "system" else action.text())

    def _build_central(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        self.session_tree = SessionTree()
        self._sessions_box = self._wrap(self.tr("Sessions"), self.session_tree)
        splitter.addWidget(self._sessions_box)

        centre = QtWidgets.QWidget()
        centre_layout = QtWidgets.QVBoxLayout(centre)
        centre_layout.setContentsMargins(0, 0, 0, 0)
        centre_layout.setSpacing(6)
        controls = QtWidgets.QHBoxLayout()
        self.direction_combo = QtWidgets.QComboBox()
        self.direction_combo.setFont(theme.body_font(9))
        self.direction_combo.currentTextChanged.connect(self._on_direction_changed)
        self._direction_label = QtWidgets.QLabel(self.tr("direction"))
        controls.addWidget(self._direction_label)
        controls.addWidget(self.direction_combo)
        controls.addStretch(1)
        self.annotation_legend = QtWidgets.QWidget()
        legend_layout = QtWidgets.QHBoxLayout(self.annotation_legend)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setSpacing(8)
        self._legend_chips: list[QtWidgets.QLabel] = []
        for kind, _name in LEGEND_KINDS:
            label = legend_label(kind)
            chip = QtWidgets.QLabel(label)
            chip.setFont(theme.body_font(8))
            chip.setProperty("role", "secondary")
            chip.setToolTip(label)
            swatch = QtWidgets.QLabel()
            swatch.setPixmap(legend_swatch(kind))
            swatch.setFixedSize(12, 12)
            legend_layout.addWidget(swatch)
            legend_layout.addWidget(chip)
            self._legend_chips.append(chip)
        controls.addWidget(self.annotation_legend)
        centre_layout.addLayout(controls)
        self.hex_view = HexView()
        centre_layout.addWidget(self.hex_view, 1)
        self._bytes_box = self._wrap(self.tr("Bytes"), centre)
        splitter.addWidget(self._bytes_box)

        self.right_tabs = QtWidgets.QTabWidget()
        self.validation_view = ValidationView()
        self.right_tabs.addTab(self.validation_view, "")
        self.compare_view = CompareView()
        self.right_tabs.addTab(self.compare_view, "")
        self.hypotheses_view = HypothesesView()
        self.right_tabs.addTab(self.hypotheses_view, "")
        self.report_view = QtWidgets.QPlainTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setFont(theme.mono_font(9))
        self.right_tabs.addTab(self.report_view, "")
        self.diff_view = QtWidgets.QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(theme.mono_font(9))
        self.right_tabs.addTab(self.diff_view, "")
        self._relabel_tabs()
        splitter.addWidget(self.right_tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([300, 720, 420])
        self.setCentralWidget(splitter)

    def _wrap(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(widget)
        return box

    def _relabel_tabs(self) -> None:
        """Translate the right-hand tab captions in place."""
        for index, label in enumerate(
            (
                self.tr("Interpretation"),
                self.tr("Compare"),
                self.tr("Hypotheses"),
                self.tr("Report"),
                self.tr("Version diff"),
            )
        ):
            self.right_tabs.setTabText(index, label)

    def _build_status(self) -> None:
        bar = self.statusBar()
        self._provenance_label = QtWidgets.QLabel(self.tr("no byte selected"))
        self._provenance_label.setFont(theme.body_font(9))
        bar.addWidget(self._provenance_label, 1)
        self._progress = QtWidgets.QProgressBar()
        self._progress.setFixedWidth(140)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        bar.addPermanentWidget(self._progress)

    def _wire(self) -> None:
        self.session_tree.directionSelected.connect(self._on_direction_selected)
        self.hex_view.byteHovered.connect(self._on_byte_hovered)
        self.hex_view.byteClicked.connect(self._on_byte_clicked)
        self.validation_view.applyRequested.connect(self.apply_rule)
        self.validation_view.applyCaptureRequested.connect(self.apply_to_capture)
        self.validation_view.loadExampleRequested.connect(self.load_example_rule)
        self.validation_view.ruleValidityChanged.connect(self.validation_view.show_rule_validity)
        self.validation_view.counterexampleSelected.connect(self._reveal_counterexample)
        self.hypotheses_view.messageSelected.connect(self.reveal_offset)

    # -- theme -------------------------------------------------------------

    def _install_theme(self) -> None:
        """Create the manager for the running application and apply its mode."""
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        if self._theme_manager is None:
            self._theme_manager = theme.ThemeManager(app)
            self._theme_manager.themeChanged.connect(self._on_theme_changed)
        else:
            self._theme_manager.apply()
        self.apply_theme()

    def set_theme_mode(self, mode: str) -> None:
        """Select and persist a theme mode (``dark``, ``light`` or ``system``)."""
        if self._theme_manager is None:
            self._install_theme()
        if self._theme_manager is not None:
            self._theme_manager.set_mode(mode)
        self.apply_theme()

    def _on_theme_changed(self, name: str) -> None:
        self._notify(f"{name} theme")

    def apply_theme(self) -> None:
        """Make every view re-read the active theme."""
        for view in (
            self.session_tree,
            self.hex_view,
            self.validation_view,
            self.compare_view,
            self.hypotheses_view,
        ):
            view.apply_theme()
        self.report_view.setFont(theme.mono_font(9))
        self.diff_view.setFont(theme.mono_font(9))

    # -- settings ----------------------------------------------------------

    def open_settings_dialog(self) -> SettingsDialog:
        """Open the preferences dialog and apply what the user accepts."""
        dialog = SettingsDialog(self._settings, self)
        dialog.settingsChanged.connect(self.apply_settings)
        dialog.exec()
        return dialog

    def apply_settings(self, values: dict) -> None:
        """Apply a settings mapping and persist it.

        ``Cancel`` also emits, with the mapping the dialog opened with, so the
        same path restores the previous state without a second code path.
        """
        self._settings = values
        write_settings(values)
        self._apply_stored_settings()
        self._notify(self.tr("settings applied"))

    def _apply_stored_settings(self, adopt_from_managers: bool = False) -> None:
        """Push the stored values into the widgets and the logging root.

        At construction the theme and language managers have already read their
        own keys, so ``adopt_from_managers`` copies their effective choice back
        into the mapping instead of forcing the dialog defaults over a choice
        the menu saved earlier.
        """
        general = self._settings.get("general", {})
        editor = self._settings.get("editor", {})
        advanced = self._settings.get("advanced", {})

        if adopt_from_managers:
            if self._theme_manager is not None:
                general["theme"] = self._theme_manager.mode
            if self._language_manager is not None:
                general["language"] = self._language_manager.preference
            self._settings["general"] = general
        else:
            theme_mode = str(general.get("theme", "system"))
            if self._theme_manager is None or self._theme_manager.mode != theme_mode:
                self.set_theme_mode(theme_mode)

            language = str(general.get("language", "system"))
            if self._language_manager is None or self._language_manager.preference != language:
                self.set_language(language)

        self.hex_view.set_font_size(int(editor.get("hex_font_size", 13)))
        self.hex_view.set_show_offset(bool(editor.get("show_offset", True)))
        self.session_tree.set_font_size(int(editor.get("tree_font_size", 11)))
        self.hex_view.set_show_diagnostics(bool(advanced.get("show_diagnostics", True)))

        level = str(advanced.get("log_level", "INFO"))
        if level in logging.getLevelNamesMapping():
            logging.getLogger().setLevel(level)

    # -- interface language ------------------------------------------------

    def _install_language(self) -> None:
        """Create the language manager and apply the stored choice."""
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        if self._language_manager is None:
            self._language_manager = LanguageManager(app)
            self._language_manager.languageChanged.connect(self._on_language_changed)
        self._sync_language_actions()
        self.retranslate_ui()

    def set_language(self, code: str) -> None:
        """Select the interface language (``ru``, ``en`` or ``system``)."""
        if self._language_manager is None:
            self._install_language()
            return
        # The manager emits languageChanged, which relabels the window.
        self._language_manager.set_language(code)

    def _sync_language_actions(self) -> None:
        """Check the language menu entry that matches the stored choice."""
        code = self._language_manager.preference if self._language_manager else "system"
        action = self._language_actions.get(code)
        if action is not None:
            action.setChecked(True)

    def _on_language_changed(self, _code: str) -> None:
        self._sync_language_actions()
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Re-apply every translatable label to the active language.

        Qt delivers a ``LanguageChange`` event to each widget, which is enough
        for strings set by Qt itself, but the labels this window builds are
        stored, so they are relabelled here without rebuilding the window and
        losing the loaded capture, rule or results.
        """
        self._base_title = self.tr("Madrigal protocol laboratory")
        self._refresh_title()
        self._relabel_menu()
        self._relabel_tabs()
        self._bytes_box.setTitle(self.tr("Bytes"))
        self._sessions_box.setTitle(self.tr("Sessions"))
        self._direction_label.setText(self.tr("direction"))
        for chip, (kind, _name) in zip(self._legend_chips, LEGEND_KINDS):
            label = legend_label(kind)
            chip.setText(label)
            chip.setToolTip(label)
        self.validation_view.retranslate_ui()
        self.compare_view.retranslate_ui()
        self.hypotheses_view.retranslate_ui()
        self.session_tree.retranslate_ui()
        self.hex_view.retranslate_ui()
        if self._capture_name:
            self._provenance_label.setText(self._capture_summary())

    def _refresh_title(self) -> None:
        """Set the window title, including the open capture's name."""
        if self._capture_name:
            self.setWindowTitle(f"{self._base_title} - {self._capture_name}")
        else:
            self.setWindowTitle(self._base_title)

    def _capture_summary(self) -> str:
        """The status-line summary of the open capture, in the active language."""
        if self._capture is None:
            return self.tr("no byte selected")
        diagnostics = (
            ", ".join(f"{d.type}@{d.offset}" for d in self._capture.diagnostics)
            or self.tr("none")
        )
        return self.tr("{0} sessions  capture_id {1}  diagnostics {2}").format(
            len(self._capture.sessions), self._capture.capture_id[:19], diagnostics
        )

    # -- loading -----------------------------------------------------------

    def open_capture(self, path: str | Path) -> None:
        """Load a normalized capture and select its first direction."""
        model = CaptureModel.from_file(path)
        self._capture = model
        self.session_tree.load(model)
        self._capture_name = Path(path).name
        self._refresh_title()
        self._provenance_label.setText(self._capture_summary())
        if model.sessions:
            self._on_direction_selected(
                model.sessions[0].session_id, model.directions(model.sessions[0].session_id)[0]
            )

    def _start_dir(self, fallback: Path) -> str:
        """The directory a file dialog should open at.

        Remembers the last directory a file was opened from or saved to, then
        falls back to the configured captures directory, and only then to the
        caller's fallback, so the second open does not start at the repository
        root again.
        """
        if self._last_dir is not None:
            return str(self._last_dir)
        configured = str(self._settings.get("paths", {}).get("capture_dir", ""))
        if configured and Path(configured).is_dir():
            return configured
        return str(fallback)

    def _output_dir(self, fallback: Path) -> str:
        """The directory a save dialog should open at."""
        if self._last_dir is not None:
            return str(self._last_dir)
        configured = str(self._settings.get("paths", {}).get("project_dir", ""))
        if configured and Path(configured).is_dir():
            return configured
        return str(fallback)

    def _remember_dir(self, path: str | Path) -> None:
        parent = Path(path).resolve().parent
        if parent.is_dir():
            self._last_dir = parent

    def open_capture_dialog(self) -> None:
        """Prompt for a normalized capture file and open it."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("Open normalized capture"), self._start_dir(REPO_ROOT), "JSON (*.json)"
        )
        if path:
            self._remember_dir(path)
            self.open_capture(path)

    def load_rule(self, path: str | Path) -> None:
        """Load a rule file, keeping the previous rule and report for diffing."""
        previous_rule = self._rule.rule if self._rule is not None else None
        previous_report = self._rule.corpus_report if self._rule is not None else None
        self._rule = RuleModel.from_file(path)
        self._rule.previous_rule = previous_rule
        self._rule.previous_report = previous_report
        self.validation_view.set_rule_text(self._rule.text)
        self.validation_view.set_rule_status(
            self.tr("loaded {0}  rule v{1}").format(Path(path).name, self._rule.rule.rule_version)
        )

    def open_rule_dialog(self) -> None:
        """Prompt for a rule file and load it."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("Open rule"), self._start_dir(REPO_ROOT / "examples"), "Rules (*.json *.yaml *.yml)"
        )
        if path:
            self._remember_dir(path)
            self.load_rule(path)

    def load_example_rule(self) -> None:
        """Load the first example rule, or report that none is present."""
        examples = sorted((REPO_ROOT / "examples").glob("*.json"))
        if not examples:
            self.validation_view.set_rule_status(self.tr("no example rule found"), error=True)
            return
        self.load_rule(examples[0])

    # -- selection ---------------------------------------------------------

    def _on_direction_selected(self, session_id: str, direction: str) -> None:
        if self._capture is None:
            return
        self._session_id = session_id
        self._direction = direction
        self.direction_combo.blockSignals(True)
        self.direction_combo.clear()
        for name in self._capture.directions(session_id):
            self.direction_combo.addItem(name)
        self.direction_combo.setCurrentText(direction)
        self.direction_combo.blockSignals(False)
        self.validation_view.set_context(session_id, direction)
        self._render_stream()

    def _on_direction_changed(self, direction: str) -> None:
        if self._capture is None or not direction or direction == self._direction:
            return
        self.session_tree.select_direction(self._session_id, direction)

    def _render_stream(self) -> None:
        if self._capture is None:
            return
        stream = self._capture.stream(self._session_id, self._direction)
        self.hex_view.set_stream(stream.data, annotations_from_stream(stream))

    # -- rule --------------------------------------------------------------

    def apply_rule(self) -> None:
        """Adopt the edited rule and apply it to the current direction."""
        if self._capture is None or self._rule is None:
            self._notify(self.tr("open a capture and a rule first"))
            return
        try:
            self._rule.reload(self.validation_view.rule_text())
        except Exception as exc:  # noqa: BLE001 - the message is shown to the user
            self.validation_view.set_rule_status(self.tr("rule error: {0}").format(exc), error=True)
            return
        application = self._rule.apply(self._capture, self._session_id, self._direction)
        self.validation_view.show_application(application)
        self.compare_view.show_application(application)
        self._show_hypotheses(self._rule.rule, application.messages)
        stream = self._capture.stream(self._session_id, self._direction)
        self.hex_view.set_annotations(annotations_from_application(application, stream))
        counts = ", ".join(f"{k}={v}" for k, v in sorted(application.counts.items()))
        self.validation_view.set_rule_status(
            self.tr("rule v{0}  {1}").format(application.rule.rule_version, counts)
        )
        self._notify(
            self.tr("applied rule v{0} to {1} {2}").format(
                application.rule.rule_version, self._session_id, self._direction
            )
        )

    def _show_hypotheses(self, rule, messages) -> None:
        """Fill the hypotheses tab with the alternative readings for the run."""
        from ..hypothesis.alternatives import suggest_alternatives

        report = suggest_alternatives(rule, messages)
        self.hypotheses_view.show_fields(report.fields)

    def _corpus_messages(self, directions: tuple[str, ...]) -> list:
        """Decode every scoped stream of the capture into one message list.

        The hypotheses panel is read against the whole corpus, not one direction,
        so the candidate scores are computed from every message the rule applies
        to rather than from a single session.
        """
        from ..protocol.engine import apply_rule

        messages: list = []
        for session in self._capture.sessions:
            for direction in self._capture.directions(session.session_id):
                if directions and direction not in directions:
                    continue
                stream = self._capture.stream(session.session_id, direction)
                messages.extend(
                    apply_rule(stream, self._rule.rule, session.session_id, direction)
                )
        return messages

    def apply_to_capture(self) -> None:
        """Verify the current rule over every direction of the capture."""
        if self._capture is None or self._rule is None:
            self._notify(self.tr("open a capture and a rule first"))
            return
        try:
            self._rule.reload(self.validation_view.rule_text())
        except Exception as exc:  # noqa: BLE001
            self.validation_view.set_rule_status(self.tr("rule error: {0}").format(exc), error=True)
            return
        self._begin_run()
        self._set_progress(20)
        report = verify_rule_on_corpus(self._rule.rule, self._capture)
        self._set_progress(100)
        self._end_run()
        if self._rule.previous_report is not None and self._rule.previous_report.rule_id == report.rule_id:
            self._show_report_diff(self._rule.previous_report, report)
        self._rule.corpus_report = report
        self._corpus_report = report
        self.validation_view.show_corpus_report(report)
        directions = (self._rule.rule.direction,) if self._rule.rule.direction else ()
        self._show_hypotheses(self._rule.rule, self._corpus_messages(directions))
        counts = ", ".join(f"{k}={v}" for k, v in sorted(report.counts().items()))
        self.validation_view.set_rule_status(
            self.tr("rule v{0} over the capture: {1}  counterexamples={2}").format(
                self._rule.rule.rule_version, counts, len(report.contradictions)
            )
        )
        self._notify(self.tr("verified rule over the whole capture: {0}").format(counts))

    def _show_report_diff(self, report_a, report_b) -> None:
        from ..hypothesis.diff import diff_reports, format_report_diff

        diff = diff_reports(report_a, report_b)
        self.diff_view.setPlainText(format_report_diff(diff))
        self.right_tabs.setCurrentWidget(self.diff_view)

    def show_version_diff(self) -> None:
        """Show how the current rule version changed the corpus report."""
        report = self._rule.corpus_report if self._rule is not None else None
        previous = self._rule.previous_report if self._rule is not None else None
        if report is None or previous is None or previous.rule_id != report.rule_id:
            self._notify(self.tr("no previous rule version to compare"))
            return
        self._show_report_diff(previous, report)
        self._notify(
            self.tr("rule v{0} supersedes v{1}; the old run is marked outdated").format(
                report.rule_version, previous.rule_version
            )
        )

    # -- bytes -------------------------------------------------------------

    def reveal_offset(self, offset: int) -> None:
        """Scroll the hex view to ``offset`` and show its provenance."""
        self.hex_view.scroll_to_byte(offset)
        self._show_provenance(offset)

    def _reveal_counterexample(self, session_id: str, direction: str, offset: int, length: int = 1) -> None:
        """Jump to a counterexample, switching session or direction if needed.

        A corpus counterexample can live in a direction other than the one on
        screen, so the tree selection is moved first, then the message bytes are
        highlighted as a block.
        """
        if session_id and direction and (
            session_id != self._session_id or direction != self._direction
        ):
            self.session_tree.select_direction(session_id, direction)
        self.hex_view.highlight_range(offset, length)
        self._show_provenance(offset)

    def _on_byte_clicked(self, offset: int) -> None:
        self._show_provenance(offset)

    def _on_byte_hovered(self, offset: int) -> None:
        self._show_provenance(offset)

    def _show_provenance(self, offset: int) -> None:
        if self._capture is None:
            return
        stream = self._capture.stream(self._session_id, self._direction)
        parts = [f"{self._session_id} {self._direction}  offset {offset}"]
        for hole in stream.provenance:
            if hole.offset <= offset < hole.end:
                parts.append(
                    self.tr("packet {0}  seq {1}  ts {2}").format(
                        hole.packet_index, hole.seq, hole.ts
                    )
                )
                break
        diagnostics = stream.holes(offset, offset + 1)
        for hole in diagnostics:
            parts.append(f"{hole.type} ({hole.offset}+{hole.length})")
        self._provenance_label.setText("   ".join(str(p) for p in parts))

    # -- report ------------------------------------------------------------

    def show_report(self) -> None:
        """Show the default report file in the right-hand tab, if present."""
        if DEFAULT_REPORT.is_file():
            self.report_view.setPlainText(DEFAULT_REPORT.read_text(encoding="utf-8"))
            self.right_tabs.setCurrentWidget(self.report_view)

    def export_markdown(self) -> None:
        """Export the report as Markdown."""
        self._export(DEFAULT_REPORT, self.tr("Markdown (*.md)"))

    def export_html(self) -> None:
        """Export the report as HTML."""
        self._export(DEFAULT_REPORT, "HTML (*.html)", html=True)

    def _export(self, source: Path, file_filter: str, html: bool = False) -> None:
        if not source.is_file():
            self._notify(self.tr("{0} is not available").format(source.name))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, self.tr("Export report"), str(source.parent / source.name), file_filter)
        if not path:
            return
        text = source.read_text(encoding="utf-8")
        if html:
            text = _markdown_to_html(text)
        Path(path).write_text(text, encoding="utf-8")
        self._notify(self.tr("wrote {0}").format(path))

    def save_result_dialog(self) -> None:
        """Prompt for a path and save the current rule application as JSON.

        The file is the contract result, validated against
        ``docs/schemas/result.schema.json`` before it is written, so a saved
        result is interchangeable with one produced by the command line.
        """
        if self._rule is None or self._rule.root is None:
            self._notify(self.tr("apply a rule before saving a result"))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, self.tr("Save result"), self._output_dir(REPO_ROOT), "JSON (*.json)")
        if not path:
            return
        self._remember_dir(path)
        application = self._rule.root
        capture_id = self._capture.capture_id if self._capture is not None else ""
        result = build_result(application.rule, capture_id, application.messages)
        try:
            write_result(result, path)
        except Exception as exc:  # noqa: BLE001 - report any write or schema failure
            self.validation_view.set_rule_status(self.tr("could not save result: {0}").format(exc), error=True)
            self._notify(self.tr("could not save the result"))
            return
        self._notify(self.tr("wrote {0}").format(path))

    def show_help(self) -> None:
        """Show a short help card with the keys and the workflow order."""
        QtWidgets.QMessageBox.information(
            self,
            self.tr("Quick help"),
            self.tr(
                "Order of work\n"
                "1. File - Open normalized capture (Ctrl+O).\n"
                "2. Pick a session, then a direction.\n"
                "3. Rule - Open rule (Ctrl+R), or Load example in the Rule tab.\n"
                "4. F5 applies the rule to the current direction; F6 to the whole capture.\n"
                "5. Read the Counterexamples tab; clicking a row jumps to the bytes.\n"
                "\n"
                "Keys\n"
                "Ctrl+O open capture   Ctrl+R open rule   Ctrl+S save result\n"
                "F5 apply direction    F6 apply capture   F1 this help\n"
                "\n"
                "The bytes are the source of truth. A rule is an interpretation; a\n"
                "mismatch is a counterexample kept against it, not discarded."
            ),
        )

    def show_about(self) -> None:
        """Show the about dialog."""
        QtWidgets.QMessageBox.information(
            self,
            self.tr("About"),
            self.tr(
                "Madrigal protocol laboratory\n"
                "A local tool for reconstructing an undocumented binary protocol "
                "over TCP.\nThe bytes are the source of truth; a rule is an "
                "interpretation checked against them."
            ),
        )

    # -- helpers -----------------------------------------------------------

    def _set_progress(self, value: int) -> None:
        self._progress.setValue(value)

    def _begin_run(self) -> None:
        """Show the progress bar at zero for the start of a run.

        Resetting to zero first means a previous run's finished bar is never
        read as the state of the run now starting.
        """
        self._progress.setValue(0)
        self._progress.setVisible(True)

    def _end_run(self) -> None:
        """Return the progress bar to idle and hide it.

        A run is synchronous, so leaving the bar at a finished value would
        report progress that no longer exists.
        """
        self._progress.setValue(0)
        self._progress.setVisible(False)

    def _notify(self, text: str) -> None:
        self.statusBar().showMessage(text, 6000)


def _markdown_to_html(text: str) -> str:
    """Minimal Markdown to HTML for the report export.

    Only the constructs the report uses are handled: headings, paragraphs and
    pipe tables. A general Markdown renderer is out of scope.
    """
    import html as html_module

    lines = text.splitlines()
    token = theme.current()
    out: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<style>body{{background:{token.background};color:{token.text_primary};"
        f"font-family:{token.font_body},sans-serif;"
        "max-width:960px;margin:2rem auto;padding:0 1rem} "
        f"h1,h2,h3{{font-family:{token.font_heading},sans-serif;color:{token.text_primary}}} "
        "table{border-collapse:collapse;margin:1rem 0} "
        f"td,th{{border:1px solid {token.border};padding:4px 8px}} "
        f"code{{color:{token.accent}}}</style>",
        "</head><body>",
    ]
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
            tag = "th" if out[-1] == "<table>" else "td"
            row = "".join(f"<{tag}>{html_module.escape(c)}</{tag}>" for c in cells)
            out.append(f"<tr>{row}</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            out.append(f"<h{level}>{html_module.escape(stripped[level:].strip())}</h{level}>")
        elif stripped:
            out.append(f"<p>{html_module.escape(stripped)}</p>")
    if in_table:
        out.append("</table>")
    out.append("</body></html>")
    return "\n".join(out)


def open_default_window(
    app: QtWidgets.QApplication | None = None,
    capture: str | Path | None = None,
    rule: str | Path | None = None,
) -> MainWindow:
    """Build a window, optionally opening *capture* and *rule*.

    The window is input-driven: nothing is loaded unless the caller passes a
    path. Tests, the screenshot script and the manual smoke run supply the
    reference corpus and rule explicitly, so no capture or rule name is
    embedded in the application itself.
    """
    window = MainWindow()
    associate_with_desktop_entry()
    if capture is not None and Path(capture).is_file():
        window.open_capture(capture)
    if rule is not None and Path(rule).is_file():
        window.load_rule(rule)
    return window


def main(argv: list[str] | None = None) -> int:
    """Launch the Qt application, opening an optional capture and rule."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="src.ui.main_window",
        description="Open the protocol laboratory window.",
    )
    parser.add_argument("--capture", type=Path, help="normalized capture JSON to open")
    parser.add_argument("--rule", type=Path, help="rule JSON or YAML to open")
    args, qt_argv = parser.parse_known_args(argv)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([sys.argv[0], *qt_argv])
    app.setApplicationName("Madrigal protocol laboratory")
    associate_with_desktop_entry(app)
    app.setWindowIcon(app_icon())
    theme.load_fonts(app)
    window = open_default_window(app, capture=args.capture, rule=args.rule)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
