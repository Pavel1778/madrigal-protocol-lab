"""Tests for the reassembled pcap export."""

from __future__ import annotations

from pathlib import Path

import dpkt

from src.capture.export_wireshark import export_reassembled_pcap
from src.capture.pipeline import normalize
from src.capture.session import Direction

from .conftest import fixture


def _read(path: Path) -> list[tuple[float, bytes]]:
    with path.open("rb") as handle:
        return list(dpkt.pcap.Reader(handle))


def test_export_creates_a_readable_pcap(tmp_path: Path) -> None:
    capture = normalize(fixture("normal.pcapng"))
    out = tmp_path / "reassembled.pcap"
    written = export_reassembled_pcap(
        capture.sessions, out, streams=capture.streams
    )
    assert out.is_file()
    assert written == 2
    rows = _read(out)
    assert len(rows) == 2
    # The payloads are the reassembled streams, HELLO one way and WORLD the other.
    payloads = sorted(row[1][-5:] for row in rows)
    assert payloads == [b"HELLO", b"WORLD"]


def test_export_writes_one_packet_per_session(tmp_path: Path) -> None:
    capture = normalize(fixture("port_reuse.pcapng"))
    out = tmp_path / "reassembled.pcap"
    written = export_reassembled_pcap(
        capture.sessions, out, streams=capture.streams
    )
    # Two sessions, one direction each.
    assert len(capture.sessions) == 2
    assert written == 2
    assert len(_read(out)) == 2


def test_exported_stream_bytes_match_reassembly(tmp_path: Path) -> None:
    capture = normalize(fixture("message_split_across_packets.pcapng"))
    out = tmp_path / "reassembled.pcap"
    export_reassembled_pcap(capture.sessions, out, streams=capture.streams)
    rows = _read(out)
    expected = bytes(
        capture.streams[capture.sessions[0].session_id][Direction.A_TO_B].bytes_
    )
    assert rows[0][1][-len(expected) :] == expected


def test_export_reassembles_when_streams_absent(tmp_path: Path) -> None:
    source = fixture("normal.pcapng")
    capture = normalize(source)
    from src.capture.parser import read_capture

    packets = list(read_capture(source))
    out = tmp_path / "reassembled.pcap"
    written = export_reassembled_pcap(capture.sessions, out, packets=packets)
    assert written == 2
    assert len(_read(out)) == 2
