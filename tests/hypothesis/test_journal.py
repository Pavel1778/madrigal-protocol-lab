"""Parse action journals and correlate them with decoded messages."""

from __future__ import annotations

from src.hypothesis.journal import (
    JournalEntry,
    JournalError,
    correlate,
    parse_journal,
    parse_timestamp,
)
from src.protocol.engine import MessageResult
from src.hypothesis.status import Status
from src.protocol.stream import DirectionalStream, Hole


JOURNAL = """\
# turns recorded during the session
10.000 | set_temperature | value=21
11.400 | toggle_power
12.100 | set_temperature | value=24
"""


def test_parse_journal_reads_entries_and_params():
    entries = parse_journal(JOURNAL)
    assert len(entries) == 3
    assert entries[0].timestamp == 10.0
    assert entries[0].action == "set_temperature"
    assert entries[0].params == {"value": 21}
    assert entries[0].line_number == 2
    assert entries[1].params == {}


def test_parse_journal_iso_timestamp():
    entries = parse_journal("2026-10-09T12:00:00Z | ping")
    assert entries[0].timestamp > 0


def test_parse_timestamp_roundtrip():
    assert parse_timestamp("12.5") == 12.5
    assert parse_timestamp("  7 ") == 7.0


def test_parse_journal_skips_prose_and_comments():
    text = """\
# Action journal

One line per transaction: `timestamp | action | parameter | result`.

```
10.0 | read | temperature | 1595
```
"""
    entries = parse_journal(text)
    assert len(entries) == 1
    assert entries[0].params == {"parameter": "temperature", "result": 1595}


def test_parse_journal_reads_positional_format():
    entries = parse_journal("10.0 | write | humidity | applied 2743\n11.0 | measure | channel_a | 8 samples\n")
    assert entries[0].action == "write"
    assert entries[0].params == {"parameter": "humidity", "result": "applied 2743"}
    assert entries[1].params == {"parameter": "channel_a", "result": "8 samples"}


def test_parse_journal_rejects_bad_lines():
    try:
        parse_journal("10 | act | value=1 | broken")
    except JournalError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected JournalError")
    try:
        parse_journal("10")
    except JournalError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected JournalError")


def _message(offset, ts, value):
    return MessageResult(
        offset=offset,
        length=4,
        status=Status.MATCHED,
        session_id="s1",
        direction="A_to_B",
        timestamp=ts,
        fields=[
            _field("value", value),
        ],
    )


def _field(name, value):
    from src.protocol.engine import FieldResult

    return FieldResult(
        message_offset=0,
        message_length=4,
        field_name=name,
        field_type="uint16",
        field_offset=0,
        field_length=2,
        value=value,
        status=Status.MATCHED,
    )


def test_correlate_pairs_within_window():
    entries = parse_journal(JOURNAL)
    messages = [_message(0, 10.05, 21), _message(4, 20.0, 99)]
    report = correlate(messages, entries, window_ms=500)
    assert len(report.correlated) == 1
    pair = report.correlated[0]
    assert pair.entry.action == "set_temperature"
    assert pair.delta_ms == 50.0
    assert pair.value_agreements == ["value=21"]
    assert pair.value_conflicts == []
    assert report.messages_without_entry == 1
    assert len(report.entries_without_message) == 2


def test_correlate_reports_value_conflict():
    entries = parse_journal("10.0 | set_temperature | value=99\n")
    messages = [_message(0, 10.0, 21)]
    report = correlate(messages, entries, window_ms=100)
    pair = report.correlated[0]
    assert pair.value_agreements == []
    assert pair.value_conflicts == ["value=21 (journal value=99)"]


def test_correlate_leaves_messages_without_timestamp_unmatched():
    entries = parse_journal(JOURNAL)
    messages = [_message(0, None, 21)]
    report = correlate(messages, entries, window_ms=500)
    assert not report.correlated
    assert report.messages_without_timestamp == 1
    assert report.messages_without_entry == 0
    assert len(report.entries_without_message) == 3


def test_correlate_uses_nearest_entry():
    entries = parse_journal("10.0 | a\n10.4 | b\n")
    messages = [_message(0, 10.3, 1)]
    report = correlate(messages, entries, window_ms=500)
    assert len(report.correlated) == 1
    assert report.correlated[0].entry.action == "b"


def test_correlate_does_not_reuse_one_entry_twice():
    entries = parse_journal("10.0 | a\n")
    messages = [_message(0, 10.0, 1), _message(4, 10.05, 1)]
    report = correlate(messages, entries, window_ms=500)
    assert len(report.correlated) == 1
    assert report.messages_without_entry == 1
    assert report.entries_without_message == []


def test_correlate_empty_inputs():
    report = correlate([], [], window_ms=500)
    assert report.correlated == []
    assert report.summary() == "0 of 0 messages correlated, 0 journal entries unmatched"


def test_correlate_rejects_negative_window():
    try:
        correlate([], [], window_ms=-1)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_engine_message_timestamp_from_provenance():
    from src.protocol.engine import apply_rule
    from src.protocol.rule import parse_rule

    stream = DirectionalStream(
        data=b"\x04\x00\x00\x15\x00\x00\x00\x00",
        provenance=[Hole(type="observed", offset=0, length=8, packet_index=3, ts=42.5)],
    )
    rule = parse_rule(
        {
            "rule_id": "r",
            "framing": {"type": "fixed_size", "size": 8},
            "fields": [{"name": "command", "offset": 0, "type": "uint8"}],
        }
    )
    message = apply_rule(stream, rule)[0]
    assert message.timestamp == 42.5
    assert message.fields[0].provenance_range["ts"] == 42.5
