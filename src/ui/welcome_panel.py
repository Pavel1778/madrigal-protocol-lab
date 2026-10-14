"""First-run welcome panel.

The window opens on this panel before a capture is loaded. It states, in three
plain sentences, what the tool is for and what the first three clicks are, and
it offers a single button that loads a capture that ships with the application.
Nothing here needs a manual: the reader sees the workflow and a way to try it
without hunting for a file.

The panel is deliberately a widget rather than a modal dialog, so it sits in the
middle of the window where the bytes will appear and is replaced the moment a
capture is opened.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from . import guidance, theme
from .constants import FONT_SIZE_BODY


class WelcomePanel(QtWidgets.QWidget):
    """A short orientation card with a demo button."""

    openDemoRequested = QtCore.Signal()
    openCaptureRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.title = QtWidgets.QLabel()
        self.title.setProperty("role", "heading")
        self.title.setFont(theme.heading_font(FONT_SIZE_BODY + 6))
        layout.addWidget(self.title)

        self.intro = QtWidgets.QLabel()
        self.intro.setWordWrap(True)
        self.intro.setProperty("role", "secondary")
        self.intro.setFont(theme.body_font(FONT_SIZE_BODY))
        layout.addWidget(self.intro)

        self._step_titles: list[QtWidgets.QLabel] = []
        self._step_bodies: list[QtWidgets.QLabel] = []
        for _title, _body in guidance.STEPS:
            heading = QtWidgets.QLabel()
            heading.setProperty("role", "heading")
            heading.setFont(theme.heading_font(FONT_SIZE_BODY))
            heading.setWordWrap(True)
            layout.addWidget(heading)
            body = QtWidgets.QLabel()
            body.setWordWrap(True)
            body.setProperty("role", "secondary")
            body.setFont(theme.body_font(FONT_SIZE_BODY))
            layout.addWidget(body)
            self._step_titles.append(heading)
            self._step_bodies.append(body)

        buttons = QtWidgets.QHBoxLayout()
        self.demo_button = QtWidgets.QPushButton()
        self.demo_button.setProperty("accent", "true")
        self.demo_button.clicked.connect(self.openDemoRequested)
        self.capture_button = QtWidgets.QPushButton()
        self.capture_button.clicked.connect(self.openCaptureRequested)
        buttons.addWidget(self.demo_button)
        buttons.addWidget(self.capture_button)
        buttons.addStretch(1)
        layout.addSpacing(6)
        layout.addLayout(buttons)
        layout.addStretch(1)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Apply the captions in the active interface language."""
        self.title.setText(self.tr("Welcome to the protocol laboratory"))
        self.intro.setText(
            self.tr(
                "This tool helps you work out what an unknown network protocol is "
                "saying. You give it a recording of the traffic and a note of what "
                "you did at the time; it lines the two up and lets you describe the "
                "message format until the bytes make sense."
            )
        )
        for (step_title, step_body), title, body in zip(
            guidance.STEPS, self._step_titles, self._step_bodies, strict=False
        ):
            title.setText(self.tr(step_title))
            body.setText(self.tr(step_body))
        self.demo_button.setText(self.tr("Open the built-in demo"))
        self.demo_button.setToolTip(
            self.tr("Loads a small capture that ships with the application, plus a matching rule.")
        )
        self.capture_button.setText(self.tr("Open a capture..."))
        self.capture_button.setToolTip(self.tr("Open a PCAP, PCAPNG or normalized JSON file."))

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Take focus so the panel is the obvious starting point."""
        super().showEvent(event)
        self.demo_button.setFocus()

    def apply_theme(self) -> None:
        """Re-apply the fonts from the active theme.

        The panel is text only, so a theme change only means the fonts are
        rebuilt from the new palette; the captions do not change.
        """
        self.title.setFont(theme.heading_font(FONT_SIZE_BODY + 6))
        for label in (self.intro, *self._step_bodies):
            label.setFont(theme.body_font(FONT_SIZE_BODY))
        for label in self._step_titles:
            label.setFont(theme.heading_font(FONT_SIZE_BODY))
