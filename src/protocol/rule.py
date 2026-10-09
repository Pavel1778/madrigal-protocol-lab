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

# Fields whose interpreted value is fully determined by the byte layout.
DATA_FIELD_TYPES = set(FIELD_TYPES) | {"bytes", "enum"}


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

    @classmethod
    def from_dict(cls, raw: dict) -> "FieldSpec":
        if not isinstance(raw, dict):
            raise RuleError("field must be an object")
        name = raw.get("name")
        if not name:
            raise RuleError("field is missing 'name'")
        ftype = raw.get("type")
        if ftype not in DATA_FIELD_TYPES:
            raise RuleError(f"field {name!r} has unsupported type {ftype!r}")
        offset = int(raw.get("offset", 0))
        if offset < 0:
            raise RuleError(f"field {name!r} has a negative offset")
        byte_order = str(raw.get("byte_order", "big"))
        if byte_order not in ("big", "little"):
            raise RuleError(f"field {name!r} has unsupported byte_order {byte_order!r}")
        length = raw.get("length")
        if ftype == "bytes":
            if length is None or int(length) < 0:
                raise RuleError(f"field {name!r} of type bytes needs a non-negative length")
            length = int(length)
        enum = raw.get("enum")
        if ftype == "enum" and not isinstance(enum, dict):
            raise RuleError(f"field {name!r} of type enum needs an enum mapping")
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
        )

    def to_dict(self) -> dict:
        out: dict = {"name": self.name, "offset": self.offset, "type": self.type}
        if self.type in FIELD_TYPES and self.byte_order != "big":
            out["byte_order"] = self.byte_order
        if self.type == "bytes" and self.length is not None:
            out["length"] = self.length
        if self.enum:
            out["enum"] = dict(self.enum)
        if self.hypothesis:
            out["hypothesis"] = True
        if self.expected is not None:
            out["expected"] = list(self.expected)
        if self.missing_ok:
            out["missing_ok"] = True
        return out

    @property
    def size(self) -> int:
        if self.type in FIELD_TYPES:
            return FIELD_TYPES[self.type]
        if self.type == "enum":
            return 1
        if self.type == "bytes":
            return int(self.length or 0)
        raise RuleError(f"field {self.name!r} has no fixed size")

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
