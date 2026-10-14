"""The compact "Start here" banner above the workspace.

The window is dense by design, and a newcomer cannot tell from the panels alone
in which order they are meant to be used. This banner names the three steps and
marks the ones already done, so the tool can be driven without reading the
manual first. The centre of the window carries the same steps at full size while
nothing is open; once work has started this banner is the only reminder.

It is a single strip, not a block of prose: the steps sit side by side and each
one's explanation is a tooltip, so the workspace keeps almost all of the window
height. The strip hides itself once a capture, a rule and an applied rule are
all present, because by then the workspace itself shows what to do.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import theme
from .constants import FONT_SIZE_BODY, FONT_SIZE_CAPTION


class _Step(QtWidgets.QFrame):
    """One numbered step: a title, a tooltip hint and an optional action."""

    def __init__(self, number: int, action: str | None) -> None:
        super().__init__()
        self.setObjectName("guideStep")
        # A step must not widen the window: its title and button are longer in
        # Russian, and the strip above the workspace has to stay shrinkable.
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.number = QtWidgets.QLabel(str(number))
        self.number.setObjectName("guideStepNumber")
        self.number.setFixedWidth(14)
        layout.addWidget(self.number)

        self.title = QtWidgets.QLabel()
        self.title.setObjectName("guideStepTitle")
        layout.addWidget(self.title)

        self.marker = QtWidgets.QLabel()
        self.marker.setObjectName("guideStepMarker")
        layout.addWidget(self.marker)

        self.button: QtWidgets.QPushButton | None = None
        if action is not None:
            self.button = QtWidgets.QPushButton()
            self.button.setObjectName("guideStepAction")
            self.button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            layout.addWidget(self.button)

    def set_state(self, state: str) -> None:
        """Colour the step: ``done``, ``next`` or ``locked``."""
        self.setProperty("state", state)
        self.marker.setText({"done": "✓", "next": "→"}.get(state, ""))
        self.title.setProperty("state", state)
        for widget in (self, self.number, self.title, self.marker):
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class GuidePanel(QtWidgets.QFrame):
    """The three-step banner shown above the workspace while work is unfinished."""

    openExampleRequested = QtCore.Signal()
    openCaptureRequested = QtCore.Signal()
    applyRequested = QtCore.Signal()
    dismissRequested = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("guidePanel")
        # The strip must never dictate the window minimum width: its longest
        # caption (the status line, the Russian step buttons) is wider than the
        # workspace can afford, and a guide that forces a 1300 px window defeats
        # the narrow-window layout it is meant to sit above.
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 8)
        outer.setSpacing(6)

        head = QtWidgets.QHBoxLayout()
        head.setSpacing(8)
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("guideTitle")
        head.addWidget(self.title)
        self.status = QtWidgets.QLabel()
        self.status.setObjectName("guideStatus")
        self.status.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )
        head.addWidget(self.status, 1)
        self.hide_button = QtWidgets.QPushButton()
        self.hide_button.setObjectName("guideDismiss")
        self.hide_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.hide_button.clicked.connect(self.dismissRequested.emit)
        head.addWidget(self.hide_button)
        outer.addLayout(head)

        self.step_capture = _Step(1, "example")
        self.step_session = _Step(2, None)
        self.step_rule = _Step(3, "apply")

        steps = QtWidgets.QHBoxLayout()
        steps.setSpacing(6)
        for step in (self.step_capture, self.step_session, self.step_rule):
            steps.addWidget(step)
        steps.addStretch(1)
        outer.addLayout(steps)
        self.step_capture.button.clicked.connect(self.openExampleRequested.emit)
        self.step_rule.button.clicked.connect(self.applyRequested.emit)

        self._capture_name: str = ""
        self._rule_name: str = ""
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
        capture_name: str = "",
        rule_name: str = "",
    ) -> None:
        """Record how far the reader has come and repaint the banner."""
        self._capture_open = bool(capture_open)
        self._session_ready = bool(session_ready)
        self._rule_ready = bool(rule_ready)
        self._applied = bool(applied)
        self._capture_name = capture_name
        self._rule_name = rule_name
        self._refresh()

    def _refresh(self) -> None:
        capture_done = self._capture_open
        session_done = capture_done and self._session_ready
        rule_done = self._rule_ready and session_done and self._applied

        if capture_done and rule_done:
            # Nothing left to explain; the workspace is self-describing now.
            self.setVisible(False)
            return
        self.setVisible(True)

        self.step_capture.set_state("done" if capture_done else "next")
        self.step_session.set_state(
            "done" if session_done else ("next" if capture_done else "locked")
        )
        self.step_rule.set_state(
            "done" if rule_done else ("next" if session_done else "locked")
        )

        if self.step_capture.button is not None:
            self.step_capture.button.setVisible(not capture_done)
        if self.step_rule.button is not None:
            self.step_rule.button.setVisible(session_done and not rule_done)

        self.status.setText(self._status_text())

    def _status_text(self) -> str:
        if not self._capture_open:
            return self.tr(
                "Nothing is open yet: the tool reads a capture file (pcap, pcapng "
                "or the normalized JSON) and a rule that says how to read it."
            )
        parts = [self.tr("capture: {0}").format(self._capture_name)]
        if self._rule_ready:
            parts.append(self.tr("rule: {0}").format(self._rule_name))
        else:
            parts.append(self.tr("no rule yet"))
        return "   ·   ".join(parts)

    # -- presentation ------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Re-apply every caption in the active interface language."""
        self.title.setText(self.tr("Start here"))
        self.hide_button.setText(self.tr("Hide"))
        self.hide_button.setToolTip(
            self.tr("Hide the guide; Help - Quick help brings it back")
        )
        self.status.setToolTip(self.tr("What is open right now"))
        self.step_capture.title.setText(self.tr("Open a recording"))
        self.step_capture.setToolTip(
            self.tr("A pcap, a pcapng or a normalized JSON. Ctrl+O.")
        )
        self.step_capture.button.setText(self.tr("Open the example"))
        self.step_capture.button.setToolTip(
            self.tr("Open the small capture and rule that ship with the tool")
        )
        self.step_session.title.setText(self.tr("Pick a conversation"))
        self.step_session.setToolTip(
            self.tr(
                "Choose the connection on the left; one way or the other is listed under it."
            )
        )
        self.step_rule.title.setText(self.tr("Describe and check"))
        self.step_rule.setToolTip(
            self.tr(
                "A rule says how the bytes are cut into messages and what each field means."
            )
        )
        self.step_rule.button.setText(self.tr("Check the rule"))
        self.step_rule.button.setToolTip(
            self.tr("Apply the rule to the current direction")
        )
        self._refresh()

    def apply_theme(self) -> None:
        """Re-read the active theme for the panel and its steps."""
        token = theme.current()
        radius = token.radius
        self.setStyleSheet(
            f"""
            QFrame#guidePanel {{
                background: {token.surface_alt};
                border: 1px solid {token.border};
                border-radius: {radius}px;
            }}
            QLabel#guideTitle {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY + 2}pt;
            }}
            QLabel#guideStatus {{ color: {token.text_secondary}; font-size: {FONT_SIZE_CAPTION}pt; }}
            QPushButton#guideDismiss {{
                background: transparent;
                color: {token.text_secondary};
                border: 1px solid {token.border};
                border-radius: {radius}px;
                padding: 2px 10px;
            }}
            QPushButton#guideDismiss:hover {{ color: {token.text_primary}; }}
            QFrame#guideStep {{
                background: {token.surface};
                border: 1px solid {token.border};
                border-radius: {radius}px;
            }}
            QFrame#guideStep[state="next"] {{ border: 1px solid {token.accent}; }}
            QLabel#guideStepNumber {{ color: {token.text_secondary}; font-size: {FONT_SIZE_BODY}pt; }}
            QLabel#guideStepTitle {{ color: {token.text_primary}; font-size: {FONT_SIZE_BODY}pt; }}
            QLabel#guideStepTitle[state="done"] {{ color: {token.status_matched_text}; }}
            QLabel#guideStepTitle[state="locked"] {{ color: {token.text_muted}; }}
            QLabel#guideStepMarker {{ color: {token.status_matched_text}; font-size: {FONT_SIZE_BODY}pt; }}
            QLabel#guideStepMarker[state="next"] {{ color: {token.accent}; }}
            QPushButton#guideStepAction {{
                background: {token.accent};
                color: {token.text_on_accent};
                border: none;
                border-radius: {radius}px;
                padding: 4px 12px;
            }}
            QPushButton#guideStepAction:hover {{ background: {token.accent_hover}; }}
            """
        )
        self.title.setFont(theme.heading_font(FONT_SIZE_BODY + 2))
        self.status.setFont(theme.body_font(FONT_SIZE_CAPTION))
        for step in (self.step_capture, self.step_session, self.step_rule):
            step.title.setFont(theme.body_font(FONT_SIZE_BODY))
            step.number.setFont(theme.body_font(FONT_SIZE_BODY))
            step.marker.setFont(theme.body_font(FONT_SIZE_BODY))
