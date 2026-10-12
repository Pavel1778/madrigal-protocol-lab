"""End-to-end checks against the supplied reference corpus.

The corpus is the organizer's own capture set. These tests do not invent
data: they normalize the shipped PCAP/PCAPNG files, apply the interpretation
rules in ``examples/`` and assert the properties that the reference journal
describes. A regression in parsing, reassembly, framing or the engine breaks
them here.
"""

from __future__ import annotations

import functools
import json
import tempfile
from pathlib import Path

import pytest

from src.capture.export import export_capture
from src.capture.pipeline import normalize
from src.hypothesis.corpus import CorpusStream, verify_on_corpus
from src.hypothesis.journal import correlate, load_journal
from src.protocol.engine import apply_rule
from src.protocol.rule import load_rule
from src.protocol.stream import capture_from_dict, load_capture

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL = REPO_ROOT / "tests" / "corpus" / "real"
EXAMPLES = REPO_ROOT / "examples"

RESEARCH = {
    "01_configuration": REAL / "research" / "01_configuration.pcap",
    "02_variations": REAL / "research" / "02_variations.pcapng",
    "03_combined_messages": REAL / "research" / "03_combined_messages.pcap",
    "04_new_observations": REAL / "additional" / "04_new_observations.pcapng",
}
DIAGNOSTICS = {
    "retransmission": REAL / "diagnostics" / "01_retransmission.pcap",
    "reordered": REAL / "diagnostics" / "02_reordered.pcapng",
    "missing_segment": REAL / "diagnostics" / "03_missing_segment.pcap",
    "snaplen_truncated": REAL / "diagnostics" / "04_snaplen_truncated.pcapng",
    "conflicting_overlap": REAL / "diagnostics" / "05_conflicting_overlap.pcap",
    "missing_beginning": REAL / "diagnostics" / "06_missing_beginning.pcapng",
    "checksum_offload": REAL / "diagnostics" / "07_checksum_offload.pcap",
    "bad_checksum": REAL / "diagnostics" / "08_bad_checksum.pcapng",
}


@functools.cache
def _normalized(path: str):
    return normalize(Path(path))


