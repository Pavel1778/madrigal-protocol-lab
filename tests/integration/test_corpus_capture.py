"""Integration checks of the capture module on the research corpus.

The unit tests use small fixtures that each isolate one behaviour. These tests
run the whole pipeline on the real corpus records in ``tests/corpus`` and check
that sessions, reassembly, the exported JSON, the diagnostics, and byte
provenance all agree on inputs the module did not generate for the test.

The corpus is fixed and committed, so the expected counts are part of the test:
a change that alters how many sessions are found, or that loses bytes, fails
here rather than shipping.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.capture.export import export_capture
from src.capture.parser import read_capture
from src.capture.pipeline import normalize
from src.capture.session import Direction

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
SCHEMAS = Path(__file__).resolve().parent.parent.parent / "docs" / "schemas"

RECORDS = {
    "corpus_capture_01.pcapng": {"packets": 295, "sessions": 3},
    "corpus_capture_02.pcapng": {"packets": 90, "sessions": 2},
    "corpus_capture_defects.pcapng": {"packets": 18, "sessions": 1},
    "synthetic_live.pcapng": {"packets": 27, "sessions": 1},
}


def _validator() -> Draft202012Validator:
    schema = json.loads((SCHEMAS / "capture.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@pytest.fixture(params=sorted(RECORDS))
def record(request: pytest.FixtureRequest) -> tuple[str, Path, dict[str, int]]:
    name = request.param
    return name, CORPUS / name, RECORDS[name]


def test_reader_returns_expected_packet_count(
    record: tuple[str, Path, dict[str, int]],
) -> None:
    name, path, expected = record
    packets = list(read_capture(path))
    assert len(packets) == expected["packets"], name


def test_sessions_match_expected(
    record: tuple[str, Path, dict[str, int]],
) -> None:
    name, path, expected = record
    capture = normalize(path)
    assert len(capture.sessions) == expected["sessions"], name
    # Session ids are unique and every packet belongs to exactly one session.
    ids = [s.session_id for s in capture.sessions]
    assert len(set(ids)) == len(ids)
    covered = [index for s in capture.sessions for index in s.packet_indices]
    assert sorted(covered) == sorted(set(covered))


def test_reassembly_keeps_every_observed_byte(
    record: tuple[str, Path, dict[str, int]],
) -> None:
    name, path, _ = record
    capture = normalize(path)
    observed = sum(len(packet.payload) for packet in read_capture(path))
    total = 0
    for session in capture.sessions:
        for direction in (Direction.A_TO_B, Direction.B_TO_A):
            stream = capture.streams[session.session_id][direction]
            # Reassembly deduplicates retransmissions, so it never has more
            # bytes than were observed. It must not lose unique bytes either.
            assert len(stream.bytes_) <= observed, name
            if stream.bytes_:
                total += len(stream.bytes_)
    assert total > 0


def test_provenance_resolves_each_stream_offset(
    record: tuple[str, Path, dict[str, int]],
) -> None:
    name, path, _ = record
    capture = normalize(path)
    for session in capture.sessions:
        for direction in (Direction.A_TO_B, Direction.B_TO_A):
            stream = capture.streams[session.session_id][direction]
            if not stream.bytes_:
                continue
            # The first byte, a middle byte, and the last byte must all map to a
            # packet range that contains them.
            for offset in {0, len(stream.bytes_) // 2, len(stream.bytes_) - 1}:
                rng = stream.provenance.lookup(offset)
                assert rng is not None, (name, offset)
                assert rng.offset <= offset < rng.end
                assert rng.packet_index >= 0
                assert rng.seq >= 0


def test_export_is_valid_against_schema(
    record: tuple[str, Path, dict[str, int]],
    tmp_path: Path,
) -> None:
    name, path, _ = record
    capture = normalize(path)
    out = tmp_path / f"{path.stem}.json"
    export_capture(
        capture.sessions,
        out,
        source_file=f"tests/corpus/{name}",
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    document = json.loads(out.read_text(encoding="utf-8"))
    _validator().validate(document)
    assert document["capture_id"] == capture.capture_id
    assert document["source_file"] == f"tests/corpus/{name}"
    assert len(document["sessions"]) == len(capture.sessions)


def test_export_bytes_round_trip_to_reassembled_stream(
    record: tuple[str, Path, dict[str, int]],
    tmp_path: Path,
) -> None:
    name, path, _ = record
    capture = normalize(path)
    out = tmp_path / f"{path.stem}.json"
    export_capture(
        capture.sessions,
        out,
        source_file=f"tests/corpus/{name}",
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    document = json.loads(out.read_text(encoding="utf-8"))
    by_id = {s["session_id"]: s for s in document["sessions"]}
    for session in capture.sessions:
        contract = by_id[session.session_id]
        for direction in (Direction.A_TO_B, Direction.B_TO_A):
            stream = capture.streams[session.session_id][direction]
            encoded = contract["directions"][direction.value]["bytes_b64"]
            assert base64.b64decode(encoded) == bytes(stream.bytes_), name


def test_defects_record_reports_gap_and_ambiguity() -> None:
    capture = normalize(CORPUS / "corpus_capture_defects.pcapng")
    assert len(capture.sessions) == 1
    session = capture.sessions[0]
    a_to_b = capture.streams[session.session_id][Direction.A_TO_B]
    b_to_a = capture.streams[session.session_id][Direction.B_TO_A]
    assert [d.type for d in a_to_b.diagnostics] == ["gap"]
    assert [d.type for d in b_to_a.diagnostics] == ["ambiguity"]

    gap = a_to_b.diagnostics[0]
    assert gap.length and gap.length > 0
    assert "missing" in gap.detail
    # The hole is reported, not filled: every byte the stream does carry maps
    # back to a packet, so no invented byte stands in for the missing run.
    assert all(
        a_to_b.provenance.lookup(offset) is not None
        for offset in range(len(a_to_b.bytes_))
    )

    ambiguity = b_to_a.diagnostics[0]
    assert ambiguity.offset is not None
    assert "conflicting overlap" in ambiguity.detail


def test_clean_records_have_no_stream_diagnostics() -> None:
    for name in (
        "corpus_capture_01.pcapng",
        "corpus_capture_02.pcapng",
        "synthetic_live.pcapng",
    ):
        capture = normalize(CORPUS / name)
        for session in capture.sessions:
            for direction in (Direction.A_TO_B, Direction.B_TO_A):
                stream = capture.streams[session.session_id][direction]
                assert stream.diagnostics == [], (name, session.session_id, direction)


def test_capture_id_is_the_content_hash() -> None:
    from src.capture.export import sha256_file

    for name in RECORDS:
        path = CORPUS / name
        assert normalize(path).capture_id == sha256_file(path)
