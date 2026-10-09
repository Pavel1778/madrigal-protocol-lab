"""Tests for TCP session identification."""

from __future__ import annotations

from pathlib import Path

from src.capture.parser import read_capture
from src.capture.session import Direction, Endpoint, build_sessions

from .conftest import fixture


def test_single_session_with_known_roles(fixtures_dir: Path) -> None:
    packets = list(read_capture(fixture("normal.pcapng")))
    sessions = build_sessions(packets)
    assert len(sessions) == 1
    session = sessions[0]
    assert session.syn_seen and session.fin_seen and not session.rst_seen
    assert session.role_a == "client" and session.role_b == "server"
    assert session.endpoints[0] == Endpoint("10.0.0.1", 40000)
    assert session.endpoints[1] == Endpoint("10.0.0.2", 9000)
    assert session.isn_a == 1000 and session.isn_b == 5000
    assert session.packet_indices == list(range(7))


def test_missing_syn_leaves_roles_unknown(fixtures_dir: Path) -> None:
    packets = list(read_capture(fixture("no_syn.pcapng")))
    sessions = build_sessions(packets)
    assert len(sessions) == 1
    assert sessions[0].role_a == "unknown"
    assert sessions[0].role_b == "unknown"
    assert sessions[0].isn_a is None and sessions[0].isn_b is None


def test_port_reuse_makes_two_sessions(fixtures_dir: Path) -> None:
    packets = list(read_capture(fixture("port_reuse.pcapng")))
    sessions = build_sessions(packets)
    assert [s.session_id for s in sessions] == ["s1", "s2"]
    assert sessions[0].isn_a == 1000
    assert sessions[1].isn_a == 90000
    assert len(sessions[0].packet_indices) + len(sessions[1].packet_indices) == len(
        packets
    )
    assert not set(sessions[0].packet_indices) & set(sessions[1].packet_indices)


def test_direction_is_derived_from_endpoints(fixtures_dir: Path) -> None:
    packets = list(read_capture(fixture("normal.pcapng")))
    session = build_sessions(packets)[0]
    from_a = [p for p in packets if session.direction_of(p) is Direction.A_TO_B]
    assert all(p.src_ip == "10.0.0.1" for p in from_a)
    assert Direction.A_TO_B.opposite is Direction.B_TO_A
