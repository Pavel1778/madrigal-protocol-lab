"""The guided-mode coach: one plain-language hint per step of the workflow.

The window is dense and a reader who has never seen it cannot tell what to do
first. Guided mode is not a separate screen: it is a single strip above the
workspace that names the current step and the next action in words a reader who
does not know TCP can follow, with the technical term, if any, kept in the
tooltip. It steps aside on its own once the workflow is finished, and the reader
can switch it off for good from the settings dialog or the strip itself.

The panel owns no application logic. It is told which step to show and emits the
two intentions the window wires to the existing slots.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import theme
from .constants import FONT_SIZE_BODY, FONT_SIZE_CAPTION

# The workflow is shown as five stages. A stage covers several small states, so
# the reader always sees "step N of 5" rather than a counter that keeps moving.
STEP_COUNT = 5


class GuidedPanel(QtWidgets.QFrame):
    """The one-step-at-a-time coach shown above the workspace."""

    nextRequested = QtCore.Signal()
    dismissRequested = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("guidedPanel")
        # The strip must not dictate the window width: its longest caption is
        # wider than the workspace can afford in a narrow window.
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 10)
        outer.setSpacing(6)

        head = QtWidgets.QHBoxLayout()
        head.setSpacing(8)
        self.step_label = QtWidgets.QLabel()
        self.step_label.setObjectName("guidedStep")
        head.addWidget(self.step_label)
        head.addStretch(1)
        self.dismiss_button = QtWidgets.QPushButton()
        self.dismiss_button.setObjectName("guidedDismiss")
        self.dismiss_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.dismiss_button.clicked.connect(self.dismissRequested.emit)
        head.addWidget(self.dismiss_button)
        outer.addLayout(head)

        self.body = QtWidgets.QLabel()
        self.body.setObjectName("guidedBody")
        self.body.setWordWrap(True)
        outer.addWidget(self.body)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.next_button = QtWidgets.QPushButton()
        self.next_button.setObjectName("guidedPrimary")
        self.next_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.next_button.clicked.connect(self.nextRequested.emit)
        actions.addWidget(self.next_button)
        actions.addStretch(1)
        outer.addLayout(actions)

        self._index = 0
        self.retranslate_ui()
        self.apply_theme()

    # -- state -------------------------------------------------------------

    def set_step(self, index: int) -> None:
        """Show the stage at *index* (0-based, clamped to the stage count)."""
        self._index = max(0, min(index, STEP_COUNT - 1))
        self.retranslate_ui()

    @property
    def step_index(self) -> int:
        """The stage currently shown."""
        return self._index

    # -- content -----------------------------------------------------------

    def _stages(self) -> list[tuple[str, str, str]]:
        """The five stages as ``(title, body, action label)``.

        Written in plain words: the point of the tool is to turn a recording
        into a description of what a device sends, and the reader is told that
        in the same breath as the next click.
        """
        return [
            (
                self.tr("Open a recording"),
                self.tr(
                    "A recording is what a device sent over the network. Open the "
                    "example to see a whole investigation, or open your own file."
                ),
                self.tr("Open the example"),
            ),
            (
                self.tr("Pick a conversation"),
                self.tr(
                    "The list on the left holds the separate conversations in the "
                    "recording. Open one, then choose which way the data flowed."
                ),
                self.tr("Pick a conversation"),
            ),
            (
                self.tr("Say what the bytes mean"),
                self.tr(
                    "The bytes are just numbers until you say what they mean. Build "
                    "a rule: which byte is what. The form explains each part."
                ),
                self.tr("Build a rule"),
            ),
            (
                self.tr("Check the rule"),
                self.tr(
                    "Apply the rule to the bytes you are looking at. Green means the "
                    "rule agrees with the bytes; red means it does not."
                ),
                self.tr("Check the rule"),
            ),
            (
                self.tr("Check on all the data"),
                self.tr(
                    "Run the rule over every conversation, not just this one. What "
                    "does not match is a counterexample: the rule is incomplete."
                ),
                self.tr("Check on all the data"),
            ),
        ]

    # -- presentation ------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Re-apply every caption in the active interface language."""
        title, body, action = self._stages()[self._index]
        self.step_label.setText(
            self.tr("Step {0} of {1}: {2}").format(self._index + 1, STEP_COUNT, title)
        )
        self.body.setText(body)
        self.next_button.setText(action)
        self.dismiss_button.setText(self.tr("Hide hints"))
        self.dismiss_button.setToolTip(
            self.tr("Turn the hints off; Settings brings them back")
        )

    def apply_theme(self) -> None:
        """Re-read the active theme for the strip."""
        token = theme.current()
        radius = token.radius
        self.setStyleSheet(
            f"""
            QFrame#guidedPanel {{
                background: {token.surface_alt};
                border: 1px solid {token.accent};
                border-radius: {radius}px;
            }}
            QLabel#guidedStep {{
                color: {token.text_primary};
                font-size: {FONT_SIZE_BODY + 2}pt;
            }}
            QLabel#guidedBody {{
                color: {token.text_secondary};
                font-size: {FONT_SIZE_BODY}pt;
            }}
            QPushButton#guidedPrimary {{
                background: {token.accent};
                color: {token.text_on_accent};
                border: none;
                border-radius: {radius}px;
                padding: 6px 16px;
            }}
            QPushButton#guidedPrimary:hover {{ background: {token.accent_hover}; }}
            QPushButton#guidedDismiss {{
                background: transparent;
                color: {token.text_secondary};
                border: 1px solid {token.border};
                border-radius: {radius}px;
                padding: 2px 10px;
            }}
            QPushButton#guidedDismiss:hover {{ color: {token.text_primary}; }}
            """
        )
        self.step_label.setFont(theme.heading_font(FONT_SIZE_BODY + 2))
        self.body.setFont(theme.body_font(FONT_SIZE_BODY))
        self.dismiss_button.setFont(theme.body_font(FONT_SIZE_CAPTION))
        self.next_button.setFont(theme.body_font(FONT_SIZE_BODY))
