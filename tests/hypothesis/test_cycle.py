"""Full cycle: observation, hypothesis, verification, counterexample, revision.

This walks the workflow the tool is built around. A first rule is written from a
handful of observed messages; it is verified on a wider corpus; the messages it
gets wrong are surfaced as counterexamples; the rule is revised to cover them;
and the two verification reports are compared so the effect of the revision is
visible.
"""

import struct

from src.hypothesis.corpus import CorpusStream, verify_on_corpus
from src.hypothesis.versioning import ResultStore, compare_reports
from src.protocol.engine import apply_rule
from src.protocol.result import build_result
from src.protocol.rule import parse_rule
from src.protocol.stream import DirectionalStream


def _message(command, value, declared=8):
    return struct.pack(">BBHH", command, 0, declared, value) + b"\x00\x00"


OBSERVED = _message(4, 21) + _message(4, 22)

HYPOTHESIS = {
    "schema_version": 1,
    "rule_id": "set_parameter",
    "rule_version": 1,
    "name": "set_parameter",
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
        {"name": "payload_length", "offset": 2, "type": "uint16", "byte_order": "big"},
        {"name": "value", "offset": 4, "type": "uint16", "byte_order": "big", "hypothesis": True},
    ],
}

# The wider corpus also contains a read request (command 5) that the first
# hypothesis did not anticipate.
CORPUS = [_message(4, 21) + _message(5, 7) + _message(4, 23)]


def test_observation_then_hypothesis_matches_observed_messages():
    rule = parse_rule(HYPOTHESIS)
    results = apply_rule(DirectionalStream.from_bytes(OBSERVED), rule, "s1", "A_to_B")
    assert [m.status.value for m in results] == ["matched", "matched"]


def test_hypothesis_fails_on_wider_corpus_and_yields_counterexample():
    rule = parse_rule(HYPOTHESIS)
    report = verify_on_corpus(rule, [CorpusStream.from_bytes(CORPUS[0], "s1")])
    assert report.totals["matched"] == 2
    assert report.totals["mismatched"] == 1
    assert not report.is_confirmed()
    counter = report.contradictions[0]
    assert counter.message_offset == 8
    assert counter.field_name == "command"
    assert counter.bytes_hex == CORPUS[0][8:16].hex()


def test_revision_removes_the_counterexample_and_versions_compare():
    rule = parse_rule(HYPOTHESIS)
    base_report = verify_on_corpus(rule, [CorpusStream.from_bytes(CORPUS[0], "s1")])

    revised = parse_rule(HYPOTHESIS)
    revised.fields[0].expected = [4, 5]
    revised = revised.bump_version()
    assert revised.rule_version == 2

    new_report = verify_on_corpus(revised, [CorpusStream.from_bytes(CORPUS[0], "s1")])
    assert new_report.is_confirmed()

    comparison = compare_reports(base_report, new_report)
    assert comparison.base_version == 1
    assert comparison.new_version == 2
    assert len(comparison.resolved) == 1
    assert comparison.introduced == []


def test_revision_does_not_change_the_bytes():
    original = CORPUS[0]
    rule = parse_rule(HYPOTHESIS)
    apply_rule(DirectionalStream.from_bytes(original), rule, "s1", "A_to_B")
    revised = parse_rule(HYPOTHESIS).bump_version()
    apply_rule(DirectionalStream.from_bytes(original), revised, "s1", "A_to_B")
    assert original == CORPUS[0]


def test_old_result_is_marked_outdated_after_revision():
    rule = parse_rule(HYPOTHESIS)
    messages = apply_rule(DirectionalStream.from_bytes(CORPUS[0]), rule, "s1", "A_to_B")
    payload = build_result(rule, "sha256:" + "11" * 32, messages).to_dict()

    store = ResultStore()
    stored = store.add(rule, "sha256:" + "11" * 32, payload)
    revised = rule.bump_version()
    store.mark_outdated(revised, "sha256:" + "11" * 32)
    assert stored.status == "outdated"
    assert all(m["status"] == "outdated" for m in stored.payload["messages"])


def test_rule_edit_is_a_new_version_without_mutating_the_old_rule():
    rule = parse_rule(HYPOTHESIS)
    revised = parse_rule(HYPOTHESIS).bump_version()
    assert rule.rule_version == 1
    assert revised.rule_version == 2
    assert rule.fields[0].expected == [4]
