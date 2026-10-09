"""Robustness tests on captures damaged at the container or network layer.

Each test checks the same three things: reading does not raise, the damage is
reported as a diagnostic of the expected type, and the readable data is still
available after the damaged part.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.capture.parser import Diagnostic, read_capture
from src.capture.pipeline import normalize

from .conftest import defect


def _types(diagnostics: list[Diagnostic]) -> list[str]:
    return [d.type for d in diagnostics]


def test_truncated_header_is_reported_not_raised() -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(defect("truncated_header.pcapng"), diagnostics))
    assert packets == []
    assert _types(diagnostics) == ["truncated_frame"]
    # The file is damaged but recognized, so navigation does not raise either.
    capture = normalize(defect("truncated_header.pcapng"))
    assert capture.sessions == []


def test_truncated_packet_keeps_reading_the_rest() -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(defect("truncated_packet.pcapng"), diagnostics))
    assert len(packets) == 6
    assert sum(p.is_truncated for p in packets) == 1
    assert _types(diagnostics) == ["truncated_packet"]
    # The clean frames after the damaged one still form a session.
    capture = normalize(defect("truncated_packet.pcapng"))
    assert len(capture.sessions) == 1


def test_mixed_link_types_reports_the_supported_and_the_unsupported() -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(defect("mixed_link_types.pcapng"), diagnostics))
    assert len(packets) == 6
    assert "unsupported_linktype" in _types(diagnostics)
    assert "non_ip" in _types(diagnostics)
    capture = normalize(defect("mixed_link_types.pcapng"))
    assert len(capture.sessions) == 1


def test_unsupported_link_type_reports_and_stops_cleanly() -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(defect("unsupported_link_type.pcapng"), diagnostics))
    assert packets == []
    assert _types(diagnostics) == ["unsupported_linktype"]


def test_mixed_ip_versions_reports_ipv6_and_keeps_ipv4() -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(defect("mixed_ip_versions.pcapng"), diagnostics))
    assert len(packets) == 6
    assert _types(diagnostics) == ["ipv6_ignored"]
    capture = normalize(defect("mixed_ip_versions.pcapng"))
    assert len(capture.sessions) == 1


def test_fragments_are_reported_and_not_reassembled() -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(defect("fragmented_ip.pcap"), diagnostics))
    assert len(packets) == 6
    assert _types(diagnostics) == ["ip_fragment", "ip_fragment", "ip_fragment"]
    capture = normalize(defect("fragmented_ip.pcap"))
    assert len(capture.sessions) == 1


def test_a_file_that_is_not_a_capture_still_raises(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"this is not a capture file at all")
    with pytest.raises(ValueError):
        list(read_capture(path))


def test_streaming_reads_deformed_captures(tmp_path: Path) -> None:
    import json

    from src.capture.streaming import process_streaming

    for name in (
        "truncated_header.pcapng",
        "truncated_packet.pcapng",
        "mixed_link_types.pcapng",
        "fragmented_ip.pcap",
    ):
        out = tmp_path / f"{name}.json"
        process_streaming(defect(name), out)
        document = json.loads(out.read_text(encoding="utf-8"))
        assert "sessions" in document
