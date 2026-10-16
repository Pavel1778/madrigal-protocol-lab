"""The contextual help card and the learning centre.

Two dialogs share the reference catalogue in :mod:`src.ui.help`:

* :class:`HelpCard` shows one entry — the element the reader asked about — with
  the plain explanation first and the technical detail behind a disclosure, so a
  newcomer is not shown the whole definition at once.
* :class:`LearningCentre` lists the course and the reference side by side, lets a
  lesson be chosen or the course continued, and searches the catalogue by name or
  term.

Neither dialog owns application state: the centre emits the lesson the reader
chose and the window decides what to do with it, so a lesson can be started
without the centre reaching into the window.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import help as reference
from . import learning, theme
from .constants import FONT_SIZE_BODY, FONT_SIZE_CAPTION


def _field_labels() -> tuple[tuple[str, str], ...]:
    """The (attribute, caption) pairs shown in a help card, in reading order."""
    return (
        ("purpose", "What it is for"),
        ("values", "Allowed values"),
        ("default", "Default"),
        ("example", "Example"),
        ("effect", "If you change it"),
        ("depends", "What it depends on"),
        ("mistakes", "Common mistakes"),
    )


class HelpCard(QtWidgets.QDialog):
    """A compact explanation of one reference entry."""

    def __init__(
        self,
        entry: reference.HelpEntry,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Help"))
        self.setModal(False)
        self.setMinimumWidth(420)
        self._entry = entry

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.title = QtWidgets.QLabel()
        self.title.setObjectName("helpTitle")
        layout.addWidget(self.title)
        self.section = QtWidgets.QLabel()
        self.section.setObjectName("helpSection")
        layout.addWidget(self.section)
        self.summary = QtWidgets.QLabel()
        self.summary.setObjectName("helpSummary")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self._details = QtWidgets.QWidget()
        self._details.setVisible(False)
        self._details_form = QtWidgets.QFormLayout(self._details)
        self._details_form.setContentsMargins(0, 4, 0, 0)
        self._details_form.setSpacing(6)
        self._detail_labels: dict[str, QtWidgets.QLabel] = {}
        for attribute, _caption in _field_labels():
            value = QtWidgets.QLabel()
            value.setWordWrap(True)
            value.setObjectName("helpDetail")
            self._detail_labels[attribute] = value
        layout.addWidget(self._details)

        buttons = QtWidgets.QHBoxLayout()
        self.more_button = QtWidgets.QPushButton()
        self.more_button.setCheckable(True)
        self.more_button.toggled.connect(self._set_details_visible)
        buttons.addWidget(self.more_button)
        buttons.addStretch(1)
        self.close_button = QtWidgets.QPushButton()
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.retranslate_ui()
        self.apply_theme()

    def set_entry(self, entry: reference.HelpEntry) -> None:
        """Show *entry*, keeping the disclosure state."""
        self._entry = entry
        self.retranslate_ui()

    def _set_details_visible(self, visible: bool) -> None:
        self._details.setVisible(bool(visible))
        self.more_button.setText(
            self.tr("Less") if visible else self.tr("More detail")
        )

    def retranslate_ui(self) -> None:
        """Re-apply the card in the active interface language."""
        entry = self._entry
        self.setWindowTitle(self.tr("Help"))
        self.title.setText(reference.translate(entry.title))
        self.section.setText(reference.translate(entry.section))
        self.summary.setText(reference.translate(entry.summary))
        self.close_button.setText(self.tr("Close"))
        self.more_button.setText(
            self.tr("Less") if self.more_button.isChecked() else self.tr("More detail")
        )
        # takeRow detaches a row without destroying its widgets, so the labels
        # created once can be reused for the next entry.
        while self._details_form.rowCount():
            self._details_form.takeRow(0)
        for attribute, caption in _field_labels():
            text = getattr(entry, attribute, "")
            if not text:
                continue
            label = self._detail_labels[attribute]
            label.setText(reference.translate(text))
            self._details_form.addRow(self.tr(caption), label)

    def apply_theme(self) -> None:
        """Read the active theme for the card's text hierarchy."""
        token = theme.current()
        self.setStyleSheet(
            f"""
            QLabel#helpTitle {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY + 5}pt;
                font-weight: 600;
            }}
            QLabel#helpSection {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_CAPTION}pt;
            }}
            QLabel#helpSummary {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY + 2}pt;
            }}
            QLabel#helpDetail {{ color: {token.text_secondary}; }}
            """
        )
        self.title.setFont(theme.heading_font(FONT_SIZE_BODY + 5))
        self.summary.setFont(theme.body_font(FONT_SIZE_BODY + 2))
        for label in self._detail_labels.values():
            label.setFont(theme.body_font(FONT_SIZE_BODY))


