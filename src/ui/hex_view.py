"""Hex viewer for one directional stream.

Three aligned columns: offset, hex bytes, ASCII. The bytes are annotated with
what is known about them: a gap is hatched red, an ambiguity is amber, a byte
covered by a matched field is green, an uncovered byte is grey. A click reports
the byte offset so the window can show where the byte came from.

Only the text is handed to ``QPlainTextEdit``, which lays out and scrolls large
streams efficiently; annotations are applied as extra selections over the
already-rendered text rather than by drawing the bytes by hand.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..protocol.stream import DirectionalStream
from . import theme
from .model import (
    AMBIGUITY,
    AMBIGUOUS,
    FIELD,
    GAP,
    INCOMPLETE,
    MATCHED,
    MISMATCHED,
    NOT_APPLICABLE,
    UNCOVERED,
    ByteAnnotation,
    RuleApplication,
)

_BYTES_PER_LINE = 16
_PREFIX = 10  # "%08x" plus two spaces
_HEX_WIDTH = _BYTES_PER_LINE * 3
_ASCII_START = _PREFIX + _HEX_WIDTH
_LINE_LEN = _ASCII_START + _BYTES_PER_LINE

_KIND_COLOURS = {
    GAP: (theme.GAP, theme.TEXT),
    AMBIGUITY: (theme.AMBIGUOUS, theme.TEXT),
    MATCHED: (theme.MATCHED, theme.TEXT),
    MISMATCHED: (theme.MISMATCHED, theme.TEXT),
    INCOMPLETE: (theme.INCOMPLETE, theme.TEXT),
    AMBIGUOUS: (theme.AMBIGUOUS, theme.TEXT),
    NOT_APPLICABLE: (theme.NOT_APPLICABLE, theme.TEXT_SECONDARY),
    UNCOVERED: (theme.UNCOVERED, theme.TEXT_SECONDARY),
}

# Kinds drawn with a hatch pattern instead of a flat fill, so a missing or
# ambiguous range reads as different from a byte a rule simply matched. The
# pattern is a small pixmap used as a QBrush texture.
_HATCHED = {GAP, AMBIGUITY, AMBIGUOUS, INCOMPLETE, MISMATCHED}
_HATCH_COLOUR = {
    GAP: theme.GAP,
    AMBIGUITY: theme.AMBIGUOUS,
    AMBIGUOUS: theme.AMBIGUOUS,
    INCOMPLETE: theme.INCOMPLETE,
    MISMATCHED: theme.MISMATCHED,
}
_HATCH_BASE = theme.PANEL


def _printable(byte: int) -> str:
    return chr(byte) if 32 <= byte < 127 else "."


def _hatch_pixmap(colour: str, base: str) -> QtGui.QPixmap:
    """A 6x6 diagonal hatch pixmap used as a brush texture.

    A texture rather than a solid fill so a missing or ambiguous range is
    distinguishable from a plain status fill at a glance.
    """
    pixmap = QtGui.QPixmap(6, 6)
    pixmap.fill(QtGui.QColor(base))
    painter = QtGui.QPainter(pixmap)
    painter.setPen(QtGui.QColor(colour))
    painter.drawLine(0, 6, 6, 0)
    painter.drawLine(-3, 3, 3, -3)
    painter.drawLine(3, 9, 9, 3)
    painter.end()
    return pixmap


def _brush_for(kind: str | None, background: str) -> QtGui.QBrush:
    """The background brush for ``kind``: a hatch for gap and ambiguity, a
    flat colour otherwise."""
    if kind in _HATCHED:
        return QtGui.QBrush(_hatch_pixmap(_HATCH_COLOUR[kind], _HATCH_BASE))
    return QtGui.QBrush(QtGui.QColor(background))


# Byte kinds shown in the legend, in the order a reader meets them.
LEGEND_KINDS = (
    (GAP, "gap"),
    (AMBIGUITY, "ambiguity"),
    (MATCHED, "matched"),
    (MISMATCHED, "mismatched"),
    (INCOMPLETE, "incomplete"),
    (UNCOVERED, "uncovered"),
)


def legend_swatch(kind: str) -> QtGui.QPixmap:
    """A swatch painted with the exact brush used for ``kind``.

    The swatch is filled with the same :func:`_brush_for` result the view uses,
    so the legend cannot drift from the bytes it explains.
    """
    pixmap = QtGui.QPixmap(12, 12)
    pixmap.fill(QtGui.QColor(_HATCH_BASE))
    painter = QtGui.QPainter(pixmap)
    painter.fillRect(0, 0, 12, 12, _brush_for(kind, _KIND_COLOURS[kind][0]))
    painter.end()
    return pixmap


class HexView(QtWidgets.QPlainTextEdit):
    """Read-only hex view of a byte stream."""

    byteClicked = QtCore.Signal(int)
    byteHovered = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(theme.mono_font())
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWordWrapMode(QtGui.QTextOption.WrapMode.NoWrap)
        self.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.viewport().setMouseTracking(True)
        self.setTabChangesFocus(True)
        self._data = b""
        self._annotations: list[ByteAnnotation] = []
        self._header = QtWidgets.QLabel(self)
        self._header.setFont(theme.body_font(9))
        self._header.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: {theme.PANEL};")
        self._header.setFixedHeight(20)
        self._header.setText(self._column_header())

    def _column_header(self) -> str:
        return (
            "offset    "
            + "".join(f"{i:02x} " for i in range(_BYTES_PER_LINE))
            + "ascii"
        )

    # -- data --------------------------------------------------------------

    def set_stream(self, data: bytes, annotations: list[ByteAnnotation] | None = None) -> None:
        """Render *data*, applying optional per-byte *annotations*."""
        self._data = bytes(data)
        self._annotations = list(annotations or [])
        self.setPlainText(self._render_text())
        self._apply_annotations()

    def set_annotations(self, annotations: list[ByteAnnotation] | None) -> None:
        """Replace the annotations without re-rendering the bytes."""
        self._annotations = list(annotations or [])
        self._apply_annotations()

    def clear_stream(self) -> None:
        """Drop the bytes and annotations."""
        self._data = b""
        self._annotations = []
        self.setPlainText("")
        self.setExtraSelections([])

    def show_hint(self, text: str) -> None:
        """Show a single explanatory line when there are no bytes to draw.

        Used for the first-run state, so an empty view says why it is empty
        instead of looking broken.
        """
        self._data = b""
        self._annotations = []
        self.setPlainText(text)
        self.setExtraSelections([])

    @property
    def data(self) -> bytes:
        """The bytes currently shown."""
        return self._data

    def _render_text(self) -> str:
        lines: list[str] = []
        for start in range(0, len(self._data), _BYTES_PER_LINE):
            chunk = self._data[start : start + _BYTES_PER_LINE]
            hexpart = "".join(f"{b:02x} " for b in chunk)
            hexpart = hexpart.ljust(_HEX_WIDTH)
            ascii_part = "".join(_printable(b) for b in chunk)
            ascii_part = ascii_part.ljust(_BYTES_PER_LINE)
            lines.append(f"{start:08x}  {hexpart}{ascii_part}")
        return "\n".join(lines)

    # -- annotation --------------------------------------------------------

    def _apply_annotations(self) -> None:
        selections: list[QtWidgets.QTextEdit.ExtraSelection] = []
        if not self._data:
            self.setExtraSelections([])
            return
        # Group contiguous bytes that share a colour so selection count stays
        # proportional to the number of runs, not the number of bytes.
        run_kind: str | None = None
        run_start = 0
        run_hex: tuple[str, str] | None = None

        def flush(end: int) -> None:
            """Emit one extra selection per line span of the current run."""
            if run_kind is None or run_hex is None or end <= run_start:
                return
            background, foreground = run_hex
            brush = _brush_for(run_kind, background)
            for start, stop in _line_spans(run_start, end):
                selections.append(self._selection(start, stop, brush, foreground))

        for index, annotation in enumerate(self._annotations):
            colour = _KIND_COLOURS.get(annotation.kind)
            if colour != run_hex:
                flush(index)
                run_start = index
                run_hex = colour
                run_kind = annotation.kind
        flush(len(self._annotations))
        self.setExtraSelections(selections)

    def _selection(self, start: int, end: int, brush, foreground: str):
        selection = QtWidgets.QTextEdit.ExtraSelection()
        fmt = QtGui.QTextCharFormat()
        fmt.setBackground(brush)
        fmt.setForeground(QtGui.QColor(foreground))
        cursor = self.textCursor()
        cursor.setPosition(_byte_char_index(start))
        cursor.setPosition(_byte_char_index(end - 1) + 2, QtGui.QTextCursor.MoveMode.KeepAnchor)
        selection.cursor = cursor
        selection.format = fmt
        return selection

    def annotation_at(self, offset: int) -> ByteAnnotation | None:
        """The annotation for byte ``offset``, or ``None``."""
        if 0 <= offset < len(self._annotations):
            return self._annotations[offset]
        return None

    def byte_tooltip(self, offset: int) -> str:
        """A tooltip for byte ``offset``: offset, hex, kind and origin."""
        if not 0 <= offset < len(self._data):
            return ""
        annotation = self.annotation_at(offset)
        parts = [f"offset {offset}", f"0x{self._data[offset]:02x}"]
        if annotation is not None:
            parts.append(annotation.kind)
            if annotation.label:
                parts.append(annotation.label)
            if annotation.value is not None:
                parts.append(f"value {annotation.value}")
            if annotation.is_hypothesis:
                parts.append("hypothesis")
            if annotation.packet_index is not None:
                parts.append(f"packet {annotation.packet_index}")
            if annotation.seq is not None:
                parts.append(f"seq {annotation.seq}")
        return "  ".join(str(p) for p in parts)

    # -- interaction -------------------------------------------------------

    def byte_at(self, position: QtCore.QPoint) -> int | None:
        """Byte offset under *position*, or ``None`` when outside the bytes."""
        cursor = self.cursorForPosition(position)
        block = cursor.block()
        line_index = block.blockNumber()
        column = cursor.positionInBlock()
        if column < _PREFIX:
            return None
        if column < _ASCII_START:
            byte_in_line = (column - _PREFIX) // 3
        else:
            byte_in_line = column - _ASCII_START
        if not 0 <= byte_in_line < _BYTES_PER_LINE:
            return None
        offset = line_index * _BYTES_PER_LINE + byte_in_line
        if 0 <= offset < len(self._data):
            return offset
        return None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Emit :attr:`byteClicked` for the byte under the cursor."""
        offset = self.byte_at(event.position().toPoint())
        if offset is not None:
            self.byteClicked.emit(offset)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Emit :attr:`byteHovered` for the byte under the cursor."""
        offset = self.byte_at(event.position().toPoint())
        if offset is not None:
            self.setToolTip(self.byte_tooltip(offset))
            self.byteHovered.emit(offset)
        else:
            self.setToolTip("")
        super().mouseMoveEvent(event)

    def scroll_to_byte(self, offset: int) -> None:
        """Centre the view on ``offset``; a no-op when out of range."""
        if not (0 <= offset < max(1, len(self._data))):
            return
        cursor = self.textCursor()
        cursor.setPosition(min(_byte_char_index(offset), self.document().characterCount() - 1))
        self.setTextCursor(cursor)
        self.centerCursor()

    def highlight_range(self, offset: int, length: int = 1) -> None:
        """Select ``length`` bytes from ``offset`` and centre them.

        The selection marks the whole message a counterexample belongs to, so
        the bytes at fault are visible as a block, not as a single byte. The
        cursor and the selection end are clamped to the document, so a range
        that runs past the last byte still leaves a valid selection.
        """
        if not self._data or length <= 0:
            return
        start = max(0, min(offset, len(self._data) - 1))
        stop = max(start + 1, min(offset + length, len(self._data)))
        last = self.document().characterCount() - 1
        cursor = self.textCursor()
        cursor.setPosition(min(_byte_char_index(start), last))
        cursor.setPosition(
            min(_byte_char_index(stop - 1) + 2, last), QtGui.QTextCursor.MoveMode.KeepAnchor
        )
        self.setTextCursor(cursor)
        self.centerCursor()


def _byte_char_index(offset: int) -> int:
    line = offset // _BYTES_PER_LINE
    column = offset % _BYTES_PER_LINE
    return line * (_LINE_LEN + 1) + _PREFIX + column * 3


def _line_spans(start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    current = start
    while current < end:
        line_end = (current // _BYTES_PER_LINE + 1) * _BYTES_PER_LINE
        stop = min(end, line_end)
        spans.append((current, stop))
        current = stop
    return spans


def annotations_from_stream(stream: DirectionalStream) -> list[ByteAnnotation]:
    """One annotation per byte derived from a stream's diagnostics.

    Args:
        stream: The directional stream to annotate.

    Returns:
        One annotation per byte; diagnostics become ``gap``/``ambiguity`` and
        every other byte ``not_applicable``. Each byte carries the packet index
        and sequence number of the range it came from, when known.
    """
    annotations = [ByteAnnotation(kind=NOT_APPLICABLE) for _ in range(len(stream.data))]
    for hole in stream.provenance:
        for offset in range(hole.offset, min(hole.end, len(annotations))):
            annotations[offset] = ByteAnnotation(
                kind=NOT_APPLICABLE,
                packet_index=getattr(hole, "packet_index", None),
                seq=getattr(hole, "seq", None),
            )
    for hole in stream.diagnostics:
        kind = GAP if hole.type == "gap" else AMBIGUITY if hole.type == "ambiguity" else UNCOVERED
        for offset in range(hole.offset, min(hole.end, len(annotations))):
            existing = annotations[offset]
            annotations[offset] = ByteAnnotation(
                kind=kind,
                label=hole.type,
                packet_index=existing.packet_index,
                seq=existing.seq,
            )
    return annotations


def annotations_from_application(
    application: RuleApplication, stream: DirectionalStream
) -> list[ByteAnnotation]:
    """Annotate every byte with the rule verdict that covers it.

    A byte covered by no field is left ``uncovered``. A byte inside a gap or an
    ambiguity keeps that diagnostic, because missing bytes are not a field
    verdict.

    Args:
        application: The rule application whose field verdicts are applied.
        stream: The directional stream the application was run on.

    Returns:
        One annotation per byte, starting from the stream diagnostics.
    """
    annotations = annotations_from_stream(stream)
    for message in application.messages:
        if message.status.value in (NOT_APPLICABLE,):
            continue
        for field in message.fields:
            if field.field_offset is None or field.field_length is None:
                continue
            start = message.offset + field.field_offset
            end = start + field.field_length
            status = field.status.value
            kind = status if status in _KIND_COLOURS else FIELD
            for offset in range(start, min(end, len(annotations))):
                if annotations[offset].kind in (GAP, AMBIGUITY):
                    continue
                existing = annotations[offset]
                annotations[offset] = ByteAnnotation(
                    kind=kind,
                    label=field.field_name,
                    value=field.value,
                    status=status,
                    is_hypothesis=bool(field.hypothesis),
                    packet_index=existing.packet_index,
                    seq=existing.seq,
                )
    return annotations
