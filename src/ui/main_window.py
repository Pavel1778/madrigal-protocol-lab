"""Application main window.

Layout: a menu bar, a horizontal splitter with the session tree on the left, the
hex view in the centre and the interpretation panel on the right, and a status
bar carrying the byte provenance, a progress indicator and a message area.

The window holds a :class:`CaptureModel` and a :class:`RuleModel`. It opens a
normalized capture (the contract JSON), never a pcap; the capture module is a
separate concern.
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..project.manifest import ManifestError
from ..project.project import Project, ProjectError
from ..protocol.result import build_result, write_result
from ..protocol.rule import load_rule_text, rule_text
from . import help as reference
from . import learning, theme
from .compare_view import CompareView
from .constants import (
    FONT_SIZE_BODY,
    PROGRESS_BAR_WIDTH,
)
from .help_dialog import HelpCard, LearningCentre
from .hex_view import (
    HexView,
    annotations_from_application,
    annotations_from_stream,
)
from .hypotheses_view import HypothesesView
from .i18n import LanguageManager
from .legend import AnnotationLegend
from .model import CaptureModel, CaptureModelError, RuleModel, verify_rule_on_corpus
from .session_tree import SessionTree
from .settings import (
    APPLICATION,
    DEFAULTS,
    ORGANISATION,
    SettingsDialog,
    read_settings,
    write_settings,
)
from .spotlight import LearningSpotlight
from .timeline_view import TimelineView
from .tutor import TutorPanel
from .validation_view import ValidationView
from .welcome_view import WelcomeView

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / "REPORT.md"
APP_ICON = REPO_ROOT / "assets" / "icons" / "app" / "madrigal-protocol-lab.svg"

# The small worked example that ships with the tool, so the first-run window can
# offer a one-click investigation instead of an empty view.
SAMPLE_DIR = Path(__file__).resolve().parent / "samples"
SAMPLE_CAPTURE = SAMPLE_DIR / "demo_capture.normalized.json"
SAMPLE_RULE = SAMPLE_DIR / "demo_rule.json"
SAMPLE_JOURNAL = SAMPLE_DIR / "demo_journal.txt"
# The desktop id, without the ``.desktop`` suffix Qt expects. The installed file
# keeps the suffix: /usr/share/applications/madrigal-protocol-lab.desktop.
APP_DESKTOP_FILE = "madrigal-protocol-lab"

# The status line shows the provenance of the selected byte. The text changes
# with every click and can be long, so the label reserves room for its text up
# to this many characters and always carries the full text as a tooltip. A
# window narrower than the reservation cannot hard-clip a value the reader still
# needs; the same text is then one hover away.
_PROVENANCE_CHAR_CAP = 120
_PROVENANCE_LABEL_PADDING = 8

# Zoom bounds for the byte and tree fonts. The tree tracks the bytes a little
# smaller; both are kept in these ranges so the layout cannot be zoomed into a
# state where a column collapses or a row is taller than the viewport.
ZOOM_MIN_FONT = 8
ZOOM_MAX_FONT = 28
TREE_MIN_FONT = 7
TREE_MAX_FONT = 26
HEX_TREE_OFFSET = 2

# The widget a lesson step points at, mapped to the reference entry its help
# button opens. The keys are the names the steps use, so the course and the
# reference stay linked in one place.
_HELP_TARGETS: dict[str, str] = {
    "sessions_box": "sessions_box",
    "hex_view": "hex_view",
    "right_tabs": "right_tabs",
    "status_bar": "status_bar",
    "direction_combo": "direction",
    "validation_view": "validation_view",
    "session_tree": "session",
}

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    """Reduce a project or rule name to a safe file-name stem."""
    cleaned = [c if c.isalnum() or c in "-_" else "-" for c in text.strip()]
    return "".join(cleaned).strip("-_") or "project"


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
        self._rule_applied = False
        # The portable project behind the window, if one was created or opened.
        # Its path identifies it in the title; the manifest is the on-disk state
        # the project API writes, so the window keeps no second copy of it.
        self._project: Project | None = None
        self._project_path: Path | None = None
        self._theme_manager = None
        self._language_manager: LanguageManager | None = None
        self._capture_name: str = ""
        self._journal: list = []
        self._corpus_dialog = None
        self._last_offset: int | None = None
        self._settings: dict = read_settings()
        # The last rule-status line is kept as a renderer rather than as a
        # finished string, so a language switch can rebuild it in the new
        # language instead of leaving the previous one on screen.
        self._rule_status_render: Callable[[], str] | None = None
        self._rule_status_error = False
        self._guided_enabled: bool = bool(
            self._settings.get("general", {}).get("guided_mode", True)
        )
        # Learning state. The course position is tracked by lesson key and step
        # index; the completion markers record which lessons were finished, so
        # the course can be continued or a single lesson replayed. The tutor is
        # only shown while it is active and the expert mode is off.
        self._learning_active: bool = False
        self._learning_lesson: str = learning.LESSONS[0].key
        self._learning_step: int = 0
        self._completed_lessons: set[str] = {
            key
            for key in str(
                self._settings.get("learning", {}).get("completed", "")
            ).split(",")
            if key
        }
        self._help_card: HelpCard | None = None
        self._learning_centre: LearningCentre | None = None
        self._pointer_clear = QtCore.QTimer(self)
        self._pointer_clear.setSingleShot(True)
        self._pointer_clear.setInterval(2600)
        self._pointer_clear.timeout.connect(self._clear_pointer)

        self._build_menu()
        self._build_central()
        self._build_status()
        self._wire()
        self._show_empty_state()
        self._install_theme()
        self._install_language()
        self._apply_stored_settings(adopt_from_managers=True)

    def _show_empty_state(self) -> None:
        """Show the welcome screen alone, before anything is open."""
        self._stack.setCurrentWidget(self.welcome_view)
        self.welcome_view.reset()
        self.hex_view.show_hint(
            self.tr(
                "no capture loaded\n\n"
                "Open a capture (Ctrl+O): pcap, pcapng or normalized JSON."
            )
        )
        self._set_rule_status(lambda: self.tr("no rule applied yet"))
        self.validation_view.set_provenance([])
        self.validation_view.set_ready(capture=False, rule=False)
        self.timeline_view.clear()

    def _show_workspace(self) -> None:
        """Reveal the workspace once a capture is open."""
        self._stack.setCurrentWidget(self.workspace)

    def _refresh_welcome_progress(self) -> None:
        """Update the welcome screen's three steps from what is open."""
        self.welcome_view.set_progress(
            capture=self._capture is not None,
            session=bool(self._session_id),
            rule=self._rule is not None,
        )

    # -- construction ------------------------------------------------------

    def _build_menu(self) -> None:
        bar = self.menuBar()

        # Menus and actions are kept so :meth:`retranslate_ui` can relabel them
        # in place when the interface language changes, without rebuilding the
        # window or losing the loaded state.
        self._menus: dict[str, QtWidgets.QMenu] = {}
        self._actions: dict[str, QtGui.QAction] = {}
        self._action_tips: dict[QtGui.QAction, str] = {}

        file_menu = bar.addMenu("")
        self._menus["file"] = file_menu
        self._actions["open_demo"] = self._action(
            file_menu,
            "Open &demo",
            self.open_demo,
            "Ctrl+D",
            tip=self.tr("Load the small capture, rule and journal that ship with the tool, for a first look"),
        )
        file_menu.addSeparator()
        self._actions["open_capture"] = self._action(
            file_menu,
            "Open &normalized capture...",
            self.open_capture_dialog,
            "Ctrl+O",
            tip=self.tr("Open a capture: a raw .pcap/.pcapng is normalized on the fly, a normalized JSON is read as is"),
        )
        self._actions["open_rule"] = self._action(
            file_menu, "Open &rule...", self.open_rule_dialog, "Ctrl+R"
        )
        self._actions["build_rule"] = self._action(
            file_menu,
            "&Build rule...",
            self.build_rule,
            "Ctrl+B",
            tip=self.tr("Describe the message in a form instead of writing JSON by hand"),
        )
        self._actions["save_result"] = self._action(
            file_menu, "&Save result...", self.save_result_dialog, "Ctrl+S"
        )
        self._actions["import_pcap"] = self._action(
            file_menu,
            "&Import PCAP...",
            self.import_pcap,
            None,
            tip=self.tr("Read a raw .pcap/.pcapng and save its normalized JSON next to it"),
        )
        file_menu.addSeparator()
        self._actions["quit"] = self._action(file_menu, "&Quit", self.close, "Ctrl+Q")

        project_menu = bar.addMenu("")
        self._menus["project"] = project_menu
        self._actions["project_new"] = self._action(
            project_menu,
            "&New project...",
            self.new_project_dialog,
            None,
            tip=self.tr("Create a portable project directory that holds captures, rules and results"),
        )
        self._actions["project_open"] = self._action(
            project_menu,
            "&Open project...",
            self.open_project_dialog,
            None,
            tip=self.tr("Open an existing portable project directory"),
        )
        self._actions["project_save"] = self._action(
            project_menu,
            "&Save project",
            self.save_project,
            None,
            tip=self.tr("Write the project manifest, refreshing its timestamp"),
        )
        project_menu.addSeparator()
        self._actions["project_add_capture"] = self._action(
            project_menu,
            "&Add capture...",
            self.add_capture_to_project_dialog,
            None,
            tip=self.tr("Copy a capture into the open project and register it"),
        )
        self._actions["project_save_rule_version"] = self._action(
            project_menu,
            "Save rule &version...",
            self.save_rule_version_dialog,
            None,
            tip=self.tr("Name the current rule version and store it in the project"),
        )
        project_menu.addSeparator()
        self._actions["project_export"] = self._action(
            project_menu,
            "&Export project...",
            self.export_project_dialog,
            None,
            tip=self.tr("Write the whole project to a zip archive"),
        )
        self._actions["project_import"] = self._action(
            project_menu,
            "&Import project...",
            self.import_project_dialog,
            None,
            tip=self.tr("Unpack a project archive into a new directory and open it"),
        )

        rule_menu = bar.addMenu("")
        self._menus["rule"] = rule_menu
        self._actions["apply_direction"] = self._action(
            rule_menu, "&Apply to current direction", self.apply_rule, "F5"
        )
        self._actions["apply_capture"] = self._action(
            rule_menu, "Apply to &whole capture", self.apply_to_capture, "F6"
        )
        self._actions["compare_versions"] = self._action(
            rule_menu, "&Compare versions", self.show_version_diff
        )
        self._actions["corpus_check"] = self._action(
            rule_menu,
            "Check on &corpus...",
            self.show_corpus_check,
            "F7",
            tip=self.tr("Show the rule's reach over the whole capture and its counterexamples"),
        )

        report_menu = bar.addMenu("")
        self._menus["report"] = report_menu
        self._actions["show_report"] = self._action(
            report_menu, "Show &REPORT.md", self.show_report
        )
        self._actions["export_markdown"] = self._action(
            report_menu, "&Export Markdown...", self.export_markdown
        )
        self._actions["export_html"] = self._action(
            report_menu, "Export &HTML...", self.export_html
        )

        view_menu = bar.addMenu("")
        self._menus["view"] = view_menu
        self._actions["theme_dark"] = self._action(
            view_menu, "&Dark theme", lambda: self.set_theme_mode("dark"), "Ctrl+1"
        )
        self._actions["theme_light"] = self._action(
            view_menu, "&Light theme", lambda: self.set_theme_mode("light"), "Ctrl+2"
        )
        self._actions["theme_system"] = self._action(
            view_menu, "&System theme", lambda: self.set_theme_mode("system"), "Ctrl+3"
        )
        view_menu.addSeparator()
        self._actions["zoom_in"] = self._action(
            view_menu,
            "Zoom &in",
            self.zoom_in,
            "Ctrl+=",
            tip=self.tr("Enlarge the bytes and the session tree (Ctrl+Plus)"),
        )
        self._actions["zoom_in_alt"] = QtGui.QAction("Zoom in", self)
        self._actions["zoom_in_alt"].setShortcut(QtGui.QKeySequence("Ctrl++"))
        self._actions["zoom_in_alt"].triggered.connect(self.zoom_in)
        self.addAction(self._actions["zoom_in_alt"])
        self._actions["zoom_out"] = self._action(
            view_menu,
            "Zoom &out",
            self.zoom_out,
            "Ctrl+-",
            tip=self.tr("Shrink the bytes and the session tree (Ctrl+Minus)"),
        )
        self._actions["zoom_reset"] = self._action(
            view_menu,
            "&Reset zoom",
            self.zoom_reset,
            "Ctrl+0",
            tip=self.tr("Restore the default byte and tree size"),
        )
        view_menu.addSeparator()

        self._actions["toggle_timeline"] = QtGui.QAction(self.tr("&Timeline"), self)
        self._actions["toggle_timeline"].setCheckable(True)
        self._actions["toggle_timeline"].setShortcut("Ctrl+T")
        self._actions["toggle_timeline"].setToolTip(
            self.tr("Show the fourth column: the message timeline against the journal")
        )
        self._actions["toggle_timeline"].toggled.connect(self._toggle_timeline)
        view_menu.addAction(self._actions["toggle_timeline"])
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
            action.triggered.connect(
                lambda _checked=False, c=code: self.set_language(c)
            )
            self._language_group.addAction(action)
            self._language_menu.addAction(action)
            self._language_actions[code] = action

        help_menu = bar.addMenu("")
        self._menus["help"] = help_menu
        self._actions["start_learning"] = self._action(
            help_menu, "Start the &interactive course", self.start_learning
        )
        self._actions["learning_centre"] = self._action(
            help_menu, "Learning and &help...", self.open_learning_centre
        )
        self._actions["toggle_learning_mode"] = QtGui.QAction(
            self.tr("&Learning mode"), self
        )
        self._actions["toggle_learning_mode"].setCheckable(True)
        self._actions["toggle_learning_mode"].setToolTip(
            self.tr("Show the guided hints and the tutor; off is the expert mode")
        )
        self._actions["toggle_learning_mode"].toggled.connect(self.set_guided_mode)
        help_menu.addAction(self._actions["toggle_learning_mode"])
        help_menu.addSeparator()
        self._actions["show_guide"] = self._action(
            help_menu, "Show the &start screen", self.show_guide
        )
        self._actions["quick_help"] = self._action(
            help_menu, "&Quick help", self.show_help, "F1"
        )
        self._actions["about"] = self._action(help_menu, "&About", self.show_about)

        self._relabel_menu()

    def _action(
        self, menu, text, slot, shortcut: str | None = None, tip: str | None = None
    ) -> QtGui.QAction:
        action = QtGui.QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
            # Keep the source tip so :meth:`_relabel_menu` can re-translate it
            # on a language switch; a QAction stores the translated string only.
            self._action_tips[action] = tip
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _relabel_menu(self) -> None:
        """Translate every menu, action and language item in place."""
        labels = {
            "file": self.tr("&File"),
            "project": self.tr("&Project"),
            "rule": self.tr("&Rule"),
            "report": self.tr("&Report"),
            "view": self.tr("&View"),
            "help": self.tr("&Help"),
            "language": self.tr("&Language"),
        }
        for key, label in labels.items():
            self._menus[key].setTitle(label)
        sources = {
            "open_demo": self.tr("Open &demo"),
            "open_capture": self.tr("Open &normalized capture..."),
            "open_rule": self.tr("Open &rule..."),
            "build_rule": self.tr("&Build rule..."),
            "save_result": self.tr("&Save result..."),
            "import_pcap": self.tr("&Import PCAP..."),
            "quit": self.tr("&Quit"),
            "project_new": self.tr("&New project..."),
            "project_open": self.tr("&Open project..."),
            "project_save": self.tr("&Save project"),
            "project_add_capture": self.tr("&Add capture..."),
            "project_save_rule_version": self.tr("Save rule &version..."),
            "project_export": self.tr("&Export project..."),
            "project_import": self.tr("&Import project..."),
            "apply_direction": self.tr("&Apply to current direction"),
            "apply_capture": self.tr("Apply to &whole capture"),
            "compare_versions": self.tr("&Compare versions"),
            "corpus_check": self.tr("Check on &corpus..."),
            "toggle_timeline": self.tr("&Timeline"),
            "show_report": self.tr("Show &REPORT.md"),
            "export_markdown": self.tr("&Export Markdown..."),
            "export_html": self.tr("Export &HTML..."),
            "theme_dark": self.tr("&Dark theme"),
            "theme_light": self.tr("&Light theme"),
            "theme_system": self.tr("&System theme"),
            "zoom_in": self.tr("Zoom &in"),
            "zoom_in_alt": self.tr("Zoom in"),
            "zoom_out": self.tr("Zoom &out"),
            "zoom_reset": self.tr("&Reset zoom"),
            "settings": self.tr("&Settings..."),
            "start_learning": self.tr("Start the &interactive course"),
            "learning_centre": self.tr("Learning and &help..."),
            "toggle_learning_mode": self.tr("&Learning mode"),
            "show_guide": self.tr("Show the &start screen"),
            "quick_help": self.tr("&Quick help"),
            "about": self.tr("&About"),
        }
        for key, label in sources.items():
            action = self._actions.get(key)
            if action is not None:
                action.setText(label)
        for action, tip in self._action_tips.items():
            action.setToolTip(self.tr(tip))
            action.setStatusTip(self.tr(tip))
        self._actions["toggle_timeline"].setToolTip(
            self.tr("Show the fourth column: the message timeline against the journal")
        )
        system_label = self.tr("System")
        language_labels = {"ru": self.tr("Russian"), "en": self.tr("English")}
        for code, action in self._language_actions.items():
            action.setText(language_labels.get(code, system_label))

    def _build_central(self) -> None:
        # Two screens share the central area: the empty-state welcome screen and
        # the workspace. Only one is ever visible. A fresh window shows the welcome
        # screen alone; the workspace appears once a capture is open.
        self.welcome_view = WelcomeView()
        self.welcome_view.learningRequested.connect(self._start_course_from_welcome)
        self.welcome_view.demoRequested.connect(self.open_demo)
        self.welcome_view.capabilitiesRequested.connect(self.open_learning_centre)

        self.workspace = QtWidgets.QWidget()
        self._build_workspace(self.workspace)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self.welcome_view)
        self._stack.addWidget(self.workspace)
        self.setCentralWidget(self._stack)

    def _build_workspace(self, container: QtWidgets.QWidget) -> None:
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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
        self.direction_combo.setFont(theme.body_font(FONT_SIZE_BODY))
        self.direction_combo.currentTextChanged.connect(self._on_direction_changed)
        self._direction_label = QtWidgets.QLabel(self.tr("direction"))
        controls.addWidget(self._direction_label)
        controls.addWidget(self.direction_combo)
        controls.addStretch(1)
        centre_layout.addLayout(controls)

        # The byte-state legend is its own strip above the hex view, not a
        # widget beside the direction selector: a strip cannot overlap the
        # bytes or take width from the ASCII column, and it folds or collapses
        # when the window is narrow.
        self.annotation_legend = AnnotationLegend()
        self._legend_chips: list[QtWidgets.QLabel] = self.annotation_legend.chips
        centre_layout.addWidget(self.annotation_legend)

        self.hex_view = HexView()
        centre_layout.addWidget(self.hex_view, 1)
        self._bytes_box = self._wrap(self.tr("Bytes"), centre)
        splitter.addWidget(self._bytes_box)

        self.right_tabs = QtWidgets.QTabWidget()
        # The right dock is narrow and its captions are longer in Russian; elide
        # them and keep the full text in a tooltip rather than letting the bar
        # force the splitter wider than the panel can afford.
        self.right_tabs.setElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.right_tabs.setUsesScrollButtons(True)
        self.validation_view = ValidationView()
        self.right_tabs.addTab(self.validation_view, "")
        self.compare_view = CompareView()
        self.right_tabs.addTab(self.compare_view, "")
        self.hypotheses_view = HypothesesView()
        self.right_tabs.addTab(self.hypotheses_view, "")
        self.report_view = QtWidgets.QPlainTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setFont(theme.mono_font(FONT_SIZE_BODY))
        self.right_tabs.addTab(self.report_view, "")
        self.diff_view = QtWidgets.QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(theme.mono_font(FONT_SIZE_BODY))
        self.right_tabs.addTab(self.diff_view, "")
        self._relabel_tabs()
        splitter.addWidget(self.right_tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([260, 720, 460])

        # The timeline is the fourth column of the old layout. It is an advanced
        # view now: reachable from View - Timeline, hidden by default so the
        # primary workspace stays three columns wide.
        self.timeline_view = TimelineView()
        self.timeline_view.messageSelected.connect(self.reveal_offset)
        self._timeline_box = self._wrap(self.tr("Timeline"), self.timeline_view)
        self._timeline_box.setVisible(False)
        splitter.addWidget(self._timeline_box)
        splitter.setStretchFactor(3, 0)
        self._splitter = splitter

        # The tutor sits above the workspace: one lesson step at a time, with a
        # pointer at the element it describes. It is a view only; the window
        # wires each button to its own slot. The welcome screen remains the
        # first-run screen, so the two never compete.
        self.tutor_panel = TutorPanel()
        self.tutor_panel.backRequested.connect(self._learning_back)
        self.tutor_panel.nextRequested.connect(self._learning_next)
        self.tutor_panel.skipRequested.connect(self._learning_skip)
        self.tutor_panel.finishRequested.connect(self._learning_finish)
        self.tutor_panel.hideRequested.connect(self._learning_hide)
        self.tutor_panel.helpRequested.connect(self._learning_help)
        self.tutor_panel.setVisible(False)

        layout.addWidget(self.tutor_panel)
        layout.addWidget(splitter, 1)

        # The spotlight dims the workspace columns around the element a lesson
        # step names, so the target stands out on a busy window. It is bounded
        # by the splitter, so it never covers the tutor strip; the overlay is
        # transparent to the mouse, so the lit element stays clickable.
        self._spotlight = LearningSpotlight(container, bounds=splitter)

    def _wrap(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(widget)
        return box

    def _relabel_tabs(self) -> None:
        """Translate the right-hand tab captions in place.

        The captions are kept short so they fit the narrow dock without eliding;
        the full name is set as the tab tooltip, so nothing is lost on hover.
        """
        captions = (
            self.tr("Interpretation"),
            self.tr("Compare"),
            self.tr("Hypotheses"),
            self.tr("Report"),
            self.tr("Version diff"),
        )
        tooltips = (
            self.tr("Interpretation tab"),
            self.tr("Compare tab"),
            self.tr("Hypotheses tab"),
            self.tr("Report tab"),
            self.tr("Version diff tab"),
        )
        for index, (label, tip) in enumerate(zip(captions, tooltips, strict=False)):
            self.right_tabs.setTabText(index, label)
            self.right_tabs.setTabToolTip(index, tip)

    def _build_status(self) -> None:
        bar = self.statusBar()
        self._provenance_label = QtWidgets.QLabel()
        self._provenance_label.setFont(theme.body_font(FONT_SIZE_BODY))
        self._provenance_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        bar.addWidget(self._provenance_label, 1)
        self._set_provenance_text(self.tr("no byte selected"))
        self._progress = QtWidgets.QProgressBar()
        self._progress.setFixedWidth(PROGRESS_BAR_WIDTH)
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
        self.validation_view.buildRuleRequested.connect(self.build_rule)
        self.validation_view.ruleValidityChanged.connect(
            self.validation_view.show_rule_validity
        )
        self.validation_view.ruleValidityChanged.connect(self._on_rule_validity)
        self.validation_view.counterexampleSelected.connect(self._reveal_counterexample)
        self.hypotheses_view.messageSelected.connect(self.reveal_offset)

    def _toggle_timeline(self, visible: bool) -> None:
        """Show or hide the fourth column (the message timeline)."""
        self._timeline_box.setVisible(bool(visible))
        if visible:
            self._timeline_box.raise_()

    def _on_rule_validity(self, valid: bool, _message: str) -> None:
        """An edited rule is a new, unrun rule: its old verdict is not current.

        A rule that parses is adopted as the model so it can be run; a rule that
        does not is left in the editor and reported, with the data the reader
        typed preserved. Either way the previous verdict is cleared, so a stale
        "applied" mark is never shown against different bytes.
        """
        if self._rule_applied:
            self._rule_applied = False
            self.validation_view.clear()
            self.hex_view.set_annotations(None)
            self._update_guided()
        if not valid:
            return
        text = self.validation_view.rule_text().strip()
        if not text:
            return
        if self._rule is not None and self._rule.text.strip() == text:
            return
        try:
            model = RuleModel.from_text(text)
        except Exception:
            return
        if self._rule is not None:
            model.previous_rule = self._rule.rule
            model.previous_report = self._rule.corpus_report
        self._rule = model

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
        self.welcome_view.apply_theme()
        self.tutor_panel.apply_theme()
        self.annotation_legend.apply_theme()
        self.report_view.setFont(theme.mono_font(FONT_SIZE_BODY))
        self.diff_view.setFont(theme.mono_font(FONT_SIZE_BODY))

    # -- zoom --------------------------------------------------------------

    def set_legend_visible(self, visible: bool) -> None:
        """Show or hide the byte-state legend strip above the hex view."""
        self.annotation_legend.setVisible(bool(visible))

    def zoom_in(self) -> None:
        """Enlarge the bytes and the tree by one step."""
        self._zoom_step(1)

    def zoom_out(self) -> None:
        """Shrink the bytes and the tree by one step."""
        self._zoom_step(-1)

    def zoom_reset(self) -> None:
        """Restore the default byte and tree size."""
        self._set_zoom(
            int(DEFAULTS["editor"]["hex_font_size"]),
            int(DEFAULTS["editor"]["tree_font_size"]),
        )

    def _zoom_step(self, delta: int) -> None:
        """Move the byte font, carrying the tree with it at a fixed offset.

        The tree is derived from the byte size rather than stepped on its own,
        so repeated zooming cannot drift the two apart.
        """
        target = max(ZOOM_MIN_FONT, min(ZOOM_MAX_FONT, self.hex_view.font_size + delta))
        self._set_zoom(target, target - HEX_TREE_OFFSET)

    def _set_zoom(self, hex_size: int, tree_size: int) -> None:
        """Apply a byte and tree font size, clamped and reflected in the menu."""
        hex_size = max(ZOOM_MIN_FONT, min(ZOOM_MAX_FONT, int(hex_size)))
        tree_size = max(TREE_MIN_FONT, min(TREE_MAX_FONT, int(tree_size)))
        if (hex_size, tree_size) == (
            self.hex_view.font_size,
            self.session_tree.font_size,
        ):
            return
        self.hex_view.set_font_size(hex_size)
        self.session_tree.set_font_size(tree_size)
        # Keep the settings mapping and the store in step so a later settings
        # round-trip does not snap the zoom back to a stale size.
        editor = self._settings.setdefault("editor", {})
        editor["hex_font_size"] = hex_size
        editor["tree_font_size"] = tree_size
        store = QtCore.QSettings(ORGANISATION, APPLICATION)
        store.setValue("editor/hex_font_size", hex_size)
        store.setValue("editor/tree_font_size", tree_size)
        self._update_zoom_actions()
        self._notify(
            self.tr("zoom {0}%").format(
                round(hex_size / int(DEFAULTS["editor"]["hex_font_size"]) * 100)
            )
        )

    def _update_zoom_actions(self) -> None:
        """Disable the zoom actions that would have no effect at a limit."""
        size = self.hex_view.font_size
        if "zoom_in" in self._actions:
            self._actions["zoom_in"].setEnabled(size < ZOOM_MAX_FONT)
            self._actions["zoom_out"].setEnabled(size > ZOOM_MIN_FONT)

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
            if (
                self._language_manager is None
                or self._language_manager.preference != language
            ):
                self.set_language(language)

        self.hex_view.set_font_size(
            int(editor.get("hex_font_size", DEFAULTS["editor"]["hex_font_size"]))
        )
        self.hex_view.set_show_offset(bool(editor.get("show_offset", True)))
        self.session_tree.set_font_size(
            int(editor.get("tree_font_size", DEFAULTS["editor"]["tree_font_size"]))
        )
        self.hex_view.set_show_diagnostics(bool(advanced.get("show_diagnostics", True)))
        self.set_legend_visible(bool(advanced.get("show_legend", True)))
        self.set_guided_mode(
            bool(general.get("guided_mode", DEFAULTS["general"]["guided_mode"]))
        )

        level = str(advanced.get("log_level", "INFO"))
        if level in logging.getLevelNamesMapping():
            logging.getLogger().setLevel(level)

        self._update_zoom_actions()

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
        self.annotation_legend.retranslate_ui()
        self.validation_view.retranslate_ui()
        self.compare_view.retranslate_ui()
        self.hypotheses_view.retranslate_ui()
        self.session_tree.retranslate_ui()
        self.hex_view.retranslate_ui()
        self.timeline_view.retranslate_ui()
        self._timeline_box.setTitle(self.tr("Timeline"))
        self.welcome_view.retranslate_ui()
        self.tutor_panel.retranslate_ui()
        self._refresh_rule_status()
        # The empty-state hint is built text, so a language change must rebuild
        # it; without this it stays in the language it was created in.
        if self._capture is None:
            self._show_empty_state()
        if self._capture is not None and self._last_offset is not None:
            self._show_provenance(self._last_offset)
        else:
            self._set_provenance_text(self._capture_summary())

    def _refresh_title(self) -> None:
        """Set the window title, including the open project and capture names."""
        parts = [self._base_title]
        if self._project_path is not None:
            parts.append(self._project_path.name)
        if self._capture_name:
            parts.append(self._capture_name)
        self.setWindowTitle(" - ".join(parts))

    def _capture_summary(self) -> str:
        """The status-line summary of the open capture, in the active language."""
        if self._capture is None:
            return self.tr("no byte selected")
        diagnostics = ", ".join(
            f"{d.type}@{d.offset}" for d in self._capture.diagnostics
        ) or self.tr("none")
        return self.tr("{0} sessions  capture_id {1}  diagnostics {2}").format(
            len(self._capture.sessions), self._capture.capture_id[:19], diagnostics
        )

    # -- loading -----------------------------------------------------------

    def open_capture(self, path: str | Path) -> None:
        """Load a normalized capture and select its first direction.

        Raises :class:`CaptureModelError` when the file is neither normalized
        JSON nor a pcap/pcapng; the callers decide how to report it, so the
        window itself never blocks on a dialog.
        """
        model = CaptureModel.from_file(path)
        self._capture = model
        self.session_tree.load(model)
        self._capture_name = Path(path).name
        self._refresh_title()
        self._set_provenance_text(self._capture_summary())
        # A new capture invalidates every verdict taken against the previous one:
        # the rule stays loaded, but it has not been run here yet, so no stale
        # result is left on screen.
        self._rule_applied = False
        self._corpus_report = None
        if self._rule is not None:
            self._rule.corpus_report = None
            self._rule.root = None
        self._clear_results()
        if model.sessions:
            self._on_direction_selected(
                model.sessions[0].session_id,
                model.directions(model.sessions[0].session_id)[0],
            )
        self._show_workspace()
        self._refresh_welcome_progress()
        self.validation_view.set_ready(capture=True, rule=self._rule is not None)
        self._update_guided()

    def _clear_results(self) -> None:
        """Drop the message and counterexample views of a previous capture."""
        self.validation_view.clear()
        self.compare_view.clear()
        self.hypotheses_view.clear()

    # -- learning mode -----------------------------------------------------

    def _learning_state(self, name: str) -> bool:
        """Whether the named completion condition currently holds.

        The course advances on these, not on button presses: a step whose
        condition is already true is not repeated, and a step whose condition is
        false cannot be passed with Next. The conditions read the window's own
        state, so no second model of the application is kept for the course.
        """
        if name == "capture_open":
            return self._capture is not None
        if name == "direction_chosen":
            return bool(self._session_id and self._direction)
        if name == "byte_selected":
            return self._last_offset is not None
        if name == "compare_open":
            return self.right_tabs.currentWidget() is self.compare_view
        if name == "rule_open":
            return self._rule is not None
        if name == "rule_applied":
            return bool(self._rule_applied)
        if name == "corpus_applied":
            return self._corpus_report is not None
        return False

    def _current_lesson(self) -> learning.Lesson:
        """The lesson the tutor is on."""
        return learning.LESSON_BY_KEY.get(
            self._learning_lesson, learning.LESSONS[0]
        )

    def _update_learning(self) -> None:
        """Show the tutor at the current lesson step, or hide it.

        The tutor is visible only while it is active and the expert mode is on
        for hints; in the expert mode nothing is shown. Within a lesson, if the
        reader has already reached a later step's condition, the tutor moves to
        it rather than making them repeat what is done.
        """
        if not (self._guided_enabled and self._learning_active):
            self.tutor_panel.setVisible(False)
            return
        lesson = self._current_lesson()
        step = lesson.steps[self._learning_step]
        while (
            step.requires is not None
            and self._learning_state(step.requires)
            and self._learning_step + 1 < len(lesson.steps)
        ):
            self._learning_step += 1
            step = lesson.steps[self._learning_step]
        done = step.requires is None or self._learning_state(step.requires)
        self.tutor_panel.show_step(lesson, self._learning_step, done)
        self.tutor_panel.setVisible(True)
        self._point_at(step)

    def start_learning(self, lesson_key: str | None = None) -> None:
        """Start or resume the course, optionally at a chosen lesson."""
        self._learning_active = True
        if isinstance(lesson_key, str) and lesson_key in learning.LESSON_BY_KEY:
            self._learning_lesson = lesson_key
            self._learning_step = 0
        self._update_learning()
        self.tutor_panel.raise_()

    def _start_course_from_welcome(self) -> None:
        """The first-run path: load the example, then start the course.

        The course teaches on real data, so the example is opened first; the
        reader is not asked to find a file before the first lesson.
        """
        if self._capture is None:
            self.open_demo()
        self.start_learning(learning.LESSONS[0].key)

    def _learning_next(self) -> None:
        """Advance one step, running the step's action when it offers one."""
        lesson = self._current_lesson()
        step = lesson.steps[self._learning_step]
        if step.requires is not None and not self._learning_state(step.requires):
            # The reader has not done what the step asks: offer the action and
            # say so rather than moving on silently.
            if not self._learning_offer(step):
                self._notify(self.tr("finish this step first, or use Skip"))
            self._update_learning()
            return
        if self._learning_step + 1 < len(lesson.steps):
            self._learning_step += 1
            self._update_learning()
            return
        # The lesson is finished: record it and move to the next one, or leave
        # the course when this was the last lesson.
        self._complete_current_lesson()
        index = learning.lesson_index(self._learning_lesson)
        if index + 1 < len(learning.LESSONS):
            self._learning_lesson = learning.LESSONS[index + 1].key
            self._learning_step = 0
            self._update_learning()
        else:
            self._learning_finish()

    def _learning_offer(self, step: learning.Step) -> bool:
        """Run the action a step offers, if it has one; return whether it did."""
        show = step.show_me
        if show == "open_demo":
            self.open_demo()
        elif show == "select_direction":
            self._select_first_direction()
        elif show == "build_rule":
            self.build_rule()
        elif show == "apply_rule":
            self.apply_rule()
        elif show == "apply_to_capture":
            self.apply_to_capture()
        elif show == "show_compare":
            self.right_tabs.setCurrentWidget(self.compare_view)
        else:
            return False
        return True

    def _select_first_direction(self) -> None:
        """Pick the first session and its first direction, as the course asks."""
        if self._capture is None or not self._capture.sessions:
            return
        session = self._capture.sessions[0]
        directions = self._capture.directions(session.session_id)
        if directions:
            self.session_tree.select_direction(session.session_id, directions[0])

    def _learning_back(self) -> None:
        """Return to the previous step, or the previous lesson at the first."""
        if self._learning_step > 0:
            self._learning_step -= 1
            self._update_learning()
            return
        index = learning.lesson_index(self._learning_lesson)
        if index > 0:
            previous = learning.LESSONS[index - 1]
            self._learning_lesson = previous.key
            self._learning_step = len(previous.steps) - 1
            self._update_learning()

    def _learning_skip(self) -> None:
        """Skip the rest of the current lesson and go to the next one."""
        self._complete_current_lesson()
        index = learning.lesson_index(self._learning_lesson)
        if index + 1 < len(learning.LESSONS):
            self._learning_lesson = learning.LESSONS[index + 1].key
            self._learning_step = 0
            self._update_learning()
        else:
            self._learning_finish()

    def _learning_finish(self) -> None:
        """Finish the course and leave the tutor."""
        self._complete_current_lesson()
        self._learning_active = False
        self.tutor_panel.setVisible(False)
        self._clear_pointer()
        self._notify(self.tr("course finished"))

    def _learning_hide(self) -> None:
        """Hide the tutor without losing the position in the course."""
        self._learning_active = False
        self.tutor_panel.setVisible(False)
        self._clear_pointer()

    def _complete_current_lesson(self) -> None:
        """Record the current lesson as done and persist the progress."""
        self._completed_lessons.add(self._learning_lesson)
        self._settings.setdefault("learning", {})["completed"] = ",".join(
            sorted(self._completed_lessons)
        )
        write_settings(self._settings)

    def reset_learning(self) -> None:
        """Forget the course progress; the reader's work is untouched."""
        self._completed_lessons = set()
        self._learning_lesson = learning.LESSONS[0].key
        self._learning_step = 0
        self._settings.setdefault("learning", {})["completed"] = ""
        write_settings(self._settings)
        self._update_learning()

    def _learning_help(self, target: str) -> None:
        """Open the reference card for the element a step points at."""
        key = _HELP_TARGETS.get(target)
        if key:
            self.show_help_for(key)

    # -- contextual help ---------------------------------------------------

    def show_help_for(self, key: str) -> None:
        """Show the reference card for *key*, reusing the open card."""
        entry = reference.lookup(key)
        if entry is None:
            return
        if self._help_card is None:
            self._help_card = HelpCard(entry, self)
        else:
            self._help_card.set_entry(entry)
        self._help_card.show()
        self._help_card.raise_()

    def open_learning_centre(self) -> None:
        """Open the learning centre, reusing the open one."""
        if self._learning_centre is None:
            self._learning_centre = LearningCentre(
                completed=self._completed_lessons,
                current_lesson=self._learning_lesson,
                parent=self,
            )
            self._learning_centre.lessonChosen.connect(self.start_learning)
            self._learning_centre.resetRequested.connect(self.reset_learning)
            self._learning_centre.helpRequested.connect(self.show_help_for)
        else:
            self._learning_centre._completed = set(self._completed_lessons)
            self._learning_centre._current = self._learning_lesson
            self._learning_centre.retranslate_ui()
        self._learning_centre.show()
        self._learning_centre.raise_()

    # -- the pointer -------------------------------------------------------

    def _point_at(self, step: learning.Step) -> None:
        """Outline and light the element a step describes, when it names one.

        The element is outlined with the accent property and, on the workspace
        columns, spotlit: the rest is dimmed so the target stands out. A step
        with no target clears both.
        """
        self._clear_pointer()
        widget = self._pointer_targets().get(step.target or "")
        if widget is None:
            return
        widget.setProperty("learningPointer", True)
        self._repolish(widget)
        self._spotlight.set_target(widget)
        self._pointer_clear.start()

    def _clear_pointer(self) -> None:
        """Remove the outline from every element it could have been set on."""
        self._spotlight.clear()
        for widget in self._pointer_targets().values():
            if widget.property("learningPointer"):
                widget.setProperty("learningPointer", False)
                self._repolish(widget)

    def _pointer_targets(self) -> dict[str, QtWidgets.QWidget]:
        """The elements a lesson step can point at, by the name a step uses."""
        return {
            "sessions_box": self._sessions_box,
            "hex_view": self.hex_view,
            "right_tabs": self.right_tabs,
            "status_bar": self.statusBar(),
            "direction_combo": self.direction_combo,
            "validation_view": self.validation_view,
            "session_tree": self.session_tree,
        }

    @staticmethod
    def _repolish(widget: QtWidgets.QWidget) -> None:
        """Re-apply the style sheet so a dynamic property takes effect."""
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    # -- hints (the former guided mode) ------------------------------------

    def _update_guided(self) -> None:
        """Keep the hint preference and the tutor in step."""
        self._update_learning()

    def set_guided_mode(self, enabled: bool) -> None:
        """Show or hide the hints, and remember the choice in the settings."""
        self._guided_enabled = bool(enabled)
        self._settings.setdefault("general", {})["guided_mode"] = self._guided_enabled
        write_settings(self._settings)
        action = self._actions.get("toggle_learning_mode")
        if action is not None and action.isChecked() != self._guided_enabled:
            # Keep the menu check in step without re-entering through toggled.
            action.blockSignals(True)
            action.setChecked(self._guided_enabled)
            action.blockSignals(False)
        self._update_learning()
        if self._guided_enabled and self._learning_active:
            self.tutor_panel.raise_()

    def open_demo(self) -> None:
        """Open the small capture, rule and journal that ship with the tool.

        This is the one-click path for a first-time reader: a real investigation
        appears without them having to find a file or write a rule. A missing
        sample is reported rather than silently ignored.
        """
        if not SAMPLE_CAPTURE.is_file():
            self._notify(self.tr("the built-in demo is not available"))
            return
        self.open_capture(SAMPLE_CAPTURE)
        if SAMPLE_RULE.is_file():
            self.load_rule(SAMPLE_RULE)
        if SAMPLE_JOURNAL.is_file():
            self.load_journal(SAMPLE_JOURNAL)
        # The direction run fills the Messages table and the hex annotations;
        # the corpus run then adds the whole-capture counterexamples without
        # touching either. Running only the corpus pass would leave the demo on
        # the empty Messages state while the rule had in fact been applied.
        self.apply_rule()
        self.apply_to_capture()
        self._notify(self.tr("opened the built-in demo"))

    def load_journal(self, path: str | Path) -> None:
        """Load an action journal and line it up with the current messages.

        The journal is the operator's own note of what they did. Pairing it with
        the decoded messages is what turns a value on the wire into evidence for
        a field's meaning, so it is offered as a first-class action.
        """
        from ..hypothesis.journal import correlate
        from ..hypothesis.journal import load_journal as _load

        if self._capture is None or self._rule is None:
            self._notify(self.tr("open a capture and a rule before a journal"))
            return
        try:
            entries = _load(path)
        except Exception as exc:
            self._notify(self.tr("could not read the journal: {0}").format(exc))
            return
        self._journal = entries
        report = correlate(self._corpus_messages(()), entries)
        self.timeline_view.show_correlation(report)
        self._notify(self.tr("journal: {0}").format(report.summary()))

    def open_journal_dialog(self) -> None:
        """Prompt for an action journal and load it."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Open action journal"),
            self._start_dir(SAMPLE_DIR),
            "Journals (*.txt *.csv *.md);;All files (*)",
        )
        if path:
            self._remember_dir(path)
            self.load_journal(path)

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
            self,
            self.tr("Open capture"),
            self._start_dir(REPO_ROOT),
            "Captures (*.json *.pcap *.pcapng)",
        )
        if path:
            self._remember_dir(path)
            self._open_capture_reported(path)

    def _open_capture_reported(self, path: str | Path) -> None:
        """Open a capture from a dialog, reporting a bad file in a message box."""
        try:
            self.open_capture(path)
        except CaptureModelError as exc:
            QtWidgets.QMessageBox.warning(
                self, self.tr("Cannot open capture"), str(exc)
            )

    def import_pcap(self) -> None:
        """Read a raw capture, write its normalized JSON, then open it.

        Opening a pcap directly normalizes it in memory only; this action also
        keeps the normalized document, which is the form the rest of the
        pipeline and the project work with. The output name is derived from the
        input file, never hard-coded.
        """
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Import PCAP"),
            self._start_dir(REPO_ROOT),
            "Captures (*.pcap *.pcapng)",
        )
        if not path:
            return
        self._remember_dir(path)
        source = Path(path)
        out = source.with_name(f"{source.stem}.normalized.json")
        try:
            from ..capture.export import export_capture
            from ..capture.pipeline import normalize

            capture = normalize(source)
            export_capture(
                capture.sessions,
                out,
                source_file=str(capture.source_file),
                capture_id=capture.capture_id,
                streams=capture.streams,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, self.tr("Cannot import capture"), str(exc)
            )
            return
        self._open_capture_reported(out)
        self._notify(self.tr("wrote {0}").format(out.name))

    def load_rule(self, path: str | Path) -> None:
        """Load a rule file, keeping the previous rule and report for diffing."""
        previous_rule = self._rule.rule if self._rule is not None else None
        previous_report = self._rule.corpus_report if self._rule is not None else None
        self._rule = RuleModel.from_file(path)
        self._rule.previous_rule = previous_rule
        self._rule.previous_report = previous_report
        # A freshly loaded rule has not been run against this capture yet, so the
        # previous verdict is not the current one.
        self._rule_applied = False
        self.validation_view.set_rule_text(self._rule.text)
        self._set_rule_status(
            lambda: self.tr("loaded {0}  rule v{1}").format(
                self._rule.path.name if self._rule.path else "",
                self._rule.rule.rule_version,
            )
        )
        self.validation_view.set_rule_overview(self._rule.rule, applied=False)
        self._refresh_welcome_progress()
        self.validation_view.set_ready(capture=self._capture is not None, rule=True)
        self._update_guided()

    # -- portable project --------------------------------------------------

    def new_project_dialog(self) -> None:
        """Ask for a directory and name, then create a project there."""
        if not self._confirm_discard_unsaved():
            return
        parent = QtWidgets.QFileDialog.getExistingDirectory(
            self, self.tr("Choose a folder for the project"), self._output_dir(REPO_ROOT)
        )
        if not parent:
            return
        name, accepted = QtWidgets.QInputDialog.getText(
            self, self.tr("New project"), self.tr("Project name:")
        )
        if not accepted:
            return
        name = name.strip()
        if not name:
            self._notify(self.tr("a project name is required"))
            return
        target = Path(parent) / _slug(name)
        try:
            project = Project.create(target, name)
        except (ProjectError, ManifestError) as exc:
            self._report_error(self.tr("could not create the project"), exc)
            return
        self._remember_dir(target)
        self._adopt_project(project)
        self._notify(self.tr("created project {0}").format(target.name))

    def open_project_dialog(self) -> None:
        """Ask for a project directory and open it without losing the current one."""
        if not self._confirm_discard_unsaved():
            return
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, self.tr("Open project"), self._output_dir(REPO_ROOT)
        )
        if not path:
            return
        try:
            project = Project.open(path)
        except (ProjectError, ManifestError) as exc:
            # A failed open leaves the window on the project it already had, so a
            # mistyped folder never costs the researcher the open investigation.
            self._report_error(self.tr("could not open the project"), exc)
            return
        self._remember_dir(path)
        self._adopt_project(project)
        self._notify(self.tr("opened project {0}").format(project.name))

    def save_project(self) -> None:
        """Write the open project's manifest back to disk."""
        if self._project is None:
            self._notify(self.tr("no project is open"))
            return
        try:
            self._project.save()
        except OSError as exc:
            self._report_error(self.tr("could not save the project"), exc)
            return
        self._refresh_title()
        self._notify(self.tr("saved project {0}").format(self._project.name))

    def add_capture_to_project_dialog(self) -> None:
        """Copy a capture file into the open project and register it."""
        if self._project is None:
            self._notify(self.tr("open or create a project first"))
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Add capture"),
            self._start_dir(REPO_ROOT),
            "Captures (*.pcap *.pcapng *.json)",
        )
        if not path:
            return
        self._remember_dir(path)
        try:
            relative = self._project.add_capture(Path(path))
            self._project.save()
        except (ProjectError, OSError) as exc:
            self._report_error(self.tr("could not add the capture"), exc)
            return
        self._notify(self.tr("added {0} to the project").format(relative))

    def save_rule_version_dialog(self) -> None:
        """Name the current rule version and store it.

        With a project open the version is copied into ``rules/`` and recorded
        in the manifest by the project API, which never overwrites an existing
        version. Without one the researcher picks a file to write. The name is
        carried in the rule document itself, so it survives in the report and
        the version list.
        """
        rule = self._current_rule()
        if rule is None:
            self._notify(self.tr("open or build a rule first"))
            return
        default = rule.rule.name or rule.rule.rule_id
        name, accepted = QtWidgets.QInputDialog.getText(
            self, self.tr("Save rule version"), self.tr("Version name:"), text=default
        )
        if not accepted:
            return
        name = name.strip()
        if not name:
            self._notify(self.tr("a version name is required"))
            return
        named = rule.rule if name == rule.rule.name else rule.rule.bump_version(name=name)
        if self._project is None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                self.tr("Save rule version"),
                self._output_dir(REPO_ROOT) + f"/{_slug(name)}.json",
                "JSON (*.json)",
            )
            if not path:
                return
            self._remember_dir(path)
            self._write_rule_file(named, Path(path))
            return
        temporary = Path(tempfile.mkdtemp()) / f"{_slug(name)}.json"
        try:
            self._write_rule_file(named, temporary)
            relative = self._project.add_rule(
                temporary, named.rule_id, named.rule_version
            )
            self._project.save()
        except (ProjectError, OSError) as exc:
            self._report_error(self.tr("could not save the rule version"), exc)
            return
        self._notify(self.tr("saved {0}").format(relative))

    def _write_rule_file(self, rule, path: Path) -> None:
        """Write ``rule`` to ``path`` and adopt it as the current rule."""
        from ..protocol.rule import save_rule

        try:
            save_rule(rule, path)
        except OSError as exc:
            self._report_error(self.tr("could not save the rule version"), exc)
            return
        if self._rule is not None:
            self._rule.rule = rule
            self._rule.text = rule_text(rule)
            self.validation_view.set_rule_text(self._rule.text)
        self._notify(self.tr("wrote {0}").format(path))

    def export_project_dialog(self) -> None:
        """Write the open project to a zip archive."""
        if self._project is None:
            self._notify(self.tr("no project is open"))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self.tr("Export project"),
            self._output_dir(REPO_ROOT) + f"/{self._project.name}.zip",
            "Zip (*.zip)",
        )
        if not path:
            return
        self._remember_dir(path)
        try:
            self._project.export(Path(path))
        except OSError as exc:
            self._report_error(self.tr("could not export the project"), exc)
            return
        self._notify(self.tr("wrote {0}").format(path))

    def import_project_dialog(self) -> None:
        """Unpack a project archive into a new directory and open it."""
        if not self._confirm_discard_unsaved():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Import project"),
            self._output_dir(REPO_ROOT),
            "Zip (*.zip)",
        )
        if not path:
            return
        parent = QtWidgets.QFileDialog.getExistingDirectory(
            self, self.tr("Choose a folder for the project"), str(Path(path).parent)
        )
        if not parent:
            return
        target = Path(parent) / _slug(Path(path).stem)
        try:
            project = Project.import_(Path(path), target)
        except (ProjectError, ManifestError) as exc:
            self._report_error(self.tr("could not import the project"), exc)
            return
        self._remember_dir(target)
        self._adopt_project(project)
        self._notify(self.tr("imported project {0}").format(project.name))

    def _adopt_project(self, project: Project) -> None:
        """Make ``project`` the open project and reflect it in the title."""
        self._project = project
        self._project_path = project.root
        self._refresh_title()

    def _confirm_discard_unsaved(self) -> bool:
        """Ask before leaving a project whose manifest has uncommitted edits.

        Returns ``True`` when the caller may proceed. A window with no open
        project, or one whose in-memory manifest matches the file on disk,
        proceeds without a dialog, so the common path is not interrupted.
        """
        if self._project is None:
            return True
        if not self._project_is_dirty():
            return True
        answer = QtWidgets.QMessageBox.question(
            self,
            self.tr("Unsaved project changes"),
            self.tr(
                "The open project has changes that were not saved. "
                "Save them before continuing?"
            ),
            QtWidgets.QMessageBox.StandardButton.Save
            | QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Save,
        )
        if answer == QtWidgets.QMessageBox.StandardButton.Cancel:
            return False
        if answer == QtWidgets.QMessageBox.StandardButton.Save:
            self.save_project()
        return True

    def _project_is_dirty(self) -> bool:
        """Whether the open project's manifest differs from the file on disk."""
        if self._project is None:
            return False
        path = self._project.path("manifest.json")
        try:
            on_disk = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return True
        return on_disk != self._project.manifest.to_dict()

    def _report_error(self, headline: str, exc: Exception) -> None:
        """Show a failed operation with its reason, and mirror it in the status."""
        self._notify(f"{headline}: {exc}")
        QtWidgets.QMessageBox.warning(self, headline, str(exc))

    def _current_rule(self) -> RuleModel | None:
        """The rule to run: the loaded model, or the text the editor holds.

        A rule built in the form or typed in the editor is a document, not a
        file. Adopting it here is what keeps "apply" from silently doing nothing
        when no rule file was ever opened. The previous run is carried over so a
        re-edit still shows the diff against it.
        """
        if self._rule is not None:
            return self._rule
        text = self.validation_view.rule_text().strip()
        if not text:
            return None
        try:
            model = RuleModel.from_text(text)
        except Exception as exc:
            self.validation_view.set_rule_status(
                self.tr("rule error: {0}").format(exc), error=True
            )
            return None
        self._rule = model
        return model

    def build_rule(self) -> None:
        """Open the form-based rule builder, seeded with the current rule.

        The builder works on the document, so a rule already loaded is offered for
        editing rather than forcing a rewrite from an empty form, and the bytes of
        the message under the cursor are shown beside the form.
        """
        from .rule_builder import RuleBuilderDialog

        seed = None
        text = self.validation_view.rule_text().strip()
        if text:
            try:
                seed = load_rule_text(text)
            except Exception:
                seed = None
        dialog = RuleBuilderDialog(seed, self, message=self._current_message_bytes())
        dialog.setFont(theme.body_font(FONT_SIZE_BODY))
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        text = dialog.rule_text()
        try:
            model = RuleModel.from_text(text)
        except Exception as exc:
            # Keep what the form produced so the reader can fix it by hand; the
            # error is reported beside the editor rather than thrown away.
            self.validation_view.set_rule_text(text)
            self._set_rule_status(
                lambda exc=exc: self.tr("rule error: {0}").format(exc), error=True
            )
            return
        # The built rule becomes the current model, so "apply" has something to
        # run instead of reporting that no rule is loaded.
        if self._rule is not None:
            model.previous_rule = self._rule.rule
            model.previous_report = self._rule.corpus_report
        self._rule = model
        self._rule_applied = False
        self.validation_view.set_rule_text(text)
        self.validation_view.set_rule_overview(model.rule, applied=False)
        self._set_rule_status(lambda: self.tr("rule built; apply it to check it"))
        self._refresh_welcome_progress()
        self._update_guided()

    def _current_message_bytes(self) -> bytes:
        """The bytes of the message the last-clicked byte belongs to, or a slice.

        The wizard shows the message a researcher is looking at. When a rule has
        been applied the message under the cursor is used; before that, or when
        the click falls outside a message, the first bytes of the stream are shown
        so the pane is never empty.
        """
        if self._capture is None:
            return b""
        stream = self._capture.stream(self._session_id, self._direction)
        message = self._message_at(self._last_offset)
        if message is not None:
            start = message[1].offset
            return stream.data[start : start + message[1].length]
        return stream.data[:256]

    def open_rule_dialog(self) -> None:
        """Prompt for a rule file and load it."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Open rule"),
            self._start_dir(REPO_ROOT / "examples"),
            "Rules (*.json *.yaml *.yml)",
        )
        if path:
            self._remember_dir(path)
            self.load_rule(path)

    def load_example_rule(self) -> None:
        """Load the first example rule, or report that none is present."""
        examples = sorted((REPO_ROOT / "examples").glob("*.json"))
        if not examples:
            self._set_rule_status(
                lambda: self.tr("no example rule found"), error=True
            )
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
        self._refresh_welcome_progress()
        self._render_stream()
        self._update_guided()

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
        """Adopt the edited rule and apply it to the current direction.

        The rule that runs is the loaded model or the text the editor holds; a
        built or typed rule becomes the model here, so the action always has
        something to run rather than reporting that no rule is loaded.
        """
        if self._capture is None:
            self._notify(self.tr("open a capture first"))
            return
        rule = self._current_rule()
        if rule is None:
            self._notify(self.tr("open or build a rule first"))
            return
        try:
            rule.reload(self.validation_view.rule_text())
        except Exception as exc:
            self._set_rule_status(
                lambda exc=exc: self.tr("rule error: {0}").format(exc), error=True
            )
            return
        application = rule.apply(self._capture, self._session_id, self._direction)
        self.validation_view.show_application(application)
        self.compare_view.show_application(application)
        self._show_hypotheses(rule.rule, application.messages)
        self.validation_view.set_rule_overview(rule.rule, applied=True)
        self._rule_applied = True
        stream = self._capture.stream(self._session_id, self._direction)
        self.hex_view.set_annotations(annotations_from_application(application, stream))
        counts = ", ".join(f"{k}={v}" for k, v in sorted(application.counts.items()))
        self._set_rule_status(
            lambda counts=counts: self.tr("rule v{0}  {1}").format(
                application.rule.rule_version, counts
            )
        )
        self._notify(
            self.tr("applied rule v{0} to {1} {2}").format(
                application.rule.rule_version, self._session_id, self._direction
            )
        )
        self._update_guided()

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
        if self._capture is None:
            self._notify(self.tr("open a capture first"))
            return
        rule = self._current_rule()
        if rule is None:
            self._notify(self.tr("open or build a rule first"))
            return
        try:
            rule.reload(self.validation_view.rule_text())
        except Exception as exc:
            self._set_rule_status(
                lambda exc=exc: self.tr("rule error: {0}").format(exc), error=True
            )
            return
        self._begin_run()
        self._set_progress(20)
        report = verify_rule_on_corpus(rule.rule, self._capture)
        self._set_progress(100)
        self._end_run()
        if (
            rule.previous_report is not None
            and rule.previous_report.rule_id == report.rule_id
        ):
            self._show_report_diff(rule.previous_report, report)
        rule.corpus_report = report
        self._corpus_report = report
        self._rule_applied = True
        self.validation_view.show_corpus_report(report)
        self.validation_view.set_rule_overview(rule.rule, applied=True)
        directions = (rule.rule.direction,) if rule.rule.direction else ()
        self._show_hypotheses(rule.rule, self._corpus_messages(directions))
        counts = ", ".join(f"{k}={v}" for k, v in sorted(report.counts().items()))
        self._set_rule_status(
            lambda counts=counts, report=report: self.tr(
                "rule v{0} over the capture: {1}  counterexamples={2}"
            ).format(
                rule.rule.rule_version, counts, len(report.contradictions)
            )
        )
        self._notify(
            self.tr("verified rule over the whole capture: {0}").format(counts)
        )
        self._update_guided()

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

    def _reveal_counterexample(
        self, session_id: str, direction: str, offset: int, length: int = 1
    ) -> None:
        """Jump to a counterexample, switching session or direction if needed.

        A corpus counterexample can live in a direction other than the one on
        screen, so the tree selection is moved first, then the message bytes are
        highlighted as a block.
        """
        if (
            session_id
            and direction
            and (session_id != self._session_id or direction != self._direction)
        ):
            self.session_tree.select_direction(session_id, direction)
        self.hex_view.highlight_range(offset, length)
        self._show_provenance(offset)

    def _on_byte_clicked(self, offset: int) -> None:
        self._last_offset = offset
        self._show_provenance(offset)
        # A lesson step that waits for a byte selection completes here.
        if self._learning_active:
            self._update_learning()

    def _on_byte_hovered(self, offset: int) -> None:
        self._last_offset = offset
        self._show_provenance(offset)

    def _show_provenance(self, offset: int) -> None:
        if self._capture is None:
            return
        self._last_offset = offset
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
        self._set_provenance_text("   ".join(str(p) for p in parts))
        self.validation_view.set_provenance(self._provenance_chain(offset))

    def _provenance_chain(self, offset: int) -> list[str]:
        """The chain from a byte back to its packet, for the inspector card.

        Reads top to bottom as the interpretation narrows: the value the rule
        assigned, the message it belongs to, the bytes it covers, the packet the
        bytes arrived in, the session and the capture file.
        """
        if self._capture is None:
            return []
        annotation = self.hex_view.annotation_at(offset)
        lines: list[str] = []
        if annotation is not None and annotation.value is not None:
            lines.append(f"value = {annotation.value}")
        message = self._message_at(offset)
        if message is not None:
            lines.append(self.tr("<- message #{0}").format(message[0]))
            lines.append(
                self.tr("<- bytes {0}..{1}").format(
                    message[1].offset, message[1].offset + message[1].length - 1
                )
            )
        stream = self._capture.stream(self._session_id, self._direction)
        for hole in stream.provenance:
            if hole.offset <= offset < hole.end:
                lines.append(self.tr("<- packet #{0}").format(hole.packet_index))
                break
        info = self._capture.session(self._session_id)
        endpoints = info.endpoints if info is not None else self._session_id
        lines.append(
            self.tr("<- session {0} ({1})").format(self._session_id, endpoints)
        )
        if self._capture_name:
            lines.append(self.tr("<- {0}").format(self._capture_name))
        return lines

    def _message_at(self, offset: int | None) -> tuple[int, object] | None:
        """The message whose range contains ``offset``, with its 1-based index.

        ``offset`` is unset until a byte is clicked. There is no message to find
        then, so an unset offset is treated the same as one that falls outside
        every message rather than dereferenced.
        """
        if offset is None or self._rule is None or self._rule.root is None:
            return None
        for index, message in enumerate(self._rule.root.messages, start=1):
            if message.offset is None:
                continue
            if message.offset <= offset < message.offset + message.length:
                return index, message
        return None

    def _show_corpus_dialog(self, report) -> None:
        """Open the corpus-check dialog on *report*, or refresh the open one."""
        from .corpus_dialog import CorpusDialog

        if self._corpus_dialog is None:
            self._corpus_dialog = CorpusDialog(self)
            self._corpus_dialog.counterexampleSelected.connect(
                self._reveal_counterexample
            )
            self._corpus_dialog.exportReportRequested.connect(self.export_markdown)
        self._corpus_dialog.show_report(report, len(self._capture.sessions))
        self._corpus_dialog.show()
        self._corpus_dialog.raise_()

    def show_corpus_check(self) -> None:
        """Show the corpus-check dialog for the last run, if there is one."""
        if self._corpus_report is None:
            self._notify(self.tr("apply the rule to the whole capture first (F6)"))
            return
        self._show_corpus_dialog(self._corpus_report)

    def _set_rule_status(self, render: Callable[[], str], error: bool = False) -> None:
        """Show a rule-status line built by ``render`` in the active language.

        ``render`` is kept so the line can be rebuilt on a language switch; the
        window never stores the finished string alone.
        """
        self._rule_status_render = render
        self._rule_status_error = error
        self.validation_view.set_rule_status(render(), error=error)

    def _refresh_rule_status(self) -> None:
        """Rebuild the rule-status line in the active language, if there is one."""
        if self._rule_status_render is not None:
            self.validation_view.set_rule_status(
                self._rule_status_render(), error=self._rule_status_error
            )

    def _set_provenance_text(self, text: str) -> None:
        """Show *text* on the status line, reserving room for it and tooltipping it.

        The label keeps the text readable at the widths the window actually uses
        and never hard-clips it: the width is reserved for the text (bounded, so
        one very long line cannot push the progress indicator away) and the full
        text is always the tooltip.
        """
        self._provenance_label.setText(text)
        self._provenance_label.setToolTip(text)
        metrics = QtGui.QFontMetrics(self._provenance_label.font())
        reserve = (
            _PROVENANCE_CHAR_CAP if len(text) > _PROVENANCE_CHAR_CAP else len(text)
        )
        width = metrics.horizontalAdvance(text[:reserve]) + _PROVENANCE_LABEL_PADDING
        self._provenance_label.setMinimumWidth(width)

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
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self.tr("Export report"),
            str(source.parent / source.name),
            file_filter,
        )
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
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self.tr("Save result"), self._output_dir(REPO_ROOT), "JSON (*.json)"
        )
        if not path:
            return
        self._remember_dir(path)
        application = self._rule.root
        capture_id = self._capture.capture_id if self._capture is not None else ""
        result = build_result(application.rule, capture_id, application.messages)
        try:
            write_result(result, path)
        except Exception as exc:
            self._set_rule_status(
                lambda exc=exc: self.tr("could not save result: {0}").format(exc),
                error=True,
            )
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
                "The empty state lists the same steps and marks the ones already\n"
                "done. Help - Show start guide brings it back over the workspace.\n"
                "1. File - Open capture (Ctrl+O).\n"
                "2. Pick a session, then a direction.\n"
                "3. Rule - Build rule (Ctrl+B) for a form, Open rule (Ctrl+R), or Load example.\n"
                "4. F5 applies the rule to the current direction; F6 to the whole capture.\n"
                "5. Read the Counterexamples tab; clicking a row jumps to the bytes.\n"
                "\n"
                "Keys\n"
                "Ctrl+O open capture   Ctrl+B build rule   Ctrl+R open rule   Ctrl+S save result\n"
                "F5 apply direction    F6 apply capture   F1 this help\n"
                "\n"
                "The bytes are the source of truth. A rule is an interpretation; a\n"
                "mismatch is a counterexample kept against it, not discarded."
            ),
        )

    def show_guide(self) -> None:
        """Return to the start screen and bring the coach back.

        The welcome screen is the first-run guide: it names the three steps and
        reports which are done. The coach is the running hint strip above the
        workspace. Showing the guide turns the coach back on and lands on the
        welcome screen; it does not close the open capture, so returning to the
        workspace is one click on a session.
        """
        self.set_guided_mode(True)
        self._refresh_welcome_progress()
        self._stack.setCurrentWidget(self.welcome_view)

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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Give the researcher a chance to save the project before quitting.

        The project is the only thing the window writes to disk, so the prompt
        is tied to it; declining keeps the window open and the work intact.
        """
        if self._confirm_discard_unsaved():
            event.accept()
        else:
            event.ignore()


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
        (
            f"<style>body{{background:{token.background};color:{token.text_primary};"
            f"font-family:{token.font_body},sans-serif;"
            "max-width:960px;margin:2rem auto;padding:0 1rem} "
            f"h1,h2,h3{{font-family:{token.font_heading},sans-serif;color:{token.text_primary}}} "
            "table{border-collapse:collapse;margin:1rem 0} "
            f"td,th{{border:1px solid {token.border};padding:4px 8px}} "
            f"code{{color:{token.accent}}}</style>"
        ),
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
            out.append(
                f"<h{level}>{html_module.escape(stripped[level:].strip())}</h{level}>"
            )
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
    parser.add_argument(
        "--capture",
        type=Path,
        help="normalized capture JSON or raw PCAP/PCAPNG to open",
    )
    parser.add_argument("--rule", type=Path, help="rule JSON or YAML to open")
    args, qt_argv = parser.parse_known_args(argv)

    if args.capture is not None and not args.capture.is_file():
        print(f"cannot open capture {args.capture}: file not found", file=sys.stderr)
        return 2
    if args.capture is not None:
        try:
            CaptureModel.from_file(args.capture)
        except CaptureModelError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
        [sys.argv[0], *qt_argv]
    )
    app.setApplicationName("Madrigal protocol laboratory")
    associate_with_desktop_entry(app)
    app.setWindowIcon(app_icon())
    theme.load_fonts(app)
    window = open_default_window(app, capture=args.capture, rule=args.rule)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
