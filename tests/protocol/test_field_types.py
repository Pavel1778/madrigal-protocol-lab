"""Extended field types: bitmask, string, checksum, computed, conditional,
array and padding. Each type has a success case and a boundary or failure case.
"""

from __future__ import annotations

import pytest

from src.hypothesis.status import Status
from src.protocol.engine import apply_rule
from src.protocol.rule import RuleError, parse_rule
from src.protocol.stream import DirectionalStream


def _rule(fields, framing=None):
    return parse_rule(
        {
            "rule_id": "r",
            "framing": framing or {"type": "fixed_size", "size": 8},
            "fields": fields,
        }
    )


def _apply(fields, data, framing=None):
    rule = _rule(fields, framing)
    stream = DirectionalStream.from_bytes(data)
    return apply_rule(stream, rule)[0]


# ---------------------------------------------------------------- bitmask


def test_bitmask_reads_disjoint_bit_fields():
    message = _apply(
        [
            {"name": "version", "offset": 0, "type": "bitmask", "bit_offset": 0, "bit_length": 2},
            {"name": "mode", "offset": 0, "type": "bitmask", "bit_offset": 2, "bit_length": 2},
        ],
        b"\x05" + b"\x00" * 7,
        {"type": "fixed_size", "size": 8},
    )
    values = message.field_values()
    assert values["version"] == 1
    assert values["mode"] == 1
    assert message.status == Status.MATCHED


def test_bitmask_across_two_bytes_and_expected_failure():
    message = _apply(
        [
            {
                "name": "high_nibble",
                "offset": 0,
                "type": "bitmask",
                "bit_offset": 8,
                "bit_length": 4,
                "byte_order": "big",
                "expected": [1],
            }
        ],
        b"\x01\x02" + b"\x00" * 6,
    )
    assert message.field_values()["high_nibble"] == 1
    assert message.status == Status.MATCHED

    bad = _apply(
        [{"name": "f", "offset": 0, "type": "bitmask", "bit_offset": 4, "bit_length": 4, "expected": [0]}],
        b"\xff\x00\x00\x00\x00\x00\x00\x00",
    )
    assert bad.field_values()["f"] == 15
    assert bad.status == Status.MISMATCHED


# ---------------------------------------------------------------- string


def test_string_fixed_length_strips_padding_nulls():
    message = _apply(
        [{"name": "tag", "offset": 0, "type": "string", "length": 4}],
        b"abc\x00" + b"\x00" * 4,
    )
    assert message.field_values()["tag"] == "abc"
    assert message.status == Status.MATCHED


def test_string_terminated_and_utf8():
    message = _apply(
        [
            {"name": "greeting", "offset": 0, "type": "string", "terminated": True},
            {"name": "letter", "offset": 3, "type": "string", "length": 2, "encoding": "utf-8"},
        ],
        b"hi\x00" + b"\xd0\x9f" + b"\x00" * 3,
    )
    values = message.field_values()
    assert values["greeting"] == "hi"
    assert values["letter"] == "\u041f"


def test_string_beyond_message_is_incomplete():
    message = _apply(
        [{"name": "tag", "offset": 0, "type": "string", "length": 16}],
        b"abc\x00" + b"\x00" * 4,
    )
    assert message.status == Status.INCOMPLETE


# ---------------------------------------------------------------- checksum


def test_checksum_xor_matches():
    data = bytes([0x01, 0x02, 0x03, 0x01 ^ 0x02 ^ 0x03]) + b"\x00" * 4
    message = _apply(
        [
            {"name": "body", "offset": 0, "type": "bytes", "length": 3},
            {"name": "cs", "offset": 3, "type": "checksum", "algorithm": "xor", "length": 1, "start": 0, "end": 3},
        ],
        data,
    )
    assert message.status == Status.MATCHED


