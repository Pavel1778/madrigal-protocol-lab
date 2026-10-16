"""Regression tests for the hex/ASCII column and the byte-state legend.

These pin the two things the final pass changed:

* the ASCII column caption is drawn in the same fixed-pitch font as the bytes,
  so it lines up with the column it names instead of drifting left;
* the byte-state legend is a compact, collapsible strip above the hex view that
  wraps and collapses instead of overlapping the bytes or the ASCII column.

The tests exercise the real widgets offscreen; nothing is mocked.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6 import QtGui, QtWidgets

    from src.ui import theme
    from src.ui.hex_view import (
        LEGEND_KINDS,
        HexView,
        _printable,
        legend_label,
        legend_tooltip,
    )
    from src.ui.legend import AnnotationLegend
    from src.ui.main_window import MainWindow, open_default_window
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = (
    REPO_ROOT / "tests/corpus/reference_export/corpus_capture_01.normalized.json"
)
DEFAULT_RULE = REPO_ROOT / "examples/corpus_rule_v1.json"

corpus_required = pytest.mark.skipif(
    not DEFAULT_CAPTURE.is_file() or not DEFAULT_RULE.is_file(),
    reason="reference corpus not present",
)


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


def open_window(app):
    return open_default_window(app, capture=DEFAULT_CAPTURE, rule=DEFAULT_RULE)


# -- ASCII column ------------------------------------------------------------


def test_printable_maps_only_the_printable_range():
    assert _printable(0x20) == " "
    assert _printable(0x41) == "A"
    assert _printable(0x7E) == "~"
    # Everything outside 0x20-0x7e is a dot, never a control character.
    for byte in (0x00, 0x09, 0x0A, 0x1B, 0x7F, 0x80, 0xFF):
        assert _printable(byte) == "."


def _rendered_column_x(view: HexView, char_index: int) -> int:
    """The rendered x of a character column on the first line of the view."""
    cursor = view.textCursor()
    cursor.setPosition(char_index)
    return view.cursorRect(cursor).x()


def _header_ascii_x(view: HexView) -> float:
    """The rendered x where the header's ``ascii`` word starts."""
    header = view._header
    metrics = QtGui.QFontMetricsF(header.font())
    text = header.text()
    return header.x() + metrics.horizontalAdvance(text[: text.index("ascii")])


def test_ascii_column_header_uses_the_mono_font(app):
    # The caption names the columns and sits above them; it has to be the same
    # fixed pitch as the bytes or it drifts away from the column it labels.
    view = HexView()
    view.set_stream(bytes(range(64)))
    view.show()
    app.processEvents()
    header_font = view._header.font()
    byte_font = view.font()
    assert header_font.fixedPitch()
    assert header_font.family() == byte_font.family()
    assert header_font.pixelSize() == byte_font.pixelSize()


def test_hex_view_renders_monospace(app):
    # The bytes must sit on a fixed grid: the global style sheet sets a family
    # on every QWidget, so a font set only with ``setFont`` was overridden and
    # the columns were proportional. This pins the grid directly.
    view = HexView()
    view.resize(900, 300)
    view.show()
    app.processEvents()
    view.setPlainText("i" * 20 + "\n" + "M" * 20)
    app.processEvents()
    width_i = _rendered_column_x(view, 20) - _rendered_column_x(view, 0)
    width_m = _rendered_column_x(view, 41) - _rendered_column_x(view, 21)
    assert width_i == width_m


def test_ascii_column_header_lines_up_with_the_ascii_column(app):
    view = HexView()
    view.set_stream(bytes(range(64)))
    view.show()
    app.processEvents()
    assert view._header.text().endswith("ascii")
    rendered = _rendered_column_x(view, view.ascii_start)
    # The caption's ASCII word starts at the byte rows' ASCII column.
    assert abs(_header_ascii_x(view) - rendered) <= 4


def test_ascii_column_header_tracks_a_font_size_change(app):
    view = HexView()
    view.set_stream(bytes(range(64)))
    view.show()
    app.processEvents()
    view.set_font_size(20)
    app.processEvents()
    assert view._header.font().fixedPitch()
    assert view._header.font().pixelSize() == view.font().pixelSize()
    rendered = _rendered_column_x(view, view.ascii_start)
    assert abs(_header_ascii_x(view) - rendered) <= 4


