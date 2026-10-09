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
    from PySide6 import QtWidgets  # noqa: E402

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
    assert window.validation_view.counter_list.count() == 0
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


def test_diff_bytes_aligns_a_shared_prefix():
    rows = diff_bytes(b"\x01\x00\x00\x05", b"\x01\x00\x00\x06")
    assert rows[0].kind == "equal"
    assert rows[-1].kind == "changed"


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
