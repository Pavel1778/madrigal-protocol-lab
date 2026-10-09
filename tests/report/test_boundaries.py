"""Boundary tests for report rendering and the report model."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.report import normalize, render_html, render_markdown, status_label
from src.report.markdown import render
from src.report.model import has_content


def test_render_returns_the_same_text_as_the_written_file(tmp_path: Path) -> None:
    investigation = {"title": "Trial", "open_questions": ["is byte 3 a flag"]}
    out = tmp_path / "report.md"
    render_markdown(investigation, out)
    assert render(investigation) == out.read_text(encoding="utf-8")


def test_render_creates_no_file_beside_the_caller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    render({"title": "Trial"})
    assert list(tmp_path.iterdir()) == []


def test_normalize_fills_every_section() -> None:
    model = normalize({"title": "Trial"})
    assert model["title"] == "Trial"
    assert model["scope"] == {}
    assert model["hypotheses"] == []
    assert model["counterexamples"] == []
    assert model["rule_versions"] == []
    assert model["open_questions"] == []


def test_normalize_uses_a_default_title() -> None:
    assert normalize({})["title"] == "Protocol investigation report"


def test_has_content_detects_an_empty_model() -> None:
    assert has_content(normalize({"title": "Trial"})) is False
    assert has_content(normalize({"title": "Trial", "hypotheses": [{"id": "h1"}]}))


def test_status_label_covers_known_and_unknown_statuses() -> None:
    assert status_label("confirmed_in_scope") == "Confirmed in scope"
    assert status_label("observation") == "Observation"
    assert status_label("some_new_status") == "Some new status"


def test_html_without_open_questions_says_so(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    render_html({"title": "Trial"}, out)
    assert "No open questions were recorded." in out.read_text(encoding="utf-8")


def test_html_without_rule_versions_says_so(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    render_html({"title": "Trial"}, out)
    assert "No rule versions were recorded." in out.read_text(encoding="utf-8")


def test_markdown_escapes_nothing_it_should_not(tmp_path: Path) -> None:
    # Markdown is plain text, so angle brackets that would be tags in HTML
    # must survive verbatim.
    out = tmp_path / "report.md"
    render_markdown({"title": "Trial", "open_questions": ["a < b & c"]}, out)
    assert "a < b & c" in out.read_text(encoding="utf-8")
