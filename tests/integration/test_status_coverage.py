"""The six core statuses must all be reachable on the shipped corpus.

A status the engine cannot produce from real data is decoration. Each of the six
core statuses is exercised here against the reference capture, its transfer and
the deliberately damaged capture, using rules built from the same declarative
vocabulary the product uses. The test fails if any status stops being produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.hypothesis.status import CORE_STATUSES, Status
from src.protocol.engine import apply_rule
from src.protocol.rule import load_rule, parse_rule
from src.protocol.stream import load_capture

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = REPO_ROOT / "tests" / "corpus" / "reference_export"
CAPTURE_01 = EXPORT_DIR / "corpus_capture_01.normalized.json"
CAPTURE_DEFECTS = EXPORT_DIR / "corpus_capture_defects.normalized.json"
RULE_V1 = REPO_ROOT / "examples" / "corpus_rule_v1.json"
RULE_V2 = REPO_ROOT / "examples" / "corpus_rule_v2.json"

corpus_required = pytest.mark.skipif(
    not CAPTURE_01.is_file() or not RULE_V1.is_file(),
    reason="reference corpus not present",
)

#: The layout both corpus rules share; only the command set differs.
FRAMING = {
    "type": "length_prefixed",
    "length_offset": 2,
    "length_size": 2,
    "byte_order": "big",
    "length_includes_payload": True,
}


def _rule(fields: list[dict], scope: dict | None = None):
    raw = {
        "schema_version": 1,
        "rule_id": "status_probe",
        "rule_version": 1,
        "name": "status_probe",
        "framing": FRAMING,
        "fields": fields,
    }
    if scope is not None:
        raw["scope"] = scope
    return parse_rule(raw)


def _statuses(capture, rule) -> set[str]:
    seen: set[str] = set()
    for session_id, direction, stream in capture.iter_streams():
        seen.update(m.status.value for m in apply_rule(stream, rule, session_id, direction))
    return seen


@corpus_required
def test_every_core_status_is_produced_on_the_corpus():
    capture = load_capture(str(CAPTURE_01))
    defects = load_capture(str(CAPTURE_DEFECTS))
    observed: set[str] = set()

    # matched, mismatched and not_applicable from rule v1: it scopes A_to_B, so
    # the responses are not_applicable, and the too-narrow command set makes the
    # requests on the later sessions mismatched.
    observed |= _statuses(capture, load_rule(str(RULE_V1)))

    # incomplete and ambiguous from the damaged capture. The unscoped refined
    # rule frames the gap and ambiguity holes that survive framing.
    v2 = load_rule(str(RULE_V2)).to_dict()
    v2.pop("scope", None)
    observed |= _statuses(defects, parse_rule(v2))
    observed |= _statuses(defects, _rule([{"name": "far", "offset": 900, "type": "uint8"}]))

    # uncovered from a message whose only declared field is padding: no field
    # produced an interpreted value, so the message carries no reading.
    observed |= _statuses(
        capture, _rule([{"name": "pad", "offset": 0, "type": "padding", "length": 1}])
    )

    missing = {s.value for s in CORE_STATUSES} - observed
    assert not missing, f"statuses never produced: {sorted(missing)}"
    assert Status.NOT_APPLICABLE.value in observed