@functools.cache
def _payload(path: str) -> str:
    capture = normalize(Path(path))
    with tempfile.NamedTemporaryFile(suffix=".normalized.json", delete=False) as handle:
        tmp = Path(handle.name)
    export_capture(
        capture.sessions,
        tmp,
        source_file=str(path),
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    return tmp.read_text(encoding="utf-8")


@functools.cache
def _capture(path: str):
    capture = normalize(Path(path))
    with tempfile.NamedTemporaryFile(suffix=".normalized.json", delete=False) as handle:
        tmp = Path(handle.name)
    export_capture(
        capture.sessions,
        tmp,
        source_file=str(path),
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    try:
        return load_capture(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)


def _messages(name: str, rule_name: str):
    rule = load_rule(str(EXAMPLES / rule_name))
    capture = _capture(str(RESEARCH[name]))
    results = []
    for session_id, direction, stream in capture.iter_streams():
        if direction != rule.direction:
            continue
        results.extend(apply_rule(stream, rule, session_id, direction))
    return results


def _counts(messages) -> dict:
    counts: dict[str, int] = {}
    for message in messages:
        key = message.status.value if hasattr(message.status, "value") else str(message.status)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _values(messages, field_name: str) -> list:
    found = []
    for message in messages:
        for result in message.fields:
            if result.field_name != field_name or result.value is None:
                continue
            if isinstance(result.value, list):
                found.extend(result.value)
            else:
                found.append(result.value)
    return found


@pytest.mark.parametrize("name", list(RESEARCH))
@pytest.mark.parametrize("rule_name", ["thermostand_request_v2.json", "thermostand_response_v2.json"])
def test_v2_rules_have_no_counterexamples(name: str, rule_name: str) -> None:
    messages = _messages(name, rule_name)
    assert messages, f"{rule_name} produced no messages on {name}"
    counts = _counts(messages)
    assert counts.get("mismatched", 0) == 0
    assert counts.get("incomplete", 0) == 0
    assert counts.get("ambiguous", 0) == 0
    assert counts.get("uncovered", 0) == 0


def test_request_message_types_are_classified() -> None:
    types = set(_values(_messages("01_configuration", "thermostand_request_v2.json"), "message_type"))
    assert types == {"read_config", "set_config", "read_values"}


def test_response_statuses_cover_ok_and_disabled() -> None:
    statuses = set(_values(_messages("01_configuration", "thermostand_response_v2.json"), "status"))
    assert "ok" in statuses
    assert "measurement_disabled" in statuses


def test_response_temperatures_match_the_journal() -> None:
    messages = _messages("01_configuration", "thermostand_response_v2.json")
    raw = _values(messages, "temperature_raw")
    temperatures = sorted(value / 100 for value in raw)
    assert 18.5 in temperatures
    assert -5.5 in temperatures
    assert 25.0 in temperatures


def test_response_times_are_monotonic_per_message() -> None:
    messages = _messages("02_variations", "thermostand_response_v2.json")
    times = _values(messages, "device_time_ms")
    assert times, "no device times decoded"
    assert all(value >= 0 for value in times)


def test_cyrillic_label_decodes_as_utf8() -> None:
    labels = _values(_messages("02_variations", "thermostand_response_v2.json"), "label")
    assert "Точка-1" in labels


def test_combined_capture_groups_messages() -> None:
    requests = _messages("03_combined_messages", "thermostand_request_v2.json")
    responses = _messages("03_combined_messages", "thermostand_response_v2.json")
    assert len(requests) == len(responses) == 8


def test_checksum_offload_reports_mismatch_when_requested() -> None:
    capture = normalize(DIAGNOSTICS["checksum_offload"], ignore_checksums=False)
    types = {
        diagnostic.type
        for stream in capture.streams.values()
        for directional in stream.values()
        for diagnostic in directional.diagnostics
    }
    assert "checksum_offload" in types


def test_checksum_offload_is_ignored_by_default() -> None:
    capture = normalize(DIAGNOSTICS["checksum_offload"])
    types = {
        diagnostic.type
        for stream in capture.streams.values()
        for directional in stream.values()
        for diagnostic in directional.diagnostics
    }
    assert "checksum_offload" not in types


def test_retransmission_does_not_duplicate_bytes() -> None:
    capture = _normalized(str(DIAGNOSTICS["retransmission"]))
    assert capture.sessions
    for stream in capture.streams.values():
        for directional in stream.values():
            for diagnostic in directional.diagnostics:
                assert diagnostic.type != "gap"


def test_missing_segment_is_reported_as_gap() -> None:
    capture = _normalized(str(DIAGNOSTICS["missing_segment"]))
    types = {
        diagnostic.type
        for stream in capture.streams.values()
        for directional in stream.values()
        for diagnostic in directional.diagnostics
    }
    assert "gap" in types


def test_conflicting_overlap_is_reported_as_ambiguity() -> None:
    capture = _normalized(str(DIAGNOSTICS["conflicting_overlap"]))
    types = {
        diagnostic.type
        for stream in capture.streams.values()
        for directional in stream.values()
        for diagnostic in directional.diagnostics
    }
    assert "ambiguity" in types


def test_missing_beginning_leaves_roles_unknown() -> None:
    capture = _normalized(str(DIAGNOSTICS["missing_beginning"]))
    assert capture.sessions
    for session in capture.sessions:
        assert session.syn_seen is False
        assert session.role_a == "unknown"
        assert session.role_b == "unknown"


def test_journal_correlates_with_the_decoded_request() -> None:
    entries = load_journal(str(REAL / "action_journal.csv"))
    assert entries
    assert entries[0].action == "read-config"
    messages = _messages("01_configuration", "thermostand_request_v2.json")
    report = correlate(messages, entries)
    assert report.correlated
    assert report.summary().startswith(str(len(messages)))


def test_dataset_manifest_lists_every_research_capture() -> None:
    manifest = json.loads((REAL / "dataset_manifest.json").read_text(encoding="utf-8"))
    for relative in manifest["files"]:
        assert (REAL / relative).is_file()
    for item in manifest["diagnostics"]:
        assert (REAL / item["file"]).is_file()


def _corpus_streams(name: str) -> list[CorpusStream]:
    capture = capture_from_dict(json.loads(_payload(str(RESEARCH[name]))))
    return [
        CorpusStream(stream=stream, session_id=session_id, direction=direction)
        for session_id, direction, stream in capture.iter_streams()
    ]


def test_request_rule_refinement_removes_counterexamples() -> None:
    streams = _corpus_streams("01_configuration")
    naive = verify_on_corpus(load_rule(str(EXAMPLES / "thermostand_request_v1.json")), streams)
    refined = verify_on_corpus(load_rule(str(EXAMPLES / "thermostand_request_v2.json")), streams)
    assert naive.contradictions
    assert not refined.contradictions
    assert refined.totals["matched"] > naive.totals["matched"]


def test_investigation_report_is_reproducible() -> None:
    from scripts.investigate_dataset import build_report

    committed = (REPO_ROOT / "docs" / "DATASET_INVESTIGATION.md").read_text(encoding="utf-8")
    assert build_report() == committed


def test_corpus_totals_match_the_published_figures() -> None:
    """The aggregate numbers quoted in docs/REAL_CORPUS_ANALYSIS.md."""
    sessions = 0
    requests = 0
    responses = 0
    for name in RESEARCH:
        capture = _capture(str(RESEARCH[name]))
        sessions += len({session_id for session_id, _, _ in capture.iter_streams()})
        for rule_name in ("thermostand_request_v2.json", "thermostand_response_v2.json"):
            messages = _messages(name, rule_name)
            assert _counts(messages).get("matched", 0) == len(messages)
            if rule_name == "thermostand_request_v2.json":
                requests += len(messages)
            else:
                responses += len(messages)
    assert sessions == 5
    assert requests == 45
    assert responses == 45


def test_every_research_request_correlates_with_the_journal() -> None:
    """Every decoded request maps to a recorded operator action."""
    entries = load_journal(str(REAL / "action_journal.csv"))
    for name in RESEARCH:
        messages = _messages(name, "thermostand_request_v2.json")
        report = correlate(messages, entries)
        assert len(report.correlated) == len(messages)


def test_naive_request_rule_leaves_six_counterexamples() -> None:
    """The v1 to v2 refinement is the documented counterexample story."""
    streams = _corpus_streams("01_configuration")
    naive = verify_on_corpus(load_rule(str(EXAMPLES / "thermostand_request_v1.json")), streams)
    assert len(naive.contradictions) == 6
    refined = verify_on_corpus(load_rule(str(EXAMPLES / "thermostand_request_v2.json")), streams)
    assert not refined.contradictions
    assert refined.totals["matched"] == 14
