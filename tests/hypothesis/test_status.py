import pytest

from src.hypothesis.status import ALL_STATUSES, CORE_STATUSES, Status


def test_six_core_statuses_are_present():
    values = {s.value for s in CORE_STATUSES}
    assert values == {
        "matched",
        "mismatched",
        "incomplete",
        "ambiguous",
        "uncovered",
        "not_applicable",
    }


def test_extended_statuses_are_available():
    values = {s.value for s in ALL_STATUSES}
    assert "outdated" in values
    assert "unknown" in values


def test_status_from_value_round_trips():
    assert Status("matched") is Status.MATCHED
    assert Status(Status.MISMATCHED.value) is Status.MISMATCHED


def test_status_string_compare():
    assert Status.MATCHED == "matched"


def test_unknown_value_raises():
    with pytest.raises(ValueError):
        Status("nonsense")
