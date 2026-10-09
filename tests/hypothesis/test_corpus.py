import struct

from src.hypothesis.corpus import CorpusStream, verify_on_corpus
from src.hypothesis.status import Status
from src.protocol.rule import parse_rule

RULE = {
    "rule_id": "r1",
    "rule_version": 1,
    "scope": {"direction": "A_to_B"},
    "framing": {
        "type": "length_prefixed",
        "length_offset": 2,
        "length_size": 2,
        "byte_order": "big",
    },
    "fields": [
        {"name": "command", "offset": 0, "type": "uint8", "expected": [4]},
        {"name": "value", "offset": 4, "type": "uint16", "byte_order": "big"},
    ],
}


def _message(command, value, declared=8):
    return struct.pack(">BBHH", command, 0, declared, value) + b"\x00\x00"


def test_corpus_without_contradictions_is_confirmed():
    rule = parse_rule(RULE)
    stream = _message(4, 21) + _message(4, 22) + _message(4, 23)
    report = verify_on_corpus(rule, [CorpusStream.from_bytes(stream, "s1")])
    assert report.total == 3
    assert report.totals["matched"] == 3
    assert report.contradictions == []
    assert report.is_confirmed()


def test_corpus_collects_counterexamples_with_offsets():
    rule = parse_rule(RULE)
    good = _message(4, 21)
    bad = _message(7, 21)
    report = verify_on_corpus(rule, [CorpusStream.from_bytes(good + bad, "s1")])
    assert report.totals["matched"] == 1
    assert report.totals["mismatched"] == 1
    assert len(report.contradictions) == 1
    counter = report.contradictions[0]
    assert counter.session_id == "s1"
    assert counter.message_offset == 8
    assert counter.bytes_hex == bad.hex()
    assert report.is_confirmed() is False


def test_counterexamples_across_multiple_streams_are_all_reported():
    rule = parse_rule(RULE)
    streams = [
        CorpusStream.from_bytes(_message(7, 1), "s1", "A_to_B"),
        CorpusStream.from_bytes(_message(4, 1), "s2", "A_to_B"),
        CorpusStream.from_bytes(_message(9, 1), "s3", "A_to_B"),
    ]
    report = verify_on_corpus(rule, streams)
    assert report.totals["matched"] == 1
    assert len(report.contradictions) == 2
    assert {c.session_id for c in report.contradictions} == {"s1", "s3"}


def test_not_applicable_streams_are_counted_not_hidden():
    rule = parse_rule(RULE)
    streams = [
        CorpusStream.from_bytes(_message(4, 1), "s1", "A_to_B"),
        CorpusStream.from_bytes(_message(4, 1), "s1", "B_to_A"),
    ]
    report = verify_on_corpus(rule, streams)
    assert report.totals["matched"] == 1
    assert report.totals["not_applicable"] == 1
    assert report.contradictions == []


def test_report_to_dict_is_serialisable():
    import json

    rule = parse_rule(RULE)
    report = verify_on_corpus(rule, [CorpusStream.from_bytes(_message(7, 1), "s1")])
    payload = report.to_dict()
    assert payload["rule_id"] == "r1"
    assert payload["total"] == 1
    assert payload["counts"]["mismatched"] == 1
    assert payload["contradictions"][0]["status"] == Status.MISMATCHED.value
    json.dumps(payload)


def test_accepts_raw_bytes_and_directional_streams():
    rule = parse_rule(RULE)
    report = verify_on_corpus(rule, [_message(4, 1), _message(4, 2)])
    assert report.total == 2
    assert report.totals["matched"] == 2
