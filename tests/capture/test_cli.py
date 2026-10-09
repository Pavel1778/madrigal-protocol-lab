"""Tests for the command line entry point."""

from __future__ import annotations

import json
from pathlib import Path

from src.capture.cli import main

from .conftest import fixture


def test_cli_writes_normalized_capture(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    code = main(
        [
            "--pcap",
            str(fixture("normal.pcapng")),
            "--out",
            str(out),
            "--quiet",
        ]
    )
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["contract_version"] == 1
    assert len(data["sessions"]) == 1
    assert data["source_file"] == str(fixture("normal.pcapng"))


def test_cli_source_name_override(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    main(
        [
            "--pcap",
            str(fixture("normal.pcapng")),
            "--out",
            str(out),
            "--source-name",
            "captures/normal.pcapng",
            "--quiet",
        ]
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source_file"] == "captures/normal.pcapng"


def test_cli_missing_file_returns_two(tmp_path: Path, capsys) -> None:
    code = main(
        ["--pcap", str(tmp_path / "nope.pcapng"), "--out", str(tmp_path / "x.json")]
    )
    assert code == 2
    assert "not found" in capsys.readouterr().err
