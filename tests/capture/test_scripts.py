"""Tests for the corpus and benchmark generators."""

from __future__ import annotations

from pathlib import Path

from scripts.generate_benchmark_pcap import build
from scripts.generate_corpus import (
    CMD_READ,
    generate,
    read_request,
    read_response,
    request,
)
from src.capture.parser import read_capture
from src.capture.pipeline import normalize
from src.capture.session import Direction


def test_request_framing_is_length_prefixed() -> None:
    message = request(CMD_READ, b"\x10")
    assert message == bytes([0x01, 0x00, 0x00, 0x01, 0x10])
    assert len(read_request(0x10)) == 5


def test_read_response_echoes_parameter_and_value() -> None:
    body = read_response(0x10, 0x1234)
    assert body[0] == CMD_READ
    assert body[1] == 0x00
    assert int.from_bytes(body[2:4], "big") == 3
    assert body[4] == 0x10
    assert body[5:7] == b"\x12\x34"


def test_generate_writes_expected_files(tmp_path: Path) -> None:
    sizes = generate(tmp_path, scale=2)
    assert set(sizes) == {
        "corpus_capture_01.pcapng",
        "corpus_capture_02.pcapng",
        "corpus_capture_defects.pcapng",
        "corpus_journal.md",
        "README.md",
    }
    assert sum(sizes.values()) < 10 * 1024 * 1024


def test_generate_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    generate(first, scale=2)
    generate(second, scale=2)
    for name in ("corpus_capture_01.pcapng", "corpus_capture_defects.pcapng"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_primary_capture_has_three_full_sessions(tmp_path: Path) -> None:
    generate(tmp_path, scale=2)
    capture = normalize(tmp_path / "corpus_capture_01.pcapng")
    assert len(capture.sessions) == 3
    for session in capture.sessions:
        stream = capture.streams[session.session_id][Direction.A_TO_B]
        assert len(stream.bytes_) > 0
        assert stream.gaps() == []
        assert stream.ambiguities() == []


def test_defects_capture_reports_gap_and_ambiguity(tmp_path: Path) -> None:
    generate(tmp_path, scale=2)
    capture = normalize(tmp_path / "corpus_capture_defects.pcapng")
    session = capture.sessions[0]
    a_to_b = capture.streams[session.session_id][Direction.A_TO_B]
    b_to_a = capture.streams[session.session_id][Direction.B_TO_A]
    assert len(a_to_b.gaps()) == 1
    assert len(b_to_a.ambiguities()) == 1


def test_journal_timestamps_exist_in_the_captures(tmp_path: Path) -> None:
    sizes = generate(tmp_path, scale=2)
    assert "corpus_journal.md" in sizes
    timestamps = set()
    for name in ("corpus_capture_01.pcapng", "corpus_capture_02.pcapng",
                 "corpus_capture_defects.pcapng"):
        for packet in read_capture(tmp_path / name):
            timestamps.add(round(packet.timestamp, 3))
    journal = (tmp_path / "corpus_journal.md").read_text(encoding="utf-8")
    rows = [
        line for line in journal.splitlines()
        if line and line[0].isdigit() and " | " in line
    ]
    assert rows
    for row in rows:
        stamp = round(float(row.split(" | ", 1)[0]), 3)
        assert stamp in timestamps


def test_benchmark_builder_shapes_a_small_capture(tmp_path: Path) -> None:
    data = build(packets=400, sessions=4, target_mib=1, max_response=4096)
    path = tmp_path / "small.pcapng"
    path.write_bytes(data)
    packets = list(read_capture(path))
    assert len(packets) == 400
    capture = normalize(path)
    assert len(capture.sessions) == 4
    assert any(len(p.payload) > 0 for p in packets)
