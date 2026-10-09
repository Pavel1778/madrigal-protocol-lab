"""Export a rule to Kaitai .ksy and to a standalone Python parser.

The Python export is checked for equivalence with the engine: over the same
stream, the generated module must report the same message spans and the same
field values the engine does.
"""

from __future__ import annotations

import types

from src.protocol.engine import apply_rule
from src.protocol.export import export_kaitai, export_python
from src.protocol.rule import parse_rule
from src.protocol.stream import DirectionalStream


def _load(source: str) -> types.ModuleType:
    module = types.ModuleType("generated_parser")
    exec(compile(source, "<generated>", "exec"), module.__dict__)
    return module


RULE = {
    "rule_id": "r1",
    "rule_version": 4,
    "framing": {
        "type": "length_prefixed",
        "length_offset": 2,
        "length_size": 2,
        "byte_order": "big",
        "length_covers": "entire_message",
    },
    "fields": [
        {"name": "command", "offset": 0, "type": "uint8"},
        {"name": "flags", "offset": 1, "type": "uint8"},
        {"name": "payload_length", "offset": 2, "type": "uint16", "byte_order": "big"},
        {"name": "value", "offset": 4, "type": "uint16", "byte_order": "big"},
    ],
}


def test_export_kaitai_has_meta_and_fields():
    text = export_kaitai(parse_rule(RULE))
    assert "meta:" in text
    assert "endian: be" in text
    assert "id: command" in text
    assert "type: u1" in text
    assert "id: value" in text
    assert "type: u2" in text


def test_export_kaitai_identifier_sanitised():
    rule = parse_rule(
        {
            "rule_id": "r",
            "name": "set-parameter",
            "framing": {"type": "fixed_size", "size": 1},
            "fields": [{"name": "2nd byte", "offset": 0, "type": "uint8"}],
        }
    )
    text = export_kaitai(rule)
    assert "id: set_parameter" in text
    assert "id: f_2nd_byte" in text


def test_export_python_is_self_contained_and_runs():
    source = export_python(parse_rule(RULE))
    module = _load(source)
    assert module.RULE["rule_id"] == "r1"
    assert module.RULE["rule_version"] == 4
    spans = module.frame(b"\x04\x00\x00\x08\x00\x15\x00\x00")
    assert spans == [(0, 8)]


def test_generated_parser_matches_engine_values():
    rule = parse_rule(RULE)
    data = b"\x04\x01\x00\x08\x00\x15\x00\x00\x04\x01\x00\x08\x00\x16\x00\x00"
    engine_messages = apply_rule(DirectionalStream.from_bytes(data), rule, "s1", "A_to_B")
    module = _load(export_python(rule))
    parsed = module.parse_stream(data, "s1", "A_to_B")

    assert len(parsed) == len(engine_messages)
    for got, expected in zip(parsed, engine_messages):
        assert got["offset"] == expected.offset
        assert got["length"] == expected.length
        assert got["fields"] == expected.field_values()


def test_generated_parser_handles_extended_types_like_engine():
    rule = parse_rule(
        {
            "rule_id": "r2",
            "framing": {"type": "fixed_size", "size": 12},
            "fields": [
                {"name": "version", "offset": 0, "type": "bitmask", "bit_offset": 0, "bit_length": 2},
                {"name": "mode", "offset": 0, "type": "bitmask", "bit_offset": 2, "bit_length": 2},
                {"name": "tag", "offset": 1, "type": "string", "length": 3},
                {"name": "count", "offset": 4, "type": "uint8"},
                {"name": "items", "offset": 5, "type": "array", "element_type": "uint16", "count": 2},
                {"name": "kind", "offset": 9, "type": "enum", "enum": {"a": 1, "b": 2}},
            ],
        }
    )
    data = b"\x05abc\x00\x02\x00\x11\x00\x22\x02\x00\x00"
    engine = apply_rule(DirectionalStream.from_bytes(data), rule)[0]
    module = _load(export_python(rule))
    parsed = module.parse_stream(data)[0]
    assert parsed["fields"] == engine.field_values()


def test_generated_parser_checks_checksum_like_engine():
    body = bytes([0x01, 0x02, 0x03])
    cs = 0x01 ^ 0x02 ^ 0x03
    rule = parse_rule(
        {
            "rule_id": "r3",
            "framing": {"type": "fixed_size", "size": 8},
            "fields": [
                {"name": "cs", "offset": 3, "type": "checksum", "algorithm": "xor", "length": 1, "start": 0, "end": 3},
            ],
        }
    )
    good = body + bytes([cs]) + b"\x00" * 4
    bad = body + b"\xff" + b"\x00" * 4
    module = _load(export_python(rule))
    assert module.parse_stream(good)[0]["field_status"]["cs"] == "matched"
    assert module.parse_stream(bad)[0]["field_status"]["cs"] == "mismatched"


def test_generated_parser_frames_marker_based():
    rule = parse_rule(
        {
            "rule_id": "r4",
            "framing": {"type": "marker_based", "start_bytes": "1b5b", "end_bytes": "03"},
            "fields": [{"name": "x", "offset": 0, "type": "uint8"}],
        }
    )
    module = _load(export_python(rule))
    data = b"\x1b[\xaa\x03\x1b[\xbb\x03"
    spans = module.frame(data)
    assert spans == [(0, 4), (4, 4)]


def test_generated_parser_frames_manual():
    rule = parse_rule(
        {
            "rule_id": "r5",
            "framing": {"type": "manual", "messages": [{"offset": 0, "length": 2}, {"offset": 4, "length": 3}]},
            "fields": [{"name": "x", "offset": 0, "type": "uint8"}],
        }
    )
    module = _load(export_python(rule))
    assert module.frame(b"\x00" * 8) == [(0, 2), (4, 3)]
