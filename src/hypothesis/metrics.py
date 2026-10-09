"""Quality metrics for a rule, computed from a verification report.

A rule is not simply "works" or "does not work". These metrics make its
behaviour measurable so two versions can be compared and so a report can state
how far a rule reaches over a corpus. Every ratio is in [0, 1] and every count
is taken from the report; nothing here re-runs the rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import VerificationReport


@dataclass
class RuleMetrics:
    """Quality metrics derived from one verification report.

    Attributes:
        rule_id: Identity of the measured rule.
        rule_version: Version of the measured rule.
        total_messages: Messages framed over the corpus.
        applicable_messages: Messages the rule scope covered.
        sessions: Distinct sessions seen.
        coverage: Applicable share of all messages, in [0, 1].
        precision: Matched share of the applicable messages, in [0, 1].
        fragmentation: Messages per session.
        unknown_ratio: Unknown share of all messages.
        uncovered_ratio: Share of stream bytes not covered by framing.
        counterexample_density: Counterexamples per applicable message.
        counterexamples: Number of distinct counterexamples.
        matched: Matched message count.
        mismatched: Mismatched message count.
        length_histogram: Message count keyed by message length.
        type_histogram: Message count keyed by the ``command`` field value.
    """

    rule_id: str
    rule_version: int
    total_messages: int
    applicable_messages: int
    sessions: int
    coverage: float
    precision: float
    fragmentation: float
    unknown_ratio: float
    uncovered_ratio: float
    counterexample_density: float
    counterexamples: int
    matched: int
    mismatched: int
    length_histogram: dict = field(default_factory=dict)
    type_histogram: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return the metrics as a JSON-ready mapping."""
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "total_messages": self.total_messages,
            "applicable_messages": self.applicable_messages,
            "sessions": self.sessions,
            "coverage": self.coverage,
            "precision": self.precision,
            "fragmentation": self.fragmentation,
            "unknown_ratio": self.unknown_ratio,
            "uncovered_ratio": self.uncovered_ratio,
            "counterexample_density": self.counterexample_density,
            "counterexamples": self.counterexamples,
            "matched": self.matched,
            "mismatched": self.mismatched,
            "length_histogram": dict(self.length_histogram),
            "type_histogram": dict(self.type_histogram),
        }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _session_ids(report: VerificationReport) -> list[str]:
    seen: list[str] = []
    for message in report.messages:
        sid = getattr(message, "session_id", "") or ""
        if sid and sid not in seen:
            seen.append(sid)
    return seen


def _field_histogram(report: VerificationReport, field_name: str) -> dict:
    counts: dict[str, int] = {}
    for message in report.messages:
        for f in message.fields:
            if f.field_name == field_name and f.value is not None:
                key = str(f.value)
                counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def compute_metrics(report: VerificationReport) -> RuleMetrics:
    """Derive the quality metrics of *report*."""
    total = report.total
    totals = report.totals
    not_applicable = totals.get("not_applicable", 0)
    matched = totals.get("matched", 0)
    mismatched = totals.get("mismatched", 0)
    unknown = totals.get("unknown", 0)
    applicable = total - not_applicable

    sessions = len(_session_ids(report))
    fragmentation = _ratio(total, sessions) if sessions else 0.0

    uncovered_ratio = 0.0
    if report.stream_bytes > 0:
        uncovered_ratio = round(
            max(0, report.stream_bytes - report.covered_bytes) / report.stream_bytes, 6
        )

    length_histogram: dict[int, int] = {}
    for message in report.messages:
        length_histogram[message.length] = length_histogram.get(message.length, 0) + 1

    return RuleMetrics(
        rule_id=report.rule_id,
        rule_version=report.rule_version,
        total_messages=total,
        applicable_messages=applicable,
        sessions=sessions,
        coverage=_ratio(applicable, total),
        precision=_ratio(matched, matched + mismatched),
        fragmentation=round(fragmentation, 6),
        unknown_ratio=_ratio(unknown, total),
        uncovered_ratio=uncovered_ratio,
        counterexample_density=round(len(report.contradictions) / applicable * 100, 6) if applicable else 0.0,
        counterexamples=len(report.contradictions),
        matched=matched,
        mismatched=mismatched,
        length_histogram=dict(sorted(length_histogram.items())),
        type_histogram=_field_histogram(report, "command"),
    )
