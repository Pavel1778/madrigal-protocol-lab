"""Property checks for directional reassembly.

Each test builds a pseudo-random exchange from a fixed seed and asserts an
invariant that must hold for any ordering of the segments: observed bytes are
never lost or invented, provenance covers the stream exactly, and the result is
reproducible. A fixed seed keeps the case reproducible while still covering
orderings the hand-written fixtures do not.
"""

from __future__ import annotations

import random

import pytest

from src.capture.parser import Packet
from src.capture.reassembly import reassemble
from src.capture.session import Direction, Endpoint, Session


def _session() -> Session:
    return Session(
        session_id="s1",
        endpoints=(Endpoint("10.0.0.1", 40000), Endpoint("10.0.0.2", 9000)),
        isn_a=1000,
    )


def _packet(index: int, seq: int, payload: bytes) -> Packet:
    return Packet(
        index=index,
        timestamp=1000.0 + index * 0.001,
        src_ip="10.0.0.1",
        src_port=40000,
        dst_ip="10.0.0.2",
        dst_port=9000,
        seq=seq,
        ack=0,
        flags=0,
        payload=payload,
    )


def _random_packets(rng: random.Random, count: int) -> list[Packet]:
    """Segments placed at random offsets, so they overlap and leave holes."""

    packets: list[Packet] = []
    for index in range(count):
        seq = 1001 + rng.randrange(0, 400)
        length = rng.randrange(1, 40)
        payload = bytes(rng.randrange(256) for _ in range(length))
        packets.append(_packet(index, seq, payload))
    return packets


@pytest.mark.parametrize("seed", range(25))
def test_provenance_covers_the_stream_exactly(seed: int) -> None:
    packets = _random_packets(random.Random(seed), 60)
    stream = reassemble(_session(), Direction.A_TO_B, packets)

    # The ranges partition [0, len(stream)): no byte is left without a source
    # and no range claims a byte that is not in the stream.
    covered = sorted(
        (r.offset, r.offset + r.length)
        for r in stream.provenance.ranges
        if not r.is_retransmission
    )
    cursor = 0
    for start, end in covered:
        assert start == cursor
        assert end > start
        cursor = end
    assert cursor == len(stream.bytes_)


@pytest.mark.parametrize("seed", range(25))
def test_observed_bytes_are_never_lost(seed: int) -> None:
    packets = _random_packets(random.Random(seed), 60)
    stream = reassemble(_session(), Direction.A_TO_B, packets)

    # Every byte that only one segment could have contributed must appear. The
    # stream is the concatenation of the first writer of each position, so its
    # length is the number of distinct sequence positions covered.
    distinct = {
        packet.seq + offset
        for packet in packets
        for offset in range(len(packet.payload))
    }
    assert len(stream.bytes_) == len(distinct)
    assert distinct  # the generator always produces bytes


@pytest.mark.parametrize("seed", range(25))
def test_reassembly_is_reproducible(seed: int) -> None:
    packets = _random_packets(random.Random(seed), 60)
    first = reassemble(_session(), Direction.A_TO_B, packets)
    second = reassemble(_session(), Direction.A_TO_B, list(reversed(packets)))

    # Order of arrival must not change the result: the algorithm orders by
    # sequence number, not by the order the packets are handed over.
    assert first.bytes_ == second.bytes_
    assert [d.type for d in first.diagnostics] == [d.type for d in second.diagnostics]
    assert [
        (r.offset, r.length, r.seq) for r in first.provenance.ranges
    ] == [(r.offset, r.length, r.seq) for r in second.provenance.ranges]


@pytest.mark.parametrize("seed", range(25))
def test_every_stream_byte_has_a_source_packet(seed: int) -> None:
    packets = _random_packets(random.Random(seed), 60)
    by_index = {p.index: p for p in packets}
    stream = reassemble(_session(), Direction.A_TO_B, packets)

    for offset in range(len(stream.bytes_)):
        range_ = stream.provenance.lookup(offset)
        assert range_ is not None
        assert range_.packet_index in by_index
        source = by_index[range_.packet_index]
        # The byte in the stream matches the byte in the source packet at the
        # recorded sequence position, offset by the distance into the range.
        index_in_source = (range_.seq - source.seq) + (offset - range_.offset)
        assert 0 <= index_in_source < len(source.payload)
        assert stream.bytes_[offset] == source.payload[index_in_source]
