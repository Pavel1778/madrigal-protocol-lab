import struct

from src.hypothesis.status import Status
from src.protocol.engine import apply_rule
from src.protocol.rule import parse_rule
from src.protocol.stream import DirectionalStream, Hole

RULE = {
    "rule_id": "r1",
    "rule_version": 1,
    "scope": {"direction": "A_to_B"},
    "framing": {
        "type": "length_prefixed",
        "length_offset": 2,
        "length_size": 2,
        "byte_order": "big",
        "length_includes_payload": True,
    },
    "fields": [
        {"name": "command", "offset": 0, "type": "uint8", "expected": [4]},
        {"name": "flags", "offset": 1, "type": "uint8"},
        {"name": "payload_length", "offset": 2, "type": "uint16", "byte_order": "big"},
        {"name": "parameter_value", "offset": 4, "type": "uint16", "byte_order": "big", "hypothesis": True},
    ],
}


def _message(command, flags, declared, value):
    return struct.pack(">BBHH", command, flags, declared, value) + b"\x00\x00"


def test_well_formed_messages_match_and_decode_fields():
    rule = parse_rule(RULE)
    data = _message(4, 0, 8, 21) + _message(4, 1, 8, 22)
    results = apply_rule(DirectionalStream.from_bytes(data), rule, "s1", "A_to_B")
    assert len(results) == 2
    assert all(m.status is Status.MATCHED for m in results)
    assert results[0].field_values() == {
        "command": 4,
        "flags": 0,
        "payload_length": 8,
        "parameter_value": 21,
    }
    value_field = next(f for f in results[0].fields if f.field_name == "parameter_value")
    assert value_field.hypothesis is True


def test_wrong_command_is_mismatched_with_counterexample():
    rule = parse_rule(RULE)
    data = _message(4, 0, 8, 21) + _message(9, 0, 8, 21)
    results = apply_rule(DirectionalStream.from_bytes(data), rule, "s1", "A_to_B")
    assert results[0].status is Status.MATCHED
    assert results[1].status is Status.MISMATCHED
    counter = results[1].counterexample()
    assert counter is not None
    assert counter.status is Status.MISMATCHED
    assert counter.field_name == "command"
    assert counter.field_offset == 0
    assert counter.field_length == 1
    assert counter.bytes_hex == data[8:16].hex()


def test_gap_in_field_range_is_incomplete():
    rule = parse_rule(RULE)
    data = _message(4, 0, 8, 21)
    stream = DirectionalStream(
        data=data,
        diagnostics=[Hole(type="gap", offset=4, length=2)],
    )

    results = apply_rule(stream, rule, "s1", "A_to_B")
    assert results[0].status is Status.INCOMPLETE
    assert results[0].reason == "gap_in_field_range"
    assert results[0].counterexample().reason == "gap_in_field_range"


def test_ambiguity_in_field_range_is_ambiguous():
    rule = parse_rule(RULE)
    data = _message(4, 0, 8, 21)
    stream = DirectionalStream(
        data=data,
        diagnostics=[Hole(type="ambiguity", offset=4, length=2)],
    )
    results = apply_rule(stream, rule, "s1", "A_to_B")
    assert results[0].status is Status.AMBIGUOUS


def test_scoped_rule_marks_other_direction_not_applicable():
    rule = parse_rule(RULE)
    data = _message(4, 0, 8, 21)
    results = apply_rule(DirectionalStream.from_bytes(data), rule, "s1", "B_to_A")
    assert results[0].status is Status.NOT_APPLICABLE
    assert all(f.status is Status.NOT_APPLICABLE for f in results[0].fields) or results[0].fields == []


def test_provenance_range_is_attached_to_fields():
    rule = parse_rule(RULE)
    data = _message(4, 0, 8, 21)
    stream = DirectionalStream(
        data=data,
        provenance=[Hole(type="provenance", offset=0, length=8, packet_index=42)],
    )
    results = apply_rule(stream, rule, "s1", "A_to_B")
    assert results[0].fields[0].provenance_range == {"offset": 0, "length": 1, "packets": [42]}


def test_missing_ok_field_is_uncovered():
    rule = parse_rule(
        {
            "rule_id": "r",
            "framing": {"type": "fixed_size", "size": 2},
            "fields": [
                {"name": "present", "offset": 0, "type": "uint8"},
                {"name": "optional", "offset": 5, "type": "uint8", "missing_ok": True},
            ],
        }
    )
    results = apply_rule(DirectionalStream.from_bytes(b"\x01\x02"), rule, "s", "A_to_B")
    optional = next(f for f in results[0].fields if f.field_name == "optional")
    assert optional.status is Status.UNCOVERED
    assert results[0].status is Status.MATCHED


def test_field_beyond_message_is_incomplete():
    rule = parse_rule(
        {
            "rule_id": "r",
            "framing": {"type": "fixed_size", "size": 2},
            "fields": [{"name": "wide", "offset": 0, "type": "uint32"}],
        }
    )
    results = apply_rule(DirectionalStream.from_bytes(b"\x01\x02"), rule, "s", "A_to_B")
    assert results[0].status is Status.INCOMPLETE
    assert results[0].fields[0].reason == "field_beyond_message"
