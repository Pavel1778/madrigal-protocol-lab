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

    # Encoding alternatives: is the field read the wrong way, from the wrong
    # place, masked, or stored as a step rather than an absolute value?
    if numeric:
        _test_endianness(alternatives, observations, spec, limit)
        _test_offset_shift(alternatives, observations, spec, limit)
        _test_xor_mask(alternatives, observations, limit)
        _test_delta_encoding(alternatives, observations, limit)

    alternatives.sort(key=lambda a: (-a.score, a.name))
    result.alternatives = alternatives
    result.best = alternatives[0].name if alternatives else None
    return result


def _raw_slice(message: MessageResult, offset: int, width: int) -> bytes | None:
    """The raw bytes a field claims, or None when they are not available."""
    data = bytes.fromhex(message.bytes_hex or "")
    if width <= 0 or offset < 0 or offset + width > len(data):
        return None
    return data[offset : offset + width]


def _is_unit_step(values: list[int]) -> list[bool]:
    """True at index i when the value is one greater than at index i-1."""
    out = []
    for index, value in enumerate(values):
        if index == 0:
            out.append(True)
        else:
            out.append(value - values[index - 1] == 1)
    return out


def _all_unit_step(values: list[int]) -> bool:
    """True when every consecutive difference is exactly one."""
    if len(values) < 3:
        return False
    return all(values[i + 1] - values[i] == 1 for i in range(len(values) - 1))


def _test_endianness(alternatives, observations, spec, limit) -> None:
    """The field may be little-endian even though the rule reads it big-endian.

    The signature of a counter stored the other way round is that the same
    bytes read little-endian advance by exactly one per message while the
    declared big-endian reading does not.
    """
    width = spec.size
    if width < 2:
        return
    little_values = []
    for message, _ in observations:
        raw = _raw_slice(message, spec.offset, width)
        if raw is None:
            return
        little_values.append(int.from_bytes(raw, "little"))
    big_values = [v for _, v in observations]
    if not _all_unit_step(little_values) or _all_unit_step(big_values):
        return
    checks = [
        (message, value, True, f"little-endian reading {little_values[index]}")
        for index, (message, value) in enumerate(observations)
    ]
    _add(
        alternatives,
        "endianness",
        "the field reads as little-endian rather than big-endian",
        checks,
        limit,
    )


def _test_offset_shift(alternatives, observations, spec, limit) -> None:
    """The field may start one byte earlier or later than the rule says."""
    width = spec.size
    if width < 1:
        return
    for shift in (1, -1):
        offset = spec.offset + shift
        shifted = []
        available = True
        for message, _ in observations:
            raw = _raw_slice(message, offset, width)
            if raw is None:
                available = False
                break
            shifted.append(int.from_bytes(raw, spec.byte_order))
        if not available or len(set(shifted)) != 1:
            continue
        if len({v for _, v in observations}) == 1:
            # The declared offset is already constant; a shift proves nothing.
            continue
        checks = [
            (
                message,
                value,
                shifted[index] == shifted[0],
                f"value at offset {offset} is {shifted[index]}",
            )
            for index, (message, value) in enumerate(observations)
        ]
        sign = "+" if shift > 0 else "-"
        _add(
            alternatives,
            f"offset_shift_{sign}1",
            f"the field starts at offset {offset} instead of {spec.offset} "
            "and is constant there",
            checks,
            limit,
        )


def _test_xor_mask(alternatives, observations, limit) -> None:
    """The field may be masked with a constant byte.

    A mask is proposed when the declared values are not already a unit step but
    some constant makes them one. Several masks can fit; the one that maps the
    sequence onto the lowest values (nearest zero) is reported, since it is the
    smallest shift that explains the data.
    """
    values = [v for _, v in observations]
    if _all_unit_step(values):
        # The declared reading is already the simplest sequence; nothing to add.
        return
    best = None
    for mask in range(1, 256):
        masked = [v ^ mask for v in values]
        if _all_unit_step(masked) or len(set(masked)) == 1:
            key = min(masked)
            if best is None or key < best[0]:
                best = (key, mask, masked)
    if best is None:
        return
    _, mask, masked = best
    checks = [
        (
            message,
            value,
            index == 0 or masked[index] - masked[index - 1] == 1,
            f"value xor {mask} is {masked[index]}",
        )
        for index, (message, value) in enumerate(observations)
    ]
    _add(
        alternatives,
        f"xor_mask_{mask}",
        f"the field is the stored value xor {mask}",
        checks,
        limit,
    )


def _test_delta_encoding(alternatives, observations, limit) -> None:
    """The field may store the step since the previous message, not the value.

    The running sum is the quantity of interest; the reading is supported when
    that running sum advances by exactly one per message.
    """
    values = [v for _, v in observations]
    running = []
    total = 0
    for value in values:
        total += value
        running.append(total)
    steps = _is_unit_step(running)
    if sum(steps[1:]) <= len(running) // 2:
        return
    checks = [
        (message, value, ok, f"running sum {running[index]}")
        for index, ((message, value), ok) in enumerate(zip(observations, steps))
    ]
    _add(
        alternatives,
        "delta_encoding",
        "the field is the step since the previous message; the running sum "
        "advances by one",
        checks,
        limit,
    )


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
