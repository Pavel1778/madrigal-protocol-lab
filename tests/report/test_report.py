"""Tests for investigation report rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.report import ReportError, render_html, render_markdown

INVESTIGATION = {
    "title": "Reference investigation",
    "scope": {"direction": "A_to_B", "captures": ["corpus_capture_01"]},
    "hypotheses": [
        {
            "id": "h1",
            "statement": "the first byte is a command",
            "status": "confirmed_in_scope",
            "rule_id": "r1",
            "rule_version": 2,
            "evidence": "holds on 205 messages",
            "counterexamples": ["c1"],
        },
        {
            "id": "h2",
            "statement": "byte 3 is a flag",
            "status": "hypothesis",
        },
    ],
    "counterexamples": [
        {
            "id": "c1",
            "rule_id": "r1",
            "rule_version": 2,
            "capture_id": "sha256:aa",
            "session_id": "s2",
            "direction": "A_to_B",
            "offset": 128,
            "length": 4,
            "bytes_hex": "ffff0001",
            "detail": "value out of the assumed range",
        }
    ],
    "rule_versions": [
        {"rule_id": "r1", "version": 1, "created_at": "2026-10-09T00:00:00Z"},
        {"rule_id": "r1", "version": 2, "note": "add the value range"},
    ],
    "open_questions": ["is byte 3 a flag or a reserved byte"],
}


def test_markdown_has_every_section(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    render_markdown(INVESTIGATION, out)
    text = out.read_text(encoding="utf-8")
    for heading in (
        "Scope",
        "Hypotheses",
        "Counterexamples",
        "Rule versions",
        "Open questions",
    ):
        assert f"## {heading}" in text
    assert "h1" in text and "c1" in text
    assert "r1 version 2" in text
    assert "is byte 3 a flag or a reserved byte" in text


def test_markdown_carries_the_counterexample_bytes(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    render_markdown(INVESTIGATION, out)
    text = out.read_text(encoding="utf-8")
    assert "ffff0001" in text
    assert "128" in text


def test_markdown_handles_an_empty_investigation(tmp_path: Path) -> None:
    out = tmp_path / "empty.md"
    render_markdown({}, out)
    text = out.read_text(encoding="utf-8")
    assert "No hypotheses were recorded." in text
    assert "No counterexamples were found" in text


def test_html_is_self_contained_and_has_sections(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    render_html(INVESTIGATION, out)
    text = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "<h2>Hypotheses</h2>" in text
    assert "ffff0001" in text
    # No external requests: the styling is inline and there are no links out.
    assert "<link" not in text
    assert "http://" not in text and "https://" not in text


def test_html_escapes_untrusted_text(tmp_path: Path) -> None:
    payload = {
        "title": "<script>alert(1)</script>",
        "open_questions": ["</li><script>alert(2)</script>"],
    }
    out = tmp_path / "escaped.html"
    render_html(payload, out)
    text = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;" in text


def test_renderers_reject_a_non_dictionary(tmp_path: Path) -> None:
    with pytest.raises(ReportError):
        render_markdown(["not", "a", "dict"], tmp_path / "x.md")  # type: ignore[arg-type]
    with pytest.raises(ReportError):
        render_html("nope", tmp_path / "x.html")  # type: ignore[arg-type]
