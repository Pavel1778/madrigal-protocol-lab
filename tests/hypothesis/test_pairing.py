"""Pair framed messages into request/response turns with a stated confidence."""

from __future__ import annotations

from src.hypothesis.pairing import (
    DEFAULT_WINDOW_SECONDS,
    PairingReport,
    build_turns,
    build_turns_for_corpus,
)
from src.hypothesis.status import Status
from src.protocol.engine import MessageResult


def _message(direction, offset, ts, status=Status.MATCHED, length=4):
    return MessageResult(
        offset=offset,
        length=length,
        status=status,
        session_id="s1",
        direction=direction,
        timestamp=ts,
        bytes_hex="00" * length,
    )


def test_alternating_messages_pair_into_turns():
    messages = [
        _message("A_to_B", 0, 1.0),
        _message("B_to_A", 4, 1.05),
        _message("A_to_B", 8, 2.0),
        _message("B_to_A", 12, 2.05),
    ]
    report = build_turns(messages, session_id="s1")
    assert len(report.turns) == 2
    assert all(turn.answered for turn in report.turns)
    assert report.turns[0].gap_seconds == 0.05


def test_unanswered_request_has_zero_confidence():
    messages = [
        _message("A_to_B", 0, 1.0),
        _message("A_to_B", 4, 1.01),
    ]
    report = build_turns(messages, session_id="s1")
    assert len(report.turns) == 2
    assert not any(turn.answered for turn in report.turns)
    assert all(turn.confidence == 0.0 for turn in report.turns)


def test_clean_pair_reaches_high_confidence():
    messages = [
        _message("A_to_B", 0, 1.0),
        _message("B_to_A", 4, 1.02),
    ]
    turn = build_turns(messages, session_id="s1").turns[0]
    # base + opposite + order + window + framed + matched
    assert abs(turn.confidence - 0.95) < 1e-9
    assert any("opposite directions" in line for line in turn.basis)
    assert any("both messages matched the rule" in line for line in turn.basis)


def test_late_reply_is_not_within_the_window():
    messages = [
        _message("A_to_B", 0, 1.0),
        _message("B_to_A", 4, 30.0),
    ]
    turn = build_turns(messages, session_id="s1").turns[0]
    assert turn.gap_seconds == 29.0
    assert not any("within the" in line for line in turn.basis)
    assert turn.confidence < 0.95


def test_weak_framing_lowers_confidence():
    messages = [
        _message("A_to_B", 0, 1.0, status=Status.AMBIGUOUS),
        _message("B_to_A", 4, 1.02, status=Status.INCOMPLETE),
    ]
    turn = build_turns(messages, session_id="s1").turns[0]
    assert any("framing is weak" in line for line in turn.basis)
    assert turn.confidence < 0.95


def test_missing_timestamp_is_reported_and_penalised():
    messages = [
        _message("A_to_B", 0, None),
        _message("B_to_A", 4, None),
    ]
    turn = build_turns(messages, session_id="s1").turns[0]
    assert turn.gap_seconds is None
    assert any("timestamp is missing" in line for line in turn.basis)


def test_summary_counts_answered_and_low_confidence():
    report = PairingReport()
    report.turns.extend(
        build_turns(
            [
                _message("A_to_B", 0, 1.0),
                _message("B_to_A", 4, 1.02),
            ],
            session_id="s1",
        ).turns
    )
    report.turns.extend(
        build_turns(
            [
                _message("A_to_B", 0, 1.0),
                _message("B_to_A", 4, 9.0, status=Status.AMBIGUOUS),
            ],
            session_id="s2",
        ).turns
    )
    summary = report.summary()
    assert summary["turns"] == 2
    assert summary["answered"] == 2
    assert summary["high_confidence"] == 1
    assert 0.0 <= summary["mean_confidence"] <= 1.0


def test_corpus_pairs_within_a_session_only():
    streams = [
        ("s1", "A_to_B", [_message("A_to_B", 0, 1.0)]),
        ("s1", "B_to_A", [_message("B_to_A", 4, 1.01)]),
        ("s2", "A_to_B", [_message("A_to_B", 0, 3.0)]),
    ]
    report = build_turns_for_corpus(streams)
    by_session = {turn.session_id: turn for turn in report.turns}
    assert by_session["s1"].answered
    assert not by_session["s2"].answered


def test_to_dict_shape():
    messages = [
        _message("A_to_B", 0, 1.0),
        _message("B_to_A", 4, 1.02),
    ]
    payload = build_turns(messages, session_id="s1").to_dict()
    assert payload["kind"] == "request_response_pairing"
    assert payload["turns"][0]["request"]["direction"] == "A_to_B"
    assert payload["turns"][0]["response"]["direction"] == "B_to_A"
    assert payload["summary"]["answered"] == 1


def test_default_window_is_exposed():
    assert DEFAULT_WINDOW_SECONDS == 5.0
