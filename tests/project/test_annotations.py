"""Tests for researcher annotations and their path into the report."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.project.annotations import (
    ANNOTATION_KINDS,
    Annotation,
    AnnotationError,
    AnnotationStore,
)
from src.project.cli import main as cli_main
from src.project.pipeline import build_investigation
from src.project.project import Project
from src.report.html import render_html
from src.report.markdown import render


def _project(tmp_path: Path) -> Project:
    return Project.create(tmp_path / "project.madrigal", "investigation")


def test_store_creates_schema_lazily(tmp_path: Path) -> None:
    store = AnnotationStore(tmp_path / "annotations.sqlite")
    store.add(
        Annotation(
            capture_id="sha256:" + "ab" * 32,
            session_id="s1",
            direction="A_to_B",
            offset=4,
            length=2,
            kind="observation",
            text="setpoint candidate",
        )
    )
    assert store.count() == 1
    store.close()

    # Reopening the same file sees the stored annotation.
    reopened = AnnotationStore(tmp_path / "annotations.sqlite")
    items = reopened.list()
    assert len(items) == 1
    assert items[0].text == "setpoint candidate"
    assert items[0].created_at.endswith("Z")
    reopened.close()


def test_annotation_rejects_unknown_kind(tmp_path: Path) -> None:
    with pytest.raises(AnnotationError):
        Annotation(
            capture_id="c",
            session_id="s1",
            direction="A_to_B",
            offset=0,
            length=1,
            kind="guess",
            text="x",
        )


def test_annotation_rejects_empty_text() -> None:
    with pytest.raises(AnnotationError):
        Annotation(
            capture_id="c",
            session_id="s1",
            direction="A_to_B",
            offset=0,
            length=1,
            kind="question",
            text="   ",
        )


def test_list_filters_by_session_and_direction(tmp_path: Path) -> None:
    store = AnnotationStore(tmp_path / "annotations.sqlite")
    for session, direction, offset in (
        ("s1", "A_to_B", 0),
        ("s1", "B_to_A", 8),
        ("s2", "A_to_B", 16),
    ):
        store.add(
            Annotation(
                capture_id="c",
                session_id=session,
                direction=direction,
                offset=offset,
                length=1,
                kind="observation",
                text=f"{session}/{direction}",
            )
        )
    assert len(store.list(session_id="s1")) == 2
    assert len(store.list(direction="A_to_B")) == 2
    assert len(store.list(session_id="s1", direction="A_to_B")) == 1
    store.close()


def test_project_add_and_read_annotation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    annotation = project.add_annotation(
        "sha256:" + "cd" * 32, "s1", "A_to_B", 12, 4, "confirmed", "frame delimiter"
    )
    assert annotation.id == 1
    with project.annotations() as store:
        items = store.list()
    assert [item.text for item in items] == ["frame delimiter"]


def test_cli_annotate_and_list(tmp_path: Path) -> None:
    project = _project(tmp_path)
    code = cli_main(
        [
            "annotate",
            "--project",
            str(project.root),
            "--capture",
            "sha256:" + "ef" * 32,
            "--session",
            "s1",
            "--direction",
            "A_to_B",
            "--offset",
            "4",
            "--length",
            "2",
            "--kind",
            "hypothesis",
            "--text",
            "parameter value",
        ]
    )
    assert code == 0

    listed = cli_main(["annotations", "--project", str(project.root)])
    assert listed == 0
    assert project.annotations().count() == 1


def test_investigation_carries_annotations_into_report(tmp_path: Path) -> None:
    annotation = Annotation(
        capture_id="sha256:" + "ab" * 32,
        session_id="s1",
        direction="A_to_B",
        offset=4,
        length=2,
        kind="observation",
        text="setpoint candidate",
        created_at="2026-01-01T00:00:00Z",
        id=1,
    )
    result = {
        "rule_id": "r1",
        "rule_version": 1,
        "capture_id": "sha256:" + "ab" * 32,
        "messages": [],
        "summary": {"matched": 0},
    }
    investigation = build_investigation(
        result,
        capture_id="sha256:" + "ab" * 32,
        source_file="captures/cap.pcapng",
        annotations=[annotation],
    )
    assert investigation["annotations"][0]["text"] == "setpoint candidate"

    markdown = render(investigation)
    assert "## Annotations" in markdown
    assert "setpoint candidate" in markdown
    assert "s1/A_to_B offset 4, length 2" in markdown

    out = tmp_path / "report.html"
    render_html(investigation, out)
    html = out.read_text(encoding="utf-8")
    assert "<h2>Annotations</h2>" in html
    assert "setpoint candidate" in html


def test_report_states_when_no_annotations(tmp_path: Path) -> None:
    investigation = build_investigation(
        {"rule_id": "r1", "rule_version": 1, "summary": {"matched": 1}},
        capture_id="c",
        source_file="captures/cap.pcapng",
    )
    assert investigation["annotations"] == []
    assert "No annotations were recorded." in render(investigation)


def test_annotation_kind_set_is_closed() -> None:
    assert set(ANNOTATION_KINDS) == {
        "observation",
        "hypothesis",
        "confirmed",
        "contradiction",
        "question",
    }
