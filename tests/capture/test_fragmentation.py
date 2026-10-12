"""Reassembly of IPv4 and IPv6 fragments.

Each test drives a generated capture through the parser and the pipeline and
checks that a datagram split by the network is put back together, that a stay
incomplete is reported rather than guessed, and that both IP versions behave as
their specifications require.
"""

from __future__ import annotations

from src.capture.fragment import (
    FRAGMENT_INCOMPLETE,
    FRAGMENT_OVERLAP,
    FRAGMENT_REASSEMBLED,
    FragmentReassembler,
    build_ip_datagram,
    extract_fragment,
)
from src.capture.parser import Diagnostic, read_capture
from src.capture.pipeline import normalize

from .conftest import defect


def _types(diagnostics: list[Diagnostic]) -> list[str]:
    return [d.type for d in diagnostics]


def _payloads(name: str) -> list[bytes]:
    """Every non-empty directional stream payload of a capture."""

    capture = normalize(defect(name))
    return [
        bytes(stream.bytes_)
        for session in capture.sessions
        for stream in capture.streams[session.session_id].values()
        if stream.length
    ]


def test_ipv4_datagram_split_into_fragments_is_reassembled() -> None:
    diagnostics: list[Diagnostic] = []
    list(read_capture(defect("fragment_reassembled.pcapng"), diagnostics))
    assert FRAGMENT_REASSEMBLED in _types(diagnostics)
    capture = normalize(defect("fragment_reassembled.pcapng"))
    # The fragmented session and the ordinary exchange in the same file.
    assert len(capture.sessions) == 2
    assert any(b"ALFAALFAALFAALFAALFAALFA" in p for p in _payloads("fragment_reassembled.pcapng"))


def test_reassembly_does_not_depend_on_fragment_arrival_order() -> None:
    # The generator writes the middle fragment, then the tail, then the head.
    # The payload can only be right if the byte offset drives the order.
    payloads = _payloads("fragment_reassembled.pcapng")
    alpha = next(p for p in payloads if b"ALFA" in p)
    assert alpha == b"ALFA" * 6


def test_ipv6_datagram_split_into_fragments_is_reassembled() -> None:
    diagnostics: list[Diagnostic] = []
    list(read_capture(defect("fragment_ipv6_reassembled.pcapng"), diagnostics))
    assert FRAGMENT_REASSEMBLED in _types(diagnostics)
    assert any(b"BRAVBRAVBRAVBRAVBRAVBRAV" in p for p in _payloads("fragment_ipv6_reassembled.pcapng"))


def test_duplicate_fragment_does_not_change_the_reassembled_bytes() -> None:
    payloads = _payloads("fragment_duplicate.pcapng")
    assert any(b"DELTDELTDELTDELTDELTDELT" in p for p in payloads)


def test_ipv4_overlap_keeps_the_first_arrival_and_reports_it() -> None:
    diagnostics: list[Diagnostic] = []
    list(read_capture(defect("fragment_overlap_ipv4.pcapng"), diagnostics))
    overlap = [d for d in diagnostics if d.type == FRAGMENT_OVERLAP]
    assert len(overlap) == 1
    # The datagram still completes, so its bytes remain available.
    assert any(b"ECHO" in p for p in _payloads("fragment_overlap_ipv4.pcapng"))


def test_ipv6_overlap_discards_the_datagram() -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(defect("fragment_overlap_ipv6.pcapng"), diagnostics))
    assert FRAGMENT_OVERLAP in _types(diagnostics)
    # RFC 5722: the whole datagram is dropped, so no session carries it.
    assert not any(b"FOXT" in p for p in _payloads("fragment_overlap_ipv6.pcapng"))
    assert len(packets) == 6


def test_missing_fragment_is_incomplete_not_guessed() -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(defect("fragment_incomplete_missing.pcapng"), diagnostics))
    incomplete = [d for d in diagnostics if d.type == FRAGMENT_INCOMPLETE]
    assert len(incomplete) == 1
    assert incomplete[0].offset == 16
    assert incomplete[0].length == 16
    assert len(packets) == 6
    assert not any(b"GOLF" in p for p in _payloads("fragment_incomplete_missing.pcapng"))


def test_misaligned_non_final_fragment_is_not_reassembled() -> None:
    diagnostics: list[Diagnostic] = []
    list(read_capture(defect("fragment_misaligned.pcapng"), diagnostics))
    assert FRAGMENT_INCOMPLETE in _types(diagnostics)
    assert not any(b"HOTE" in p for p in _payloads("fragment_misaligned.pcapng"))


def test_a_whole_datagram_is_not_reported_as_a_fragment() -> None:
    """An ordinary capture yields no fragment diagnostic at all."""

    diagnostics: list[Diagnostic] = []
    list(read_capture(defect("truncated_packet.pcapng"), diagnostics))
    assert not {FRAGMENT_REASSEMBLED, FRAGMENT_INCOMPLETE, FRAGMENT_OVERLAP} & set(
        _types(diagnostics)
    )


def test_extract_fragment_returns_none_for_a_whole_datagram() -> None:
    # A datagram with offset zero and the more-fragments flag clear is whole and
    # must not be treated as a fragment.
    assert extract_fragment(4, _fragment_frame(b"DATA", 0, False), 1, 0.0) is None


def test_build_ip_datagram_round_trips_through_the_parser() -> None:
    """The synthetic header preserves the addresses and protocol."""

    from src.capture.fragment import ReassembledDatagram

    datagram = ReassembledDatagram(
        version=4,
        src="192.0.2.1",
        dst="192.0.2.2",
        protocol=6,
        payload=b"\x00" * 20 + b"DATA",
        packet_indices=[1],
        timestamp=0.0,
    )
    raw = build_ip_datagram(datagram)
    assert raw[0] >> 4 == 4
    assert raw[9] == 6
    spec = extract_fragment(4, raw, 1, 0.0)
    assert spec is None


def test_fragment_reassembler_reports_incomplete_on_finish() -> None:
    reassembler = FragmentReassembler()
    # A lone middle fragment of a datagram that never closes.
    segment = b"\x00" * 32
    spec = extract_fragment(4, _fragment_frame(segment[:16], 16, True), 1, 0.0)
    assert spec is not None
    assert reassembler.add(spec) is None
    report = reassembler.finish()
    assert report[0][0] == FRAGMENT_INCOMPLETE


def _fragment_frame(chunk: bytes, offset: int, more: bool) -> bytes:
    """A raw IPv4 datagram carrying one fragment, without any link header."""

    import socket
    import struct

    header = bytearray(20)
    header[0] = 0x45
    struct.pack_into("!H", header, 2, 20 + len(chunk))
    struct.pack_into("!H", header, 4, 0x0102)
    flags_frag = ((0x2000 if more else 0) | (offset // 8)) & 0xFFFF
    struct.pack_into("!H", header, 6, flags_frag)
    header[8] = 64
    header[9] = 6
    header[12:16] = socket.inet_aton("10.0.0.1")
    header[16:20] = socket.inet_aton("10.0.0.2")
    return bytes(header) + chunk
