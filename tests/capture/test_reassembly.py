"""Tests for directional stream reassembly."""

from __future__ import annotations

from pathlib import Path

from src.capture.parser import Packet
from src.capture.pipeline import normalize
from src.capture.reassembly import reassemble
from src.capture.session import Direction, Endpoint, Session

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
    # The repeat is named as a retransmission, not left as an anonymous range.
    repeats = stream.retransmissions()
    assert repeats
    assert all(r.is_retransmission for r in repeats)


def test_clean_stream_has_no_retransmissions(fixtures_dir: Path) -> None:
    assert _stream("normal.pcapng").retransmissions() == []


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


def test_segment_straddling_the_wrap_keeps_its_byte_order() -> None:
    mask = 0xFFFFFFFF
    session = Session(
        session_id="s1",
        endpoints=(Endpoint("10.0.0.1", 1), Endpoint("10.0.0.2", 2)),
        isn_a=mask - 1,
    )
    # One segment whose payload crosses 2**32: it starts at 0xFFFFFFFE and its
    # later bytes belong to sequence numbers past the wrap.
    packet = Packet(
        index=0,
        timestamp=1.0,
        src_ip="10.0.0.1",
        src_port=1,
        dst_ip="10.0.0.2",
        dst_port=2,
        seq=mask - 1,
        ack=0,
        flags=0,
        payload=b"WXYZ",
    )
    stream = reassemble(session, Direction.A_TO_B, [packet])
    assert bytes(stream.bytes_) == b"WXYZ"
    assert stream.gaps() == []
    rng = stream.provenance.lookup(3)
    assert rng is not None and rng.seq == mask - 1


def test_out_of_order_segments_across_the_wrap_are_ordered() -> None:
    mask = 0xFFFFFFFF
    session = Session(
        session_id="s1",
        endpoints=(Endpoint("10.0.0.1", 1), Endpoint("10.0.0.2", 2)),
        isn_a=mask - 2,
    )

    def packet(index: int, seq: int, payload: bytes) -> Packet:
        return Packet(
            index=index,
            timestamp=1.0 + index,
            src_ip="10.0.0.1",
            src_port=1,
            dst_ip="10.0.0.2",
            dst_port=2,
            seq=seq,
            ack=0,
            flags=0,
            payload=payload,
        )

    # The segment that wraps arrives first; the earlier one arrives second.
    packets = [packet(0, 0, b"CD"), packet(1, mask - 1, b"AB")]
    stream = reassemble(session, Direction.A_TO_B, packets)
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
