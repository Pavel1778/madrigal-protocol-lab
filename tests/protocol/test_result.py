import json
import os
import struct

import jsonschema

from src.protocol.engine import apply_rule
from src.protocol.result import build_result, summarise
from src.protocol.rule import parse_rule
from src.protocol.stream import DirectionalStream

RULE = {
    "rule_id": "r1",
    "rule_version": 3,
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
        {"name": "value", "offset": 4, "type": "uint16", "byte_order": "big"},
    ],
}

CAPTURE_ID = "sha256:" + "ab" * 32


def _message(command, declared, value):
    return struct.pack(">BBHH", command, 0, declared, value) + b"\x00\x00"


def test_summary_covers_all_statuses():
    rule = parse_rule(RULE)
    messages = apply_rule(DirectionalStream.from_bytes(_message(4, 8, 21)), rule, "s1", "A_to_B")
    summary = summarise(messages)
    assert summary["matched"] == 1
    assert summary["mismatched"] == 0
    for key in ("incomplete", "ambiguous", "uncovered", "not_applicable", "outdated", "unknown"):
        assert summary[key] == 0


def test_build_result_matches_contract_shape():
    rule = parse_rule(RULE)
    messages = apply_rule(DirectionalStream.from_bytes(_message(4, 8, 21)), rule, "s1", "A_to_B")
    result = build_result(rule, CAPTURE_ID, messages)
    payload = result.to_dict()
    assert payload["contract_version"] == 1
    assert payload["rule_id"] == "r1"
    assert payload["rule_version"] == 3
    assert payload["capture_id"] == CAPTURE_ID
    message = payload["messages"][0]
    assert set(message) <= {"offset", "length", "fields", "status", "provenance_range"}
    assert message["offset"] == 0 and message["length"] == 8
    assert message["fields"] == {"command": 4, "value": 21}
    assert message["status"] == "matched"
    assert json.dumps(payload)


def test_result_passes_schema_validation():
    schema_path = os.path.join("docs", "schemas", "result.schema.json")
    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    rule = parse_rule(RULE)
    messages = apply_rule(DirectionalStream.from_bytes(_message(4, 8, 21)), rule, "s1", "A_to_B")
    payload = build_result(rule, CAPTURE_ID, messages).to_dict()
    jsonschema.Draft202012Validator(schema).validate(payload)