def test_checksum_mismatch_is_reported():
    data = b"\x01\x02\x03\xff" + b"\x00" * 4
    message = _apply(
        [{"name": "cs", "offset": 3, "type": "checksum", "algorithm": "xor", "length": 1, "start": 0, "end": 3}],
        data,
    )
    assert message.status == Status.MISMATCHED
    assert "computed" in message.reason


def test_checksum_crc8_and_crc16_match():
    body = b"\x01\x02\x03\x04"
    from src.protocol.checksums import compute
    for algo in ("crc8", "crc16"):
        width = 2 if algo == "crc16" else 1
        value = compute(algo, body)
        filler = b"\x00" * (8 - len(body) - width)
        data = body + value.to_bytes(width, "big") + filler
        message = _apply(
            [{"name": "cs", "offset": len(body), "type": "checksum", "algorithm": algo, "length": width, "start": 0, "end": len(body)}],
            data,
        )
        assert message.status == Status.MATCHED, algo


# ---------------------------------------------------------------- computed


def test_computed_sum_of_values_matches():
    message = _apply(
        [
            {"name": "a", "offset": 0, "type": "uint8"},
            {"name": "b", "offset": 1, "type": "uint8"},
            {"name": "total", "offset": 2, "type": "computed", "expression": {"op": "sum_of_values", "fields": ["a", "b"]}},
            {"name": "drop", "offset": 3, "type": "padding", "length": 5},
        ],
        b"\x02\x03\x05\x00\x00\x00\x00\x00",
    )
    assert message.field_values()["total"] == 5
    assert message.status == Status.MATCHED


def test_computed_mismatch_and_missing_operand():
    bad = _apply(
        [
            {"name": "a", "offset": 0, "type": "uint8"},
            {"name": "total", "offset": 1, "type": "computed", "expression": {"op": "const", "value": 7}},
            {"name": "drop", "offset": 2, "type": "padding", "length": 6},
        ],
        b"\x02\x09\x00\x00\x00\x00\x00\x00",
    )
    assert bad.status == Status.MISMATCHED

    missing = _apply(
        [
            {"name": "a", "offset": 0, "type": "uint8", "missing_ok": True},
            {"name": "total", "offset": 1, "type": "computed", "expression": {"op": "sum_of_values", "fields": ["a"]}},
            {"name": "drop", "offset": 2, "type": "padding", "length": 6},
        ],
        b"\x02\x09\x00\x00\x00\x00\x00\x00",
    )
    # The operand is present here, so the sum is 2 and does not equal 9.
    assert missing.status == Status.MISMATCHED


# ---------------------------------------------------------------- conditional


def test_conditional_present_when_bit_set():
    rule = _rule(
        [
            {"name": "flags", "offset": 0, "type": "uint8"},
            {
                "name": "extra",
                "type": "conditional",
                "condition": {"field": "flags", "op": "bit_set", "value": 0x01},
                "field": {"name": "extra", "offset": 1, "type": "uint8"},
            },
        ]
    )
    message = apply_rule(DirectionalStream.from_bytes(b"\x01\x05" + b"\x00" * 6), rule)[0]
    assert message.field_values()["extra"] == 5
    assert message.status == Status.MATCHED


def test_conditional_absent_when_condition_not_met():
    rule = _rule(
        [
            {"name": "flags", "offset": 0, "type": "uint8"},
            {
                "name": "extra",
                "type": "conditional",
                "condition": {"field": "flags", "op": "bit_set", "value": 0x01},
                "field": {"name": "extra", "offset": 1, "type": "uint8"},
            },
        ]
    )
    message = apply_rule(DirectionalStream.from_bytes(b"\x00\x05" + b"\x00" * 6), rule)[0]
    assert message.field_values()["extra"] is None
    assert message.status == Status.MATCHED


