"""Statistical alternative readings: entropy, periodicity, bit pattern, delta.

These functions summarize how a numeric field varies rather than what value it
carries. Each is tested on its own and through ``analyze_field``, so a wrong
reading of the data shows up as a wrong candidate in the alternatives list.
"""

from __future__ import annotations

import math

from src.hypothesis.alternatives import (
    analyze_field,
    bit_pattern,
    delta_correlation,
    entropy,
    periodicity,
)
from src.protocol.engine import apply_rule
from src.protocol.rule import parse_rule
from src.protocol.stream import DirectionalStream


def _rule(fields, size=8):
    return parse_rule(
        {"rule_id": "r1", "framing": {"type": "fixed_size", "size": size}, "fields": fields}
    )


def _messages(rule, payloads):
    stream = DirectionalStream.from_bytes(b"".join(payloads))
    return apply_rule(stream, rule)


def _uint8_field(values, hypothesis=True):
    rule = _rule([{"name": "value", "offset": 0, "type": "uint8", "hypothesis": hypothesis}])
    payloads = [bytes([value]) + b"\x00" * 7 for value in values]
    return rule, _messages(rule, payloads)


def _names(report):
    return {a.name for a in report.alternatives}


# --- entropy ---------------------------------------------------------------


def test_entropy_zero_for_constant_and_one_bit_for_two_values():
    assert entropy([5, 5, 5, 5]) == 0.0
    assert entropy([1, 2, 1, 2]) == 1.0


def test_entropy_matches_the_shannon_formula_for_a_uniform_spread():
    values = list(range(16))  # 16 equiprobable values, 4 bits each
    assert entropy(values) == 4.0
    # Half the values appear twice: entropy falls below the uniform 4 bits.
    skewed = values + values[:8]
    assert entropy(skewed) < 4.0


def test_entropy_ignores_non_numeric_values():
    assert entropy([b"\x01\x02", None, "x"]) == 0.0


def test_analyze_field_offers_an_entropy_band_for_a_small_closed_set():
    rule, messages = _uint8_field([1, 2, 1, 2, 1, 2, 1, 2])
    report = analyze_field(rule, messages, "value")
    assert "entropy_enum" in _names(report)
    enum = next(a for a in report.alternatives if a.name == "entropy_enum")
    assert enum.score == 1.0
    assert "bits/value" in enum.evidence[0]["detail"]


# --- periodicity -----------------------------------------------------------


def test_periodicity_finds_a_repeating_lag():
    assert periodicity([1, 2, 3] * 5) == 3
    assert periodicity([7, 8, 9, 10] * 5) == 4


def test_periodicity_is_none_for_a_monotone_counter_and_a_constant():
    # A plain ramp correlates with itself at every short lag; there is no
    # meaningful period, so nothing should be reported.
    assert periodicity(list(range(1, 21))) is None
    assert periodicity([7] * 12) is None


def test_analyze_field_reports_a_period_when_the_values_repeat():
    rule, messages = _uint8_field([1, 2, 3] * 4)
    report = analyze_field(rule, messages, "value")
    assert "periodicity" in _names(report)
    candidate = next(a for a in report.alternatives if a.name == "periodicity")
    assert candidate.support >= 3
    assert "3 messages" in candidate.description


# --- bit pattern -----------------------------------------------------------


def test_bit_pattern_detects_stable_high_bits():
    # Top bits fixed at 0x40's leading bits, low bits sweeping 0..7.
    values = [0x40 | i for i in range(8)]
    pattern = bit_pattern(values, 4)
    assert pattern["verdict"] == "flags_high"
    assert pattern["stable_ratio"] == 1.0
    assert pattern["distinct_high_values"] == 1


def test_bit_pattern_is_inconclusive_when_the_field_uses_few_bits():
    # With values below 2**4 the top 4 bits are the whole value, so the reading
    # would only restate the field being constant.
    pattern = bit_pattern([1, 2, 3, 1, 2, 3], 4)
    assert pattern["verdict"] == "inconclusive"
    assert pattern["shift"] == 0


def test_analyze_field_offers_a_bit_pattern_reading():
    values = [0x40 | i for i in range(8)]
    rule, messages = _uint8_field(values)
    report = analyze_field(rule, messages, "value")
    assert "bit_pattern_4" in _names(report)
    candidate = next(a for a in report.alternatives if a.name == "bit_pattern_4")
    assert candidate.score == 1.0


# --- delta correlation -----------------------------------------------------


def test_delta_correlation_flags_a_constant_step():
    reading = delta_correlation([1, 3, 5, 7, 9, 11])
    assert reading["verdict"] == "delta"
    assert reading["mean_step"] == 2.0
    assert reading["cv"] == 0.0


def test_delta_correlation_rejects_an_irregular_step():
    reading = delta_correlation([1, 5, 2, 9, 3, 20])
    assert reading["verdict"] == "contradict"
    assert reading["cv"] is not None and reading["cv"] > 0.5


def test_analyze_field_offers_a_delta_reading_for_a_regular_step():
    rule, messages = _uint8_field([1, 3, 5, 7, 9, 11, 13])
    report = analyze_field(rule, messages, "value")
    assert "delta_correlation" in _names(report)
    candidate = next(a for a in report.alternatives if a.name == "delta_correlation")
    assert candidate.score == 1.0
    assert math.isclose(float(candidate.evidence[0]["detail"].split()[-1]), 2.0)
