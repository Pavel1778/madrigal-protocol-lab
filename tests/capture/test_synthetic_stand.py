"""Tests for the synthetic stand."""

from __future__ import annotations

from pathlib import Path

from scripts.run_synthetic_stand import (
    CMD_MEASURE,
    CMD_READ,
    CMD_SET,
    encode_request,
    encode_response,
    handle_request,
    parse_request,
    render_journal,
    run_stand,
)
from src.capture.parser import read_capture
from src.capture.pipeline import normalize
from src.capture.session import Direction


def test_request_uses_little_endian_length_and_txid() -> None:
    frame = encode_request(CMD_READ, 0x0A, b"\x31")
    # command, txid, len_lo, len_hi, payload
    assert frame == bytes([0x21, 0x0A, 0x01, 0x00, 0x31])
    request = parse_request(frame)
    assert request.command == CMD_READ
    assert request.txid == 0x0A
    assert request.payload == b"\x31"


def test_response_sets_high_bit() -> None:
    frame = encode_response(CMD_SET, 0x03, b"\x32\x64\x00")
    assert frame[0] == (CMD_SET | 0x80)
    assert frame[1] == 0x03
    assert int.from_bytes(frame[2:4], "little") == 3


def test_handle_request_is_deterministic() -> None:
    request = parse_request(encode_request(CMD_READ, 1, b"\x31"))
    first = handle_request(request)
    second = handle_request(request)
    assert first == second
    assert first[0] == 0x31


def test_measure_response_length_varies_with_sensor() -> None:
    short = handle_request(parse_request(encode_request(CMD_MEASURE, 1, b"\x40")))
    long = handle_request(parse_request(encode_request(CMD_MEASURE, 1, b"\x43")))
    assert short[1] != long[1]
    assert len(short) == 2 + 2 * short[1]
    assert len(long) == 2 + 2 * long[1]


def test_render_journal_shape() -> None:
    from scripts.run_synthetic_stand import JournalEntry

    text = render_journal([JournalEntry(1.5, "read", "flow_rate", "1824")])
    assert "1.500 | read | flow_rate | 1824" in text


def test_stand_records_a_verifiable_session(tmp_path: Path) -> None:
    capture, journal, _info = run_stand()
    path = tmp_path / "live.pcapng"
    path.write_bytes(capture)

    packets = list(read_capture(path))
    assert packets

    normalized = normalize(path)
    assert len(normalized.sessions) == 1
    session = normalized.sessions[0]
    assert session.syn_seen and session.fin_seen
    assert session.role_a == "client" and session.role_b == "server"

    a_to_b = normalized.streams[session.session_id][Direction.A_TO_B]
    b_to_a = normalized.streams[session.session_id][Direction.B_TO_A]
    assert a_to_b.gaps() == [] and b_to_a.gaps() == []
    assert not a_to_b.ambiguities() and not b_to_a.ambiguities()

    # The scenario issues 3 reads, 3 sets, and 5 measurements.
    assert len(journal) == 11
    assert [entry.action for entry in journal].count("read") == 3
    assert [entry.action for entry in journal].count("set") == 3
    assert [entry.action for entry in journal].count("measure") == 5

    # Journal timestamps must be real packet times in the capture. The pcapng
    # writer stores whole microseconds, so a recorded time can round across a
    # millisecond boundary; compare within one microsecond rather than by an
    # exact three-decimal rounding, which is not stable at that boundary.
    for entry in journal:
        assert any(
            abs(entry.timestamp - packet.timestamp) <= 1e-6 for packet in packets
        )


def test_generate_writes_and_verifies(tmp_path: Path) -> None:
    from scripts.run_synthetic_stand import generate

    sizes = generate(tmp_path)
    assert sizes["synthetic_live.pcapng"] < 2 * 1024 * 1024
    assert (tmp_path / "synthetic_live_journal.md").is_file()
    assert (tmp_path / "synthetic_live_README.md").is_file()
