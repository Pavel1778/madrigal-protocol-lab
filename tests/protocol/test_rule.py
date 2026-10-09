import pytest

from src.protocol.rule import FieldSpec, RuleError, parse_rule


def _sample_rule():
    return {
        "schema_version": 1,
        "rule_id": "r1",
        "rule_version": 3,
        "name": "set_parameter_request",
        "scope": {"direction": "A_to_B"},
        "framing": {
            "type": "length_prefixed",
            "length_offset": 2,
            "length_size": 2,
            "byte_order": "big",
            "length_covers": "entire_message",
        },
        "fields": [
            {"name": "command", "offset": 0, "type": "uint8"},
            {"name": "flags", "offset": 1, "type": "uint8"},
            {"name": "payload_length", "offset": 2, "type": "uint16", "byte_order": "big"},
            {
                "name": "parameter_value",
                "offset": 4,
                "type": "uint16",
                "byte_order": "big",
                "hypothesis": True,
            },
        ],
    }


def test_parse_rule_keeps_identity_and_hypothesis_flag():
    rule = parse_rule(_sample_rule())
    assert rule.rule_id == "r1"
    assert rule.rule_version == 3
    assert rule.name == "set_parameter_request"
    assert rule.framing["type"] == "length_prefixed"
    value = next(f for f in rule.fields if f.name == "parameter_value")
    assert value.hypothesis is True
    command = next(f for f in rule.fields if f.name == "command")
    assert command.hypothesis is False


def test_field_sizes():
    rule = parse_rule(_sample_rule())
    sizes = {f.name: f.size for f in rule.fields}
    assert sizes["command"] == 1
    assert sizes["payload_length"] == 2
    assert sizes["parameter_value"] == 2


def test_round_trip_to_dict():
    rule = parse_rule(_sample_rule())
    again = parse_rule(rule.to_dict())
    assert [f.equals(g) for f, g in zip(rule.fields, again.fields)] == [True, True, True, True]


def test_bump_version():
    rule = parse_rule(_sample_rule())
    bumped = rule.bump_version()
    assert bumped.rule_version == 4
    assert rule.rule_version == 3  # original untouched


def test_scope_and_out_of_date():
    rule = parse_rule(_sample_rule())
    assert rule.applies_to("A_to_B") is True
    assert rule.applies_to("B_to_A") is False
    assert rule.is_out_of_date(2) is True
    assert rule.is_out_of_date(3) is False


def test_enum_and_bytes_fields():
    rule = parse_rule(
        {
            "rule_id": "r2",
            "framing": {"type": "fixed_size", "size": 4},
            "fields": [
                {"name": "kind", "offset": 0, "type": "enum", "enum": {"ping": 1, "pong": 2}},
                {"name": "blob", "offset": 1, "type": "bytes", "length": 3},
            ],
        }
    )
    assert rule.fields[0].size == 1
    assert rule.fields[1].size == 3


def test_invalid_cases():
    with pytest.raises(RuleError):
        parse_rule({"rule_id": "r", "fields": [{"name": "x", "offset": 0, "type": "uint64"}]})
    with pytest.raises(RuleError):
        parse_rule({"rule_id": "r", "fields": [{"name": "b", "offset": 0, "type": "bytes"}]})
    with pytest.raises(RuleError):
        parse_rule({"rule_id": "r", "fields": [{"name": "e", "offset": 0, "type": "enum"}]})
    with pytest.raises(RuleError):
        parse_rule(
            {
                "rule_id": "r",
                "fields": [
                    {"name": "x", "offset": 0, "type": "uint8"},
                    {"name": "x", "offset": 1, "type": "uint8"},
                ],
            }
        )
    with pytest.raises(RuleError):
        parse_rule({"fields": []})
    with pytest.raises(RuleError):
        parse_rule({"rule_id": "r", "schema_version": 99, "fields": []})


def test_field_expected_normalised_to_list():
    field = FieldSpec.from_dict({"name": "cmd", "offset": 0, "type": "uint8", "expected": 4})
    assert field.expected == [4]
