"""The first-run and no-documentation paths.

These tests cover the promise that the window is usable without a manual: it
opens on a welcome card, a single action loads a worked example, the rule can be
built from a byte selection rather than typed as JSON, and the journal panel
lines the operator's own actions up with the messages.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from src.ui import theme
from src.ui.main_window import SAMPLE_CAPTURE, SAMPLE_JOURNAL, SAMPLE_RULE, MainWindow

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT = REPO_ROOT / "tests" / "corpus" / "reference_export"
CAPTURE_01 = EXPORT / "corpus_capture_01.normalized.json"
RULE_V1 = REPO_ROOT / "examples" / "corpus_rule_v1.json"


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # pragma: no cover - depends on the runner
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


@pytest.fixture()
def window(app):
    win = MainWindow()
    yield win
    win._language_manager.set_language("system")
    win.close()


def test_window_opens_on_the_welcome_card(window):
    assert window._centre_stack.currentWidget() is window.welcome_panel


def test_welcome_card_states_the_three_steps(window):
    from src.ui import guidance

    captions = [label.text() for label in window.welcome_panel._step_titles]
    assert captions == [title for title, _body in guidance.STEPS]
    assert all(label.text() for label in window.welcome_panel._step_bodies)


def test_opening_a_capture_replaces_the_welcome_card(window):
    window.open_capture(CAPTURE_01)
    assert window._centre_stack.currentIndex() == 1
    assert window._capture is not None


def test_the_bundled_demo_ships_with_the_tool():
    assert SAMPLE_CAPTURE.is_file()
    assert SAMPLE_RULE.is_file()
    assert SAMPLE_JOURNAL.is_file()


def test_open_demo_runs_a_whole_investigation(window):
    window.open_demo()
    assert window._capture is not None
    assert window._rule is not None
    # The demo applies the rule across the capture and fills the timeline, so a
    # first-time reader sees a result rather than an empty window.
    assert window._corpus_report is not None
    assert window.timeline_view.table.rowCount() > 0


def test_rule_builder_writes_a_rule_from_a_selection(window):
    window.rule_builder.set_selection(0, 2)
    window.rule_builder.name_edit.setText("magic")
    window.rule_builder._on_add_field()
    document = json.loads(window.rule_builder.rule_json())
    assert document["fields"][0]["name"] == "magic"
    assert document["fields"][0]["offset"] == 0
    assert document["fields"][0]["type"] == "uint8"


def test_rule_builder_refuses_a_field_without_a_selection(window):
    window.rule_builder.set_selection(0, 0)
    window.rule_builder.name_edit.setText("magic")
    window.rule_builder._on_add_field()
    assert json.loads(window.rule_builder.rule_json())["fields"] == []


def test_rule_builder_output_is_accepted_by_the_engine(window):
    window.rule_builder.set_selection(0, 1)
    window.rule_builder.name_edit.setText("command")
    window.rule_builder._on_add_field()
    from src.protocol.rule import load_rule_text, parse_rule

    rule = parse_rule(load_rule_text(window.rule_builder.rule_json()))
    assert rule.rule_id == "new_rule"
    assert [f.name for f in rule.fields] == ["command"]


def test_hex_selection_maps_to_a_byte_range(window):
    window.open_capture(CAPTURE_01)
    view = window.hex_view
    captured: list[tuple[int, int]] = []
    view.rangeSelected.connect(lambda off, length: captured.append((off, length)))
    cursor = view.textCursor()
    start = view._char_index(3)
    cursor.setPosition(start)
    cursor.setPosition(start + 3, cursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    assert captured
    offset, length = captured[-1]
    assert offset == 3
    assert length >= 1


def test_journal_panel_pairs_actions_with_messages(window):
    window.open_capture(CAPTURE_01)
    window.load_rule(RULE_V1)
    window.load_journal(SAMPLE_JOURNAL)
    # The bundled journal is built from the demo capture; loading it against a
    # different capture still parses and reports, never raising.
    assert window._journal


def test_journal_without_a_rule_is_reported_not_raised(window):
    window.open_capture(CAPTURE_01)
    window.load_journal(SAMPLE_JOURNAL)
    assert window._journal == []


def test_tab_captions_name_the_purpose_not_the_engine(window):
    captions = [window.right_tabs.tabText(i) for i in range(window.right_tabs.count())]
    assert captions == ["Build rule", "Results", "Compare", "Hypotheses", "Report", "Versions"]
    # The engine term survives as a tooltip, so nothing is hidden, only demoted.
    assert "JSON" in window.right_tabs.tabToolTip(0)


def test_status_meanings_are_available_for_tooltips():
    from src.ui import guidance

    for status in ("matched", "mismatched", "incomplete", "ambiguous", "uncovered", "not_applicable"):
        assert guidance.status_meaning(status)
