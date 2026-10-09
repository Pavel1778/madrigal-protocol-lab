"""Alternative explanations for a hypothesis field."""

from __future__ import annotations

import struct

from src.hypothesis.alternatives import analyze_field, suggest_alternatives
from src.protocol.engine import apply_rule
from src.protocol.rule import parse_rule
from src.protocol.stream import DirectionalStream


def _rule(fields, size=8):
    return parse_rule({"rule_id": "r1", "framing": {"type": "fixed_size", "size": size}, "fields": fields})


def _messages(rule, payloads):
    stream = DirectionalStream.from_bytes(b"".join(payloads))
    return apply_rule(stream, rule)


def test_constant_field_is_detected_as_an_alternative():
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [struct.pack(">B", 5) + b"\x00" * 7 for _ in range(4)]
    report = analyze_field(rule, _messages(rule, payloads), "value")
    names = {a.name for a in report.alternatives}
    assert "constant" in names
    constant = next(a for a in report.alternatives if a.name == "constant")
    assert constant.support == 4
    assert constant.contradict == 0
    assert constant.score == 1.0


def test_counter_field_beats_constant_on_increasing_values():
    rule = _rule([{"name": "seq", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [bytes([value]) + b"\x00" * 7 for value in (1, 2, 3, 4, 5)]
    report = analyze_field(rule, _messages(rule, payloads), "seq")
    counter = next(a for a in report.alternatives if a.name == "counter")
    assert counter.support == 4
    assert counter.score == 1.0
    # A constant does not fit a field that changes every message.
    constant = next((a for a in report.alternatives if a.name == "constant"), None)
    assert constant is None or constant.score < 1.0
    assert report.best is not None


def test_message_length_alternative():
    rule = _rule([{"name": "len_like", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [struct.pack(">B", 8) + b"\x00" * 7 for _ in range(3)]
    report = analyze_field(rule, _messages(rule, payloads), "len_like")
    names = {a.name for a in report.alternatives}
    assert "message_length" in names
    length_alts = [a for a in report.alternatives if a.name == "message_length"]
    assert all(a.score == 1.0 for a in length_alts)


def test_alias_alternative_when_mirroring_another_field():
    rule = _rule(
        [
            {"name": "source", "offset": 0, "type": "uint8"},
            {"name": "value", "offset": 1, "type": "uint8", "hypothesis": True},
        ]
    )
    payloads = [bytes([v, v]) + b"\x00" * 6 for v in (3, 4, 5)]
    report = analyze_field(rule, _messages(rule, payloads), "value")
    names = {a.name for a in report.alternatives}
    assert "alias_of_source" in names


def test_checksum_alternative_detected():
    rule = _rule(
        [
            {"name": "cs", "offset": 0, "type": "uint8", "hypothesis": True},
            {"name": "body", "offset": 1, "type": "bytes", "length": 3},
        ]
    )
    payloads = []
    for body in (b"\x01\x02\x03", b"\x10\x20\x30", b"\xff\x00\x11"):
        payloads.append(bytes([body[0] ^ body[1] ^ body[2]]) + body + b"\x00" * 4)
    report = analyze_field(rule, _messages(rule, payloads), "cs")
    names = {a.name for a in report.alternatives}
    assert any(name.startswith("checksum_xor") for name in names)


def test_journal_alternative():
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [struct.pack(">B", v) + b"\x00" * 7 for v in (21, 22)]
    messages = _messages(rule, payloads)
    messages[0].timestamp = 10.0
    messages[1].timestamp = 10.1

    from src.hypothesis.journal import JournalEntry, Correlation

    correlations = [
        Correlation(
            session_id="", direction="", message_offset=messages[0].offset,
            message_timestamp=10.0, entry=JournalEntry(timestamp=10.0, action="set", params={"value": 21}),
            delta_ms=0.0,
        ),
        Correlation(
            session_id="", direction="", message_offset=messages[1].offset,
            message_timestamp=10.1, entry=JournalEntry(timestamp=10.1, action="set", params={"value": 22}),
            delta_ms=0.0,
        ),
    ]
    report = analyze_field(rule, messages, "value", correlations=correlations)
    names = {a.name for a in report.alternatives}
    assert "journal_value" in names


def test_enum_like_field_reports_low_cardinality_on_string_values():
    rule = _rule(
        [
            {
                "name": "target",
                "offset": 0,
                "type": "enum",
                "hypothesis": True,
                "enum": {"a": 1, "b": 2},
            }
        ]
    )
    payloads = [bytes([value]) + b"\x00" * 7 for value in (1, 2, 1, 2)]
    report = analyze_field(rule, _messages(rule, payloads), "target")
    low = next(a for a in report.alternatives if a.name == "low_cardinality")
    assert low.support == 4
    assert low.score == 1.0
    assert report.best == "low_cardinality"


def test_unknown_field_is_rejected():
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8"}])
    try:
        analyze_field(rule, [], "missing")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_suggest_covers_only_hypothesis_fields():
    rule = _rule(
        [
            {"name": "known", "offset": 0, "type": "uint8"},
            {"name": "guess", "offset": 1, "type": "uint8", "hypothesis": True},
        ]
    )
    payloads = [bytes([1, v]) + b"\x00" * 6 for v in (7, 8, 9)]
    report = suggest_alternatives(rule, _messages(rule, payloads))
    assert [f.field_name for f in report.fields] == ["guess"]
    assert report.fields[0].is_hypothesis is True
