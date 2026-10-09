"""Boundary and negative tests for the capture engine.

These cover the edges the main suites leave out: malformed captures, unusual
datalink types, payload-free sessions, checksum handling, and provenance
mapping at the ends of a range.
"""

from __future__ import annotations

import struct
from pathlib import Path

import dpkt
import pytest

from scripts.generate_fixture import _write_pcapng, data_a, syn
from src.capture.parser import TH_SYN, Diagnostic, read_capture
from src.capture.pipeline import normalize
from src.capture.provenance import Provenance, Range
from src.capture.reassembly import reassemble
from src.capture.session import Direction, build_sessions

from .conftest import fixture


def _pcapng_with_linktype(linktype: int, frame: bytes) -> bytes:
    """Build a minimal pcapng file whose interface advertises ``linktype``."""

    def block(block_type: int, body: bytes) -> bytes:
        total = 12 + len(body)
        return struct.pack("<II", block_type, total) + body + struct.pack("<I", total)

    section = block(0x0A0D0D0A, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1))
    interface_body = struct.pack("<HHI", linktype, 0, 65535) + struct.pack("<I", 0)
    interface = block(1, interface_body)
    padded = frame + b"\x00" * (-len(frame) % 4)
    packet_body = struct.pack("<IIIII", 0, 0, 0, len(frame), len(frame)) + padded
    packet = block(6, packet_body)
    return section + interface + packet


def _ipv4_tcp(seq: int, flags: int, sport: int = 1000, dport: int = 2000) -> bytes:
    tcp = dpkt.tcp.TCP(sport=sport, dport=dport, seq=seq, flags=flags, data=b"", off=5)
    ip = dpkt.ip.IP(
        src=b"\x0a\x00\x00\x01",
        dst=b"\x0a\x00\x00\x02",
        p=dpkt.ip.IP_PROTO_TCP,
        data=bytes(tcp),
    )
    ip.len = len(bytes(ip))
    return bytes(ip)


# -- parser edges ---------------------------------------------------------


def test_non_capture_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "notes.bin"
    # Long enough that dpkt reaches the header check rather than running short.
    path.write_bytes(b"this is not a capture\n" * 64)
    with pytest.raises(ValueError):
        list(read_capture(path))


def test_missing_directory_is_reported_as_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(read_capture(tmp_path / "absent" / "nothing.pcapng"))


def test_raw_linktype_is_parsed(tmp_path: Path) -> None:
    path = tmp_path / "raw.pcapng"
    path.write_bytes(_pcapng_with_linktype(12, _ipv4_tcp(seq=1, flags=TH_SYN)))
    packets = list(read_capture(path))
    assert len(packets) == 1
    assert packets[0].syn and packets[0].src_port == 1000


def test_sll_linktype_is_parsed(tmp_path: Path) -> None:
    cooked = b"\x00\x00\x00\x01" + b"\x00" * 12 + _ipv4_tcp(seq=7, flags=TH_SYN)
    path = tmp_path / "sll.pcapng"
    path.write_bytes(_pcapng_with_linktype(113, cooked))
    packets = list(read_capture(path))
    assert len(packets) == 1
    assert packets[0].seq == 7


def test_loopback_linktype_is_parsed(tmp_path: Path) -> None:
    # A BSD/loopback header is a 4-byte address family in front of the IP packet.
    loopback = struct.pack("<I", 2) + _ipv4_tcp(seq=11, flags=TH_SYN)
    path = tmp_path / "loop.pcapng"
    path.write_bytes(_pcapng_with_linktype(0, loopback))
    packets = list(read_capture(path))
    assert len(packets) == 1
    assert packets[0].seq == 11


def test_short_loopback_header_is_a_diagnostic(tmp_path: Path) -> None:
    diagnostics: list[Diagnostic] = []
    path = tmp_path / "short-loop.pcapng"
    path.write_bytes(_pcapng_with_linktype(0, b"\x02\x00"))
    packets = list(read_capture(path, diagnostics))
    assert packets == []
    assert "truncated_frame" in [d.type for d in diagnostics]


def test_short_cooked_header_is_a_diagnostic(tmp_path: Path) -> None:
    diagnostics: list[Diagnostic] = []
    path = tmp_path / "short-sll.pcapng"
    path.write_bytes(_pcapng_with_linktype(113, b"\x00" * 8))
    packets = list(read_capture(path, diagnostics))
    assert packets == []
    assert "truncated_frame" in [d.type for d in diagnostics]


