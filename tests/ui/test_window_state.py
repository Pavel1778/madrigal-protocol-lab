"""Offscreen tests for the window's state wiring.

These exercise the window itself rather than its rendering: which capture and
session it holds, what a language switch does to the selection, and how a theme
change leaves the loaded data alone. They drive the real model and the real
engine against the reference corpus, so a regression in the wiring shows up as a
wrong session, a lost direction or a stale result — not as a pixel difference.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

try:
    from PySide6 import QtWidgets  # noqa: E402

    from src.ui import theme  # noqa: E402
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
    except Exception as exc:  # noqa: BLE001 - a missing Qt runtime is a skip
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


@pytest.fixture
def window(app):
    win = open_default_window(app, capture=DEFAULT_CAPTURE, rule=DEFAULT_RULE)
    yield win
    win.close()


@corpus_required
def test_open_capture_selects_first_session(window):
    assert window._capture is not None
    first = window._capture.sessions[0].session_id
    assert window._session_id == first
    assert window._direction in window._capture.directions(first)


@corpus_required
def test_rule_application_reports_counts(window):
    window.apply_rule()
    status = window.validation_view.rule_status.text()
    assert "error" not in status.lower()
    # The run must be non-empty: matched+uncovered at least.
    assert any(token in status for token in ("matched", "uncovered"))


@corpus_required
def test_language_switch_keeps_selected_session(window):
    session_before = window._session_id
    direction_before = window._direction
    window.set_language("ru")
    assert window._session_id == session_before
    assert window._direction == direction_before
    window.set_language("en")
    assert window._session_id == session_before


@corpus_required
def test_theme_change_keeps_the_capture(window):
    capture_before = window._capture
    window.set_theme_mode("light")
    assert window._capture is capture_before
    assert window._session_id
    window.set_theme_mode("dark")


@corpus_required
def test_direction_switch_updates_the_context(window):
    directions = window._capture.directions(window._session_id)
    if len(directions) < 2:
        pytest.skip("single-direction session")
    window._on_direction_selected(window._session_id, directions[1])
    assert window._direction == directions[1]
    assert window.validation_view._direction == directions[1]
