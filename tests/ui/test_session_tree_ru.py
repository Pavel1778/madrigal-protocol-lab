"""Tests for the session-tree column widths in Russian.

The tree header carries the column labels. When the sessions panel is narrow -
a small window or a narrower splitter - the panel collapses to the tree's
minimum width and the labels used to be clipped ("сессия" cut to a sliver).
These tests use the real translator and the real reference corpus: they shrink
the window so the panel is narrow, switch to Russian, and assert that each
header is at least as wide as its own text, so no label is cut off.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

try:
    from PySide6 import QtCore, QtWidgets  # noqa: E402

    from src.ui import i18n, theme  # noqa: E402
    from src.ui.main_window import MainWindow  # noqa: E402
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = REPO_ROOT / "src" / "ui" / "locale" / "madrigal_ru.qm"
CAPTURE = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
DEFECT_CAPTURE = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_defects.normalized.json"

# A window small enough that the splitter hands the sessions panel only its
# minimum width - the state in which the old tree clipped its headers.
NARROW = (640, 480)

catalogue_required = pytest.mark.skipif(
    not CATALOGUE.is_file(), reason="Russian catalogue is not compiled"
)
corpus_required = pytest.mark.skipif(not CAPTURE.is_file(), reason="reference corpus not present")


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # noqa: BLE001 - a missing Qt runtime is a skip
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Point the language preference at a throwaway settings file."""
    monkeypatch.setattr(i18n, "_SETTINGS_ORG", "madrigal-test")
    monkeypatch.setattr(i18n, "_SETTINGS_APP", f"protocol-lab-tree-{tmp_path.name}")
    yield


@pytest.fixture
def window(app, isolated_settings):
    """A narrow window with the reference capture open, restored to English after."""
    window = MainWindow()
    window.resize(*NARROW)
    window.show()
    if CAPTURE.is_file():
        window.open_capture(CAPTURE)
    QtCore.QCoreApplication.processEvents()
    yield window
    window._language_manager.set_language("en")
    window.close()


def _widths(window) -> list[tuple[str, int, int]]:
    """Return (header text, text width, column width) per column."""
    tree = window.session_tree
    metrics = tree.header().fontMetrics()
    out = []
    for column in range(tree.columnCount()):
        text = tree.headerItem().text(column)
        out.append((text, metrics.horizontalAdvance(text), tree.columnWidth(column)))
    return out


@catalogue_required
@corpus_required
def test_russian_headers_fit_the_first_column(window):
    window.set_language("ru")
    QtCore.QCoreApplication.processEvents()
    widths = _widths(window)
    assert widths[0][0] == "сессия"
    for text, text_width, column_width in widths:
        assert column_width >= text_width, (
            f"column {text!r}: width {column_width} < text {text_width}"
        )


@catalogue_required
@corpus_required
def test_english_headers_still_fit(window):
    QtCore.QCoreApplication.processEvents()
    for text, text_width, column_width in _widths(window):
        assert column_width >= text_width, (
            f"column {text!r}: width {column_width} < text {text_width}"
        )


@catalogue_required
@corpus_required
def test_switching_language_recomputes_the_widths(window):
    window.set_language("en")
    QtCore.QCoreApplication.processEvents()
    english = window.session_tree.columnWidth(0)
    window.set_language("ru")
    QtCore.QCoreApplication.processEvents()
    russian = window.session_tree.columnWidth(0)
    # The session column is sized to its header, so each language must fit its
    # own label once the language changes while the window is already narrow.
    # The two scripts differ in width, so the Russian column need not be at
    # least the English one; both must fit their own header text.
    english_text = window.session_tree.header().fontMetrics().horizontalAdvance("session")
    russian_text = window.session_tree.header().fontMetrics().horizontalAdvance("сессия")
    assert russian >= russian_text
    assert english >= english_text
    assert russian != english or russian_text == english_text


@catalogue_required
@corpus_required
def test_defect_capture_headers_fit(window):
    if not DEFECT_CAPTURE.is_file():
        pytest.skip("defect corpus not present")
    window.open_capture(DEFECT_CAPTURE)
    window.set_language("ru")
    QtCore.QCoreApplication.processEvents()
    for text, text_width, column_width in _widths(window):
        assert column_width >= text_width, (
            f"column {text!r}: width {column_width} < text {text_width}"
        )


@catalogue_required
def test_headers_fit_without_a_capture(window):
    """The widths are recomputed even when no session is loaded."""
    window.set_language("ru")
    QtCore.QCoreApplication.processEvents()
    for text, text_width, column_width in _widths(window):
        assert column_width >= text_width, (
            f"column {text!r}: width {column_width} < text {text_width}"
        )