def test_checksum_verification_accepts_a_valid_segment(tmp_path: Path) -> None:
    path = tmp_path / "one.pcapng"
    path.write_bytes(_write_pcapng([syn(seq=1000)]))
    packets = list(read_capture(path, verify_checksums=True))
    assert len(packets) == 1
    assert packets[0].checksum_valid is True


def test_checksum_verification_marks_a_bad_segment(tmp_path: Path) -> None:
    # dpkt recomputes the checksum when it serializes a segment, so the frame
    # is built first and the checksum field is then corrupted in place.
    eth = dpkt.ethernet.Ethernet(syn(seq=1000))
    eth.data.data.sum ^= 0xFFFF
    path = tmp_path / "bad.pcapng"
    path.write_bytes(_write_pcapng([bytes(eth)]))
    packets = list(read_capture(path, verify_checksums=True))
    assert len(packets) == 1
    assert packets[0].checksum_valid is False


# -- session edges --------------------------------------------------------


def test_syn_retransmission_does_not_split_the_session() -> None:
    packets = list(read_capture(fixture("normal.pcapng")))
    packets += [p for p in packets if p.syn and not p.ack_flag]
    sessions = build_sessions(packets)
    assert len(sessions) == 1


def test_direction_opposite_swaps() -> None:
    assert Direction.A_TO_B.opposite is Direction.B_TO_A
    assert Direction.B_TO_A.opposite is Direction.A_TO_B


# -- provenance edges -----------------------------------------------------


def test_provenance_lookup_at_range_end_is_none() -> None:
    prov = Provenance()
    prov.add(Range(offset=0, length=4, packet_index=1, seq=10, ts=0.0))
    assert prov.lookup(3) is not None
    assert prov.lookup(4) is None
    assert prov.lookup(-1) is None


def test_provenance_lookup_after_a_gap_is_none() -> None:
    prov = Provenance()
    prov.add(Range(offset=0, length=2, packet_index=1, seq=10, ts=0.0))
    prov.add(Range(offset=10, length=2, packet_index=2, seq=30, ts=1.0))
    assert prov.lookup(5) is None
    assert prov.lookup(10) is not None


def test_provenance_split_clips_to_the_span() -> None:
    prov = Provenance()
    prov.add(Range(offset=0, length=6, packet_index=1, seq=10, ts=0.0))
    (part,) = prov.split(2, 4)
    assert (part.offset, part.length, part.seq) == (2, 2, 12)


def test_provenance_split_over_a_gap_returns_two_parts() -> None:
    prov = Provenance()
    prov.add(Range(offset=0, length=2, packet_index=1, seq=10, ts=0.0))
    prov.add(Range(offset=4, length=2, packet_index=2, seq=20, ts=1.0))
    parts = prov.split(1, 5)
    assert [p.offset for p in parts] == [1, 4]


# -- reassembly edges -----------------------------------------------------


def test_reassemble_ignores_packets_of_the_other_direction() -> None:
    packets = list(read_capture(fixture("normal.pcapng")))
    (session,) = build_sessions(packets)
    stream = reassemble(session, Direction.A_TO_B, packets)
    assert bytes(stream.bytes_) == b"HELLO"


def test_checksum_failure_is_a_diagnostic_when_requested(tmp_path: Path) -> None:
    eth = dpkt.ethernet.Ethernet(syn(seq=1000))
    eth.data.data.sum ^= 0xFFFF
    path = tmp_path / "bad.pcapng"
    path.write_bytes(_write_pcapng([bytes(eth), data_a(seq=1001, payload=b"HS")]))
    packets = list(read_capture(path, verify_checksums=True))
    (session,) = build_sessions(packets)
    stream = reassemble(session, Direction.A_TO_B, packets, ignore_checksums=False)
    assert any(d.type == "checksum_offload" for d in stream.diagnostics)


def test_direction_without_payload_yields_an_empty_stream() -> None:
    packets = list(read_capture(fixture("normal.pcapng")))
    (session,) = build_sessions(packets)
    transport = [p for p in packets if session.direction_of(p) is Direction.A_TO_B]
    stream = reassemble(session, Direction.B_TO_A, transport)
    assert bytes(stream.bytes_) == b""
    assert stream.length == 0
    assert stream.provenance.ranges == []


def test_every_observed_byte_has_a_provenance_range() -> None:
    capture = normalize(fixture("gap.pcapng"))
    stream = capture.streams[capture.sessions[0].session_id][Direction.A_TO_B]
    for offset in range(len(stream.bytes_)):
        assert stream.provenance.lookup(offset) is not None
