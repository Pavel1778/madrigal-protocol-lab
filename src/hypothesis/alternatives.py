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

import math
from collections import Counter
from dataclasses import dataclass, field

from ..protocol.checksums import ALGORITHMS, compute as checksum_compute
from ..protocol.engine import MessageResult
from ..protocol.rule import Rule


@dataclass
class Alternative:
    """One candidate explanation for a field, with its measured fit.

    Attributes:
        name: Machine-readable candidate name (for example ``"counter"``).
        description: Human-readable one-line description.
        support: Messages the candidate agrees with.
        contradict: Messages the candidate disagrees with.
        score: ``support / (support + contradict)`` in [0, 1].
        evidence: A bounded sample of supporting and contradicting messages.
    """

    name: str
    description: str
    support: int
    contradict: int
    score: float
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return the alternative as a JSON-ready mapping."""
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
    """All candidate explanations tested for one field.

    Attributes:
        field_name: The analysed field.
        declared_meaning: The meaning the rule assigns (the field name).
        is_hypothesis: Whether the rule flagged the meaning as an assumption.
        total: Messages where the field had a value.
        alternatives: Candidates, sorted by score descending.
        best: Name of the highest-scoring candidate, or ``None``.
    """

    field_name: str
    declared_meaning: str | None
    is_hypothesis: bool
    total: int
    alternatives: list[Alternative] = field(default_factory=list)
    best: str | None = None

    def to_dict(self) -> dict:
        """Return the field's alternatives as a JSON-ready mapping."""
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
    """The alternatives test for every hypothesis field of one rule.

    Args:
        rule_id: Identity of the analysed rule.
        rule_version: Version of the analysed rule.
        fields: Per-field alternatives for each ``hypothesis`` field.
    """

    rule_id: str
    rule_version: int
    fields: list[FieldAlternatives] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return the report as a JSON-ready mapping."""
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
    """Test the candidate meanings of one field.

    Args:
        rule: The rule the field belongs to.
        messages: Messages already decoded with ``rule``.
        field_name: The field to analyse.
        correlations: Optional journal correlations for the journal candidate.
        limit: Maximum evidence entries kept per candidate.

    Returns:
        The field's alternatives, sorted by score descending.

    Raises:
        ValueError: If ``rule`` has no field named ``field_name``.
    """
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

    # Statistical readings: distribution, repetition, leading-bit stability and
    # step regularity. These need only the values, not the message bytes.
    _test_entropy(alternatives, observations, limit)
    _test_periodicity(alternatives, observations, limit)
    _test_bit_pattern(alternatives, observations, limit)
    _test_delta_correlation(alternatives, observations, limit)

    alternatives.sort(key=lambda a: (-a.score, a.name))
    result.alternatives = alternatives
    result.best = alternatives[0].name if alternatives else None
    return result


def entropy(field_values: list) -> float:
    """Shannon entropy of a field, in bits per value.

    This is an interpretability measure, not a statistical test: it says how
    many bits on average are needed to describe one value, which is a direct
    read on how much the field varies. Only integers are read; bytes and enums
    are out of scope because their bit width is not a property of the value.

    Banding, used when the function is turned into a candidate reading:

    - more than 6 bits per value: a nonce, hash or random field;
    - 3 to 6 bits: a parameter that changes, such as a counter or a measurement;
    - fewer than 2 bits: a closed set of values, an enum or flags.

    Args:
        field_values: The observed values. Non-integers are ignored.

    Returns:
        Entropy in bits per value, rounded to six decimals. ``0.0`` when fewer
        than two values remain or all of them are equal.
    """
    values = _integer_values(field_values)
    if len(values) < 2:
        return 0.0
    return round(_shannon_entropy(values), 6)


def periodicity(field_values: list) -> int | None:
    """Autocorrelation lag at which a numeric field repeats, if any.

    Values are centre-reduced and correlated against themselves at each lag; a
    lag is reported only when its correlation is a local peak that stands clear
    of the neighbouring lags, so noise does not register as a cycle and the
    broad, slowly falling autocorrelation of a plain ramp or counter does not
    either. A real period points at a counter that wraps, a packet or sequence
    number, or a timestamp with a fixed step.

    Args:
        field_values: The observed values. Non-integers are ignored.

    Returns:
        The smallest repeating lag in messages (at least 2), or ``None`` when no
        clear period is found or fewer than four values are available.
    """
    values = _integer_values(field_values)
    if len(values) < 4:
        return None
    mean = sum(values) / len(values)
    centred = [value - mean for value in values]
    if not any(centred):
        return None
    max_lag = len(values) // 2
    correlations = {1: 1.0}
    for lag in range(2, max_lag + 1):
        correlations[lag] = _autocorrelation(centred, lag)
    for lag in range(2, max_lag + 1):
        r = correlations[lag]
        if r < 0.7:
            continue
        left = correlations.get(lag - 1, float("-inf"))
        right = correlations.get(lag + 1, float("-inf"))
        if r - max(left, right) < 0.1:
            continue
        return lag
    return None


def _autocorrelation(centred: list, lag: int) -> float:
    """Normalised autocorrelation of *centred* at *lag* (0 for a flat tail)."""
    if lag <= 0 or lag >= len(centred):
        return 0.0
    pairs = [(centred[i], centred[i - lag]) for i in range(lag, len(centred))]
    numerator = sum(a * b for a, b in pairs)
    pair_energy = sum(b * b for _, b in pairs)
    denominator = sum(x * x for x in centred)
    if pair_energy == 0 or denominator == 0:
        return 0.0
    return numerator / math.sqrt(denominator * pair_energy)


def bit_pattern(field_values: list, bit_count: int = 4) -> dict:
    """Stability of the high-order bits of a numeric field.

    Some fields pack a flag or a small enum into their high-order bits and a
    value into the rest. For a given bit width ``n`` this reports how often the
    top ``n`` bits are identical across messages, which is the signature of such
    a split. Meant to be called for ``n`` in ``(2, 4, 6)``.

    The bit width of the field is taken from the largest observed value. When
    the field does not use more than ``n`` bits, the top ``n`` bits are the whole
    value and the reading would only restate ``constant``, so the verdict is
    ``"inconclusive"``.

    Args:
        field_values: The observed values. Non-integers are ignored.
        bit_count: Number of high-order bits to inspect, at least 1.

    Returns:
        A mapping with ``bit_count``, ``field_bit_width``, ``shift``, ``total``,
        ``stable`` (messages whose top bits equal the first value's),
        ``stable_ratio``, ``distinct_high_values`` and ``verdict`` --
        ``"flags_high"`` when more than 90 percent are stable (a flag or enum in
        the high bits), ``"contradict"`` when 50 percent or fewer are (the
        reading does not hold), otherwise ``"inconclusive"``.
    """
    values = _integer_values(field_values)
    width = max(1, int(bit_count))
    empty = {
        "bit_count": width,
        "field_bit_width": 0,
        "shift": 0,
        "total": 0,
        "stable": 0,
        "stable_ratio": 0.0,
        "distinct_high_values": 0,
        "verdict": "inconclusive",
    }
    if not values:
        return empty
    field_width = max(value.bit_length() for value in values)
    shift = field_width - width
    if shift <= 0:
        return {**empty, "field_bit_width": field_width}
    high = [value >> shift for value in values]
    stable = sum(1 for value in high if value == high[0])
    ratio = round(stable / len(high), 6)
    if ratio > 0.9:
        verdict = "flags_high"
    elif ratio <= 0.5:
        verdict = "contradict"
    else:
        verdict = "inconclusive"
    return {
        "bit_count": width,
        "field_bit_width": field_width,
        "shift": shift,
        "total": len(high),
        "stable": stable,
        "stable_ratio": ratio,
        "distinct_high_values": len(set(high)),
        "verdict": verdict,
    }


def delta_correlation(field_values: list) -> dict:
    """Regularity of the step between consecutive values.

    The coefficient of variation of the first differences (their standard
    deviation over their mean) measures how constant the step is. A small value
    means every message advances by nearly the same amount, which is a delta
    encoding or a fixed step. A large value means the step varies and the
    reading does not hold.

    Args:
        field_values: The observed values. Non-integers are ignored.

    Returns:
        A mapping with ``total`` (number of differences), ``mean_step``,
        ``std_step``, ``cv`` and ``verdict`` -- ``"delta"`` when ``cv < 0.1``,
        ``"contradict"`` when ``cv > 0.5``, otherwise ``"inconclusive"``.
    """
    values = _integer_values(field_values)
    steps = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    if not steps:
        return {"total": 0, "mean_step": 0.0, "std_step": 0.0, "cv": 0.0, "verdict": "inconclusive"}
    mean = sum(steps) / len(steps)
    std = math.sqrt(sum((step - mean) ** 2 for step in steps) / len(steps))
    if mean == 0:
        cv = 0.0 if std == 0 else float("inf")
    else:
        cv = abs(std / mean)
    if cv < 0.1:
        verdict = "delta"
    elif cv > 0.5:
        verdict = "contradict"
    else:
        verdict = "inconclusive"
    return {
        "total": len(steps),
        "mean_step": round(mean, 6),
        "std_step": round(std, 6),
        "cv": round(cv, 6) if math.isfinite(cv) else None,
        "verdict": verdict,
    }


def _integer_values(field_values: list) -> list[int]:
    """Keep the integers in *field_values*, dropping booleans and the rest."""
    return [v for v in field_values if isinstance(v, int) and not isinstance(v, bool)]


def _shannon_entropy(values: list[int]) -> float:
    """Shannon entropy of a list of integers, in bits per value."""
    counts = Counter(values)
    total = len(values)
    entropy_bits = 0.0
    for count in counts.values():
        probability = count / total
        entropy_bits -= probability * math.log2(probability)
    return entropy_bits


def _entropy_readings(values: list[int]) -> list[tuple[str, str, bool, str]]:
    """Banded readings of the entropy of *values* (random / parameter / enum)."""
    bits = _shannon_entropy(values)
    readings = [
        ("entropy_random", "nonce, hash or random", bits > 6.0, f"{bits:.2f} bits/value"),
        ("entropy_parameter", "value that changes between messages", 3.0 <= bits <= 6.0, f"{bits:.2f} bits/value"),
        ("entropy_enum", "closed set of values (enum or flags)", bits < 2.0, f"{bits:.2f} bits/value"),
    ]
    return readings


def _test_entropy(alternatives, observations, limit) -> None:
    """Offer the entropy-band reading as a candidate, if a band fits."""
    values = [v for _, v in observations if isinstance(v, int) and not isinstance(v, bool)]
    if len(values) < 2:
        return
    for name, description, holds, detail in _entropy_readings(values):
        if not holds:
            continue
        checks = [(message, value, holds, detail) for message, value in observations]
        _add(alternatives, name, f"the field's spread suggests a {description}", checks, limit)


def _period_agreement(values: list[int], lag: int) -> list[tuple[int, bool]]:
    """Per-index (value, agrees-with-value-at-lag) for a candidate period."""
    return [(value, index < lag or value == values[index - lag]) for index, value in enumerate(values)]


def _test_periodicity(alternatives, observations, limit) -> None:
    """Offer a detected period as a candidate, if one stands out."""
    values = [v for _, v in observations if isinstance(v, int) and not isinstance(v, bool)]
    lag = periodicity(values)
    if lag is None:
        return
    agreement = _period_agreement(values, lag)
    checks = [
        (message, value, ok, f"matches the value {lag} messages earlier")
        for (message, value), (_, ok) in zip(observations, agreement)
    ]
    _add(
        alternatives,
        "periodicity",
        f"the field repeats every {lag} messages",
        checks,
        limit,
    )


def _test_bit_pattern(alternatives, observations, limit) -> None:
    """Offer a high-order-bit reading when the top bits are stable."""
    values = [v for _, v in observations if isinstance(v, int) and not isinstance(v, bool)]
    if len(values) < 2:
        return
    for width in (2, 4, 6):
        pattern = bit_pattern(values, width)
        if pattern["verdict"] != "flags_high":
            continue
        shift = pattern["shift"]
        top = max(values) >> shift
        checks = [
            (message, value, (value >> shift) == top, f"top {width} bits are {top}")
            for message, value in observations
        ]
        _add(
            alternatives,
            f"bit_pattern_{width}",
            f"the top {width} bits stay constant; a flag or enum there, "
            "the value in the low bits",
            checks,
            limit,
        )


def _test_delta_correlation(alternatives, observations, limit) -> None:
    """Offer a constant-step reading when the first differences are regular."""
    values = [v for _, v in observations if isinstance(v, int) and not isinstance(v, bool)]
    if len(values) < 3:
        return
    reading = delta_correlation(values)
    if reading["verdict"] != "delta":
        return
    mean = reading["mean_step"]
    checks = [
        (
            message,
            value,
            index == 0 or (values[index] - values[index - 1]) == mean,
            f"step {mean}",
        )
        for index, (message, value) in enumerate(observations)
    ]
    _add(
        alternatives,
        "delta_correlation",
        f"consecutive values differ by a near-constant {mean}",
        checks,
        limit,
    )


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
    """Analyse every field marked as a hypothesis in *rule*.

    Args:
        rule: The rule to analyse.
        messages: Messages already decoded with ``rule``.
        correlations: Optional journal correlations.
        limit: Maximum evidence entries kept per candidate.

    Returns:
        One :class:`FieldAlternatives` per ``hypothesis`` field.
    """
    report = AlternativesReport(rule_id=rule.rule_id, rule_version=rule.rule_version)
    for spec in rule.fields:
        if not spec.hypothesis:
            continue
        report.fields.append(
            analyze_field(rule, messages, spec.name, correlations=correlations, limit=limit)
        )
    return report
