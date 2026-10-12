"""Tests for reading PCAP and PCAPNG files."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.capture.parser import Diagnostic, Packet, read_capture

from .conftest import fixture


def test_reads_pcapng_in_file_order(fixtures_dir: Path) -> None:
    packets = list(read_capture(fixture("normal.pcapng")))
    assert len(packets) == 7
    assert [p.index for p in packets] == list(range(7))
    assert isinstance(packets[0], Packet)
    assert packets[0].syn and not packets[0].ack_flag
    assert (packets[0].src_ip, packets[0].src_port) == ("10.0.0.1", 40000)
    assert (packets[0].dst_ip, packets[0].dst_port) == ("10.0.0.2", 9000)


def test_payload_and_sequence_numbers(fixtures_dir: Path) -> None:
    packets = list(read_capture(fixture("normal.pcapng")))
    hello = [p for p in packets if p.payload == b"HELLO"]
    assert len(hello) == 1
    assert hello[0].seq == 1001
    world = [p for p in packets if p.payload == b"WORLD"]
    assert len(world) == 1
    assert world[0].seq == 5001


def test_reads_classic_pcap(tmp_path: Path) -> None:
    import dpkt

    from scripts.generate_fixture import segment
    from src.capture.parser import TH_SYN

    frame = segment(
        src_ip="10.0.0.1",
        src_port=1,
        dst_ip="10.0.0.2",
        dst_port=2,
        seq=1,
        ack=0,
        flags=TH_SYN,
    )
    path = tmp_path / "one.pcap"
    with path.open("wb") as handle:
        writer = dpkt.pcap.Writer(handle)
        writer.writepkt(frame, ts=1700000000.0)
    packets = list(read_capture(path))
    assert len(packets) == 1
    assert packets[0].syn


def test_ipv6_packets_are_parsed(fixtures_dir: Path) -> None:
    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(fixture("ipv6_mixed.pcapng"), diagnostics))
    assert len(packets) == 6
    assert diagnostics == []
    assert (packets[0].src_ip, packets[0].dst_ip) == ("2001:db8::1", "2001:db8::2")
    assert packets[0].syn and not packets[0].ack_flag


def test_ipv6_session_endpoints_and_roles(fixtures_dir: Path) -> None:
    from src.capture.session import build_sessions

    packets = list(read_capture(fixture("ipv6_session.pcapng")))
    sessions = build_sessions(packets)
    assert len(sessions) == 1
    session = sessions[0]
    assert session.endpoints[0].ip == "2001:db8::1"
    assert session.endpoints[1].ip == "2001:db8::2"
    assert (session.role_a, session.role_b) == ("client", "server")
    assert session.syn_seen


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(read_capture(tmp_path / "absent.pcapng"))
