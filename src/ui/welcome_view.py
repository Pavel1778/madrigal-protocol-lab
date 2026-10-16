"""First-run screen.

The window before a capture is open must be almost empty: a title, one question
and two ways to answer it. The three steps underneath state the order of work so
the first action is obvious without a manual, and each step reports whether it is
done, waiting or blocked by an earlier step.

The panel owns no application logic. It emits the two intentions the window
already handles (open the built-in example, open a file) and the window wires
them to its own slots, so the empty state stays a view.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import theme
from .constants import FONT_SIZE_BODY, FONT_SIZE_CAPTION

# Layout numbers for the empty state, in pixels. Kept together so the spacing
# grid is visible in one place rather than spread through the widget tree.
_TOP_GAP = 80
_TITLE_TO_QUESTION = 48
_QUESTION_TO_BUTTON = 32
_BETWEEN_BUTTONS = 16
_BUTTONS_TO_STEPS = 64
_BETWEEN_STEPS = 16
_PRIMARY_WIDTH = 280
_PRIMARY_HEIGHT = 48
_SECONDARY_HEIGHT = 40
_STEP_BADGE = 24


class _Step(QtWidgets.QWidget):
    """One numbered step: a badge, a title and a status line."""

    def __init__(self, number: int, title: str, pending: str) -> None:
        super().__init__()
        self._pending = pending
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        self.badge = QtWidgets.QLabel(str(number))
        self.badge.setObjectName("welcomeStepBadge")
        self.badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(_STEP_BADGE, _STEP_BADGE)
        row.addWidget(self.badge, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        text = QtWidgets.QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("welcomeStepTitle")
        text.addWidget(self.title)
        self.status = QtWidgets.QLabel(pending)
        self.status.setObjectName("welcomeStepStatus")
        text.addWidget(self.status)
        row.addLayout(text, 1)

    def set_state(self, state: str, status: str | None = None) -> None:
        """Mark the step ``done``, ``next`` or ``todo`` and set its status line."""
        self.setProperty("state", state)
        self.badge.setText("✓" if state == "done" else self.badge.text())
        self.status.setText(status if status is not None else self._pending)
        for widget in (self, self.badge, self.title, self.status):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def set_pending(self, text: str) -> None:
        """Replace the status text used when the step is not done."""
        self._pending = text


class WelcomeView(QtWidgets.QWidget):
    """The first-run screen: a title, what the tool is, and three choices."""

    learningRequested = QtCore.Signal()
    demoRequested = QtCore.Signal()
    capabilitiesRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomeView")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(24, 0, 24, 0)
        outer.addSpacing(_TOP_GAP)

        self.title = QtWidgets.QLabel()
        self.title.setObjectName("welcomeTitle")
        self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.title)

        outer.addSpacing(_TITLE_TO_QUESTION)
        self.question = QtWidgets.QLabel()
        self.question.setObjectName("welcomeQuestion")
        self.question.setWordWrap(True)
        self.question.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.question)

        outer.addSpacing(_QUESTION_TO_BUTTON)
        self.learning_button = QtWidgets.QPushButton()
        self.learning_button.setObjectName("welcomePrimary")
        self.learning_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.learning_button.setMinimumSize(_PRIMARY_WIDTH, _PRIMARY_HEIGHT)
        self.learning_button.clicked.connect(self.learningRequested.emit)
        outer.addWidget(self.learning_button, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        outer.addSpacing(_BETWEEN_BUTTONS)
        self.demo_button = QtWidgets.QPushButton()
        self.demo_button.setObjectName("welcomeSecondary")
        self.demo_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.demo_button.setMinimumSize(_PRIMARY_WIDTH, _SECONDARY_HEIGHT)
        self.demo_button.clicked.connect(self.demoRequested.emit)
        outer.addWidget(self.demo_button, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        outer.addSpacing(_BETWEEN_BUTTONS)
        self.capabilities_button = QtWidgets.QPushButton()
        self.capabilities_button.setObjectName("welcomeSecondary")
        self.capabilities_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.capabilities_button.setMinimumSize(_PRIMARY_WIDTH, _SECONDARY_HEIGHT)
        self.capabilities_button.clicked.connect(self.capabilitiesRequested.emit)
        outer.addWidget(
            self.capabilities_button, 0, QtCore.Qt.AlignmentFlag.AlignHCenter
        )

        outer.addSpacing(_BUTTONS_TO_STEPS)
        self.step_capture = _Step(1, "", "")
        self.step_session = _Step(2, "", "")
        self.step_rule = _Step(3, "", "")
        steps = QtWidgets.QVBoxLayout()
        steps.setSpacing(_BETWEEN_STEPS)
        for step in (self.step_capture, self.step_session, self.step_rule):
            steps.addWidget(step)
        # The steps are a fixed-width block, centred, so the empty state reads as
        # one column rather than a full-width form.
        steps_host = QtWidgets.QWidget()
        steps_host.setLayout(steps)
        steps_host.setMaximumWidth(520)
        outer.addWidget(steps_host, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)

        self.reset()
        self.retranslate_ui()
        self.apply_theme()

    # -- state -------------------------------------------------------------

    def reset(self) -> None:
        """Return to the state shown before anything is opened."""
        self.set_progress(capture=False, session=False, rule=False)

    def set_progress(self, *, capture: bool, session: bool, rule: bool) -> None:
        """Mark the three steps according to what has been done."""
        if capture:
            self.step_capture.set_state("done", self.tr("done"))
        else:
            self.step_capture.set_state("next", self.tr("not done"))
        if session:
            self.step_session.set_state("done", self.tr("done"))
        elif capture:
            self.step_session.set_state(
                "next", self.tr("pick a session and a direction")
            )
        else:
            self.step_session.set_state("todo", self.tr("becomes active after step 1"))
        if rule:
            self.step_rule.set_state("done", self.tr("done"))
        elif session:
            self.step_rule.set_state("next", self.tr("create a rule and check it"))
        else:
            self.step_rule.set_state("todo", self.tr("becomes active after step 2"))

    # -- presentation ------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Re-apply every caption in the active interface language."""
        self.title.setText(self.tr("Madrigal protocol laboratory"))
        self.question.setText(
            self.tr(
                "A laboratory for reading a protocol that was never written down. "
                "Study the bytes, form a hypothesis, write it as a rule, and check "
                "it against the recording."
            )
        )
        self.learning_button.setText(self.tr("Take the interactive course"))
        self.learning_button.setToolTip(
            self.tr("A guided tour that uses the built-in example, step by step")
        )
        self.demo_button.setText(self.tr("Go straight to work"))
        self.demo_button.setToolTip(
            self.tr("Open the built-in example and the usual interface")
        )
        self.capabilities_button.setText(self.tr("What can Madrigal do?"))
        self.capabilities_button.setToolTip(
            self.tr("Open the reference and the list of capabilities")
        )
        self.step_capture.title.setText(self.tr("Open a traffic record"))
        self.step_capture.set_pending(self.tr("not done"))
        self.step_session.title.setText(self.tr("Pick a session and a direction"))
        self.step_session.set_pending(self.tr("becomes active after step 1"))
        self.step_rule.title.setText(self.tr("Create a rule and check it"))
        self.step_rule.set_pending(self.tr("becomes active after step 2"))
        self.reset()

    def apply_theme(self) -> None:
        """Re-read the active theme for the screen and its steps."""
        token = theme.current()
        radius = token.radius
        self.setStyleSheet(
            f"""
            QWidget#welcomeView {{ background: {token.background}; }}
            QLabel#welcomeTitle {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY + 11}pt;
                font-weight: 600;
            }}
            QLabel#welcomeQuestion {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_BODY + 7}pt;
            }}
            QPushButton#welcomePrimary {{
                background: {token.accent};
                color: {token.text_on_accent};
                border: none;
                border-radius: {radius}px;
                padding: 0 16px;
                font-size: {FONT_SIZE_BODY + 5}pt;
                font-weight: 600;
            }}
            QPushButton#welcomePrimary:hover {{ background: {token.accent_hover}; }}
            QPushButton#welcomeSecondary {{
                background: {token.surface_alt};
                color: {token.text_primary};
                border: 1px solid {token.border};
                border-radius: {radius}px;
                padding: 0 16px;
                font-size: {FONT_SIZE_BODY + 4}pt;
            }}
            QPushButton#welcomeSecondary:hover {{ background: {token.surface_elevated}; }}
            QLabel#welcomeStepBadge {{
                color: {token.text_secondary};
                border: 1px solid {token.border};
                border-radius: {radius}px;
                font-size: {FONT_SIZE_BODY + 3}pt;
            }}
            QLabel#welcomeStepTitle {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY + 4}pt;
            }}
            QLabel#welcomeStepStatus {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_CAPTION + 3}pt;
                font-style: italic;
            }}
            QWidget[state="done"] QLabel#welcomeStepBadge {{
                color: {token.status_matched_text};
                border: 1px solid {token.status_matched_text};
            }}
            QWidget[state="done"] QLabel#welcomeStepTitle {{
                color: {token.status_matched_text};
            }}
            QWidget[state="next"] QLabel#welcomeStepBadge {{
                color: {token.text_on_accent};
                background: {token.accent};
                border: 1px solid {token.accent};
            }}
            """
        )
        self.title.setFont(theme.heading_font(FONT_SIZE_BODY + 11))
        self.question.setFont(theme.body_font(FONT_SIZE_BODY + 7))
        for step in (self.step_capture, self.step_session, self.step_rule):
            step.title.setFont(theme.body_font(FONT_SIZE_BODY + 4))
            step.status.setFont(theme.body_font(FONT_SIZE_CAPTION + 3))
            step.badge.setFont(theme.body_font(FONT_SIZE_BODY + 3))
