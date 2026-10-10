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

# The annotation kinds that have a colour; the set does not depend on the theme.
_KIND_KEYS = frozenset(
    {
        GAP,
        AMBIGUITY,
        MATCHED,
        MISMATCHED,
        INCOMPLETE,
        AMBIGUOUS,
        NOT_APPLICABLE,
        UNCOVERED,
    }
)


def _kind_colours() -> dict[str, tuple[str, str]]:
    """Byte-annotation fills for the active theme."""
    token = theme.current()
    return {
        GAP: (token.gap, token.text_primary),
        AMBIGUITY: (token.status_ambiguous, token.text_primary),
        MATCHED: (token.status_matched, token.text_primary),
        MISMATCHED: (token.status_mismatched, token.text_primary),
        INCOMPLETE: (token.status_incomplete, token.text_primary),
        AMBIGUOUS: (token.status_ambiguous, token.text_primary),
        NOT_APPLICABLE: (token.status_not_applicable, token.text_secondary),
        UNCOVERED: (token.status_uncovered, token.text_secondary),
    }


def _printable(byte: int) -> str:
    return chr(byte) if 32 <= byte < 127 else "."


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
        self._header.setFixedHeight(20)
        self._header.setText(self._column_header())
        self._style_header()

    def _style_header(self) -> None:
        token = theme.current()
        self._header.setStyleSheet(
            f"color: {token.text_secondary}; background: {token.surface};"
        )

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

    def apply_theme(self) -> None:
        """Re-read the active theme: header colours and byte annotations."""
        self._style_header()
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
        kind_colours = _kind_colours()
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
            for start, stop in _line_spans(run_start, end):
                selections.append(self._selection(start, stop, background, foreground))

        for index, annotation in enumerate(self._annotations):
            colour = kind_colours.get(annotation.kind)
            if colour is None:
                colour = None
            if colour != run_hex:
                flush(index)
                run_start = index
                run_hex = colour
                run_kind = annotation.kind
        flush(len(self._annotations))
        self.setExtraSelections(selections)

    def _selection(self, start: int, end: int, background: str, foreground: str):
        selection = QtWidgets.QTextEdit.ExtraSelection()
        fmt = QtGui.QTextCharFormat()
        fmt.setBackground(QtGui.QColor(background))
        fmt.setForeground(QtGui.QColor(foreground))
        cursor = self.textCursor()
        cursor.setPosition(_byte_char_index(start))
        cursor.setPosition(_byte_char_index(end - 1) + 2, QtGui.QTextCursor.MoveMode.KeepAnchor)
        selection.cursor = cursor
        selection.format = fmt
        return selection

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
            self.byteHovered.emit(offset)
        super().mouseMoveEvent(event)

    def scroll_to_byte(self, offset: int) -> None:
        """Centre the view on ``offset``; a no-op when out of range."""
        if not (0 <= offset < max(1, len(self._data))):
            return
        cursor = self.textCursor()
        cursor.setPosition(min(_byte_char_index(offset), self.document().characterCount() - 1))
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
        every other byte ``not_applicable``.
    """
    annotations = [ByteAnnotation(kind=NOT_APPLICABLE) for _ in range(len(stream.data))]
    for hole in stream.diagnostics:
        kind = GAP if hole.type == "gap" else AMBIGUITY if hole.type == "ambiguity" else UNCOVERED
        for offset in range(hole.offset, min(hole.end, len(annotations))):
            annotations[offset] = ByteAnnotation(kind=kind, label=hole.type)
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
            kind = status if status in _KIND_KEYS else FIELD
            for offset in range(start, min(end, len(annotations))):
                if annotations[offset].kind in (GAP, AMBIGUITY):
                    continue
                annotations[offset] = ByteAnnotation(
                    kind=kind,
                    label=field.field_name,
                    value=field.value,
                    status=status,
                    is_hypothesis=bool(field.hypothesis),
                )
    return annotations
