"""Layout helpers shared by the interface widgets.

The panels hold rows of short captions and buttons — the byte legend, the rule
actions. Those rows have to stay within the panel when the window is small or
the interface is switched to a language whose labels are wider. A plain
``QHBoxLayout`` cannot do that: its minimum width is the sum of its children, so
a row of six legend chips silently sets a floor on the whole window and the
splitter refuses to shrink past it.

:class:`FlowLayout` lays the same children out left to right, wrapping to a new
line when the next one would cross the right edge. Its minimum width is the
widest single child rather than their sum, so the row folds instead of pushing
the window wider. It is a ``QLayout``, so children are still added with
``addWidget`` and participate in the normal size machinery.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

_DEFAULT_SPACING = 6


class FlowLayout(QtWidgets.QLayout):
    """A left-to-right layout that wraps its items onto further lines.

    Item layout is decided in :meth:`_do_layout`, which both the geometry pass
    and the height-for-width query run, so the reported height always matches
    the arrangement that is drawn.
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        margin: int = 0,
        spacing: int = _DEFAULT_SPACING,
    ) -> None:
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    # -- QLayout plumbing --------------------------------------------------

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:  # noqa: N802 - Qt name
        """Append *item* to the flow order."""
        self._items.append(item)

    def count(self) -> int:
        """Return the number of items in the flow."""
        return len(self._items)

    def itemAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # noqa: N802 - Qt name
        """Return the item at *index*, or ``None`` when out of range."""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # noqa: N802 - Qt name
        """Remove and return the item at *index*, or ``None`` when out of range."""
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> QtCore.Qt.Orientation:  # noqa: N802 - Qt name
        """Return no expanding direction; the flow grows downward only."""
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt name
        """Report that the height depends on the available width."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt name
        """Return the height the flow needs at *width*."""
        return self._do_layout(QtCore.QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # noqa: N802 - Qt name
        """Arrange the items inside *rect*."""
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt name
        """Return the preferred size, which is the minimum."""
        return self.minimumSize()

    def minimumSize(self) -> QtCore.QSize:  # noqa: N802 - Qt name
        """Return the size of a single line holding the widest item."""
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    # -- arrangement -------------------------------------------------------

    def _do_layout(self, rect: QtCore.QRect, test_only: bool) -> int:
        """Place items in rows within *rect* and return the used height."""
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = area.x()
        y = area.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > area.right() + 1 and line_height > 0:
                x = area.x()
                y += line_height + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()
