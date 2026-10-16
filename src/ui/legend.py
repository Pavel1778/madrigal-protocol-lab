"""The byte-annotation legend: a compact, collapsible strip above the hex view.

The legend explains the colours painted over the bytes. It is a strip of its own
above the hex view rather than a widget beside the direction selector, so it
cannot overlap the bytes or take width from the ASCII column. The chips flow onto
further lines when the window is narrow, and the whole strip can be collapsed to
its title so a reader who already knows the vocabulary gets the height back.

Each chip is a swatch painted with the exact brush the hex view uses for that
kind, so the legend cannot drift from the bytes it explains. The swatch carries
the same explanatory tooltip as the caption next to it.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import theme
from .constants import FONT_SIZE_CAPTION, LEGEND_SWATCH_PX
from .hex_view import LEGEND_KINDS, legend_label, legend_swatch, legend_tooltip
from .layout import FlowLayout


class AnnotationLegend(QtWidgets.QFrame):
    """A collapsible row of painted byte-kind swatches and their captions."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("annotationLegend")
        # The strip must not dictate the window width: its row folds instead of
        # setting a floor on the splitter.
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 6)
        outer.setSpacing(4)

        head = QtWidgets.QHBoxLayout()
        head.setSpacing(8)
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("legendTitle")
        head.addWidget(self.title)
        head.addStretch(1)
        self.toggle = QtWidgets.QPushButton()
        self.toggle.setObjectName("legendToggle")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(True)
        self.toggle.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.toggle.toggled.connect(self.set_expanded)
        head.addWidget(self.toggle)
        outer.addLayout(head)

        self.body = QtWidgets.QWidget()
        flow = FlowLayout(self.body, margin=0, spacing=10)
        self.chips: list[QtWidgets.QLabel] = []
        for kind, _name in LEGEND_KINDS:
            swatch = QtWidgets.QLabel()
            swatch.setPixmap(legend_swatch(kind))
            swatch.setFixedSize(LEGEND_SWATCH_PX, LEGEND_SWATCH_PX)
            swatch.setToolTip(legend_tooltip(kind))
            caption = QtWidgets.QLabel(legend_label(kind))
            caption.setFont(theme.body_font(FONT_SIZE_CAPTION))
            caption.setProperty("role", "secondary")
            caption.setToolTip(legend_tooltip(kind))
            flow.addWidget(swatch)
            flow.addWidget(caption)
            self.chips.append(caption)
        outer.addWidget(self.body)

        self._expanded = True
        self.retranslate_ui()
        self.apply_theme()

    # -- state -------------------------------------------------------------

    def is_expanded(self) -> bool:
        """Whether the chips are shown (True) or only the title bar (False)."""
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Show or hide the chips, keeping the title bar visible."""
        self._expanded = bool(expanded)
        self.body.setVisible(self._expanded)
        if self.toggle.isChecked() != self._expanded:
            self.toggle.setChecked(self._expanded)
        self.toggle.setText(self.tr("Hide") if self._expanded else self.tr("Show"))
        self.toggle.setToolTip(
            self.tr("Collapse the byte-state legend")
            if self._expanded
            else self.tr("Expand the byte-state legend")
        )

    # -- labels and theme --------------------------------------------------

    def retranslate_ui(self) -> None:
        """Re-apply every caption to the active interface language."""
        self.title.setText(self.tr("Byte states"))
        self.toggle.setText(self.tr("Hide") if self._expanded else self.tr("Show"))
        self.toggle.setToolTip(
            self.tr("Collapse the byte-state legend")
            if self._expanded
            else self.tr("Expand the byte-state legend")
        )
        for caption, (kind, _name) in zip(self.chips, LEGEND_KINDS, strict=False):
            caption.setText(legend_label(kind))
            caption.setToolTip(legend_tooltip(kind))
        # The swatches carry the same tooltips; refresh them too.
        swatches = [
            w
            for w in self.body.findChildren(QtWidgets.QLabel)
            if not w.pixmap().isNull()
        ]
        for swatch, (kind, _name) in zip(swatches, LEGEND_KINDS, strict=False):
            swatch.setToolTip(legend_tooltip(kind))

    def apply_theme(self) -> None:
        """Re-read the active theme for the strip and its controls."""
        token = theme.current()
        radius = token.radius
        # The application style sheet sets a family on every QWidget, and a
        # style-sheet rule outranks setFont, so the families are restated here
        # where they win over the global rule.
        title_font = theme.heading_font(FONT_SIZE_CAPTION)
        body_font = theme.body_font(FONT_SIZE_CAPTION)
        self.setStyleSheet(
            f"""
            QFrame#annotationLegend {{
                background: {token.surface_alt};
                border: 1px solid {token.border};
                border-radius: {radius}px;
            }}
            QLabel#legendTitle {{
                color: {token.text_secondary};
                font-family: "{title_font.family()}";
                font-size: {FONT_SIZE_CAPTION}pt;
            }}
            QPushButton#legendToggle {{
                background: transparent;
                color: {token.text_secondary};
                border: 1px solid {token.border};
                border-radius: {radius}px;
                padding: 1px 8px;
            }}
            QPushButton#legendToggle:hover {{ color: {token.text_primary}; }}
            """
        )
        self.title.setFont(title_font)
        self.toggle.setFont(body_font)
        for caption in self.chips:
            caption.setFont(body_font)