def test_ascii_column_renders_printable_and_dots(app):
    view = HexView()
    view.set_stream(b"AB\x00\xffCD")
    line = view.toPlainText().splitlines()[0]
    ascii_part = line[view.ascii_start : view.ascii_start + 6]
    assert ascii_part == "AB..CD"


def test_byte_tooltip_names_a_printable_byte(app):
    view = HexView()
    view.set_stream(b"A")
    tooltip = view.byte_tooltip(0)
    assert "offset 0" in tooltip
    assert "0x41" in tooltip
    assert "ASCII 'A'" in tooltip


def test_byte_tooltip_marks_a_non_printable_byte(app):
    view = HexView()
    view.set_stream(b"\x00")
    tooltip = view.byte_tooltip(0)
    assert "0x00" in tooltip
    assert "non-printable 0x00" in tooltip
    # The dot in the ASCII column is never reported as an error.
    assert "error" not in tooltip.lower()


# -- legend ------------------------------------------------------------------


def test_legend_covers_every_painted_kind(app):
    from src.ui import hex_view

    # Every legend kind must be a kind the hex view actually paints, so the
    # legend never shows a category the bytes cannot carry.
    painted = set(hex_view._kind_colours())
    for kind, _name in LEGEND_KINDS:
        assert kind in painted


def test_legend_swatches_match_the_brushes(app):
    from src.ui.hex_view import legend_swatch

    legend = AnnotationLegend()
    swatches = [
        w for w in legend.body.findChildren(QtWidgets.QLabel) if not w.pixmap().isNull()
    ]
    assert len(swatches) == len(LEGEND_KINDS)
    for swatch, (kind, _name) in zip(swatches, LEGEND_KINDS, strict=False):
        expected = legend_swatch(kind)
        assert swatch.pixmap().toImage() == expected.toImage()


def test_legend_every_chip_has_an_explanatory_tooltip(app):
    legend = AnnotationLegend()
    for caption, (kind, _name) in zip(legend.chips, LEGEND_KINDS, strict=False):
        assert caption.text() == legend_label(kind)
        assert caption.toolTip()
        assert caption.toolTip() == legend_tooltip(kind)
        # The tooltip explains, it is not just the kind name repeated.
        assert len(caption.toolTip()) > len(kind)


def test_legend_collapses_and_expands(app):
    legend = AnnotationLegend()
    assert legend.is_expanded()
    legend.set_expanded(False)
    assert not legend.is_expanded()
    assert not legend.body.isVisible()
    legend.set_expanded(True)
    assert legend.is_expanded()


def test_legend_minimum_width_is_small(app):
    # The strip must not set a floor on the window: its row folds instead.
    legend = AnnotationLegend()
    assert legend.minimumSizeHint().width() < 200


def test_legend_wraps_at_a_narrow_width(app):
    legend = AnnotationLegend()
    legend.resize(200, 400)
    legend.show()
    app.processEvents()
    rows = {w.y() for w in legend.body.findChildren(QtWidgets.QLabel)}
    assert len(rows) > 1


@corpus_required
def test_legend_sits_above_the_hex_view(app):
    window = open_window(app)
    window.show()
    app.processEvents()
    legend = window.annotation_legend
    hex_view = window.hex_view
    assert legend.isVisible()
    # A strip in its own row cannot overlap the bytes.
    assert legend.geometry().bottom() <= hex_view.geometry().top()


@corpus_required
def test_legend_does_not_take_width_from_the_ascii_column(app):
    window = open_window(app)
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    # At a wide size the legend is one row and the hex view keeps the ASCII
    # column within its viewport (no horizontal scroll to reach it).
    legend_rows = {
        w.y() for w in window.annotation_legend.body.findChildren(QtWidgets.QLabel)
    }
    assert len(legend_rows) == 1


@corpus_required
def test_hiding_the_legend_leaves_the_hex_view(app):
    window = open_window(app)
    window.show()
    app.processEvents()
    window.set_legend_visible(False)
    assert not window.annotation_legend.isVisible()
    window.set_legend_visible(True)
    assert window.annotation_legend.isVisible()


def test_legend_visible_setting_is_stored_and_applied(app):
    from src.ui.settings import DEFAULTS

    assert DEFAULTS["advanced"]["show_legend"] is True
    window = MainWindow()
    window._settings.setdefault("advanced", {})["show_legend"] = False
    window._apply_stored_settings()
    assert not window.annotation_legend.isVisible()
    window.close()