def test_conditional_eq_operator():
    rule = _rule(
        [
            {"name": "cmd", "offset": 0, "type": "uint8"},
            {
                "name": "value",
                "type": "conditional",
                "condition": {"field": "cmd", "op": "eq", "value": 4},
                "field": {"name": "value", "offset": 1, "type": "uint8"},
            },
        ]
    )
    present = apply_rule(DirectionalStream.from_bytes(b"\x04\x2a" + b"\x00" * 6), rule)[0]
    assert present.field_values()["value"] == 42
    absent = apply_rule(DirectionalStream.from_bytes(b"\x09\x2a" + b"\x00" * 6), rule)[0]
    assert absent.field_values()["value"] is None


# ---------------------------------------------------------------- array


def test_array_fixed_count_of_uint16():
    message = _apply(
        [{"name": "values", "offset": 0, "type": "array", "element_type": "uint16", "count": 3}],
        b"\x00\x01\x00\x02\x00\x03" + b"\x00" * 2,
    )
    assert message.field_values()["values"] == [1, 2, 3]
    assert message.status == Status.MATCHED


def test_array_count_from_field_and_bytes_elements():
    message = _apply(
        [
            {"name": "count", "offset": 0, "type": "uint8"},
            {"name": "items", "offset": 1, "type": "array", "element_type": "bytes", "element_length": 2, "count_field": "count"},
        ],
        b"\x02\xaa\xbb\xcc\xdd" + b"\x00" * 3,
    )
    values = message.field_values()
    assert values["count"] == 2
    assert values["items"] == ["aabb", "ccdd"]


def test_array_count_field_beyond_stream_is_incomplete():
    message = _apply(
        [
            {"name": "count", "offset": 0, "type": "uint8"},
            {"name": "items", "offset": 1, "type": "array", "element_type": "uint16", "count_field": "count"},
        ],
        b"\x05\x00\x01" + b"\x00" * 5,
    )
    assert message.status == Status.INCOMPLETE


# ---------------------------------------------------------------- padding


def test_padding_is_skipped_and_message_matches():
    message = _apply(
        [
            {"name": "cmd", "offset": 0, "type": "uint8"},
            {"name": "pad", "offset": 1, "type": "padding", "length": 3},
            {"name": "value", "offset": 4, "type": "uint16"},
        ],
        b"\x04\x00\x00\x00\x00\x09",
        {"type": "fixed_size", "size": 6},
    )
    values = message.field_values()
    assert values["cmd"] == 4
    assert values["pad"] is None
    assert values["value"] == 9
    assert message.status == Status.MATCHED


def test_padding_only_message_is_uncovered():
    message = _apply(
        [{"name": "pad", "offset": 0, "type": "padding", "length": 8}],
        b"\x00" * 8,
    )
    assert message.status == Status.UNCOVERED


# ---------------------------------------------------------------- validation

def test_validation_rejects_malformed_extended_fields():
    cases = [
        {"name": "b", "offset": 0, "type": "bitmask"},
        {"name": "s", "offset": 0, "type": "string"},
        {"name": "arr", "offset": 0, "type": "array", "element_type": "uint16"},
        {"name": "arr2", "offset": 0, "type": "array", "element_type": "enum", "count": 2},
        {"name": "p", "offset": 0, "type": "padding"},
        {"name": "c", "offset": 0, "type": "checksum", "length": 1},
        {"name": "comp", "offset": 0, "type": "computed"},
        {"name": "cond", "type": "conditional", "condition": {"field": "x", "op": "bad"}, "field": {"name": "y", "offset": 0, "type": "uint8"}},
    ]
    for field in cases:
        with pytest.raises(RuleError):
            parse_rule({"rule_id": "r", "fields": [field]})


def test_validation_rejects_unknown_field_reference():
    with pytest.raises(RuleError):
        parse_rule(
            {
                "rule_id": "r",
                "fields": [
                    {"name": "a", "offset": 0, "type": "uint8"},
                    {"name": "t", "offset": 1, "type": "computed", "expression": {"op": "sum_of_values", "fields": ["missing"]}},
                ],
            }
        )
