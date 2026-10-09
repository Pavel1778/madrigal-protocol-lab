"""The template narrative for the hypotheses of an investigation."""

from __future__ import annotations

from src.hypothesis.narrative import render_hypothesis_narrative


def test_empty_investigation_renders_nothing():
    assert render_hypothesis_narrative({}) == ""


def test_section_uses_the_supplied_numbers():
    investigation = {
        "hypotheses": [
            {
                "id": "h2",
                "statement": "the command byte",
                "field": "command",
                "offset": 0,
                "corpus_total": 140,
                "corpus_matched": 60,
                "corpus_contradicted": 80,
                "corpus_uncovered": 0,
            }
        ]
    }
    text = render_hypothesis_narrative(investigation)
    assert "## Hypothesis 1: the command byte" in text
    assert "Field `command` at offset 0." in text
    assert "over 140 messages" in text
    assert "matched 60" in text
    assert "contradicted 80" in text


def test_missing_figures_are_dropped_not_guessed():
    investigation = {"hypotheses": [{"id": "h1", "statement": "a claim"}]}
    text = render_hypothesis_narrative(investigation)
    assert "Corpus check" not in text
    assert "Best alternative" not in text
    assert "a claim" in text


def test_best_alternative_is_the_highest_score():
    investigation = {
        "hypotheses": [
            {
                "id": "h1",
                "statement": "a claim",
                "alternatives": [
                    {"name": "counter", "support": 3, "contradict": 7, "score": 0.3},
                    {"name": "constant", "support": 9, "contradict": 1, "score": 0.9},
                ],
            }
        ]
    }
    text = render_hypothesis_narrative(investigation)
    assert "constant" in text
    assert "counter" not in text
    assert "requires manual review" in text


def test_not_tested_on_is_stated():
    investigation = {
        "hypotheses": [
            {
                "id": "h1",
                "statement": "a claim",
                "applicability": "the corpus protocol",
                "not_tested_on": "synthetic_live",
            }
        ]
    }
    text = render_hypothesis_narrative(investigation)
    assert "Applicability: the corpus protocol." in text
    assert "Not checked on synthetic_live." in text
