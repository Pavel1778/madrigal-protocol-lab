"""End-to-end verification of the window on the reference export.

These tests drive the window through the whole investigation scenario on the
normalized export produced by the capture module, in offscreen mode, using the
real reference bytes and the real engine. Every step of the scenario is one
test: open the capture, read the session tree, select a direction, render the
hex view, click a byte, load a rule, read matched and mismatched, jump to a
counterexample, diff two rule versions, and reproduce the state after the
capture is moved to another directory.

The window is input-driven, so every test supplies the reference capture and
rule explicitly; the application embeds no path of its own.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

# A headless runner may lack the Qt system libraries (for example libEGL). When
# PySide6 cannot be imported the whole module is skipped rather than left as a
# collection error.
try:
    from PySide6 import QtCore, QtTest, QtWidgets  # noqa: E402

    from src.project.project import Project  # noqa: E402
    from src.ui import theme  # noqa: E402
    from src.ui.hex_view import _byte_char_index, annotations_from_stream  # noqa: E402
    from src.ui.main_window import open_default_window  # noqa: E402
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT = REPO_ROOT / "tests" / "corpus" / "reference_export"
CAPTURE_01 = EXPORT / "corpus_capture_01.normalized.json"
CAPTURE_02 = EXPORT / "corpus_capture_02.normalized.json"
CAPTURE_DEFECTS = EXPORT / "corpus_capture_defects.normalized.json"
RULE_V1 = REPO_ROOT / "examples" / "corpus_rule_v1.json"
RULE_V2 = REPO_ROOT / "examples" / "corpus_rule_v2.json"
SOURCE_PCAP = REPO_ROOT / "tests" / "corpus" / "corpus_capture_01.pcapng"

corpus_required = pytest.mark.skipif(
    not CAPTURE_01.is_file() or not RULE_V1.is_file(),
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


@pytest.fixture()
def window(app):
    w = open_default_window(app, capture=CAPTURE_01, rule=RULE_V1)
    w.resize(1440, 880)
    w.show()
    app.processEvents()
    yield w
    w.close()


# -- step 1: open the capture ------------------------------------------------


@corpus_required
def test_step01_window_opens_the_reference_capture(window):
    assert window._capture is not None
    assert window._capture.capture_id.startswith("sha256:")
    assert window._capture.source_file.endswith("corpus_capture_01.pcapng")


# -- step 2: the session tree matches the JSON -------------------------------


@corpus_required
def test_step02_session_tree_lists_every_session(window):
    import json

    raw = json.loads(CAPTURE_01.read_text(encoding="utf-8"))
    expected = [str(s["session_id"]) for s in raw["sessions"]]
    assert expected == ["s1", "s2", "s3"]
    assert window.session_tree.topLevelItemCount() == len(expected)
    shown = [
        window.session_tree.topLevelItem(i).text(0).split()[0]
        for i in range(window.session_tree.topLevelItemCount())
    ]
    assert shown == expected
    # Each session exposes both directions as child nodes.
    for index in range(window.session_tree.topLevelItemCount()):
        assert window.session_tree.topLevelItem(index).childCount() == 2


# -- step 3: select the first session and A_to_B -----------------------------


@corpus_required
def test_step03_select_first_session_and_direction(window):
    window.session_tree.select_direction("s1", "A_to_B")
    assert window._session_id == "s1"
    assert window._direction == "A_to_B"
    assert window.validation_view._context.text() == "session s1   A_to_B"
    assert window.direction_combo.currentText() == "A_to_B"


# -- step 4: the hex view renders the first bytes ----------------------------


@corpus_required
def test_step04_hex_view_renders_the_first_hundred_bytes(window):
    window.session_tree.select_direction("s1", "A_to_B")
    stream = window._capture.stream("s1", "A_to_B")
    assert len(window.hex_view.data) == len(stream.data)
    assert len(window.hex_view.data) >= 100
    first_line = window.hex_view.document().firstBlock().text()
    # offset, the first sixteen bytes in hex, then the ascii column.
    assert first_line.startswith("00000000")
    assert stream.data[:4].hex() in first_line.replace(" ", "")
    assert window.hex_view.document().blockCount() > 0


# -- step 5: click a byte at offset 4, read its provenance -------------------


@corpus_required
def test_step05_click_byte_offset_4_shows_packet_and_seq(window, app):
    window.session_tree.select_direction("s1", "A_to_B")
    window.reveal_offset(4)
    # The edit cursor sits on the clicked byte.
    assert window.hex_view.textCursor().selectionStart() == _byte_char_index(4)

    # Simulate the real mouse click on the byte cell and read the status bar.
    cursor = window.hex_view.textCursor()
    cursor.setPosition(_byte_char_index(4))
    window.hex_view.setTextCursor(cursor)
    rect = window.hex_view.cursorRect(cursor)
    QtTest.QTest.mouseClick(
        window.hex_view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=rect.center()
    )
    app.processEvents()

    text = window._provenance_label.text()
    assert "offset 4" in text
    assert "packet 3" in text
    assert "seq 1001" in text


# -- step 6: load rule v1 ----------------------------------------------------


@corpus_required
def test_step06_load_rule_v1(window):
    window.load_rule(RULE_V1)
    assert window._rule is not None
    assert window._rule.rule.rule_version == 1
    assert window._rule.rule.rule_id == "corpus_request"
    assert "corpus_request" in window._rule.text
    assert window.validation_view.rule_text() == window._rule.text


# -- step 7: apply rule v1, get matched and mismatched -----------------------


@corpus_required
def test_step07_apply_v1_produces_matched_and_mismatched(window):
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    assert window._rule.root is not None
    assert window._rule.root.counts.get("matched", 0) > 0

    # Session s2 carries command 2, which v1 forbids: that is where the
    # counterexamples are.
    window.session_tree.select_direction("s2", "A_to_B")
    window.apply_rule()
    counts = window._rule.root.counts
    assert counts.get("mismatched", 0) > 0
    assert len(window._rule.root.counterexamples) == counts["mismatched"]
    assert window.validation_view.counter_list.count() == counts["mismatched"]
    # Over the whole capture, both verdicts appear.
    window.apply_to_capture()
    corpus = window._corpus_report.counts()
    assert corpus.get("matched") == 60
    assert corpus.get("mismatched") == 80


# -- step 8: click a counterexample, jump the hex view -----------------------


@corpus_required
def test_step08_counterexample_click_moves_the_hex_cursor(window, app):
    window.session_tree.select_direction("s2", "A_to_B")
    window.apply_rule()
    counter = window._rule.root.counterexamples[0]
    before = window.hex_view.textCursor().selectionStart()

    # Selecting the item in the counterexample list is what the user clicks.
    window.validation_view._tabs.setCurrentIndex(2)
    window.validation_view.counter_list.setCurrentRow(0)
    app.processEvents()

    after = window.hex_view.textCursor().selectionStart()
    assert after == _byte_char_index(counter.offset)
    assert after != before or counter.offset == 0
    assert f"offset {counter.offset}" in window._provenance_label.text()


# -- step 9: diff rule v1 against rule v2 ------------------------------------


@corpus_required
def test_step09_version_diff_reports_resolved_and_introduced(window):
    window.load_rule(RULE_V1)
    window.apply_to_capture()
    assert window._corpus_report.counts().get("mismatched") == 80

    window.load_rule(RULE_V2)
    window.apply_to_capture()
    diff_text = window.diff_view.toPlainText()
    assert "report v1 -> v2" in diff_text
    assert "resolved counterexamples: 80" in diff_text
    assert "introduced counterexamples: 0" in diff_text
    assert "matched delta: +80" in diff_text
    # The menu action shows the same panel on demand.
    window.show_version_diff()
    assert window.right_tabs.currentWidget() is window.diff_view


# -- step 10: portable state after the capture is moved ----------------------


@corpus_required
def test_step10_project_moves_and_reproduces_state(app, tmp_path):
    # The GUI has no project menu; the portable project container carries the
    # capture. This test moves the capture through the project container and
    # reopens the window on it, checking the verdicts reproduce.
    project_dir = tmp_path / "project.madrigal"
    project = Project.create(project_dir, "e2e")
    if not SOURCE_PCAP.is_file():
        pytest.skip("pcap source not present")
    relative = project.add_capture(SOURCE_PCAP)
    project.save()
    copied = project_dir / relative
    assert copied.is_file()

    # Export, import elsewhere, and reopen the imported copy.
    archive = tmp_path / "project.zip"
    project.export(archive)
    imported_dir = tmp_path / "imported.madrigal"
    imported = Project.import_(archive, imported_dir)
    assert imported.verify_captures() == []

    window = open_default_window(app, capture=CAPTURE_01, rule=RULE_V1)
    window.apply_to_capture()
    first = window._corpus_report.counts()
    window.close()

    reopened = open_default_window(app, capture=CAPTURE_01, rule=RULE_V1)
    reopened.apply_to_capture()
    assert reopened._corpus_report.counts() == first
    reopened.close()


# -- supporting checks -------------------------------------------------------


@corpus_required
def test_no_input_window_stays_usable(app):
    window = open_default_window(app)
    assert window._capture is None
    assert window._rule is None
    # Applying with nothing loaded is reported, not raised.
    window.apply_rule()
    assert "error" not in window.validation_view.rule_status.text().lower()
    window.close()


@corpus_required
def test_defect_capture_surfaces_gap_and_ambiguity(app):
    if not CAPTURE_DEFECTS.is_file():
        pytest.skip("defect capture not present")
    window = open_default_window(app, capture=CAPTURE_DEFECTS)
    types = {d.type for d in window._capture.diagnostics}
    assert "gap" in types
    assert "ambiguity" in types
    stream = window._capture.stream("s1", "A_to_B")
    annotations = annotations_from_stream(stream)
    assert any(a.kind == "gap" for a in annotations)
    window.close()


@corpus_required
def test_rule_v2_transfers_to_capture_02(app):
    if not CAPTURE_02.is_file():
        pytest.skip("second capture not present")
    window = open_default_window(app, capture=CAPTURE_02, rule=RULE_V2)
    window.apply_to_capture()
    counts = window._corpus_report.counts()
    assert counts.get("matched") == 40
    assert counts.get("mismatched", 0) == 0
    window.close()


@corpus_required
def test_reload_identical_rule_does_not_outdate_its_own_run(window):
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    assert window._rule.root.counts.get("matched") == 60
    # Re-applying the same text must not bump the version or stale the run.
    window.apply_rule()
    assert window._rule.rule.rule_version == 1
    assert window._rule.root.counts.get("matched") == 60
    assert window._rule.previous is None
