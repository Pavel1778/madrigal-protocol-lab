"""Serialise rule application results into the contract result format.

The result is the hand-off to the UI: it pairs every interpreted message with
the byte range it occupies, plus a per-status summary. The writer validates the
result against ``docs/schemas/result.schema.json`` when jsonschema is available
so a schema drift is caught before the file leaves the engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..hypothesis.status import ALL_STATUSES, Status
from .engine import MessageResult
from .rule import Rule

CONTRACT_VERSION = 1

@dataclass
class ApplicationResult:
    """The contract-shaped result of applying one rule to one capture.

    Attributes:
        rule_id: Identity of the applied rule.
        rule_version: Version of the applied rule.
        capture_id: Identity of the capture the rule ran on.
        messages: Per-message mappings in the contract result format.
        summary: Counts per status over ``messages``.
    """

    rule_id: str
    rule_version: int
    capture_id: str
    messages: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return the result in the contract result format."""
        return {
            "contract_version": CONTRACT_VERSION,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "capture_id": self.capture_id,
            "messages": self.messages,
            "summary": self.summary,
        }


def summarise(messages: list[MessageResult]) -> dict:
    """Count messages per status, always including the contract keys."""
    summary = {status.value: 0 for status in ALL_STATUSES}
    for message in messages:
        summary[message.status.value] += 1
    # The contract fixes these keys; keep them even if absent from ALL_STATUSES.
    for required in ("matched", "mismatched", "unknown", "uncovered"):
        summary.setdefault(required, 0)
    return summary


def _message_dict(message: MessageResult) -> dict:
    out: dict = {
        "offset": message.offset,
        "length": message.length,
        "fields": message.field_values(),
        "status": message.status.value,
    }
    provenance = _message_provenance(message)
    if provenance is not None:
        out["provenance_range"] = provenance
    return out


def _message_provenance(message: MessageResult) -> dict | None:
    for f in message.fields:
        if f.provenance_range:
            return {
                "offset": message.offset,
                "length": message.length,
                "packets": f.provenance_range.get("packets", []),
            }
    return None


def build_result(
    rule: Rule,
    capture_id: str,
    messages: list[MessageResult],
) -> ApplicationResult:
    """Assemble the contract result for one rule application.

    Args:
        rule: The rule that produced ``messages``.
        capture_id: Identity of the capture the rule ran on.
        messages: Message results produced by :func:`apply_rule`.

    Returns:
        The result, with a per-status summary.
    """
    return ApplicationResult(
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        capture_id=capture_id,
        messages=[_message_dict(m) for m in messages],
        summary=summarise(messages),
    )


def write_result(result: ApplicationResult, path: str, validate: bool = True) -> None:
    """Write a result as JSON, optionally validating it against the schema.

    Args:
        result: The result to write.
        path: Destination file path.
        validate: Whether to validate against the result JSON Schema first.

    Raises:
        jsonschema.ValidationError: If ``validate`` is set and the payload does
            not match the schema.
        OSError: If the file cannot be written.
    """
    payload = result.to_dict()
    if validate:
        validate_result(payload)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def validate_result(payload: dict, schema_path: str | None = None) -> None:
    """Validate a result payload against ``result.schema.json``.

    Validation is skipped (not failed) when jsonschema or the schema file is
    unavailable, so the engine still runs in a bare environment.

    Args:
        payload: The result mapping to validate.
        schema_path: Schema location; defaults to the bundled schema.

    Raises:
        jsonschema.ValidationError: If the payload does not match the schema.
    """
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - jsonschema is a dev dependency
        return
    if schema_path is None:
        import os

        here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        schema_path = os.path.join(here, "docs", "schemas", "result.schema.json")
    if not os.path.exists(schema_path):
        return
    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    jsonschema.Draft202012Validator(schema).validate(payload)


def message_status(result_payload: dict, offset: int) -> Status | None:
    """Status of the message at ``offset`` in a result payload, or ``None``."""
    for message in result_payload.get("messages", []):
        if message.get("offset") == offset:
            return Status(message.get("status"))
    return None
