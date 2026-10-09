"""Shared model for an investigation report.

An investigation is handed to the renderers as a plain dictionary so the
protocol module can build it without importing anything from here. The shape
is::

    {
      "title": "...",                      # optional
      "scope": { ... },                    # rule applicability, free-form
      "hypotheses": [
        {"id": "h1", "statement": "...", "status": "hypothesis",
         "rule_id": "r1", "rule_version": 2, "evidence": "...",
         "counterexamples": ["c1"]}
      ],
      "counterexamples": [
        {"id": "c1", "rule_id": "r1", "rule_version": 2,
         "capture_id": "sha256:...", "session_id": "s2",
         "direction": "A_to_B", "offset": 128, "length": 4,
         "bytes_hex": "ffff0001", "detail": "..."}
      ],
      "rule_versions": [
        {"rule_id": "r1", "version": 1, "created_at": "...", "note": "..."}
      ],
      "open_questions": ["...", "..."]
    }

Only ``hypotheses``, ``counterexamples``, ``rule_versions``, ``scope`` and
``open_questions`` are part of the contract; every other key is optional. The
normalizer here fills in what is missing so both renderers can rely on the same
structure.
"""

from __future__ import annotations

from typing import Any

SECTIONS = (
    "scope",
    "hypotheses",
    "counterexamples",
    "rule_versions",
    "open_questions",
)

STATUS_LABELS = {
    "observation": "Observation",
    "hypothesis": "Hypothesis",
    "confirmed_in_scope": "Confirmed in scope",
    "contradiction": "Contradiction",
    "unknown": "Unknown",
    "ambiguous": "Ambiguous",
    "not_applicable": "Not applicable",
    "outdated": "Outdated",
}


class ReportError(ValueError):
    """Raised when an investigation cannot be rendered."""


def normalize(investigation: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``investigation`` with every known section present."""

    if not isinstance(investigation, dict):
        raise ReportError("investigation must be a dictionary")

    model: dict[str, Any] = {
        "title": str(investigation.get("title") or "Protocol investigation report"),
        "scope": investigation.get("scope") or {},
        "hypotheses": list(investigation.get("hypotheses") or []),
        "counterexamples": list(investigation.get("counterexamples") or []),
        "rule_versions": list(investigation.get("rule_versions") or []),
        "open_questions": list(investigation.get("open_questions") or []),
    }
    return model


def status_label(status: str) -> str:
    """Map an interpretation status to a readable label."""

    return STATUS_LABELS.get(status, status.replace("_", " ").capitalize())


def has_content(model: dict[str, Any]) -> bool:
    """True when the investigation carries anything worth writing."""

    return any(model.get(section) for section in SECTIONS)
