"""Boundary tests for the capture command line entry point."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from src.capture.cli import main

from .conftest import fixture


def test_verbose_enables_info_logging(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    try:
        code = main(
            [
                "--pcap",
                str(fixture("normal.pcapng")),
                "--out",
                str(out),
                "--verbose",
            ]
        )
        assert code == 0
        assert logging.getLogger().getEffectiveLevel() == logging.INFO
    finally:
        # main() reconfigures the root logger; restore it for the other tests.
        logging.getLogger().setLevel(logging.WARNING)


def test_without_verbose_stays_quiet(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    try:
        code = main(["--pcap", str(fixture("normal.pcapng")), "--out", str(out)])
        assert code == 0
        assert logging.getLogger().getEffectiveLevel() == logging.WARNING
    finally:
        logging.getLogger().setLevel(logging.WARNING)


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


def test_unreadable_capture_reports_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.pcapng"
    bad.write_bytes(b"not a capture at all")
    code = main(["--pcap", str(bad), "--out", str(tmp_path / "out.json")])
    assert code == 2
    err = capsys.readouterr().err
    assert "cannot read capture" in err
    assert "Traceback" not in err


def test_empty_capture_reports_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.pcapng"
    empty.write_bytes(b"")
    code = main(["--pcap", str(empty), "--out", str(tmp_path / "out.json")])
    assert code == 2
    err = capsys.readouterr().err
    assert "cannot read capture" in err
    assert "Traceback" not in err
