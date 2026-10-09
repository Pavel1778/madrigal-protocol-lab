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


def _alt_names(rule, payloads, field):
    report = analyze_field(rule, _messages(rule, payloads), field)
    return {a.name: a for a in report.alternatives}


def test_endianness_suggested_for_a_little_endian_counter():
    # A counter 0, 1, 2 stored little-endian appears on the wire as 00 00,
    # 01 00, 02 00. Read little-endian they step by one; read big-endian they
    # jump by 256, so the big-endian reading is flagged as the wrong one.
    rule = _rule([{"name": "seq", "offset": 0, "type": "uint16", "byte_order": "big", "hypothesis": True}])
    payloads = [b"\x00\x00" + b"\x00" * 6, b"\x01\x00" + b"\x00" * 6, b"\x02\x00" + b"\x00" * 6]
    names = _alt_names(rule, payloads, "seq")
    assert "endianness" in names
    assert names["endianness"].score == 1.0


def test_endianness_not_suggested_when_big_endian_is_regular():
    rule = _rule([{"name": "seq", "offset": 0, "type": "uint16", "byte_order": "big", "hypothesis": True}])
    payloads = [struct.pack(">H", v) + b"\x00" * 6 for v in (1, 2, 3, 4)]
    names = _alt_names(rule, payloads, "seq")
    assert "endianness" not in names


def test_offset_shift_suggests_a_constant_neighbouring_byte():
    # Byte 0 varies, byte 1 is the true constant field.
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [bytes([v, 7]) + b"\x00" * 6 for v in (1, 2, 3)]
    names = _alt_names(rule, payloads, "value")
    assert "offset_shift_+1" in names
    assert names["offset_shift_+1"].score == 1.0
    assert names["offset_shift_+1"].support == 3


def test_offset_shift_absent_when_no_neighbour_is_constant():
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [bytes([v, v + 1, v + 2]) + b"\x00" * 5 for v in (1, 2, 3)]
    names = _alt_names(rule, payloads, "value")
    assert "offset_shift_+1" not in names
    assert "offset_shift_-1" not in names


def test_xor_mask_detected_on_masked_counter():
    # Stored values are the counter xor 0x55.
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [bytes([v ^ 0x55]) + b"\x00" * 7 for v in (1, 2, 3, 4)]
    names = _alt_names(rule, payloads, "value")
    assert "xor_mask_85" in names
    assert names["xor_mask_85"].score == 1.0


def test_xor_mask_not_reported_for_plain_values():
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [bytes([v]) + b"\x00" * 7 for v in (10, 40, 90, 130)]
    names = _alt_names(rule, payloads, "value")
    assert not any(name.startswith("xor_mask_") for name in names)


def test_delta_encoding_detected_when_values_are_steps():
    # A constant value of 1 is either a constant field or a delta of 1; the
    # running sum 1,2,3,4,5 advances by one, so the delta reading is offered.
    rule = _rule([{"name": "delta", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [b"\x01" + b"\x00" * 7 for _ in range(5)]
    names = _alt_names(rule, payloads, "delta")
    assert "delta_encoding" in names
    assert names["delta_encoding"].support == 5


def test_delta_encoding_absent_for_irregular_values():
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8", "hypothesis": True}])
    payloads = [bytes([v]) + b"\x00" * 7 for v in (5, 40, 7, 90, 3)]
    names = _alt_names(rule, payloads, "value")
    assert "delta_encoding" not in names


def test_encoding_alternatives_are_numeric_only():
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
    payloads = [bytes([v]) + b"\x00" * 7 for v in (1, 2, 1, 2)]
    names = _alt_names(rule, payloads, "target")
    assert not any(name.startswith("xor_mask_") for name in names)
    assert "delta_encoding" not in names
    assert "endianness" not in names

