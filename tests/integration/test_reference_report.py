"""Guards for the investigation report and the refined rule it produces.

The report is a claim about the corpus, so it must stay in step with the bytes:
the framing verdict, the version comparison and the boundary result quoted in
``REPORT.md`` are re-derived here from the same captures. The refined rule is
checked against the rule schema and against the refinement it is supposed to be.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.hypothesis.corpus import CorpusStream, verify_on_corpus
from src.protocol.rule import load_rule
from src.protocol.stream import capture_from_dict

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "tests" / "corpus"
CORPUS_PCAP = CORPUS_DIR / "corpus_capture_01.pcapng"
CORPUS_PCAP_2 = CORPUS_DIR / "corpus_capture_02.pcapng"
SYNTHETIC_PCAP = CORPUS_DIR / "synthetic_live.pcapng"
RULE_V1 = REPO_ROOT / "examples" / "corpus_rule_v1.json"
RULE_V2 = REPO_ROOT / "examples" / "corpus_rule_v2.json"
REPORT = REPO_ROOT / "REPORT.md"
INVESTIGATION = REPO_ROOT / "docs" / "REFERENCE_INVESTIGATION.md"
RULE_SCHEMA = REPO_ROOT / "docs" / "schemas" / "rule.schema.json"

CORPUS_READY = (
    CORPUS_PCAP.is_file()
    and RULE_V1.is_file()
    and importlib.util.find_spec("src.capture.pipeline") is not None
)

corpus_required = pytest.mark.skipif(
    not CORPUS_READY,
    reason="corpus not ready, waiting for Agent 1",
)


def _normalized(capture_path: Path) -> dict:
    import tempfile

    from src.capture.export import export_capture
    from src.capture.pipeline import normalize

    capture = normalize(capture_path)
    with tempfile.TemporaryDirectory() as directory:
        exported = Path(directory) / "normalized.json"
        export_capture(
            capture.sessions,
            exported,
            source_file=str(capture_path),
            capture_id=capture.capture_id,
            streams=capture.streams,
        )
        return json.loads(exported.read_text(encoding="utf-8"))


def _verify(rule, payload: dict):
    capture = capture_from_dict(payload)
    streams = [
        CorpusStream.from_bytes(stream.data, session_id, direction)
        for session_id, direction, stream in capture.iter_streams()
    ]
    return verify_on_corpus(rule, streams)


@corpus_required
def test_rule_v2_is_valid_and_widens_the_command_set():
    if not RULE_V2.is_file():
        pytest.skip("refined rule not generated")
    import jsonschema

    rule_v2 = json.loads(RULE_V2.read_text(encoding="utf-8"))
    schema = json.loads(RULE_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(rule_v2)
    assert rule_v2["rule_version"] == 2

    v1 = json.loads(RULE_V1.read_text(encoding="utf-8"))
    v1_command = next(f for f in v1["fields"] if f["name"] == "command")
    v2_command = next(f for f in rule_v2["fields"] if f["name"] == "command")
    assert set(v1_command["expected"]) < set(v2_command["expected"])
    # Only the version and the command set change; the layout is untouched.
    assert v1["framing"] == rule_v2["framing"]
    assert len(v1["fields"]) == len(rule_v2["fields"])


@corpus_required
def test_v2_transfers_to_the_second_capture_without_counterexamples():
    rule_v2 = load_rule(str(RULE_V2))
    report = _verify(rule_v2, _normalized(CORPUS_PCAP_2))
    assert report.counts()["mismatched"] == 0
    assert report.contradictions == []
    assert report.counts()["matched"] == 40


@corpus_required
def test_v2_fails_at_the_synthetic_boundary():
    rule_v2 = load_rule(str(RULE_V2))
    report = _verify(rule_v2, _normalized(SYNTHETIC_PCAP))
    counts = report.counts()
    assert counts["matched"] == 0
    assert counts["incomplete"] >= 1


@corpus_required
def test_refinement_resolves_every_v1_counterexample():
    from src.hypothesis.versioning import compare_reports

    payload = _normalized(CORPUS_PCAP)
    before = _verify(load_rule(str(RULE_V1)), payload)
    after = _verify(load_rule(str(RULE_V2)), payload)
    comparison = compare_reports(before, after)
    assert len(before.contradictions) == 80
    assert len(comparison.resolved) == 80
    assert comparison.introduced == []


def test_report_and_investigation_exist_with_expected_sections():
    assert REPORT.is_file()
    assert INVESTIGATION.is_file()
    text = REPORT.read_text(encoding="utf-8")
    for section in (
        "## 1. Context",
        "## 2. Methodology",
        "## 3. Hypotheses and their basis",
        "## 4. Framing decision",
        "## 5. Counterexamples",
        "## 6. Refinement and version differentiation",
        "## 7. Transfer to the second capture",
        "## 8. Applicability boundary",
        "## 9. Journal correlation",
        "## 10. Alternative explanations",
        "## 11. Applicability and open questions",
        "## 12. Limitations",
    ):
        assert section in text


def test_report_has_no_automation_traces():
    text = REPORT.read_text(encoding="utf-8").lower()
    for word in ("generated by", "auto-generated", "language model"):
        assert word not in text
    assert "!" not in text
