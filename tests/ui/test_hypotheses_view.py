"""Offscreen tests for the hypotheses panel.

The panel is filled from real ``FieldAlternatives`` values so the colour code,
the counts and the offset it emits on selection are all checked against the
engine's own output rather than a hand-made stand-in.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

try:
    from PySide6 import QtWidgets  # noqa: E402

    from src.hypothesis.alternatives import Alternative, FieldAlternatives  # noqa: E402
    from src.ui import theme  # noqa: E402
    from src.ui.hypotheses_view import (  # noqa: E402
        HIGH_SCORE,
        MID_SCORE,
        HypothesesView,
        score_colour,
    )
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # noqa: BLE001 - a missing Qt runtime is a skip
        pytest.skip(f"Qt platform could not start: {exc}")
    return application


def _field(name, alternatives):
    return FieldAlternatives(name, name, True, sum(a.support for a in alternatives), alternatives, name)


def test_score_colour_bands():
    assert score_colour(1.0) == theme.MATCHED_TEXT
    assert score_colour(HIGH_SCORE) == theme.MATCHED_TEXT
    assert score_colour(0.7) == theme.INCOMPLETE_TEXT
    assert score_colour(MID_SCORE) == theme.INCOMPLETE_TEXT
    assert score_colour(0.2) == theme.TEXT_SECONDARY


def test_panel_shows_one_row_per_candidate(app):
    field = _field(
        "value",
        [
            Alternative("entropy_parameter", "d", 60, 0, 1.0, []),
            Alternative("constant", "d", 1, 59, 0.017, []),
        ],
    )
    view = HypothesesView()
    view.show_fields([field])
    assert view.table.rowCount() == 2
    assert view.table.item(0, 0).text() == "value"
    assert view.table.item(0, 1).text() == "entropy_parameter"
    assert "2 candidate reading(s)" in view.header.text()


def test_panel_colours_the_score_column(app):
    field = _field(
        "flag",
        [
            Alternative("high", "d", 9, 1, 0.9, []),
            Alternative("mid", "d", 5, 5, 0.5, []),
            Alternative("low", "d", 1, 9, 0.1, []),
        ],
    )
    view = HypothesesView()
    view.show_fields([field])
    assert view.table.item(0, 4).foreground().color().name().lower() == theme.MATCHED_TEXT.lower()
    assert view.table.item(1, 4).foreground().color().name().lower() == theme.INCOMPLETE_TEXT.lower()
    assert view.table.item(2, 4).foreground().color().name().lower() == theme.TEXT_SECONDARY.lower()


def test_selecting_a_candidate_emits_its_first_evidence_offset(app):
    evidence = [{"message_offset": 12, "value": 1, "detail": "x"}]
    field = _field("value", [Alternative("constant", "d", 10, 0, 1.0, evidence)])
    view = HypothesesView()
    view.show_fields([field])
    seen = []
    view.messageSelected.connect(seen.append)
    view.table.selectRow(0)
    assert seen == [12]


def test_clear_empties_the_panel(app):
    view = HypothesesView()
    view.show_fields([_field("value", [Alternative("constant", "d", 1, 0, 1.0, [])])])
    view.clear()
    assert view.table.rowCount() == 0
    assert view.header.text() == "no rule applied"
