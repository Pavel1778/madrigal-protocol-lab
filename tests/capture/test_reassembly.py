"""Tests for directional stream reassembly."""

from __future__ import annotations

from pathlib import Path

from src.capture.pipeline import normalize
from src.capture.session import Direction

from .conftest import fixture


def _stream(name: str, direction: Direction = Direction.A_TO_B):
    capture = normalize(fixture(name))
    session = capture.sessions[0]
    return capture.streams[session.session_id][direction]


def test_clean_stream(fixtures_dir: Path) -> None:
    stream = _stream("normal.pcapng")
    assert bytes(stream.bytes_) == b"HELLO"
    assert stream.gaps() == []
    assert stream.ambiguities() == []
    other = _stream("normal.pcapng", Direction.B_TO_A)
    assert bytes(other.bytes_) == b"WORLD"


def test_identical_retransmission_adds_no_bytes(fixtures_dir: Path) -> None:
    stream = _stream("retransmission.pcapng")
    assert bytes(stream.bytes_) == b"ABCD"
    assert stream.ambiguities() == []
    # The retransmitted payload is kept as an extra source, not as extra bytes.
    assert len(stream.provenance.ranges) >= 3


def test_out_of_order_is_reordered_by_sequence(fixtures_dir: Path) -> None:
    stream = _stream("ooo.pcapng")
    assert bytes(stream.bytes_) == b"ABCD"
    assert stream.gaps() == []


def test_gap_is_reported_not_filled(fixtures_dir: Path) -> None:
    stream = _stream("gap.pcapng")
    # Only observed bytes are present; nothing is invented for the hole.
    assert bytes(stream.bytes_) == b"ABGH"
    gaps = stream.gaps()
    assert len(gaps) == 1
    assert gaps[0].length == 4
    assert gaps[0].offset == 2


def test_conflicting_overlap_is_ambiguous(fixtures_dir: Path) -> None:
    stream = _stream("overlap_conflict.pcapng")
    assert bytes(stream.bytes_) == b"ABCD"
    ambiguities = stream.ambiguities()
    assert len(ambiguities) == 1
    assert ambiguities[0].length == 2
    assert ambiguities[0].offset == 2
    assert "kept 4344, rejected 5859" in (ambiguities[0].detail or "")


def test_sequence_wrap_is_ordered(fixtures_dir: Path) -> None:
    stream = _stream("seq_wrap.pcapng")
    assert bytes(stream.bytes_) == b"ABCD"
    assert stream.gaps() == []


def test_message_boundaries_do_not_matter(fixtures_dir: Path) -> None:
    split = _stream("message_split_across_packets.pcapng")
    assert bytes(split.bytes_) == b"\x00\x07PAYLOAD"
    packed = _stream("two_messages_in_one_packet.pcapng")
    assert bytes(packed.bytes_) == b"\x00\x03AAA\x00\x02BB"


def test_provenance_maps_offsets_to_packets(fixtures_dir: Path) -> None:
    stream = _stream("normal.pcapng")
    rng = stream.provenance.lookup(0)
    assert rng is not None
    assert rng.packet_index == 3
    assert rng.seq == 1001
    parts = stream.provenance.split(0, 5)
    assert [(p.offset, p.length) for p in parts] == [(0, 5)]
    assert stream.provenance.lookup(5) is None
