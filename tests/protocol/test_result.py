import json
import os
import struct

import jsonschema

from src.protocol.engine import apply_rule
from src.protocol.result import build_result, summarise, write_result
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
        "length_covers": "entire_message",
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
    with open(schema_path, encoding="utf-8") as handle:
        schema = json.load(handle)
    rule = parse_rule(RULE)
    messages = apply_rule(DirectionalStream.from_bytes(_message(4, 8, 21)), rule, "s1", "A_to_B")
    payload = build_result(rule, CAPTURE_ID, messages).to_dict()
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_csv_export_has_a_column_per_field(tmp_path):
    import csv

    rule = parse_rule(RULE)
    messages = apply_rule(
        DirectionalStream.from_bytes(_message(4, 8, 21) + _message(9, 8, 22)),
        rule,
        "s1",
        "A_to_B",
    )
    result = build_result(rule, CAPTURE_ID, messages)
    path = tmp_path / "result.csv"
    write_result(result, str(path))
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0].keys() == {
        "message_offset", "message_length", "message_status", "reason",
        "command", "value",
    }
    assert rows[0]["message_status"] == "matched"
    assert rows[0]["command"] == "4"
    assert rows[1]["message_status"] == "mismatched"


def test_jsonl_export_writes_one_message_per_line(tmp_path):
    rule = parse_rule(RULE)
    messages = apply_rule(
        DirectionalStream.from_bytes(_message(4, 8, 21) + _message(4, 8, 22)),
        rule,
        "s1",
        "A_to_B",
    )
    result = build_result(rule, CAPTURE_ID, messages)
    path = tmp_path / "result.jsonl"
    write_result(result, str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["status"] == "matched"
    assert first["fields"]["value"] == 21
