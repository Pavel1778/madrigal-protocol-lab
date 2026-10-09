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


class SessionTree(QtWidgets.QTreeWidget):
    """Tree of sessions and their directions."""

    directionSelected = QtCore.Signal(str, str)  # session_id, direction

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderLabels(["session", "traffic"])
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setFont(theme.body_font(10))
        self.header().setStretchLastSection(True)
        self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._model: CaptureModel | None = None
        self.itemSelectionChanged.connect(self._on_selection)

    def load(self, model: CaptureModel) -> None:
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
        parent.setFont(0, theme.heading_font(10))
        parent.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("session", session.session_id))
        parent.setToolTip(
            0,
            f"{session.endpoints}\nroles: {session.role_a} / {session.role_b}\n"
            f"packets: {session.packet_count}",
        )
        if types:
            parent.setForeground(0, QtGui.QColor(theme.INCOMPLETE_TEXT))
        self.addTopLevelItem(parent)

        for direction, size in session.direction_bytes.items():
            child = QtWidgets.QTreeWidgetItem([direction, f"{size} B"])
            child.setFont(0, theme.body_font(10))
            child.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("direction", session.session_id, direction))
            child.setToolTip(
                0,
                f"{session.session_id} {direction}: {size} bytes",
            )
            if any(d.direction == direction for d in diagnostics):
                child.setForeground(0, QtGui.QColor(theme.INCOMPLETE_TEXT))
            parent.addChild(child)

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
        for index in range(self.topLevelItemCount()):
            parent = self.topLevelItem(index)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                data = child.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if data and data[1] == session_id and data[2] == direction:
                    self.setCurrentItem(child)
                    return
