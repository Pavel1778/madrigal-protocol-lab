import json
import struct

from src.hypothesis.corpus import CorpusStream, verify_on_corpus
from src.hypothesis.versioning import ResultStore, compare_reports
from src.protocol.engine import apply_rule
from src.protocol.result import build_result
from src.protocol.rule import parse_rule
from src.protocol.stream import DirectionalStream

RULE = {
    "rule_id": "r1",
    "rule_version": 1,
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


def _message(command, value=21, declared=8):
    return struct.pack(">BBHH", command, 0, declared, value) + b"\x00\x00"


def test_editing_a_rule_marks_old_results_outdated():
    rule = parse_rule(RULE)
    stream = _message(4)
    messages = apply_rule(DirectionalStream.from_bytes(stream), rule, "s1", "A_to_B")
    payload = build_result(rule, "sha256:" + "cd" * 32, messages).to_dict()

    store = ResultStore()
    stored = store.add(rule, "sha256:" + "cd" * 32, payload)
    assert stored.status == "current"

    revised = rule.bump_version()
    touched = store.mark_outdated(revised, "sha256:" + "cd" * 32)
    assert touched == [stored]
    assert stored.status == "outdated"
    assert stored.payload["messages"][0]["status"] == "outdated"
    assert stored.payload["summary"]["outdated"] == 1
    assert stored.payload["summary"]["matched"] == 0


def test_outdated_is_scoped_to_the_version():
    rule = parse_rule(RULE)
    payload = {"messages": [{"off": 0}], "summary": {"matched": 1}}
    store = ResultStore()
    old = store.add(rule, "c1", payload)
    revised = rule.bump_version()
    future = store.add(revised, "c1", {"messages": [], "summary": {}})
    store.mark_outdated(revised, "c1")
    assert old.status == "outdated"
    assert future.status == "current"


def test_compare_reports_lists_introduced_and_resolved():
    base_rule = parse_rule(RULE)
    corpus = [
        CorpusStream.from_bytes(_message(4) + _message(7), "s1"),
    ]
    base = verify_on_corpus(base_rule, corpus)

    fixed = parse_rule({**RULE, "rule_version": 2})
    fixed.fields[0].expected = [4, 7]
    new = verify_on_corpus(fixed, corpus)

    comparison = compare_reports(base, new)
    assert comparison.rule_id == "r1"
    assert comparison.base_version == 1
    assert comparison.new_version == 2
    assert comparison.resolved
    assert comparison.introduced == []


def test_store_round_trips_to_json(tmp_path):
    rule = parse_rule(RULE)
    store = ResultStore()
    store.add(rule, "c1", {"messages": [], "summary": {}})
    out = tmp_path / "results.json"
    store.save(str(out))
    data = json.loads(out.read_text())
    assert data[0]["rule_id"] == "r1"
    assert data[0]["rule_version"] == 1
