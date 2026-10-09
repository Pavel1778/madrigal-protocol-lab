"""Propose alternative explanations for a field flagged as a hypothesis.

A field marked ``hypothesis: true`` is named on a guess. This module asks a
different question: given the values that field actually takes across a corpus,
which *other* readings survive? It tests a fixed set of candidate meanings --
constant, counter, length, checksum, low-cardinality enum, alias of another
field, or a value seen in a journal -- and scores each by how many messages it
agrees with. The declared meaning is one candidate among them, and it may lose.

The output is the evidence, not a verdict: each alternative lists the messages
that support it and those that contradict it, so a human chooses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..protocol.checksums import ALGORITHMS, compute as checksum_compute
from ..protocol.engine import MessageResult
from ..protocol.rule import Rule


@dataclass
class Alternative:
    """One candidate explanation for a field, with its measured fit."""

    name: str
    description: str
    support: int
    contradict: int
    score: float
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "support": self.support,
            "contradict": self.contradict,
            "score": self.score,
            "evidence": self.evidence,
        }


@dataclass
class FieldAlternatives:
    field_name: str
    declared_meaning: str | None
    is_hypothesis: bool
    total: int
    alternatives: list[Alternative] = field(default_factory=list)
    best: str | None = None

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "declared_meaning": self.declared_meaning,
            "is_hypothesis": self.is_hypothesis,
            "total": self.total,
            "best": self.best,
            "alternatives": [a.to_dict() for a in self.alternatives],
        }


@dataclass
class AlternativesReport:
    rule_id: str
    rule_version: int
    fields: list[FieldAlternatives] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "fields": [f.to_dict() for f in self.fields],
        }


def _observed(messages: list[MessageResult], field_name: str):
    """Return (message, value) for every message where the field has a value."""
    out = []
    for message in messages:
        values = message.field_values()
        if field_name not in values:
            continue
        value = values[field_name]
        if value is None:
            continue
        out.append((message, value))
    return out


def _score(support: int, contradict: int) -> float:
    total = support + contradict
    if total <= 0:
        return 0.0
    return round(support / total, 6)


def _add(alternatives, name, description, checks, limit):
    support = 0
    contradict = 0
    evidence = []
    for message, value, ok, detail in checks:
        if ok:
            support += 1
            if len(evidence) < limit:
                evidence.append(
                    {"message_offset": message.offset, "value": value, "detail": detail}
                )
        else:
            contradict += 1
            if len(evidence) < limit:
                evidence.append(
                    {
                        "message_offset": message.offset,
                        "value": value,
                        "detail": detail,
                        "contradicts": True,
                    }
                )
    if support == 0 and contradict == 0:
        return
    alternatives.append(
        Alternative(
            name=name,
            description=description,
            support=support,
            contradict=contradict,
            score=_score(support, contradict),
            evidence=evidence,
        )
    )


def analyze_field(
    rule: Rule,
    messages: list[MessageResult],
    field_name: str,
    correlations: list | None = None,
    limit: int = 5,
) -> FieldAlternatives:
    """Test the candidate meanings of one field."""
    spec = next((f for f in rule.fields if f.name == field_name), None)
    if spec is None:
        raise ValueError(f"rule {rule.rule_id!r} has no field {field_name!r}")
    observations = _observed(messages, field_name)
    result = FieldAlternatives(
        field_name=field_name,
        declared_meaning=spec.name,
        is_hypothesis=spec.hypothesis,
        total=len(observations),
    )
    if not observations:
        return result

    values = [value for _, value in observations]
    numeric = all(isinstance(v, int) and not isinstance(v, bool) for v in values)
    alternatives: list[Alternative] = []

    # Constant: the field never varies.
    top = values[0]
    _add(
        alternatives,
        "constant",
        f"the field is always {top!r} in this corpus",
        [(m, v, v == top, f"expected {top!r}") for m, v in observations],
        limit,
    )

    # Counter / sequence: values step by a fixed amount.
    if numeric:
        steps = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        if steps:
            from collections import Counter

            step, step_count = Counter(steps).most_common(1)[0]
            if step_count >= max(1, len(steps) * 0.6) and step_count > 0:
                checks = []
                for index, (message, value) in enumerate(observations):
                    if index == 0:
                        continue
                    ok = value - values[index - 1] == step
                    checks.append((message, value, ok, f"expected step {step}"))
                _add(
                    alternatives,
                    "counter",
                    f"the field advances by {step} between successive messages",
                    checks,
                    limit,
                )

    # Length of the message, or of the region after the field.
    field_end = spec.offset + spec.size
    if numeric:
        _add(
            alternatives,
            "message_length",
            "the field equals the length of its message",
            [(m, v, v == m.length, f"message length {m.length}") for m, v in observations],
            limit,
        )
        _add(
            alternatives,
            "remaining_length",
            "the field equals the number of bytes after it in its message",
            [(m, v, v == m.length - field_end, f"{m.length - field_end} bytes follow") for m, v in observations],
            limit,
        )

        # Checksum over a candidate byte range.
        _test_checksums(alternatives, observations, spec, limit)

    # Low-cardinality: a small closed set of values looks like an enum or flags.
    distinct = sorted({v for v in values if isinstance(v, int)})
    if not distinct:
        distinct = sorted({v for v in values}, key=str)
    if distinct and len(distinct) <= max(2, int(len(observations) * 0.3)):
        _add(
            alternatives,
            "low_cardinality",
            f"the field takes only {len(distinct)} distinct value(s) {distinct}",
            [(m, v, v in distinct, f"one of {distinct}") for m, v in observations],
            limit,
        )

    # Alias of another field in the same message.
    other_names = [f.name for f in rule.fields if f.name != field_name]
    for other in other_names:
        checks = []
        for message, value in observations:
            other_value = message.field_values().get(other)
            checks.append((message, value, other_value == value, f"{other}={other_value!r}"))
        support = sum(1 for _, _, ok, _ in checks if ok)
        if support >= max(1, len(observations) * 0.8):
            _add(
                alternatives,
                f"alias_of_{other}",
                f"the field mirrors the value of {other!r}",
                checks,
                limit,
            )

    # Journal: the field agrees with an intended value recorded by the user.
    if correlations:
        _test_journal(alternatives, observations, correlations, limit)

    alternatives.sort(key=lambda a: (-a.score, a.name))
    result.alternatives = alternatives
    result.best = alternatives[0].name if alternatives else None
    return result


def _test_checksums(alternatives, observations, spec, limit) -> None:
    field_end = spec.offset + spec.size
    for algorithm in ALGORITHMS:
        ranges = {
            "whole_message": lambda data: data,
            "bytes_after_field": lambda data: data[field_end:],
            "bytes_before_field": lambda data: data[: spec.offset],
        }
        for label, select in ranges.items():
            checks = []
            for message, value in observations:
                data = bytes.fromhex(message.bytes_hex or "")
                span = select(data)
                if not span:
                    checks.append((message, value, False, f"{algorithm}: empty range"))
                    continue
                computed = checksum_compute(algorithm, span)
                checks.append(
                    (message, value, computed == value, f"{algorithm} computed {computed}")
                )
            support = sum(1 for _, _, ok, _ in checks if ok)
            if support >= max(1, len(observations) * 0.5):
                _add(
                    alternatives,
                    f"checksum_{algorithm}_{label}",
                    f"the field is a {algorithm} checksum over {label.replace('_', ' ')}",
                    checks,
                    limit,
                )


def _test_journal(alternatives, observations, correlations, limit) -> None:
    by_offset = {
        (c.message_offset, c.session_id): c for c in correlations
    }
    params: dict[str, list] = {}
    for correlation in correlations:
        for key, value in correlation.entry.params.items():
            params.setdefault(key, []).append(value)
    if not params:
        return
    for key, intended in params.items():
        checks = []
        for message, value in observations:
            correlation = by_offset.get((message.offset, message.session_id))
            ok = correlation is not None and correlation.entry.params.get(key) == value
            checks.append((message, value, ok, f"journal {key}={intended[0]!r}"))
        if any(ok for *_, ok, _ in checks):
            _add(
                alternatives,
                f"journal_{key}",
                f"the field matches the journal parameter {key!r}",
                checks,
                limit,
            )


def suggest_alternatives(
    rule: Rule,
    messages: list[MessageResult],
    correlations: list | None = None,
    limit: int = 5,
) -> AlternativesReport:
    """Analyse every field marked as a hypothesis in *rule*."""
    report = AlternativesReport(rule_id=rule.rule_id, rule_version=rule.rule_version)
    for spec in rule.fields:
        if not spec.hypothesis:
            continue
        report.fields.append(
            analyze_field(rule, messages, spec.name, correlations=correlations, limit=limit)
        )
    return report
