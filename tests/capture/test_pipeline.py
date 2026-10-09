"""Tests for the end-to-end normalization pipeline."""

from __future__ import annotations

from pathlib import Path

from src.capture.pipeline import normalize, normalize_bytes
from src.capture.session import Direction

from .conftest import fixture


def test_normalize_returns_sessions_and_streams() -> None:
    capture = normalize(fixture("normal.pcapng"))
    assert len(capture.sessions) == 1
    session = capture.sessions[0]
    assert set(capture.streams[session.session_id]) == {
        Direction.A_TO_B,
        Direction.B_TO_A,
    }


def test_normalize_bytes_matches_normalize(tmp_path: Path) -> None:
    from src.capture.pipeline import normalize as normalize_path

    path = fixture("retransmission.pcapng")
    from_disk = normalize_path(path)
    from_memory = normalize_bytes(path.read_bytes(), source_file=path)
    assert from_memory.capture_id == from_disk.capture_id
    assert len(from_memory.sessions) == len(from_disk.sessions)


def test_streams_are_deterministic() -> None:
    first = normalize(fixture("ooo.pcapng"))
    second = normalize(fixture("ooo.pcapng"))
    a = first.streams["s1"][Direction.A_TO_B]
    b = second.streams["s1"][Direction.A_TO_B]
    assert bytes(a.bytes_) == bytes(b.bytes_)
    assert [r.to_contract() for r in a.provenance.ranges] == [
        r.to_contract() for r in b.provenance.ranges
    ]
