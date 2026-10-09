"""Boundary tests for the project command line entry point."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.project.cli import main

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
CAPTURE = CORPUS / "corpus_capture_01.pcapng"


def test_cli_create_then_open_with_show(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project.madrigal"
    assert main(["create", "--path", str(project), "--name", "trial"]) == 0
    capsys.readouterr()
    assert main(["open", "--path", str(project), "--show"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["manifest"]["name"] == "trial"
    assert payload["name"] == "trial"


def test_cli_open_without_show_omits_the_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project.madrigal"
    assert main(["create", "--path", str(project)]) == 0
    capsys.readouterr()
    assert main(["open", "--path", str(project)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "manifest" not in payload


def test_cli_add_capture_registers_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project.madrigal"
    assert main(["create", "--path", str(project)]) == 0
    capsys.readouterr()
    assert main(["add-capture", "--project", str(project), "--pcap", str(CAPTURE)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["capture"] == f"captures/{CAPTURE.name}"


def test_cli_open_on_a_missing_project_returns_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["open", "--path", str(tmp_path / "absent")])
    assert code == 2
    assert "is not a directory" in capsys.readouterr().err


def test_cli_export_and_import_round_trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project.madrigal"
    assert main(["create", "--path", str(project)]) == 0
    assert main(["add-capture", "--project", str(project), "--pcap", str(CAPTURE)]) == 0
    capsys.readouterr()
    archive = tmp_path / "bundle.zip"
    assert main(["export", "--project", str(project), "--out", str(archive)]) == 0
    capsys.readouterr()
    target = tmp_path / "restored.madrigal"
    assert main(["import", "--in", str(archive), "--target", str(target)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["broken"] == []
    assert (target / "manifest.json").is_file()


def test_cli_import_of_a_missing_archive_returns_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "import",
            "--in",
            str(tmp_path / "absent.zip"),
            "--target",
            str(tmp_path / "x"),
        ]
    )
    assert code == 2
    assert "no archive" in capsys.readouterr().err


def test_cli_pipeline_with_report_and_wireshark(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project.madrigal"
    extra = tmp_path / "REPORT.md"
    code = main(
        [
            "pipeline",
            "--pcap",
            str(CAPTURE),
            "--project",
            str(project),
            "--report",
            str(extra),
            "--wireshark-pcap",
        ]
    )
    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["report_html"].endswith("REPORT.html")
    assert summary["wireshark"].endswith("reassembled.pcap")
    assert extra.is_file()


def test_cli_pipeline_quiet_prints_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project.madrigal"
    code = main(
        ["pipeline", "--pcap", str(CAPTURE), "--project", str(project), "--quiet"]
    )
    assert code == 0
    assert capsys.readouterr().out == ""


def test_cli_pipeline_no_html_skips_the_html_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project.madrigal"
    code = main(
        ["pipeline", "--pcap", str(CAPTURE), "--project", str(project), "--no-html"]
    )
    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert "report_html" not in summary


def test_cli_pipeline_missing_capture_returns_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    assert capsys.readouterr().err.strip()


def test_cli_open_without_manifest_reports_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "empty.madrigal"
    directory.mkdir()
    code = main(["open", "--path", str(directory)])
    assert code == 2
    err = capsys.readouterr().err
    assert "no manifest" in err
    assert "Traceback" not in err


def test_cli_open_with_corrupt_manifest_reports_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "broken.madrigal"
    directory.mkdir()
    (directory / "manifest.json").write_text("{ not json", encoding="utf-8")
    code = main(["open", "--path", str(directory)])
    assert code == 2
    err = capsys.readouterr().err
    assert "not valid JSON" in err
    assert "Traceback" not in err
