"""End-to-end pipeline: capture -> protocol -> result on the shared corpus.

The corpus is produced by the capture module and lives in ``tests/corpus/``.
Until Agent 1 publishes it, every test below is skipped with an explicit
reason; nothing here fabricates corpus data.

Run with the corpus present:

    python -m pytest tests/integration -v
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.protocol.engine import apply_rule
from src.protocol.result import build_result
from src.protocol.rule import load_rule
from src.protocol.stream import capture_from_dict, load_capture

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "tests" / "corpus"
CORPUS_PCAP = CORPUS_DIR / "corpus_capture_01.pcapng"
CORPUS_PCAP_2 = CORPUS_DIR / "corpus_capture_02.pcapng"
CORPUS_PCAP_DEFECTS = CORPUS_DIR / "corpus_capture_defects.pcapng"
CORPUS_JOURNAL = CORPUS_DIR / "corpus_journal.md"
CORPUS_RULE = REPO_ROOT / "examples" / "corpus_rule_v1.json"
CAPTURE_SCHEMA = REPO_ROOT / "docs" / "schemas" / "capture.schema.json"
RESULT_SCHEMA = REPO_ROOT / "docs" / "schemas" / "result.schema.json"

CORPUS_READY = (
    CORPUS_PCAP.is_file()
    and CORPUS_RULE.is_file()
    and (REPO_ROOT / "src" / "capture").is_dir()
    and importlib.util.find_spec("src.capture.pipeline") is not None
)

corpus_required = pytest.mark.skipif(
    not CORPUS_READY,
    reason="corpus not ready, waiting for Agent 1",
)


def _validate(schema_path: Path, payload: dict) -> None:
    if not schema_path.is_file():
        pytest.skip(f"schema not present: {schema_path}")
    import jsonschema

    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    jsonschema.Draft202012Validator(schema).validate(payload)


def _export_normalized(capture_path: Path, destination: Path) -> dict:
    from src.capture.export import export_capture
    from src.capture.pipeline import normalize

    capture = normalize(capture_path)
    export_capture(
        capture.sessions,
        destination,
        source_file=str(capture_path),
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    return json.loads(destination.read_text(encoding="utf-8"))


@corpus_required
def test_capture_to_result_pipeline(tmp_path):
    # 1. Read the corpus capture and export the normalized capture.
    normalized_path = tmp_path / "normalized.json"
    normalized = _export_normalized(CORPUS_PCAP, normalized_path)
    _validate(CAPTURE_SCHEMA, normalized)

    # 2. Load it into the protocol engine and apply the corpus rule.
    loaded = load_capture(str(normalized_path))
    rule = load_rule(str(CORPUS_RULE))
    messages = []
    for session_id, direction, stream in loaded.iter_streams():
        if not rule.applies_to(direction):
            continue
        messages.extend(apply_rule(stream, rule, session_id, direction))
    assert messages, "the corpus rule framed no messages"

    # 3. Build the contract result and validate it.
    result = build_result(rule, loaded.capture_hash, messages)
    payload = result.to_dict()
    _validate(RESULT_SCHEMA, payload)

    # 4. Rule v1 is deliberately too narrow: read requests match, write and
    #    measurement requests are counterexamples tied to their bytes.
    summary = payload["summary"]
    assert summary["matched"] > 0
    assert summary["mismatched"] > 0
    for message in payload["messages"]:
        if message["status"] == "mismatched":
            provenance = message.get("provenance_range")
            assert provenance is not None, "mismatched message without provenance"
            assert provenance.get("offset") is not None
            assert provenance.get("length")


@corpus_required
def test_framing_hypothesis_is_decided_by_the_bytes(tmp_path):
    from src.protocol.framing import FramingStrategy, frame_stream

    normalized = _export_normalized(CORPUS_PCAP, tmp_path / "n.json")
    capture = capture_from_dict(normalized)
    checked = 0
    clean = FramingStrategy.from_dict(
        {
            "type": "length_prefixed",
            "length_offset": 2,
            "length_size": 2,
            "byte_order": "big",
            "length_covers": "payload",
        }
    )
    for _session_id, _direction, stream in capture.iter_streams():
        if not stream.data:
            continue
        checked += 1
        for covers in ("payload_and_length_field", "entire_message"):
            strategy = FramingStrategy.from_dict(
                {
                    "type": "length_prefixed",
                    "length_offset": 2,
                    "length_size": 2,
                    "byte_order": "big",
                    "length_covers": covers,
                }
            )
            messages = frame_stream(stream.data, strategy)
            complete = all(m.complete for m in messages)
            assert not complete or sum(m.length for m in messages) != len(stream.data), (
                f"{covers} unexpectedly frames a corpus stream cleanly"
            )
        messages = frame_stream(stream.data, clean)
        assert all(m.complete for m in messages)
        assert sum(m.length for m in messages) == len(stream.data)
    assert checked, "no non-empty corpus stream was checked"


@corpus_required
def test_verify_corpus_finds_counterexamples(tmp_path):
    from src.hypothesis.corpus import CorpusStream, verify_on_corpus

    normalized = _export_normalized(CORPUS_PCAP, tmp_path / "n.json")
    capture = capture_from_dict(normalized)
    streams = [
        CorpusStream.from_bytes(stream.data, session_id, direction)
        for session_id, direction, stream in capture.iter_streams()
    ]
    rule = load_rule(str(CORPUS_RULE))
    report = verify_on_corpus(rule, streams)
    assert report.total > 0
    assert report.contradictions, "the narrow rule should have counterexamples"
    for counter in report.contradictions:
        assert counter.bytes_hex
        assert counter.message_offset is not None


@corpus_required
def test_journal_correlates_every_request(tmp_path):
    from src.hypothesis.journal import correlate, load_journal

    normalized = _export_normalized(CORPUS_PCAP, tmp_path / "n.json")
    capture = capture_from_dict(normalized)
    rule = load_rule(str(CORPUS_RULE))
    messages = []
    for session_id, direction, stream in capture.iter_streams():
        if not rule.applies_to(direction):
            continue
        messages.extend(apply_rule(stream, rule, session_id, direction))
    entries = load_journal(str(CORPUS_JOURNAL))
    report = correlate(messages, entries, window_ms=500)
    assert len(report.correlated) == len(messages)
    assert report.messages_without_entry == 0
    assert report.messages_without_timestamp == 0


@corpus_required
def test_second_capture_is_framed_with_the_same_rule(tmp_path):
    destination = tmp_path / "n2.json"
    _export_normalized(CORPUS_PCAP_2, destination)
    loaded = load_capture(str(destination))
    rule = load_rule(str(CORPUS_RULE))
    messages = []
    for session_id, direction, stream in loaded.iter_streams():
        if not rule.applies_to(direction):
            continue
        messages.extend(apply_rule(stream, rule, session_id, direction))
    assert messages
    assert all(m.length > 0 for m in messages)


@corpus_required
def test_defect_capture_reports_incomplete_instead_of_failing(tmp_path):
    from src.hypothesis.corpus import CorpusStream, verify_on_corpus

    if not CORPUS_PCAP_DEFECTS.is_file():
        pytest.skip("defect capture not present")
    normalized = _export_normalized(CORPUS_PCAP_DEFECTS, tmp_path / "nd.json")
    capture = capture_from_dict(normalized)
    streams = [
        CorpusStream.from_bytes(stream.data, session_id, direction)
        for session_id, direction, stream in capture.iter_streams()
    ]
    rule = load_rule(str(CORPUS_RULE))
    report = verify_on_corpus(rule, streams)
    # A damaged capture yields incomplete messages tied to bytes and a reason,
    # never a crash and never a silent zero-length message.
    assert any(m.status.value == "incomplete" for m in report.messages)
    for message in report.messages:
        if message.status.value == "incomplete":
            assert message.reason
            assert message.length > 0
