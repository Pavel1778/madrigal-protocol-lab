"""Rule and result versioning.

Changing a rule never rewrites the bytes it was applied to. Instead the rule
gets a new version and every result produced by an older version is marked
``outdated``. Re-checking a corpus after an edit yields a side-by-side
comparison of the two versions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..protocol.rule import Rule
from .corpus import VerificationReport


@dataclass
class StoredResult:
    """A result kept on disk, tagged with the rule version that produced it."""

    rule_id: str
    rule_version: int
    capture_id: str
    payload: dict
    status: str = "current"

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "capture_id": self.capture_id,
            "status": self.status,
            "payload": self.payload,
        }


@dataclass
class VersionComparison:
    rule_id: str
    base_version: int
    new_version: int
    base_counts: dict = field(default_factory=dict)
    new_counts: dict = field(default_factory=dict)
    introduced: list = field(default_factory=list)
    resolved: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "base_version": self.base_version,
            "new_version": self.new_version,
            "base_counts": self.base_counts,
            "new_counts": self.new_counts,
            "introduced": self.introduced,
            "resolved": self.resolved,
        }


class ResultStore:
    """A minimal in-memory store of results keyed by rule and capture."""

    def __init__(self) -> None:
        self._results: list[StoredResult] = []

    def add(self, rule: Rule, capture_id: str, payload: dict) -> StoredResult:
        stored = StoredResult(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            capture_id=capture_id,
            payload=payload,
        )
        self._results.append(stored)
        return stored

    def results_for(self, rule_id: str, capture_id: str | None = None) -> list[StoredResult]:
        return [
            r
            for r in self._results
            if r.rule_id == rule_id and (capture_id is None or r.capture_id == capture_id)
        ]

    def mark_outdated(self, rule: Rule, capture_id: str | None = None) -> list[StoredResult]:
        """Mark results produced by versions older than *rule* as ``outdated``."""
        touched = []
        for stored in self.results_for(rule.rule_id, capture_id):
            if stored.rule_version < rule.rule_version and stored.status != "outdated":
                stored.status = "outdated"
                _retag_payload(stored)
                touched.append(stored)
        return touched

    def to_list(self) -> list[dict]:
        return [r.to_dict() for r in self._results]

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_list(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")


def _retag_payload(stored: StoredResult) -> None:
    payload = stored.payload
    for message in payload.get("messages", []):
        message["status"] = "outdated"
    summary = payload.get("summary")
    if isinstance(summary, dict):
        summary["outdated"] = len(payload.get("messages", []))
        for key in ("matched", "mismatched", "incomplete", "ambiguous", "uncovered", "not_applicable", "unknown"):
            if key in summary:
                summary[key] = 0


def compare_reports(base: VerificationReport, new: VerificationReport) -> VersionComparison:
    """Compare two verification reports for the same rule id."""
    base_keys = {(c.session_id, c.direction, c.message_offset, c.status.value) for c in base.contradictions}
    new_keys = {(c.session_id, c.direction, c.message_offset, c.status.value) for c in new.contradictions}
    introduced = [c.to_dict() for c in new.contradictions if (c.session_id, c.direction, c.message_offset, c.status.value) not in base_keys]
    resolved = [c.to_dict() for c in base.contradictions if (c.session_id, c.direction, c.message_offset, c.status.value) not in new_keys]
    return VersionComparison(
        rule_id=base.rule_id,
        base_version=base.rule_version,
        new_version=new.rule_version,
        base_counts=base.counts(),
        new_counts=new.counts(),
        introduced=introduced,
        resolved=resolved,
    )
