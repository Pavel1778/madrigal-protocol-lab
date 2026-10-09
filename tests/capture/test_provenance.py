"""Tests for the provenance helpers."""

from __future__ import annotations

from src.capture.provenance import Provenance, Range


def test_lookup_inside_and_outside_ranges() -> None:
    provenance = Provenance()
    provenance.add(Range(offset=0, length=4, packet_index=1, seq=100, ts=1.0))
    provenance.add(Range(offset=10, length=3, packet_index=2, seq=200, ts=2.0))

    first = provenance.lookup(0)
    assert first is not None and first.packet_index == 1
    second = provenance.lookup(3)
    assert second is not None and second.packet_index == 1
    assert provenance.lookup(4) is None  # a gap
    third = provenance.lookup(10)
    assert third is not None and third.packet_index == 2
    fourth = provenance.lookup(12)
    assert fourth is not None and fourth.packet_index == 2
    assert provenance.lookup(13) is None  # past the end
    assert provenance.lookup(99) is None


def test_split_returns_covering_subranges() -> None:
    provenance = Provenance()
    provenance.add(Range(offset=0, length=5, packet_index=1, seq=1000, ts=1.0))
    provenance.add(Range(offset=5, length=5, packet_index=2, seq=2000, ts=2.0))

    parts = provenance.split(3, 8)
    assert [(p.offset, p.length, p.packet_index) for p in parts] == [
        (3, 2, 1),
        (5, 3, 2),
    ]
    # The sequence number is shifted by the same amount as the offset.
    assert parts[0].seq == 1003
    assert parts[1].seq == 2000


def test_range_end_and_contract() -> None:
    rng = Range(offset=2, length=3, packet_index=7, seq=42, ts=1.5)
    assert rng.end == 5
    assert rng.to_contract() == {
        "offset": 2,
        "length": 3,
        "packet_index": 7,
        "seq": 42,
        "ts": 1.5,
    }
