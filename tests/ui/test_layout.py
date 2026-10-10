"""Offscreen tests for layout behaviour.

The window must stay usable when it is small or when the interface is Russian,
whose labels are wider than the English ones. These tests pin the two things
that used to break that: rows that forced a floor on the window width, and tab
captions that were pinned open by their own length.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

try:
    from PySide6 import QtCore, QtWidgets  # noqa: E402

    from src.ui import theme  # noqa: E402
    from src.ui.layout import FlowLayout  # noqa: E402
    from src.ui.main_window import open_default_window  # noqa: E402
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = REPO_ROOT / "tests/corpus/reference_export/corpus_capture_01.normalized.json"
DEFAULT_RULE = REPO_ROOT / "examples/corpus_rule_v1.json"

corpus_required = pytest.mark.skipif(
    not DEFAULT_CAPTURE.is_file() or not DEFAULT_RULE.is_file(),
    reason="reference corpus not present",
)


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


@pytest.fixture(autouse=True)
def _restore_preferences(app):
    """Undo any preference a layout test persisted to ``QSettings``."""
    settings = QtCore.QSettings("madrigal", "protocol-lab")
    keys = ("interface/language", "appearance/theme")
    saved = {key: (settings.contains(key), settings.value(key)) for key in keys}
    yield
    for key, (had, previous) in saved.items():
        if had:
            settings.setValue(key, previous)
        else:
            settings.remove(key)


def test_flow_layout_minimum_is_widest_child(app):
    host = QtWidgets.QWidget()
    flow = FlowLayout(host)
    widths = [40, 50, 30, 200, 60]
    for width in widths:
        label = QtWidgets.QLabel("x" * 5)
        label.setFixedWidth(width)
        flow.addWidget(label)
    # The minimum width is the widest single child plus the margins, not the
    # sum of the row.
    assert flow.minimumSize().width() <= max(widths) + 20
    host.deleteLater()


def test_flow_layout_wraps_onto_more_lines(app):
    host = QtWidgets.QWidget()
    flow = FlowLayout(host, spacing=4)
    for _ in range(6):
        label = QtWidgets.QLabel("chip")
        label.setFixedSize(60, 18)
        flow.addWidget(label)
    one_line = flow.heightForWidth(1000)
    narrow = flow.heightForWidth(140)
    assert narrow > one_line
    host.deleteLater()


@corpus_required
def test_window_shrinks_to_minimum_size_in_russian(app):
    window = open_default_window(app, capture=DEFAULT_CAPTURE, rule=DEFAULT_RULE)
    previous = window._language_manager.preference
    window.set_language("ru")
    window.resize(800, 600)
    window.show()
    app.processEvents()
    # The splitter used to refuse to shrink below 1510 px; a small window must
    # now be honoured rather than silently widened.
    assert window.minimumSizeHint().width() <= 1000
    # Switching language installs an application-wide translator; put the
    # previous choice back so the English-string tests that run later are not
    # translated.
    window.set_language(previous)
    window.close()


@corpus_required
def test_legend_does_not_set_a_width_floor(app):
    window = open_default_window(app, capture=DEFAULT_CAPTURE, rule=DEFAULT_RULE)
    legend = window.annotation_legend
    # Six chips at a fixed swatch were 584 px; the wrapped row must be far
    # smaller, close to a couple of chips.
    assert legend.minimumSizeHint().width() < 200
    window.close()
