"""Quality metrics computed from a verification report."""

from __future__ import annotations

import struct

from src.hypothesis.corpus import CorpusStream, verify_on_corpus
from src.hypothesis.metrics import compute_metrics
from src.protocol.rule import parse_rule

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


def _message(command, value, declared=8):
    return struct.pack(">BBHH", command, 0, declared, value) + b"\x00\x00"


def _report(streams):
    return verify_on_corpus(parse_rule(RULE), streams)


def test_metrics_all_matched():
    report = _report([CorpusStream.from_bytes(_message(4, 21) + _message(4, 22), "s1")])
    metrics = compute_metrics(report)
    assert metrics.total_messages == 2
    assert metrics.matched == 2
    assert metrics.coverage == 1.0
    assert metrics.precision == 1.0
    assert metrics.counterexample_density == 0.0
    assert metrics.rule_id == "r1"
    assert metrics.rule_version == 3


def test_metrics_with_mismatch_precision():
    report = _report([CorpusStream.from_bytes(_message(4, 21) + _message(7, 22), "s1")])
    metrics = compute_metrics(report)
    assert metrics.matched == 1
    assert metrics.mismatched == 1
    assert metrics.precision == 0.5
    assert metrics.counterexample_density == 50.0


def test_metrics_all_uncovered_ratio_and_length_histogram():
    rule = parse_rule(
        {
            "rule_id": "r1",
            "framing": {"type": "fixed_size", "size": 4},
            "fields": [{"name": "pad", "offset": 0, "type": "padding", "length": 4}],
        }
    )
    report = verify_on_corpus(rule, [CorpusStream.from_bytes(b"\x00" * 8, "s1")])
    metrics = compute_metrics(report)
    assert metrics.total_messages == 2
    assert metrics.length_histogram == {4: 2}
    assert metrics.uncovered_ratio == 0.0  # messages cover every byte


def test_metrics_not_applicable_reduces_coverage():
    report = _report(
        [
            CorpusStream.from_bytes(_message(4, 21), "s1", "A_to_B"),
            CorpusStream.from_bytes(_message(4, 21), "s2", "B_to_A"),
        ]
    )
    metrics = compute_metrics(report)
    assert metrics.total_messages == 2
    assert metrics.applicable_messages == 1
    assert metrics.coverage == 0.5
    assert metrics.precision == 1.0


def test_metrics_empty_corpus_is_zeroed():
    metrics = compute_metrics(_report([]))
    assert metrics.total_messages == 0
    assert metrics.coverage == 0.0
    assert metrics.precision == 0.0
    assert metrics.fragmentation == 0.0
    assert metrics.counterexample_density == 0.0


def test_metrics_single_message_and_fragmentation():
    report = _report([CorpusStream.from_bytes(_message(4, 21), "s1")])
    metrics = compute_metrics(report)
    assert metrics.total_messages == 1
    assert metrics.sessions == 1
    assert metrics.fragmentation == 1.0
    assert metrics.type_histogram == {"4": 1}


def test_metrics_type_histogram_counts_command_values():
    report = _report(
        [CorpusStream.from_bytes(_message(4, 21) + _message(4, 22) + _message(9, 23), "s1")]
    )
    metrics = compute_metrics(report)
    assert metrics.type_histogram == {"4": 2, "9": 1}
    assert metrics.counterexamples == 1
