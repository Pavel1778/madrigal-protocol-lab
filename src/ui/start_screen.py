"""The empty-state screen shown in the centre of a fresh window.

Before a capture is open the workspace has nothing to draw, and a hex grid of
zero bytes explains nothing to a reader who has not seen the tool before. This
screen takes the centre instead and names the three steps in plain words, with
one obvious first action: open the example. It steps aside as soon as the first
message is on screen, because from then on the workspace itself shows the way.

The screen owns no application logic. It emits the intentions the menu already
offers, and the window wires them to the existing slots.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import theme
from .constants import FONT_SIZE_BODY, FONT_SIZE_CAPTION


class _Step(QtWidgets.QFrame):
    """One numbered step: a title, a plain description and a state marker."""

    def __init__(self, number: int) -> None:
        super().__init__()
        self.setObjectName("startStep")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        self.number = QtWidgets.QLabel(str(number))
        self.number.setObjectName("startStepNumber")
        self.number.setFixedWidth(20)
        self.number.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignHCenter
        )
        layout.addWidget(self.number)

        body = QtWidgets.QVBoxLayout()
        body.setSpacing(2)
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("startStepTitle")
        body.addWidget(self.title)
        self.description = QtWidgets.QLabel()
        self.description.setObjectName("startStepDescription")
        self.description.setWordWrap(True)
        body.addWidget(self.description)
        layout.addLayout(body, 1)

        self.marker = QtWidgets.QLabel()
        self.marker.setObjectName("startStepMarker")
        self.marker.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignRight
        )
        layout.addWidget(self.marker)

    def set_state(self, state: str) -> None:
        """Colour the step: ``done``, ``next`` or ``locked``."""
        self.setProperty("state", state)
        self.title.setProperty("state", state)
        self.marker.setProperty("state", state)
        for widget in (self, self.number, self.title, self.marker):
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class StartScreen(QtWidgets.QWidget):
    """The three-step first-run screen for the centre of the window."""

    openExampleRequested = QtCore.Signal()
    openCaptureRequested = QtCore.Signal()
    buildRuleRequested = QtCore.Signal()
    applyRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("startScreen")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(10)
        outer.addStretch(1)

        self.title = QtWidgets.QLabel()
        self.title.setObjectName("startTitle")
        self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(self.title)

        self.intro = QtWidgets.QLabel()
        self.intro.setObjectName("startIntro")
        self.intro.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.intro.setWordWrap(True)
        outer.addWidget(self.intro)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        self.example_button = QtWidgets.QPushButton()
        self.example_button.setObjectName("startPrimary")
        self.example_button.setProperty("accent", "true")
        self.example_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.example_button.clicked.connect(self.openExampleRequested.emit)
        actions.addWidget(self.example_button)
        self.capture_button = QtWidgets.QPushButton()
        self.capture_button.setObjectName("startSecondary")
        self.capture_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.capture_button.clicked.connect(self.openCaptureRequested.emit)
        actions.addWidget(self.capture_button)
        actions.addStretch(1)
        outer.addLayout(actions)

        self.step_capture = _Step(1)
        self.step_session = _Step(2)
        self.step_rule = _Step(3)
        steps = QtWidgets.QVBoxLayout()
        steps.setSpacing(6)
        for step in (self.step_capture, self.step_session, self.step_rule):
            steps.addWidget(step)
        outer.addLayout(steps)

        rule_actions = QtWidgets.QHBoxLayout()
        rule_actions.setSpacing(8)
        rule_actions.addStretch(1)
        self.build_button = QtWidgets.QPushButton()
        self.build_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.build_button.clicked.connect(self.buildRuleRequested.emit)
        rule_actions.addWidget(self.build_button)
        self.apply_button = QtWidgets.QPushButton()
        self.apply_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.apply_button.clicked.connect(self.applyRequested.emit)
        rule_actions.addWidget(self.apply_button)
        rule_actions.addStretch(1)
        outer.addLayout(rule_actions)

        outer.addStretch(2)

        self._capture_open = False
        self._session_ready = False
        self._rule_ready = False
        self._applied = False
        self.retranslate_ui()
        self.apply_theme()

    # -- state -------------------------------------------------------------

    def set_progress(
        self,
        *,
        capture_open: bool,
        session_ready: bool,
        rule_ready: bool,
        applied: bool,
    ) -> None:
        """Record how far the reader has come and repaint the three steps."""
        self._capture_open = bool(capture_open)
        self._session_ready = bool(session_ready)
        self._rule_ready = bool(rule_ready)
        self._applied = bool(applied)
        self._refresh()

    def _refresh(self) -> None:
        capture_done = self._capture_open
        session_done = capture_done and self._session_ready
        rule_done = self._rule_ready and session_done and self._applied

        self.step_capture.set_state("done" if capture_done else "next")
        self.step_session.set_state(
            "done" if session_done else ("next" if capture_done else "locked")
        )
        self.step_rule.set_state(
            "done" if rule_done else ("next" if session_done else "locked")
        )

        markers = {"done": "✓", "next": "→", "locked": ""}
        self.step_capture.marker.setText(
            markers[self.step_capture.property("state")]
        )
        self.step_session.marker.setText(
            markers[self.step_session.property("state")]
        )
        self.step_rule.marker.setText(markers[self.step_rule.property("state")])

        # The first action stays in front until a capture is open; the rule
        # actions appear once there is a session and a direction to check.
        self.example_button.setVisible(not capture_done)
        self.capture_button.setVisible(not capture_done)
        self.build_button.setVisible(session_done and not rule_done)
        self.apply_button.setVisible(session_done and not rule_done)

    # -- presentation ------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Re-apply every caption in the active interface language."""
        self.title.setText(self.tr("Start here"))
        self.intro.setText(
            self.tr(
                "A capture is a recording of a network exchange. This tool puts "
                "the bytes back in order and shows how a rule reads them. Open "
                "the example to see a whole investigation, or open your own file."
            )
        )
        self.example_button.setText(self.tr("Open the example"))
        self.example_button.setToolTip(
            self.tr("Open the small capture and rule that ship with the tool")
        )
        self.capture_button.setText(self.tr("Open a file..."))
        self.capture_button.setToolTip(
            self.tr("Open a recording: pcap, pcapng or a normalized JSON")
        )

        self.step_capture.title.setText(self.tr("Open a recording"))
        self.step_capture.description.setText(
            self.tr(
                "A pcap, a pcapng or an already normalized JSON. Open the "
                "example if you have none at hand."
            )
        )
        self.step_session.title.setText(self.tr("Pick a conversation and a direction"))
        self.step_session.description.setText(
            self.tr(
                "One connection on the left, then the traffic one way or the "
                "other. The bytes appear as hex."
            )
        )
        self.step_rule.title.setText(self.tr("Describe the messages and check them"))
        self.step_rule.description.setText(
            self.tr(
                "Write a rule that says how the bytes are cut into messages and "
                "what each field means, then check it. The tool marks every "
                "message the rule disagrees with."
            )
        )

        self.build_button.setText(self.tr("Build a rule..."))
        self.build_button.setToolTip(
            self.tr("Describe a message in a form instead of writing JSON by hand")
        )
        self.apply_button.setText(self.tr("Check the rule"))
        self.apply_button.setToolTip(
            self.tr("Apply the rule to the current direction")
        )
        self._refresh()

    def apply_theme(self) -> None:
        """Re-read the active theme for the screen and its steps."""
        token = theme.current()
        radius = token.radius
        self.setStyleSheet(
            f"""
            QWidget#startScreen {{ background: {token.background}; }}
            QLabel#startTitle {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY + 8}pt;
            }}
            QLabel#startIntro {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_BODY}pt;
            }}
            QPushButton#startPrimary {{
                background: {token.accent};
                color: {token.text_on_accent};
                border: none;
                border-radius: {radius}px;
                padding: 8px 20px;
            }}
            QPushButton#startPrimary:hover {{ background: {token.accent_hover}; }}
            QPushButton#startSecondary {{
                background: {token.surface};
                color: {token.text_primary};
                border: 1px solid {token.border};
                border-radius: {radius}px;
                padding: 8px 20px;
            }}
            QPushButton#startSecondary:hover {{ border-color: {token.accent}; }}
            QFrame#startStep {{
                background: {token.surface};
                border: 1px solid {token.border};
                border-radius: {radius}px;
            }}
            QFrame#startStep[state="next"] {{ border: 1px solid {token.accent}; }}
            QLabel#startStepNumber {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_BODY}pt;
            }}
            QLabel#startStepTitle {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY}pt;
            }}
            QLabel#startStepTitle[state="done"] {{ color: {token.status_matched_text}; }}
            QLabel#startStepTitle[state="locked"] {{ color: {token.text_muted}; }}
            QLabel#startStepDescription {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_CAPTION}pt;
            }}
            QLabel#startStepMarker {{
                color: {token.status_matched_text};
                font-size: {FONT_SIZE_BODY}pt;
            }}
            QLabel#startStepMarker[state="next"] {{ color: {token.accent}; }}
            """
        )
        self.title.setFont(theme.heading_font(FONT_SIZE_BODY + 8))
        self.intro.setFont(theme.body_font(FONT_SIZE_BODY))
        for step in (self.step_capture, self.step_session, self.step_rule):
            step.number.setFont(theme.body_font(FONT_SIZE_BODY))
            step.title.setFont(theme.body_font(FONT_SIZE_BODY))
            step.description.setFont(theme.body_font(FONT_SIZE_CAPTION))
            step.marker.setFont(theme.body_font(FONT_SIZE_BODY))
