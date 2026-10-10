"""Offscreen smoke tests for the window.

The tests run against the reference corpus and rule so they exercise real bytes
and the real engine. They check that the window opens, that the session tree
reflects the capture, that the hex view renders and can be poked, and that a
rule produces the matched and mismatched verdicts the research report states.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

# A headless runner may lack the Qt system libraries (for example libEGL). When
# PySide6 cannot be imported the whole module is skipped rather than left as a
# collection error, so a missing runtime never masks the rest of the suite.
try:
    from PySide6 import QtGui, QtTest, QtWidgets  # noqa: E402

    from src.ui import theme  # noqa: E402
    from src.ui.compare_view import diff_bytes  # noqa: E402
    from src.ui.hex_view import HexView, annotations_from_stream  # noqa: E402
    from src.ui.main_window import (  # noqa: E402
        MainWindow,
        open_default_window,
    )
    from src.ui.model import CaptureModel, RuleModel  # noqa: E402
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
DEFAULT_RULE = REPO_ROOT / "examples" / "corpus_rule_v1.json"
DEFECT_CAPTURE = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_defects.normalized.json"


def open_window(app):
    """Open the window with the reference corpus and rule supplied explicitly.

    The application itself embeds no capture or rule name; the reference paths
    are a fixture of the test suite.
    """
    return open_default_window(app, capture=DEFAULT_CAPTURE, rule=DEFAULT_RULE)


corpus_required = pytest.mark.skipif(
    not DEFAULT_CAPTURE.is_file() or not DEFAULT_RULE.is_file(),
    reason="reference corpus not present",
)


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # noqa: BLE001 - a missing Qt runtime is a skip, not a failure
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


def test_application_opens_offscreen(app):
    from PySide6 import QtGui

    assert QtGui.QGuiApplication.platformName() == "offscreen"


def test_window_accepts_no_input_without_crashing(app):
    # The window is input-driven: launched with no capture and no rule it must
    # stay usable rather than fall back to a built-in reference file.
    window = open_default_window(app)
    assert window._capture is None
    assert window._rule is None
    window.apply_rule()
    assert "error" not in window.validation_view.rule_status.text().lower()
    window.close()


def test_fonts_load(app):
    families = theme.load_fonts(app)
    assert "Montserrat" in families
    assert "Tektur" in families


@corpus_required
def test_window_opens_and_loads_capture(app):
    window = open_window(app)
    model = window._capture
    assert model is not None
    assert len(model.sessions) == 3
    assert window.session_tree.topLevelItemCount() == 3
    window.close()


@corpus_required
def test_hex_view_renders_the_stream(app):
    window = open_window(app)
    stream = window._capture.stream(window._session_id, window._direction)
    assert len(window.hex_view.data) == len(stream.data)
    assert len(window.hex_view.data) > 0
    window.close()


@corpus_required
def test_hex_view_renders_many_lines(app):
    view = HexView()
    view.set_stream(bytes(range(256)) * 8)  # 2048 bytes -> 128 lines
    assert len(view.data) == 2048
    assert view.document().blockCount() >= 128


@corpus_required
def test_applying_rule_v1_shows_matched_and_mismatched(app):
    window = open_window(app)
    window.apply_to_capture()
    report = window._corpus_report
    assert report is not None
    counts = report.counts()
    assert counts.get("matched") == 60
    assert counts.get("mismatched") == 80
    assert len(report.contradictions) == 80
    window.close()


@corpus_required
def test_applying_rule_v2_clears_counterexamples(app):
    window = open_window(app)
    v2 = DEFAULT_RULE.with_name("corpus_rule_v2.json")
    if not v2.is_file():
        pytest.skip("refined rule not generated")
    window.load_rule(v2)
    window.apply_to_capture()
    assert window._corpus_report.counts().get("mismatched", 0) == 0
    assert len(window._corpus_report.contradictions) == 0
    window.session_tree.select_direction("s2", "A_to_B")
    window.apply_rule()
    assert window._rule.root.counts.get("mismatched", 0) == 0
    assert window.validation_view.counterexample_count == 0
    window.close()


@corpus_required
def test_counterexample_click_reveals_bytes(app):
    window = open_window(app)
    window.session_tree.select_direction("s2", "A_to_B")
    window.apply_rule()
    assert window._rule.root.counterexamples, "expected a counterexample in s2"
    first = window._rule.root.counterexamples[0]
    window.reveal_offset(first.offset)
    assert "offset" in window._provenance_label.text()
    window.close()


@corpus_required
def test_defect_capture_surfaces_diagnostics(app):
    if not DEFECT_CAPTURE.is_file():
        pytest.skip("defect capture not present")
    window = MainWindow()
    window.open_capture(DEFECT_CAPTURE)
    model = window._capture
    assert model is not None
    types = {d.type for d in model.diagnostics}
    assert "gap" in types or "ambiguity" in types
    # A stream annotation over a gap must not be reported as a matched field.
    session = model.sessions[0]
    stream = model.stream(session.session_id, "A_to_B")
    annotations = annotations_from_stream(stream)
    assert any(a.kind == "gap" for a in annotations)
    window.close()


@corpus_required
def test_apply_to_capture_verifies_the_rule(app):
    window = open_window(app)
    window.load_rule(DEFAULT_RULE.with_name("corpus_rule_v2.json"))
    window.apply_to_capture()
    assert "counterexamples=0" in window.validation_view.rule_status.text()
    window.close()


@corpus_required
def test_compare_view_shows_two_messages(app):
    window = open_window(app)
    window.apply_rule()
    view = window.compare_view
    assert view.left_combo.count() == len(window._rule.root.messages)
    assert view.table.rowCount() > 0
    window.close()


@corpus_required
def test_hypotheses_tab_fills_on_apply(app):
    window = open_window(app)
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    view = window.hypotheses_view
    # Rule v1 flags three fields as hypotheses; each contributes at least one
    # candidate reading, so the panel is never empty after an apply.
    assert view.table.rowCount() >= 3
    fields = {view.table.item(r, 0).text() for r in range(view.table.rowCount())}
    assert {"command", "target", "value"} <= fields
    window.close()


@corpus_required
def test_hypotheses_tab_scores_over_the_whole_capture(app):
    window = open_window(app)
    window.load_rule(DEFAULT_RULE)  # rule v1
    window.apply_to_capture()
    view = window.hypotheses_view
    rows = {
        (view.table.item(r, 0).text(), view.table.item(r, 1).text()): (
            view.table.item(r, 2).text(),
            view.table.item(r, 3).text(),
        )
        for r in range(view.table.rowCount())
    }
    # Over the whole capture the constant reading of command is contradicted by
    # 80 of 140 messages; that is the evidence the refinement rests on.
    assert rows[("command", "constant")] == ("60", "80")
    window.close()


def test_rule_editor_flags_invalid_text_without_touching_the_run(app):
    window = open_window(app)
    window.apply_rule()
    status_before = window.validation_view.rule_status.text()
    window.validation_view.rule_edit.setPlainText('{"schema_version": 1, "fields": [')
    app.processEvents()
    assert "invalid rule" in window.validation_view.rule_status.text().lower()
    # The previous application is left in place.
    assert window.validation_view.messages_table.rowCount() > 0
    assert status_before != window.validation_view.rule_status.text()
    window.close()


def test_rule_editor_reports_a_clean_parse(app):
    window = open_window(app)
    if not DEFAULT_RULE.is_file():
        window.close()
        return
    text = DEFAULT_RULE.read_text()
    window.validation_view.rule_edit.setPlainText(text)
    app.processEvents()
    assert "parses" in window.validation_view.rule_status.text()
    window.close()


def test_rule_editor_completes_a_field_type(app):
    window = open_window(app)
    edit = window.validation_view.rule_edit
    edit.setPlainText('{"type": "uint')
    cursor = edit.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    edit.setTextCursor(cursor)
    assert window.validation_view._completion_prefix(cursor) == "uint"
    # Typing through the event filter opens the completion popup.
    QtTest.QTest.keyClicks(edit, "1")
    app.processEvents()
    completer = window.validation_view._completer
    assert completer.popup().isVisible()
    offered = [
        completer.completionModel().index(i, 0).data()
        for i in range(completer.completionCount())
    ]
    assert "uint16" in offered
    window.close()


def test_load_example_rule_populates_the_editor(app):
    window = open_window(app)
    window.validation_view.example_button.click()
    app.processEvents()
    assert window.validation_view.rule_edit.toPlainText().strip()
    assert window._rule is not None
    window.close()


def test_saved_result_matches_the_contract_schema(app, tmp_path, monkeypatch):
    import json

    from src.protocol.result import validate_result

    window = open_window(app)
    window.apply_rule()
    destination = tmp_path / "result.json"
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(destination), "JSON (*.json)")),
    )
    window.save_result_dialog()
    payload = json.loads(destination.read_text())
    # A shape the contract accepts, not a bespoke one.
    validate_result(payload)
    assert payload["contract_version"] == 1
    assert payload["capture_id"] == window._capture.capture_id
    assert "summary" in payload and "messages" in payload
    window.close()


def test_help_action_has_the_f1_shortcut(app):
    window = open_window(app)
    help_menu = next(
        m for m in window.menuBar().findChildren(QtWidgets.QMenu) if "Help" in m.title()
    )
    quick = [a for a in help_menu.actions() if "help" in a.text().lower()]
    assert quick
    assert quick[0].shortcut().toString() == "F1"
    window.close()


def test_legend_uses_painted_swatches(app):
    from src.ui.hex_view import LEGEND_KINDS

    window = open_window(app)
    labels = window.annotation_legend.findChildren(QtWidgets.QLabel)
    pixmaps = [
        label.pixmap()
        for label in labels
        if not label.pixmap().isNull()
    ]
    # One swatch per legend kind, and every name is spelled out.
    assert len(pixmaps) == len(LEGEND_KINDS)
    assert all(p.width() == 12 and p.height() == 12 for p in pixmaps)
    names = {label.text() for label in labels}
    assert {"gap", "ambiguity", "matched", "mismatched"} <= names
    window.close()


def test_window_starts_with_an_empty_state_hint(app):
    window = MainWindow()
    assert "no capture loaded" in window.hex_view.toPlainText()
    assert window._progress.isVisible() is False
    window.close()


def test_progress_returns_to_idle_after_a_run(app):
    window = open_window(app)
    window.apply_to_capture()
    assert window._progress.value() == 0
    assert window._progress.isVisible() is False
    window.close()


def test_no_counterexamples_shows_a_note(app):
    window = open_window(app)
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    assert window.validation_view.counterexample_count == 0
    # The tab is not simply empty; it states that there is nothing here.
    assert window.validation_view.counter_list.count() == 1
    assert "no counterexamples" in window.validation_view.counter_list.item(0).text()
    window.close()


def test_messages_tab_states_why_it_is_empty(app):
    window = MainWindow()
    table = window.validation_view.messages_table
    assert table.rowCount() == 1
    assert "no messages yet" in table.item(0, 0).text()
    window.close()


def test_file_dialogs_remember_the_last_directory(app, monkeypatch):
    from src.ui.main_window import REPO_ROOT

    window = open_window(app)
    seen = []

    def fake_open(*args, **kwargs):
        seen.append(args[2])
        return (str(DEFAULT_CAPTURE), "JSON (*.json)")

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", staticmethod(fake_open))
    window.open_capture_dialog()
    window.open_capture_dialog()
    # The first open starts at the repository root; the second at the file's
    # own directory, because the first open was remembered.
    assert seen[0] == str(REPO_ROOT)
    assert seen[1] == str(DEFAULT_CAPTURE.resolve().parent)
    window.close()


def test_diff_bytes_marks_a_deletion_without_crashing():
    # The left message is longer; the shared tail sits at a different offset on
    # each side, which used to read past the end of the shorter message.
    rows = diff_bytes(b"\x01\x02\x09\x03", b"\x01\x02\x03")
    kinds = [r.kind for r in rows]
    assert "deleted" in kinds
    assert rows[-1].kind == "equal"
    assert all(r.left != "" and r.right != "" for r in rows)


def test_diff_bytes_marks_an_insertion():
    rows = diff_bytes(b"\x01\x02\x03", b"\x01\x02\x09\x03")
    kinds = [r.kind for r in rows]
    assert "inserted" in kinds
    assert rows[-1].kind == "equal"


def test_diff_bytes_of_identical_messages_is_all_equal():
    rows = diff_bytes(b"\x01\x02\x03", b"\x01\x02\x03")
    assert {r.kind for r in rows} == {"equal"}


def test_rule_edit_marks_the_previous_run_outdated(app):
    if not DEFAULT_RULE.is_file():
        pytest.skip("rule not present")
    model = RuleModel.from_file(DEFAULT_RULE)
    text = DEFAULT_RULE.read_text(encoding="utf-8").replace('"expected": [1]', '"expected": [1, 2]')
    model.reload(model.text)
    if not DEFAULT_CAPTURE.is_file():
        pytest.skip("capture not present")
    capture = CaptureModel.from_file(DEFAULT_CAPTURE)
    model.apply(capture, "s1", "A_to_B")
    assert model.root is not None
    model.reload(text)
    assert model.root is None


# -- hex view tooltip and hatching -------------------------------------------


@corpus_required
def test_hex_tooltip_reports_offset_hex_and_provenance(app):
    window = open_window(app)
    window.session_tree.select_direction("s1", "A_to_B")
    tooltip = window.hex_view.byte_tooltip(0)
    assert "offset 0" in tooltip
    assert "0x01" in tooltip
    assert "packet 3" in tooltip
    assert "seq 1001" in tooltip
    window.close()


@corpus_required
def test_hex_tooltip_names_the_field_after_apply(app):
    window = open_window(app)
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    tooltip = window.hex_view.byte_tooltip(0)
    assert "matched" in tooltip
    assert "command" in tooltip
    window.close()


def test_hex_tooltip_is_empty_outside_the_bytes(app):
    view = HexView()
    view.set_stream(b"\x01\x02")
    assert view.byte_tooltip(99) == ""


def test_gap_and_ambiguity_use_a_hatch_brush(app):
    from PySide6 import QtCore

    from src.ui.hex_view import _brush_for
    from src.ui.model import AMBIGUITY, GAP, MATCHED

    texture = QtCore.Qt.BrushStyle.TexturePattern
    assert _brush_for(GAP, "#000000").style() == texture
    assert _brush_for(AMBIGUITY, "#000000").style() == texture
    assert _brush_for(MATCHED, "#2F5D45").style() != texture


def test_annotation_from_stream_carries_provenance():
    from src.protocol.stream import DirectionalStream, Hole
    from src.ui.hex_view import annotations_from_stream

    stream = DirectionalStream.from_bytes(b"\x01\x02\x03\x04")
    stream.provenance = [Hole(type="provenance", offset=0, length=4, packet_index=7, seq=42, ts=1.5)]
    annotations = annotations_from_stream(stream)
    assert annotations[0].packet_index == 7
    assert annotations[3].seq == 42


# -- corpus run fills the counterexample tab ---------------------------------


@corpus_required
def test_capture_run_fills_the_counterexample_tab(app):
    window = open_window(app)
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    assert window.validation_view.counterexample_count == 0
    window.apply_to_capture()
    report = window._corpus_report
    # The tab must agree with the report, not with the earlier single-direction run.
    assert window.validation_view.counterexample_count == len(report.contradictions)
    assert window.validation_view.counterexample_count > 0
    window.close()


@corpus_required
def test_corpus_counterexample_click_switches_direction(app):
    window = open_window(app)
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_to_capture()
    window.validation_view._tabs.setCurrentIndex(2)
    window.validation_view.counter_list.setCurrentRow(0)
    app.processEvents()
    item = window.validation_view.counter_list.item(0)
    session_id, direction, offset, length = item.data(0x0100)  # UserRole
    # The reveal switched the window to the counterexample's own direction.
    assert window._session_id == session_id
    assert window._direction == direction
    assert f"offset {offset}" in window._provenance_label.text()
    # The whole message is highlighted, not just the first byte.
    selection = window.hex_view.textCursor()
    assert selection.hasSelection()
    assert length > 1
    window.close()


def test_highlight_range_selects_the_whole_message(app):
    view = HexView()
    view.set_stream(bytes(range(64)))
    view.highlight_range(20, 7)
    cursor = view.textCursor()
    assert cursor.hasSelection()
    selected = cursor.selectedText().replace("\u2029", "")
    # 7 bytes, three characters each ("xx ").
    assert selected.count(" ") == 6
    view.highlight_range(1000, 4)  # clamped, must not raise
    assert view.textCursor().hasSelection()


@corpus_required
def test_zoom_actions_scale_the_hex_view(app):
    window = open_window(app)
    try:
        theme.set_zoom(theme.DEFAULT_ZOOM)
        window.apply_zoom()
        base = window.hex_view.font().pixelSize()
        assert window._actions["zoom_in"].shortcut().toString() in ("Ctrl+=", "Ctrl++")
        window.zoom_by(10)
        assert theme.zoom() == 110
        assert window.hex_view.font().pixelSize() > base
        window.zoom_by(-20)
        assert theme.zoom() == 90
        window.reset_zoom()
        assert theme.zoom() == theme.DEFAULT_ZOOM
        assert window.hex_view.font().pixelSize() == base
    finally:
        theme.set_zoom(theme.DEFAULT_ZOOM)
        window.apply_zoom()
        window.close()


def test_zoom_is_clamped_at_the_limits(app):
    window = MainWindow()
    try:
        for _ in range(50):
            window.zoom_by(10)
        assert theme.zoom() == theme.MAX_ZOOM
        for _ in range(50):
            window.zoom_by(-10)
        assert theme.zoom() == theme.MIN_ZOOM
    finally:
        theme.set_zoom(theme.DEFAULT_ZOOM)
        window.apply_zoom()
        window.close()
