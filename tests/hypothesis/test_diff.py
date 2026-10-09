"""Rule and report diffs across rule versions."""

from __future__ import annotations

from src.hypothesis.corpus import CorpusStream
from src.hypothesis.diff import diff_reports, diff_rules, format_report_diff, format_rule_diff
from src.hypothesis.corpus import verify_on_corpus
from src.protocol.rule import parse_rule
from src.protocol.stream import DirectionalStream


def _rule(fields, version=1, framing=None, scope=None):
    return parse_rule(
        {
            "rule_id": "r",
            "rule_version": version,
            "scope": scope or {"direction": "A_to_B"},
            "framing": framing or {"type": "fixed_size", "size": 4},
            "fields": fields,
        }
    )


BASE_FIELDS = [
    {"name": "command", "offset": 0, "type": "uint8", "expected": [4]},
    {"name": "value", "offset": 1, "type": "uint16", "byte_order": "big"},
]


def test_diff_detects_added_field():
    a = _rule(BASE_FIELDS)
    b = _rule(BASE_FIELDS + [{"name": "flags", "offset": 3, "type": "uint8"}], framing={"type": "fixed_size", "size": 4})
    diff = diff_rules(a, b)
    assert diff.added_fields == ["flags"]
    assert not diff.removed_fields
    assert "flags" in format_rule_diff(diff)


def test_diff_detects_removed_field():
    a = _rule(BASE_FIELDS)
    b = _rule([BASE_FIELDS[0]])
    diff = diff_rules(a, b)
    assert diff.removed_fields == ["value"]
    assert not diff.added_fields


def test_diff_detects_changed_offset():
    a = _rule(BASE_FIELDS)
    b = _rule([BASE_FIELDS[0], {"name": "value", "offset": 2, "type": "uint16", "byte_order": "big"}])
    diff = diff_rules(a, b)
    paths = {(c.field_name, c.path) for c in diff.changed_fields}
    assert ("value", "offset") in paths
    change = next(c for c in diff.changed_fields if c.field_name == "value" and c.path == "offset")
    assert change.old == 1
    assert change.new == 2


def test_diff_detects_changed_type():
    a = _rule(BASE_FIELDS)
    b = _rule([BASE_FIELDS[0], {"name": "value", "offset": 1, "type": "uint32"}])
    diff = diff_rules(a, b)
    change = next(c for c in diff.changed_fields if c.field_name == "value" and c.path == "type")
    assert (change.old, change.new) == ("uint16", "uint32")


def test_diff_detects_changed_framing_and_scope():
    a = _rule(BASE_FIELDS)
    b = _rule(
        BASE_FIELDS,
        framing={"type": "length_prefixed", "length_offset": 2, "length_size": 2, "length_covers": "payload"},
        scope={"direction": "B_to_A"},
    )
    diff = diff_rules(a, b)
    framing_patterns = {c.path for c in diff.changed_framing}
    assert "type" in framing_patterns
    assert {c.path for c in diff.scope_changes} == {"direction"}


def test_diff_reports_resolves_counterexample():
    stream = DirectionalStream.from_bytes(b"\x09\x00\x01\x00")
    a = _rule(BASE_FIELDS)
    b = _rule([{"name": "command", "offset": 0, "type": "uint8", "expected": [4, 9]}, BASE_FIELDS[1]])
    report_a = verify_on_corpus(a, [CorpusStream.from_bytes(stream.data, "s1", "A_to_B")])
    report_b = verify_on_corpus(b, [CorpusStream.from_bytes(stream.data, "s1", "A_to_B")])
    diff = diff_reports(report_a, report_b)
    assert len(diff.resolved_counterexamples) == 1
    assert not diff.introduced_counterexamples
    assert diff.matched_delta == 1


def test_diff_reports_introduces_counterexample():
    stream = DirectionalStream.from_bytes(b"\x09\x00\x01\x00")
    a = _rule([{"name": "command", "offset": 0, "type": "uint8", "expected": [4, 9]}, BASE_FIELDS[1]])
    b = _rule(BASE_FIELDS)
    report_a = verify_on_corpus(a, [CorpusStream.from_bytes(stream.data, "s1", "A_to_B")])
    report_b = verify_on_corpus(b, [CorpusStream.from_bytes(stream.data, "s1", "A_to_B")])
    diff = diff_reports(report_a, report_b)
    assert len(diff.introduced_counterexamples) == 1
    assert not diff.resolved_counterexamples
    assert diff.matched_delta == -1


def test_diff_reports_no_change():
    stream = DirectionalStream.from_bytes(b"\x04\x00\x01\x00")
    rule = _rule(BASE_FIELDS)
    report = verify_on_corpus(rule, [CorpusStream.from_bytes(stream.data, "s1", "A_to_B")])
    diff = diff_reports(report, report)
    assert not diff.resolved_counterexamples
    assert not diff.introduced_counterexamples
    assert not diff.unchanged_mismatches
    assert diff.matched_delta == 0
    assert diff.coverage_delta == 0.0
    assert "no differences" in format_rule_diff(diff_rules(rule, rule))
    assert "resolved counterexamples: 0" in format_report_diff(diff)


def test_diff_reports_unchanged_mismatch_and_coverage():
    stream = DirectionalStream.from_bytes(b"\x09\x00\x01\x00")
    rule = _rule(BASE_FIELDS)
    report = verify_on_corpus(rule, [CorpusStream.from_bytes(stream.data, "s1", "A_to_B")])
    changed = _rule([BASE_FIELDS[0], {"name": "value", "offset": 1, "type": "uint32"}])
    report_b = verify_on_corpus(changed, [CorpusStream.from_bytes(stream.data, "s1", "A_to_B")])
    diff = diff_reports(report, report_b)
    assert diff.unchanged_mismatches
    assert diff.coverage_delta == 0.0


def test_diff_reports_coverage_delta_on_scope_change():
    stream = DirectionalStream.from_bytes(b"\x04\x00\x01\x00")
    a = _rule(BASE_FIELDS, scope={"direction": "A_to_B"})
    b = _rule(BASE_FIELDS, scope={"direction": "B_to_A"})
    report_a = verify_on_corpus(a, [CorpusStream.from_bytes(stream.data, "s1", "B_to_A")])
    report_b = verify_on_corpus(b, [CorpusStream.from_bytes(stream.data, "s1", "B_to_A")])
    diff = diff_reports(report_a, report_b)
    assert diff.coverage_delta == 1.0
