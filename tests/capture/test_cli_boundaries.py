"""Boundary tests for the capture command line entry point."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.capture.cli import main

from .conftest import fixture


def test_streaming_mode_writes_a_normalized_capture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.json"
    code = main(
        [
            "--pcap",
            str(fixture("normal.pcapng")),
            "--out",
            str(out),
            "--stream",
            "--chunk-size",
            "1",
        ]
    )
    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["mode"] == "streaming"
    assert summary["sessions"] == 1
    document = json.loads(out.read_text(encoding="utf-8"))
    assert len(document["sessions"]) == 1


def test_quiet_suppresses_the_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    assert capsys.readouterr().out == ""


def test_wireshark_export_writes_a_pcap(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    pcap = tmp_path / "reassembled.pcap"
    code = main(
        [
            "--pcap",
            str(fixture("normal.pcapng")),
            "--out",
            str(out),
            "--wireshark-pcap",
            str(pcap),
        ]
    )
    assert code == 0
    assert pcap.is_file() and pcap.stat().st_size > 0


def test_checksum_flag_is_accepted(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    code = main(
        [
            "--pcap",
            str(fixture("normal.pcapng")),
            "--out",
            str(out),
            "--verify-checksums",
        ]
    )
    assert code == 0
    assert out.is_file()
