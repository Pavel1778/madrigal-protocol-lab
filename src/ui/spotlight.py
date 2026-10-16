"""The course spotlight: dim everything except the element a step describes.

The window already outlines the element a lesson step points at with a dynamic
property. An outline alone is easy to miss on a busy workspace, so the course
also darkens the rest of the workspace and cuts a lit opening around the real
widget. The spotlight is a view: it is told which widget to light and paints
around it; it never reaches into the window and never runs application logic.

The overlay is transparent to the mouse, so the dimmed areas do not block the
reader from clicking the element the step asks for. It is positioned over the
workspace columns only, never over the tutor strip, so the course buttons stay
fully readable and reachable at every step.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

# The dim wash over the rest of the workspace and the margin the lit opening
# leaves around the target so a border control is not clipped by the edge.
_DIM = QtGui.QColor(9, 10, 11, 150)
_OPENING_MARGIN = 4
_OUTLINE_WIDTH = 2
_OUTLINE_RADIUS = 8
_GLOW_WIDTH = 3


class LearningSpotlight(QtWidgets.QWidget):
    """A transparent overlay that dims the workspace around a target widget."""

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        bounds: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("learningSpotlight")
        # Clicks reach the widget underneath, so the lit element stays usable.
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        # The overlay covers the workspace columns only. The bounds widget (the
        # splitter) keeps it off the tutor strip, so the course buttons stay
        # readable while the workspace around the target is dimmed.
        self._bounds = bounds if bounds is not None else parent
        self._target: QtWidgets.QWidget | None = None
        # Follow the workspace as it is resized or the splitter is dragged, so
        # the dim and the lit opening stay aligned with the real layout.
        self._bounds.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self._bounds and event.type() in (
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.Move,
        ):
            self.refresh()
        return super().eventFilter(obj, event)

    def set_target(self, widget: QtWidgets.QWidget | None) -> None:
        """Light *widget*; ``None`` clears the spotlight and hides the overlay."""
        self._target = widget
        if widget is None:
            self.hide()
            return
        self._fit_parent()
        self.raise_()
        self.show()
        self.update()

    def refresh(self) -> None:
        """Re-fit the overlay after the workspace moved or resized."""
        if self._target is None or not self.isVisible():
            return
        self._fit_parent()
        self.raise_()
        self.update()

    def clear(self) -> None:
        """Drop the target and hide the overlay."""
        self.set_target(None)

    # -- geometry ----------------------------------------------------------

    def _fit_parent(self) -> None:
        parent = self.parentWidget()
        bounds = self._bounds
        if parent is None or bounds is None:
            return
        top_left = bounds.mapTo(parent, QtCore.QPoint(0, 0))
        self.setGeometry(QtCore.QRect(top_left, bounds.size()))

    def _opening(self) -> QtCore.QRect | None:
        """The lit rectangle in this overlay's coordinates, or ``None``.

        The target is mapped through the common ancestor so the opening follows
        the widget wherever the splitter and the layout place it. A target that
        is not a child of this overlay's parent has no opening here.
        """
        target = self._target
        parent = self.parentWidget()
        if target is None or parent is None or not target.isVisible():
            return None
        # Map through the shared parent: the overlay is a sibling of the target,
        # not one of its ancestors, so ``target.mapTo(self, ...)`` is invalid.
        top_left = target.mapTo(parent, QtCore.QPoint(0, 0)) - self.pos()
        rect = QtCore.QRect(top_left, target.size())
        if not self.rect().intersects(rect):
            return None
        return rect.marginsAdded(
            QtCore.QMargins(_OPENING_MARGIN, _OPENING_MARGIN, _OPENING_MARGIN, _OPENING_MARGIN)
        )

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        opening = self._opening()
        if opening is None:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        # Fill the whole overlay, then cut the opening out with the composition
        # mode so the lit widget shows through untouched.
        region = QtGui.QRegion(self.rect())
        region = region.subtracted(QtGui.QRegion(opening, QtGui.QRegion.RegionType.Rectangle))
        painter.setClipRegion(region)
        painter.fillRect(self.rect(), _DIM)
        painter.setClipping(False)
        self._paint_outline(painter, opening)

    def _paint_outline(self, painter: QtGui.QPainter, opening: QtCore.QRect) -> None:
        accent = self._accent()
        pen = QtGui.QPen(accent, _OUTLINE_WIDTH)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        rect = QtCore.QRectF(opening).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(rect, _OUTLINE_RADIUS, _OUTLINE_RADIUS)
        glow = QtGui.QColor(accent)
        glow.setAlpha(70)
        glow_pen = QtGui.QPen(glow, _OUTLINE_WIDTH + _GLOW_WIDTH * 2)
        painter.setPen(glow_pen)
        painter.drawRoundedRect(rect, _OUTLINE_RADIUS, _OUTLINE_RADIUS)

    @staticmethod
    def _accent() -> QtGui.QColor:
        from . import theme

        try:
            return QtGui.QColor(theme.current().accent)
        except Exception:  # pragma: no cover - theme is always available in the app
            return QtGui.QColor("#A2391D")
