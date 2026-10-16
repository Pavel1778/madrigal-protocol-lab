"""The tutor panel: the strip that walks through the course.

The panel is a view. It is told which lesson and which step to show and whether
that step's action has been performed; it emits the intentions (back, next, skip,
finish, hide, open help) and the window wires each one to the real slot. It owns
no application logic and never reaches into the window, so the course can be
driven by the window's own state.

The strip is laid out to stay narrow: it must not set the minimum width of the
window, because its longest instruction is wider than the workspace can afford.
Its pointer is a dynamic property set on the target widget, which the window's
style sheet turns into an accent outline; the property is cleared on a timer so
the highlight is temporary.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import learning, theme
from .constants import FONT_SIZE_BODY, FONT_SIZE_CAPTION


class TutorPanel(QtWidgets.QFrame):
    """The one-step-at-a-time course strip shown above the workspace."""

    backRequested = QtCore.Signal()
    nextRequested = QtCore.Signal()
    skipRequested = QtCore.Signal()
    finishRequested = QtCore.Signal()
    hideRequested = QtCore.Signal()
    helpRequested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tutorPanel")
        # The strip must not dictate the window width: its longest instruction is
        # wider than the workspace can afford in a narrow window.
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )

        self._lesson: learning.Lesson | None = None
        self._index = 0
        self._done = False
        self._why_open = False

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 10)
        outer.setSpacing(6)

        head = QtWidgets.QHBoxLayout()
        head.setSpacing(8)
        self.lesson_label = QtWidgets.QLabel()
        self.lesson_label.setObjectName("tutorLesson")
        head.addWidget(self.lesson_label)
        head.addStretch(1)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setObjectName("tutorProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(120)
        self.progress.setFixedHeight(6)
        head.addWidget(self.progress)
        self.step_label = QtWidgets.QLabel()
        self.step_label.setObjectName("tutorStep")
        head.addWidget(self.step_label)
        self.help_button = QtWidgets.QPushButton()
        self.help_button.setObjectName("tutorIcon")
        self.help_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.help_button.clicked.connect(self._emit_help)
        head.addWidget(self.help_button)
        self.hide_button = QtWidgets.QPushButton()
        self.hide_button.setObjectName("tutorIcon")
        self.hide_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.hide_button.clicked.connect(self.hideRequested.emit)
        head.addWidget(self.hide_button)
        outer.addLayout(head)

        self.body = QtWidgets.QLabel()
        self.body.setObjectName("tutorBody")
        self.body.setWordWrap(True)
        outer.addWidget(self.body)

        self.why_label = QtWidgets.QLabel()
        self.why_label.setObjectName("tutorWhy")
        self.why_label.setWordWrap(True)
        self.why_label.setVisible(False)
        outer.addWidget(self.why_label)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.why_button = QtWidgets.QPushButton()
        self.why_button.setObjectName("tutorGhost")
        self.why_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.why_button.clicked.connect(self._toggle_why)
        actions.addWidget(self.why_button)
        actions.addStretch(1)
        self.back_button = QtWidgets.QPushButton()
        self.back_button.setObjectName("tutorGhost")
        self.back_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self.backRequested.emit)
        actions.addWidget(self.back_button)
        self.skip_button = QtWidgets.QPushButton()
        self.skip_button.setObjectName("tutorGhost")
        self.skip_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.skip_button.clicked.connect(self.skipRequested.emit)
        actions.addWidget(self.skip_button)
        self.next_button = QtWidgets.QPushButton()
        self.next_button.setObjectName("tutorPrimary")
        self.next_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.next_button.clicked.connect(self.nextRequested.emit)
        actions.addWidget(self.next_button)
        outer.addLayout(actions)

        self.retranslate_ui()
        self.apply_theme()

    # -- state -------------------------------------------------------------

    def show_step(self, lesson: learning.Lesson, index: int, done: bool) -> None:
        """Show step *index* of *lesson*; *done* is whether its action was met."""
        self._lesson = lesson
        self._index = max(0, min(index, len(lesson.steps) - 1))
        self._done = bool(done)
        self._why_open = False
        self.why_label.setVisible(False)
        self.retranslate_ui()

    @property
    def lesson_key(self) -> str:
        """The key of the lesson currently shown, or an empty string."""
        return self._lesson.key if self._lesson is not None else ""

    @property
    def step_index(self) -> int:
        """The step currently shown."""
        return self._index

    @property
    def step_done(self) -> bool:
        """Whether the shown step's action has been performed."""
        return self._done

    @property
    def current_step(self) -> learning.Step | None:
        """The step currently shown, or ``None``."""
        if self._lesson is None:
            return None
        return self._lesson.steps[self._index]

    # -- content -----------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Re-apply every caption in the active interface language."""
        self.hide_button.setText(self.tr("Hide"))
        self.hide_button.setToolTip(self.tr("Hide the tutor; View brings it back"))
        self.help_button.setText("?")
        self.help_button.setToolTip(self.tr("Explain this element"))
        self.why_button.setText(self.tr("Why this?"))
        self.back_button.setText(self.tr("Back"))
        self.next_button.setText(self.tr("Next"))
        if self._lesson is None:
            self.lesson_label.setText("")
            self.step_label.setText("")
            self.body.setText("")
            self.why_label.setText("")
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            return
        total = len(self._lesson.steps)
        self.lesson_label.setText(learning.translate(self._lesson.title))
        self.step_label.setText(
            self.tr("Step {0} of {1}").format(self._index + 1, total)
        )
        self.progress.setRange(0, total)
        self.progress.setValue(self._index + 1)
        step = self._lesson.steps[self._index]
        self.body.setText(learning.translate(step.text))
        self.why_label.setText(learning.translate(step.why))
        self.why_label.setVisible(self._why_open)
        self.skip_button.setText(
            self.tr("Skip") if total > 1 else self.tr("Skip lesson")
        )
        self.next_button.setText(
            self.tr("Next") if self._index + 1 < total else self.tr("Finish")
        )

    def _toggle_why(self) -> None:
        self._why_open = not self._why_open
        self.why_label.setVisible(self._why_open)

    def _emit_help(self) -> None:
        step = self.current_step
        target = step.target if step is not None else None
        self.helpRequested.emit(target or "")

    # -- presentation ------------------------------------------------------

    def apply_theme(self) -> None:
        """Re-read the active theme for the strip."""
        token = theme.current()
        radius = token.radius
        self.setStyleSheet(
            f"""
            QFrame#tutorPanel {{
                background: {token.surface_alt};
                border: 1px solid {token.accent};
                border-radius: {radius}px;
            }}
            QLabel#tutorLesson {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY + 2}pt;
                font-weight: 600;
            }}
            QLabel#tutorStep {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_CAPTION}pt;
            }}
            QLabel#tutorBody {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY}pt;
            }}
            QLabel#tutorWhy {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_BODY}pt;
                border-left: 2px solid {token.accent};
                padding-left: 8px;
            }}
            QProgressBar#tutorProgress {{
                background: {token.surface};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar#tutorProgress::chunk {{
                background: {token.accent};
                border-radius: 3px;
            }}
            QPushButton#tutorPrimary {{
                background: {token.accent};
                color: {token.text_on_accent};
                border: none;
                border-radius: {radius}px;
                padding: 6px 16px;
            }}
            QPushButton#tutorPrimary:hover {{ background: {token.accent_hover}; }}
            QPushButton#tutorGhost {{
                background: transparent;
                color: {token.text_secondary};
                border: 1px solid {token.border};
                border-radius: {radius}px;
                padding: 4px 12px;
            }}
            QPushButton#tutorGhost:hover {{ color: {token.text_primary}; }}
            QPushButton#tutorIcon {{
                background: transparent;
                color: {token.text_secondary};
                border: 1px solid {token.border};
                border-radius: {radius}px;
                padding: 0 8px;
                min-width: 22px;
            }}
            QPushButton#tutorIcon:hover {{ color: {token.text_primary}; }}
            """
        )
        self.lesson_label.setFont(theme.heading_font(FONT_SIZE_BODY + 2))
        self.step_label.setFont(theme.body_font(FONT_SIZE_CAPTION))
        self.body.setFont(theme.body_font(FONT_SIZE_BODY))
        self.why_label.setFont(theme.body_font(FONT_SIZE_BODY))
        for button in (
            self.why_button,
            self.back_button,
            self.skip_button,
            self.next_button,
            self.hide_button,
        ):
            button.setFont(theme.body_font(FONT_SIZE_BODY))
