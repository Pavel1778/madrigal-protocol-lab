"""Verify a rule on a corpus and collect counterexamples.

A rule that fits the messages it was written against is not confirmed. It is
verified on a corpus of directional streams; every message that contradicts the
rule becomes a counterexample tied to a byte range. The report keeps the rule
identity and version so a later rule revision can be compared against it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..protocol.engine import Counterexample, MessageResult, apply_rule
from ..protocol.rule import Rule
from ..protocol.stream import DirectionalStream
from .status import ALL_STATUSES


@dataclass
class CorpusStream:
    """One labelled directional stream in a corpus."""

    stream: DirectionalStream
    session_id: str = ""
    direction: str = "A_to_B"

    @classmethod
    def from_bytes(cls, data: bytes, session_id: str = "", direction: str = "A_to_B") -> "CorpusStream":
        return cls(stream=DirectionalStream.from_bytes(data), session_id=session_id, direction=direction)


@dataclass
class VerificationReport:
    rule_id: str
    rule_version: int
    totals: dict = field(default_factory=dict)
    total: int = 0
    contradictions: list[Counterexample] = field(default_factory=list)
    messages: list[MessageResult] = field(default_factory=list)
    summary: str = ""
    stream_bytes: int = 0

    def counts(self) -> dict:
        return dict(self.totals)

    def is_confirmed(self) -> bool:
        """A rule is confirmed only when there are no contradictions."""
        return self.total > 0 and not self.contradictions

    @property
    def covered_bytes(self) -> int:
        """Bytes consumed by framed messages."""
        return sum(message.length for message in self.messages)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "total": self.total,
            "counts": self.counts(),
            "contradictions": [c.to_dict() for c in self.contradictions],
            "summary": self.summary,
            "stream_bytes": self.stream_bytes,
            "messages": [
                {
                    "offset": m.offset,
                    "length": m.length,
                    "session_id": m.session_id,
                    "direction": m.direction,
                    "status": m.status.value,
                    "fields": m.field_values(),
                    "bytes_hex": m.bytes_hex,
                }
                for m in self.messages
            ],
        }


def verify_on_corpus(
    rule: Rule,
    corpus: list[CorpusStream] | list[DirectionalStream],
) -> VerificationReport:
    """Apply *rule* to every stream in *corpus* and summarise the outcome."""
    items = [_coerce(item) for item in corpus]
    totals = {status.value: 0 for status in ALL_STATUSES}
    messages: list[MessageResult] = []
    contradictions: list[Counterexample] = []
    stream_bytes = 0

    for item in items:
        stream_bytes += len(item.stream.data)
        results = apply_rule(item.stream, rule, item.session_id, item.direction)
        for result in results:
            messages.append(result)
            totals[result.status.value] += 1
            counterexample = result.counterexample()
            if counterexample is not None and counterexample not in contradictions:
                contradictions.append(counterexample)

    summary = _describe(totals, contradictions)
    return VerificationReport(
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        totals=totals,
        total=len(messages),
        contradictions=contradictions,
        messages=messages,
        summary=summary,
        stream_bytes=stream_bytes,
    )


def _coerce(item) -> CorpusStream:
    if isinstance(item, CorpusStream):
        return item
    if isinstance(item, DirectionalStream):
        return CorpusStream(stream=item)
    if isinstance(item, bytes):
        return CorpusStream(stream=DirectionalStream.from_bytes(item))
    raise TypeError(f"cannot use {type(item)!r} as a corpus stream")


def _describe(totals: dict, contradictions: list[Counterexample]) -> str:
    matched = totals.get("matched", 0)
    mismatched = totals.get("mismatched", 0)
    if not contradictions:
        return f"{matched} messages matched, no counterexamples"
    return (
        f"{matched} messages matched, {len(contradictions)} counterexamples "
        f"({mismatched} mismatched)"
    )
