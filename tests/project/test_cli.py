"""Tests for the project CLI and the end-to-end pipeline.

The rule path is exercised only when the protocol engine is importable, so this
suite does not depend on another work stream being present.
"""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

from src.project import Project
from src.project.cli import main
from src.project.pipeline import build_investigation, run_pipeline

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
CAPTURE = CORPUS / "corpus_capture_01.pcapng"

HAS_ENGINE = importlib.util.find_spec("src.protocol.engine") is not None


def test_pipeline_end_to_end(tmp_path: Path) -> None:
    project_path = tmp_path / "project.madrigal"
    outcome = run_pipeline(CAPTURE, project_path, report_path=tmp_path / "REPORT.md")

    assert outcome.sessions == 3
    assert outcome.normalized.is_file()
    assert (project_path / "captures" / CAPTURE.name).is_file()
    assert (project_path / "reports" / "REPORT.md").is_file()
    assert (project_path / "reports" / "REPORT.html").is_file()
    assert (tmp_path / "REPORT.md").is_file()

    # The project still verifies its captures, and the manifest points at the
    # results it produced.
    reopened = Project.open(project_path)
    assert reopened.verify_captures() == []
    kinds = {entry["kind"] for entry in reopened.manifest.results}
    assert {"normalized_capture", "report"} <= kinds

    # The normalized capture is the contract document.
    normalized = json.loads(outcome.normalized.read_text(encoding="utf-8"))
    assert normalized["contract_version"] == 1
    assert len(normalized["sessions"]) == 3
    assert normalized["source_file"] == f"captures/{CAPTURE.name}"


def test_pipeline_cli_creates_project_and_report(tmp_path: Path) -> None:
    project_path = tmp_path / "project.madrigal"
    code = main(
        [
            "pipeline",
            "--pcap",
            str(CAPTURE),
            "--project",
            str(project_path),
            "--report",
            str(tmp_path / "REPORT.md"),
            "--quiet",
        ]
    )
    assert code == 0
    assert (project_path / "manifest.json").is_file()
    report = (project_path / "reports" / "REPORT.md").read_text(encoding="utf-8")
    assert "## Open questions" in report
    assert "No interpretation rule was applied" in report


def test_pipeline_streaming_matches_regular(tmp_path: Path) -> None:
    regular = tmp_path / "regular"
    streamed = tmp_path / "streamed"
    run_pipeline(CAPTURE, regular / "project.madrigal", html=False)
    run_pipeline(CAPTURE, streamed / "project.madrigal", html=False, streaming=True)

    a = json.loads((regular / "project.madrigal" / "results" / "normalized.json").read_text())
    b = json.loads((streamed / "project.madrigal" / "results" / "normalized.json").read_text())
    assert len(a["sessions"]) == len(b["sessions"]) == 3
    assert a["capture_id"] == b["capture_id"]
    assert a["source_file"] == b["source_file"]
    for left, right in zip(a["sessions"], b["sessions"]):
        assert left["directions"] == right["directions"]


def test_pipeline_refuses_existing_project_without_force(tmp_path: Path) -> None:
    project_path = tmp_path / "project.madrigal"
    run_pipeline(CAPTURE, project_path)
    with pytest.raises(Exception):
        run_pipeline(CAPTURE, project_path)
    # force replaces it cleanly
    outcome = run_pipeline(CAPTURE, project_path, force=True)
    assert outcome.sessions == 3


def test_pipeline_wireshark_export(tmp_path: Path) -> None:
    project_path = tmp_path / "project.madrigal"
    outcome = run_pipeline(CAPTURE, project_path, wireshark=True)
    assert outcome.wireshark is not None and outcome.wireshark.is_file()
    assert outcome.wireshark.read_bytes()[:4] in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4")


def test_cli_create_open_add_export_import(tmp_path: Path) -> None:
    project_path = tmp_path / "project.madrigal"
    assert main(["create", "--path", str(project_path), "--name", "demo"]) == 0
    assert Project.open(project_path).name == "demo"

    assert main(["open", "--path", str(project_path), "--show"]) == 0
    assert main(["add-capture", "--project", str(project_path), "--pcap", str(CAPTURE)]) == 0
    assert Project.open(project_path).verify_captures() == []

    archive = tmp_path / "bundle.zip"
    assert main(["export", "--project", str(project_path), "--out", str(archive)]) == 0
    assert zipfile.is_zipfile(archive)

    target = tmp_path / "restored"
    assert main(["import", "--in", str(archive), "--target", str(target)]) == 0
    restored = Project.open(target)
    assert restored.verify_captures() == []


def test_cli_reports_missing_capture(tmp_path: Path) -> None:
    code = main(
        [
            "pipeline",
            "--pcap",
            str(tmp_path / "absent.pcapng"),
            "--project",
            str(tmp_path / "project.madrigal"),
        ]
    )
    assert code == 2


def test_investigation_from_contradictory_result() -> None:
    result = {
        "rule_id": "r1",
        "rule_version": 2,
        "capture_id": "sha256:aa",
        "summary": {"matched": 3, "mismatched": 1, "incomplete": 0, "ambiguous": 0, "unknown": 0, "uncovered": 0},
        "messages": [
            {"offset": 0, "length": 8, "status": "matched"},
            {"offset": 8, "length": 8, "status": "mismatched"},
        ],
    }
    investigation = build_investigation(result, capture_id="sha256:aa", source_file="cap.pcapng")
    assert investigation["hypotheses"][0]["status"] == "contradiction"
    assert len(investigation["counterexamples"]) == 1
    assert investigation["counterexamples"][0]["offset"] == 8


@pytest.mark.skipif(not HAS_ENGINE, reason="protocol engine not present in this checkout")
def test_pipeline_applies_rule_when_engine_present(tmp_path: Path) -> None:
    rule = Path(__file__).resolve().parent.parent.parent / "src" / "protocol" / "examples" / "set_parameter_request.json"
    if not rule.is_file():
        pytest.skip("example rule not present")
    project_path = tmp_path / "project.madrigal"
    outcome = run_pipeline(CAPTURE, project_path, rule_path=rule)
    assert outcome.result is not None and outcome.result.is_file()
    result = json.loads(outcome.result.read_text(encoding="utf-8"))
    assert result["rule_id"] == "set_parameter_request"
    assert result["summary"]["matched"] + result["summary"]["incomplete"] > 0
    report = (project_path / "reports" / "REPORT.md").read_text(encoding="utf-8")
    assert "## Counterexamples" in report