class LearningCentre(QtWidgets.QDialog):
    """Choose a lesson, continue the course, or look a term up."""

    lessonChosen = QtCore.Signal(str)
    resetRequested = QtCore.Signal()
    helpRequested = QtCore.Signal(str)

    def __init__(
        self,
        completed: set[str] | None = None,
        current_lesson: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Learning and help"))
        self.setModal(True)
        self.setMinimumSize(640, 460)
        self._completed = set(completed or ())
        self._current = current_lesson or ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.intro = QtWidgets.QLabel()
        self.intro.setObjectName("centreIntro")
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._build_course(), "")
        self.tabs.addTab(self._build_reference(), "")
        layout.addWidget(self.tabs, 1)

        buttons = QtWidgets.QHBoxLayout()
        self.reset_button = QtWidgets.QPushButton()
        self.reset_button.clicked.connect(self._on_reset)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)
        self.close_button = QtWidgets.QPushButton()
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self._populate_lessons()
        self._populate_reference()
        self.retranslate_ui()
        self.apply_theme()

    # -- pages -------------------------------------------------------------

    def _build_course(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.lesson_list = QtWidgets.QListWidget()
        self.lesson_list.itemActivated.connect(self._on_lesson_activated)
        self.lesson_list.itemDoubleClicked.connect(self._on_lesson_activated)
        layout.addWidget(self.lesson_list, 1)
        self.lesson_hint = QtWidgets.QLabel()
        self.lesson_hint.setObjectName("centreHint")
        self.lesson_hint.setWordWrap(True)
        layout.addWidget(self.lesson_hint)
        row = QtWidgets.QHBoxLayout()
        self.continue_button = QtWidgets.QPushButton()
        self.continue_button.clicked.connect(self._on_continue)
        row.addWidget(self.continue_button)
        self.start_button = QtWidgets.QPushButton()
        self.start_button.clicked.connect(self._on_start)
        row.addWidget(self.start_button)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    def _build_reference(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QtWidgets.QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._populate_reference)
        layout.addWidget(self.search)
        self.entry_list = QtWidgets.QListWidget()
        self.entry_list.currentItemChanged.connect(self._on_entry_changed)
        layout.addWidget(self.entry_list, 1)
        self.entry_body = QtWidgets.QPlainTextEdit()
        self.entry_body.setReadOnly(True)
        self.entry_body.setMinimumHeight(140)
        layout.addWidget(self.entry_body, 1)
        self.open_help_button = QtWidgets.QPushButton()
        self.open_help_button.clicked.connect(self._on_open_help)
        layout.addWidget(self.open_help_button)
        return page

    # -- content -----------------------------------------------------------

    def _populate_lessons(self) -> None:
        self.lesson_list.clear()
        for lesson in learning.LESSONS:
            done = lesson.key in self._completed
            marker = self.tr("done") if done else ""
            item = QtWidgets.QListWidgetItem(
                f"{learning.translate(lesson.title)}  {marker}".rstrip()
            )
            item.setData(QtCore.Qt.ItemDataRole.UserRole, lesson.key)
            if lesson.key == self._current:
                item.setText(f"▶ {item.text()}")
            self.lesson_list.addItem(item)

    def _populate_reference(self) -> None:
        query = self.search.text() if hasattr(self, "search") else ""
        self.entry_list.clear()
        for entry in reference.search(query):
            item = QtWidgets.QListWidgetItem(reference.translate(entry.title))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, entry.key)
            self.entry_list.addItem(item)
        if self.entry_list.count():
            self.entry_list.setCurrentRow(0)
        else:
            self.entry_body.setPlainText(self.tr("nothing matches the search"))

    def _on_entry_changed(self, current, _previous=None) -> None:
        if current is None:
            return
        key = current.data(QtCore.Qt.ItemDataRole.UserRole)
        entry = reference.lookup(str(key))
        if entry is None:
            return
        parts = [reference.translate(entry.title), "", reference.translate(entry.summary)]
        for attribute, caption in _field_labels():
            text = getattr(entry, attribute, "")
            if text:
                parts += ["", f"{self.tr(caption)}: {reference.translate(text)}"]
        self.entry_body.setPlainText("\n".join(parts))

    # -- actions -----------------------------------------------------------

    def _selected_key(self) -> str:
        item = self.lesson_list.currentItem()
        if item is None:
            return ""
        return str(item.data(QtCore.Qt.ItemDataRole.UserRole))

    def _on_lesson_activated(self, _item) -> None:
        key = self._selected_key()
        if key:
            self.lessonChosen.emit(key)
            self.accept()

    def _on_continue(self) -> None:
        key = self._current or learning.LESSONS[0].key
        self.lessonChosen.emit(key)
        self.accept()

    def _on_start(self) -> None:
        self.lessonChosen.emit(learning.LESSONS[0].key)
        self.accept()

    def _on_reset(self) -> None:
        self.resetRequested.emit()
        self._completed = set()
        self._current = ""
        self._populate_lessons()

    def _on_open_help(self) -> None:
        item = self.entry_list.currentItem()
        if item is None:
            return
        key = str(item.data(QtCore.Qt.ItemDataRole.UserRole))
        self.helpRequested.emit(key)

    # -- presentation ------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Re-apply the centre in the active interface language."""
        self.setWindowTitle(self.tr("Learning and help"))
        self.intro.setText(
            self.tr(
                "Follow the course from the beginning, jump to one lesson, or look "
                "up any element of the interface and any parameter of a rule."
            )
        )
        self.tabs.setTabText(0, self.tr("Course"))
        self.tabs.setTabText(1, self.tr("Reference"))
        self.search.setPlaceholderText(self.tr("Search a term or a parameter"))
        self.lesson_hint.setText(
            self.tr("Double-click a lesson to start it, or use the buttons below.")
        )
        self.continue_button.setText(self.tr("Continue the course"))
        self.start_button.setText(self.tr("Start from the beginning"))
        self.reset_button.setText(self.tr("Reset progress"))
        self.close_button.setText(self.tr("Close"))
        self.open_help_button.setText(self.tr("Open the full explanation"))
        self._populate_lessons()

    def apply_theme(self) -> None:
        """Read the active theme for the centre's list and text."""
        token = theme.current()
        self.setStyleSheet(
            f"""
            QLabel#centreIntro {{ color: {token.text_secondary}; }}
            QLabel#centreHint {{ color: {token.text_muted}; }}
            QListWidget::item {{ padding: 4px 6px; }}
            """
        )
        self.intro.setFont(theme.body_font(FONT_SIZE_BODY))
        self.entry_body.setFont(theme.body_font(FONT_SIZE_BODY))
        self.lesson_hint.setFont(theme.body_font(FONT_SIZE_CAPTION))
