"""No state is lost when the interface is reconfigured at run time.

Changing the language, the theme, the zoom or the window size must not reopen
the capture, clear the rule, drop the applied result or move the selection. The
tests capture the state before and after a change and compare the two.
"""

from __future__ import annotations

import pytest
from PySide6 import QtWidgets

from tests.ui.support import RESOLUTIONS, ZOOM_FONTS, load_window


@pytest.fixture(scope="module")
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return application


@pytest.fixture()
def window(app):
    w = load_window(app)
    w.resize(1280, 800)
    w.show()
    app.processEvents()
    yield w
    w.set_language("en")
    w.set_theme_mode("dark")
    app.processEvents()
    w.close()


def _snapshot(window):
    """The state that must survive every reconfiguration."""
    return {
        "session": window._session_id,
        "direction": window._direction,
        "capture_name": window._capture_name,
        "capture_id": window._capture.capture_id if window._capture else None,
        "rule_version": window._rule.rule.rule_version if window._rule else None,
        "message_rows": window.validation_view.messages_table.rowCount(),
        "session_rows": window.session_tree.topLevelItemCount(),
    }


def test_changing_language_keeps_the_capture(window, app):
    before = _snapshot(window)
    window.set_language("ru")
    app.processEvents()
    assert _snapshot(window) == before


def test_changing_theme_keeps_the_capture(window, app):
    before = _snapshot(window)
    window.set_theme_mode("light")
    app.processEvents()
    assert _snapshot(window) == before


def test_changing_zoom_keeps_the_capture_and_selection(window, app):
    before = _snapshot(window)
    window._set_zoom(*ZOOM_FONTS[150])
    app.processEvents()
    assert _snapshot(window) == before


def test_resizing_keeps_the_capture_and_selection(window, app):
    before = _snapshot(window)
    for width, height in RESOLUTIONS:
        window.setFixedSize(width, height)
        app.processEvents()
        assert _snapshot(window) == before


def test_language_round_trip_restores_the_state(window, app):
    before = _snapshot(window)
    window.set_language("ru")
    window.set_language("en")
    app.processEvents()
    assert _snapshot(window) == before


def test_theme_round_trip_restores_the_state(window, app):
    before = _snapshot(window)
    window.set_theme_mode("light")
    window.set_theme_mode("dark")
    app.processEvents()
    assert _snapshot(window) == before


def test_applied_result_survives_a_language_switch(window, app):
    window.set_language("en")
    window.apply_rule()
    window.apply_to_capture()
    app.processEvents()
    before = _snapshot(window)
    assert before["message_rows"] > 0
    window.set_language("ru")
    app.processEvents()
    assert _snapshot(window) == before


def test_session_selection_survives_a_theme_switch(window, app):
    sessions = [
        window.session_tree.topLevelItem(i).text(0).split()[0]
        for i in range(window.session_tree.topLevelItemCount())
    ]
    assert len(sessions) >= 2
    window.session_tree.select_direction(sessions[1], "A_to_B")
    app.processEvents()
    before = _snapshot(window)
    window.set_theme_mode("light")
    app.processEvents()
    assert _snapshot(window) == before
    assert window._session_id == sessions[1]


def test_open_capture_object_is_not_rebuilt(window, app):
    capture_before = window._capture
    window.set_language("ru")
    window.set_theme_mode("light")
    window._set_zoom(*ZOOM_FONTS[200])
    app.processEvents()
    assert window._capture is capture_before


def test_rule_object_is_not_rebuilt(window, app):
    rule_before = window._rule
    window.set_language("ru")
    window._set_zoom(*ZOOM_FONTS[200])
    app.processEvents()
    assert window._rule is rule_before
