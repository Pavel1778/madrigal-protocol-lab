"""Session tree.

Shows every session of the open capture as a parent node, and its two
directions below it. A direction node carries the byte count and a marker when
the direction has diagnostics, so a gap or an ambiguity is visible before the
bytes are opened.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from . import theme
from .model import CaptureModel, SessionInfo

# Role holding whether an item carries a diagnostic (so it can be recoloured
# when the theme changes without rebuilding the tree).
_DIAG_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


class SessionTree(QtWidgets.QTreeWidget):
    """Tree of sessions and their directions."""

    directionSelected = QtCore.Signal(str, str)  # session_id, direction

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderLabels([self.tr("session"), self.tr("traffic")])
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self._font_size = 10
        self.setFont(theme.body_font(self._font_size))
        self.header().setStretchLastSection(True)
        self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._model: CaptureModel | None = None
        self.itemSelectionChanged.connect(self._on_selection)

    def set_font_size(self, size: int) -> None:
        """Set the tree font size and re-apply it to every row.

        Session rows use the heading font and direction rows the body font, so
        both are refreshed, not just the widget default.
        """
        self._font_size = max(6, int(size))
        self._reapply_row_fonts()

    def apply_zoom(self) -> None:
        """Re-read every row font so the tree follows the active zoom."""
        self._reapply_row_fonts()

    def _reapply_row_fonts(self) -> None:
        self.setFont(theme.body_font(self._font_size))
        for index in range(self.topLevelItemCount()):
            parent = self.topLevelItem(index)
            parent.setFont(0, theme.heading_font(self._font_size))
            for child_index in range(parent.childCount()):
                parent.child(child_index).setFont(0, theme.body_font(self._font_size))

    def load(self, model: CaptureModel) -> None:
        """Rebuild the tree from *model* and select the first direction."""
        self._model = model
        self.clear()
        for session in model.sessions:
            self._add_session(session)
        if self.topLevelItemCount():
            first = self.topLevelItem(0)
            first.setExpanded(True)
            if first.childCount():
                first.child(0).setSelected(True)

    def _add_session(self, session: SessionInfo) -> None:
        diagnostics = session.diagnostics
        types = sorted({d.type for d in diagnostics})
        summary = "  ".join(
            f"{name}:{size} B" for name, size in session.direction_bytes.items()
        )
        label = session.session_id
        if types:
            label = f"{label}   [{', '.join(types)}]"
        parent = QtWidgets.QTreeWidgetItem([label, summary])
        parent.setFont(0, theme.heading_font(self._font_size))
        parent.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("session", session.session_id))
        parent.setToolTip(
            0,
            f"{session.endpoints}\n"
            + self.tr("roles: {0} / {1}").format(session.role_a, session.role_b)
            + "\n"
            + self.tr("packets: {0}").format(session.packet_count),
        )
        if types:
            parent.setData(0, _DIAG_ROLE, True)
            parent.setForeground(0, QtGui.QColor(theme.current().status_incomplete_text))
        else:
            parent.setData(0, _DIAG_ROLE, False)
        self.addTopLevelItem(parent)

        for direction, size in session.direction_bytes.items():
            child = QtWidgets.QTreeWidgetItem([direction, f"{size} B"])
            child.setFont(0, theme.body_font(self._font_size))
            child.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("direction", session.session_id, direction))
            child.setToolTip(
                0,
                self.tr("{0} {1}: {2} bytes").format(session.session_id, direction, size),
            )
            has_diag = any(d.direction == direction for d in diagnostics)
            child.setData(0, _DIAG_ROLE, has_diag)
            if has_diag:
                child.setForeground(0, QtGui.QColor(theme.current().status_incomplete_text))
            parent.addChild(child)

    def retranslate_ui(self) -> None:
        """Re-apply the header labels and rebuild the rows in the active language."""
        self.setHeaderLabels([self.tr("session"), self.tr("traffic")])
        if self._model is not None:
            self.load(self._model)

    def apply_theme(self) -> None:
        """Recolour diagnostic items in the active theme."""
        colour = QtGui.QColor(theme.current().status_incomplete_text)
        for index in range(self.topLevelItemCount()):
            parent = self.topLevelItem(index)
            self._recolour(parent, 0, colour)
            for child_index in range(parent.childCount()):
                self._recolour(parent.child(child_index), 0, colour)

    @staticmethod
    def _recolour(item: QtWidgets.QTreeWidgetItem, column: int, colour: QtGui.QColor) -> None:
        brush = QtGui.QBrush(colour) if item.data(column, _DIAG_ROLE) else QtGui.QBrush()
        item.setForeground(column, brush)

    def _on_selection(self) -> None:
        items = self.selectedItems()
        if not items:
            return
        data = items[0].data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data[0] == "direction":
            self.directionSelected.emit(data[1], data[2])
        elif data[0] == "session":
            session_id = data[1]
            if self._model is not None:
                directions = self._model.directions(session_id)
                if directions:
                    self.directionSelected.emit(session_id, directions[0])

    def select_direction(self, session_id: str, direction: str) -> None:
        """Select the direction node for (``session_id``, ``direction``)."""
        for index in range(self.topLevelItemCount()):
            parent = self.topLevelItem(index)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                data = child.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if data and data[1] == session_id and data[2] == direction:
                    self.setCurrentItem(child)
                    return
