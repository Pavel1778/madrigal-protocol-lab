"""Declarative interpretation rules.

A rule has a schema version, an identity, a version, a scope, a framing
description and an ordered list of fields. Every field is read from a fixed
offset inside a framed message. A field may carry an ``expected`` set (the
allowed values) and a ``hypothesis`` flag marking the value as an assumption
about the meaning of the bytes rather than an observation.

Rules are versioned. Editing anything that changes how messages are read or
checked produces a new ``rule_version``; old results that reference the previous
version become ``outdated`` (see :mod:`src.hypothesis.versioning`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace

RULE_SCHEMA_VERSION = 1

FIELD_TYPES = {
    "uint8": 1,
    "uint16": 2,
    "uint32": 4,
    "int8": 1,
    "int16": 2,
    "int32": 4,
}

# Field types read directly from the byte layout of a message.
DATA_FIELD_TYPES = set(FIELD_TYPES) | {
    "bytes",
    "enum",
    "bitmask",
    "string",
    "array",
    "padding",
}

# Field types that are checked against a computed value rather than extracted.
CHECK_FIELD_TYPES = {"checksum", "computed"}

# Fields whose presence depends on a condition evaluated against other fields.
CONDITIONAL_FIELD_TYPES = {"conditional"}

ALL_FIELD_TYPES = DATA_FIELD_TYPES | CHECK_FIELD_TYPES | CONDITIONAL_FIELD_TYPES

CONDITION_OPS = ("eq", "ne", "bit_set", "bit_clear", "gt", "lt")


class RuleError(ValueError):
    """Raised when a rule is malformed or unsupported."""


@dataclass
class FieldSpec:
    name: str
    offset: int
    type: str
    byte_order: str = "big"
    length: int | None = None
    enum: dict[str, int] | None = None
    hypothesis: bool = False
    expected: list | None = None
    missing_ok: bool = False
    # bitmask
    bit_offset: int = 0
    bit_length: int | None = None
    # string
    encoding: str = "ascii"
    terminated: bool = False
    # array
    element_type: str | None = None
    element_length: int | None = None
    count: int | None = None
    count_field: str | None = None
    # checksum / computed
    algorithm: str | None = None
    start: int | None = None
    end: int | None = None
    expression: dict | None = None
    # conditional
    condition: dict | None = None
    inner: "FieldSpec | None" = None

    @classmethod
    def from_dict(cls, raw: dict) -> "FieldSpec":
        if not isinstance(raw, dict):
            raise RuleError("field must be an object")
        name = raw.get("name")
        if not name:
            raise RuleError("field is missing 'name'")
        ftype = raw.get("type")
        if ftype not in ALL_FIELD_TYPES:
            raise RuleError(f"field {name!r} has unsupported type {ftype!r}")
        offset = int(raw.get("offset", 0))
        if offset < 0:
            raise RuleError(f"field {name!r} has a negative offset")
        byte_order = str(raw.get("byte_order", "big"))
        if byte_order not in ("big", "little"):
            raise RuleError(f"field {name!r} has unsupported byte_order {byte_order!r}")

        length = raw.get("length")
        enum = raw.get("enum")
        if ftype in ("bytes",):
            if length is None or int(length) < 0:
                raise RuleError(f"field {name!r} of type bytes needs a non-negative length")
            length = int(length)
        if ftype == "string":
            if length is None and not raw.get("terminated"):
                raise RuleError(
                    f"field {name!r} of type string needs 'length' or 'terminated'"
                )
            if length is not None:
                length = int(length)
        if ftype == "enum" and not isinstance(enum, dict):
            raise RuleError(f"field {name!r} of type enum needs an enum mapping")

        bit_length = raw.get("bit_length")
        if ftype == "bitmask":
            if bit_length is None or int(bit_length) <= 0:
                raise RuleError(f"field {name!r} of type bitmask needs a positive 'bit_length'")
            bit_length = int(bit_length)
            if int(raw.get("bit_offset", 0)) < 0:
                raise RuleError(f"field {name!r} has a negative bit_offset")

        element_type = raw.get("element_type")
        count = raw.get("count")
        count_field = raw.get("count_field")
        element_length = raw.get("element_length")
        if ftype == "array":
            if element_type not in FIELD_TYPES and element_type != "bytes":
                raise RuleError(
                    f"field {name!r} array element_type must be a numeric type or bytes"
                )
            if element_type == "bytes":
                if element_length is None:
                    raise RuleError(f"field {name!r} array of bytes needs 'element_length'")
                element_length = int(element_length)
            if count is None and count_field is None:
                raise RuleError(f"field {name!r} array needs 'count' or 'count_field'")
            if count is not None:
                count = int(count)
                if count < 0:
                    raise RuleError(f"field {name!r} array has a negative count")

        if ftype == "padding":
            if length is None or int(length) < 0:
                raise RuleError(f"field {name!r} of type padding needs a non-negative length")
            length = int(length)

        expression = raw.get("expression")
        algorithm = raw.get("algorithm")
        if ftype == "checksum":
            if algorithm not in ("xor", "sum", "crc8", "crc16"):
                raise RuleError(
                    f"field {name!r} checksum needs algorithm in xor|sum|crc8|crc16"
                )
            width = FIELD_TYPES.get(str(raw.get("length_type", "uint8")), 1)
            length = length if length is not None else width
            length = int(length)
        if ftype == "computed":
            if not isinstance(expression, dict):
                raise RuleError(f"field {name!r} of type computed needs an 'expression' object")
            expression = dict(expression)
            op = expression.get("op")
            if op not in ("sum_of_lengths", "sum_of_values", "const", "add", "sub", "xor"):
                raise RuleError(f"field {name!r} computed has unsupported op {op!r}")
            width = FIELD_TYPES.get(str(raw.get("length_type", "uint8")), 1)
            length = length if length is not None else width
            length = int(length)
            if length <= 0:
                raise RuleError(f"field {name!r} of type computed needs a positive length")

        inner = None
        condition = None
        if ftype == "conditional":
            condition = raw.get("condition")
            if not isinstance(condition, dict):
                raise RuleError(f"field {name!r} of type conditional needs a 'condition' object")
            op = condition.get("op")
            if op not in CONDITION_OPS:
                raise RuleError(f"field {name!r} condition has unsupported op {op!r}")
            if "field" not in condition:
                raise RuleError(f"field {name!r} condition needs a 'field' reference")
            condition = dict(condition)
            inner_raw = raw.get("field")
            if not isinstance(inner_raw, dict):
                raise RuleError(f"field {name!r} of type conditional needs a nested 'field'")
            inner = cls.from_dict(inner_raw)
            if inner.name in ("", None):
                raise RuleError(f"field {name!r} conditional inner field needs a name")
            offset = offset if "offset" in raw else inner.offset
            length = None

        expected = raw.get("expected")
        if expected is not None and not isinstance(expected, list):
            expected = [expected]
        return cls(
            name=str(name),
            offset=offset,
            type=str(ftype),
            byte_order=byte_order,
            length=length,
            enum={str(k): int(v) for k, v in enum.items()} if enum else None,
            hypothesis=bool(raw.get("hypothesis", False)),
            expected=expected,
            missing_ok=bool(raw.get("missing_ok", False)),
            bit_offset=int(raw.get("bit_offset", 0)),
            bit_length=bit_length,
            encoding=str(raw.get("encoding", "ascii")),
            terminated=bool(raw.get("terminated", False)),
            element_type=str(element_type) if element_type else None,
            element_length=int(element_length) if element_length is not None else None,
            count=int(count) if count is not None else None,
            count_field=str(count_field) if count_field else None,
            algorithm=str(algorithm) if algorithm else None,
            start=int(raw["start"]) if raw.get("start") is not None else None,
            end=int(raw["end"]) if raw.get("end") is not None else None,
            expression=expression,
            condition=condition,
            inner=inner,
        )

    @staticmethod
    def _size_of(ftype: str, length: int | None, element_type: str | None = None) -> int | None:
        if ftype in FIELD_TYPES:
            return FIELD_TYPES[ftype]
        if ftype == "enum":
            return 1
        if ftype in ("bytes", "string", "checksum", "padding", "computed"):
            return length
        return None

    def to_dict(self) -> dict:
        out: dict = {"name": self.name, "offset": self.offset, "type": self.type}
        if self.byte_order != "big" and self.type in set(FIELD_TYPES) | {"enum", "array", "bitmask"}:
            out["byte_order"] = self.byte_order
        if self.type in ("bytes", "string", "checksum", "padding") and self.length is not None:
            out["length"] = self.length
        if self.enum:
            out["enum"] = dict(self.enum)
        if self.type == "bitmask":
            out["bit_offset"] = self.bit_offset
            out["bit_length"] = self.bit_length
        if self.type == "string":
            out["encoding"] = self.encoding
            if self.terminated:
                out["terminated"] = True
        if self.type == "array":
            out["element_type"] = self.element_type
            if self.element_length is not None:
                out["element_length"] = self.element_length
            if self.count is not None:
                out["count"] = self.count
            if self.count_field is not None:
                out["count_field"] = self.count_field
        if self.type == "checksum":
            out["algorithm"] = self.algorithm
            if self.start is not None:
                out["start"] = self.start
            if self.end is not None:
                out["end"] = self.end
        if self.type == "computed":
            out["expression"] = dict(self.expression or {})
        if self.type == "conditional":
            out["condition"] = dict(self.condition or {})
            out["field"] = self.inner.to_dict() if self.inner else {}
        if self.hypothesis:
            out["hypothesis"] = True
        if self.expected is not None:
            out["expected"] = list(self.expected)
        if self.missing_ok:
            out["missing_ok"] = True
        return out

    @property
    def size(self) -> int:
        if self.type == "bitmask":
            bits = (self.bit_offset or 0) + (self.bit_length or 0)
            return max(1, (bits + 7) // 8)
        if self.type == "array":
            elem = self._size_of(self.element_type or "", self.element_length)
            if self.count is None or elem is None:
                raise RuleError(f"field {self.name!r} array has no fixed size")
            return self.count * elem
        if self.type == "conditional":
            if self.inner is None:
                raise RuleError(f"field {self.name!r} conditional has no inner field")
            return self.inner.size
        size = self._size_of(self.type, self.length)
        if size is None:
            raise RuleError(f"field {self.name!r} has no fixed size")
        return size

    def equals(self, other: "FieldSpec") -> bool:
        return self.to_dict() == other.to_dict()


@dataclass
class Rule:
    schema_version: int
    rule_id: str
    rule_version: int
    name: str
    scope: dict
    framing: dict
    fields: list[FieldSpec]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "name": self.name,
            "scope": dict(self.scope),
            "framing": dict(self.framing),
            "fields": [f.to_dict() for f in self.fields],
        }

    def bump_version(self, **changes) -> "Rule":
        """Return a copy of this rule with a new ``rule_version``."""
        updated = replace(self, **changes) if changes else self
        return replace(updated, rule_version=self.rule_version + 1)

    @property
    def direction(self) -> str | None:
        return self.scope.get("direction")

    def applies_to(self, direction: str) -> bool:
        scope_direction = self.direction
        return scope_direction is None or scope_direction == direction

    def is_out_of_date(self, result_rule_version: int) -> bool:
        return result_rule_version < self.rule_version

    def referenced_field_names(self) -> set[str]:
        """Names of fields other rules depend on (conditions, computed, counts)."""
        names: set[str] = set()
        for f in self.fields:
            if f.type == "conditional" and f.condition:
                names.add(str(f.condition.get("field")))
            if f.type == "array" and f.count_field:
                names.add(f.count_field)
            if f.type == "computed" and f.expression:
                for key in ("fields", "children"):
                    for ref in f.expression.get(key, []) or []:
                        names.add(str(ref))
                if f.expression.get("field"):
                    names.add(str(f.expression["field"]))
        names.discard("None")
        return names


def parse_rule(raw: dict) -> Rule:
    if not isinstance(raw, dict):
        raise RuleError("rule must be an object")
    for key in ("rule_id", "fields"):
        if key not in raw:
            raise RuleError(f"rule is missing {key!r}")
    schema_version = int(raw.get("schema_version", RULE_SCHEMA_VERSION))
    if schema_version != RULE_SCHEMA_VERSION:
        raise RuleError(f"unsupported rule schema_version {schema_version}")
    fields = [FieldSpec.from_dict(f) for f in raw.get("fields", [])]
    seen: set[str] = set()
    for f in fields:
        if f.name in seen:
            raise RuleError(f"duplicate field name {f.name!r}")
        seen.add(f.name)
    for f in fields:
        if f.type == "computed":
            for ref in (f.expression or {}).get("fields", []) or []:
                if ref not in seen:
                    raise RuleError(f"field {f.name!r} references unknown field {ref!r}")
        if f.type == "array" and f.count_field and f.count_field not in seen:
            raise RuleError(f"field {f.name!r} references unknown count_field {f.count_field!r}")
        if f.type == "conditional" and f.condition:
            ref = f.condition.get("field")
            if ref not in seen:
                raise RuleError(f"field {f.name!r} references unknown condition field {ref!r}")
    return Rule(
        schema_version=schema_version,
        rule_id=str(raw["rule_id"]),
        rule_version=int(raw.get("rule_version", 1)),
        name=str(raw.get("name", "")),
        scope=dict(raw.get("scope", {})),
        framing=dict(raw.get("framing", {"type": "manual"})),
        fields=fields,
    )


def load_rule(path: str) -> Rule:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    return parse_rule(load_rule_text(text))


def load_rule_text(text: str) -> dict:
    """Parse rule text as JSON; YAML is accepted when PyYAML is available."""
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return json.loads(text)
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised only without PyYAML
        raise RuleError("rule is not JSON and PyYAML is not installed") from exc
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise RuleError("rule text did not parse to an object")
    return data
