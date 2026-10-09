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
    """One labelled directional stream in a corpus.

    Args:
        stream: The directional stream.
        session_id: Session label carried onto every message result.
        direction: Direction label (``"A_to_B"`` or ``"B_to_A"``).
    """

    stream: DirectionalStream
    session_id: str = ""
    direction: str = "A_to_B"

    @classmethod
    def from_bytes(
        cls, data: bytes, session_id: str = "", direction: str = "A_to_B"
    ) -> "CorpusStream":
        """Wrap raw bytes as a labelled corpus stream.

        Args:
            data: The bytes of one direction.
            session_id: Session label for the stream.
            direction: Direction label for the stream.

        Returns:
            A corpus stream over a copy of ``data``.
        """
        return cls(
            stream=DirectionalStream.from_bytes(data),
            session_id=session_id,
            direction=direction,
        )


@dataclass
class VerificationReport:
    """The outcome of verifying one rule over a corpus.

    Attributes:
        rule_id: Identity of the verified rule.
        rule_version: Version of the verified rule.
        totals: Message count per status.
        total: Total messages framed over the corpus.
        contradictions: Counterexamples tied to byte ranges.
        messages: Every message result, for byte-level drill-down.
        summary: One-line human-readable summary.
        stream_bytes: Total bytes across all corpus streams.
    """

    rule_id: str
    rule_version: int
    totals: dict = field(default_factory=dict)
    total: int = 0
    contradictions: list[Counterexample] = field(default_factory=list)
    messages: list[MessageResult] = field(default_factory=list)
    summary: str = ""
    stream_bytes: int = 0

    def counts(self) -> dict:
        """Message count per status."""
        return dict(self.totals)

    def is_confirmed(self) -> bool:
        """Whether the rule is confirmed within the tested scope.

        Confirmation requires both that the rule actually applied to something
        and that nothing contradicted it. A report that is applicable nowhere
        (only ``not_applicable`` messages), or that is empty, is not a
        confirmation of the rule: it is evidence of nothing. This keeps
        "consistent in the tested scope" distinct from "proven".
        """
        if not self.is_relevant():
            return False
        return not self.contradictions

    def is_relevant(self) -> bool:
        """Whether the rule reached at least one message it applies to."""
        return self.totals.get("matched", 0) + self.totals.get("mismatched", 0) > 0

    @property
    def covered_bytes(self) -> int:
        """Bytes consumed by framed messages."""
        return sum(message.length for message in self.messages)

    def to_dict(self) -> dict:
        """Return the report as a JSON-ready mapping with per-message detail."""
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
    """Apply *rule* to every stream in *corpus* and summarise the outcome.

    Args:
        rule: The rule to verify.
        corpus: Labelled corpus streams, bare directional streams, or bytes.

    Returns:
        A report with per-status totals and the collected counterexamples.

    Raises:
        TypeError: If an item is not a corpus stream, a directional stream or
            bytes.
    """
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
