"""Boundary and negative tests for the project container and manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.generate_fixture import _write_pcapng, syn
from src.project import Manifest, ManifestError, Project, ProjectError
from src.project.manifest import read_manifest
from src.project.pipeline import build_investigation


def _capture(tmp_path: Path, name: str = "one.pcapng") -> Path:
    path = tmp_path / name
    path.write_bytes(_write_pcapng([syn(seq=1000)]))
    return path


# -- project lifecycle ----------------------------------------------------


def test_open_a_file_path_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "not-a-dir"
    target.write_text("plain file", encoding="utf-8")
    with pytest.raises(ProjectError):
        Project.open(target)


def test_open_reports_missing_directories(tmp_path: Path) -> None:
    project = Project.create(tmp_path / "project.madrigal", "trial")
    (project.root / "rules").rmdir()
    with pytest.raises(ProjectError):
        Project.open(project.root)


def test_add_missing_capture_is_refused(tmp_path: Path) -> None:
    project = Project.create(tmp_path / "project.madrigal", "trial")
    with pytest.raises(ProjectError):
        project.add_capture(tmp_path / "absent.pcapng")


def test_two_captures_with_the_same_name_get_a_suffix(tmp_path: Path) -> None:
    project = Project.create(tmp_path / "project.madrigal", "trial")
    first = _capture(tmp_path)
    relative = project.add_capture(first)
    # A different capture under the same name must not overwrite the first.
    first.write_bytes(_write_pcapng([syn(seq=999)]))
    second = project.add_capture(first)
    assert relative == "captures/one.pcapng"
    assert second == "captures/one-1.pcapng"


def test_path_resolves_relative_to_the_root(tmp_path: Path) -> None:
    project = Project.create(tmp_path / "project.madrigal", "trial")
    assert (
        project.path("captures", "x.pcapng") == project.root / "captures" / "x.pcapng"
    )


# -- manifest validation --------------------------------------------------


def _valid_manifest() -> dict:
    return {
        "contract_version": 1,
        "project_version": 1,
        "name": "trial",
        "created_at": "2026-10-09T00:00:00Z",
        "updated_at": "2026-10-09T00:00:00Z",
        "captures": [],
        "rules": [],
        "results": [],
        "annotations": "annotations.sqlite",
    }


def test_manifest_rejects_a_non_object() -> None:
    with pytest.raises(ManifestError):
        Manifest.from_dict(["not", "an", "object"])


def test_manifest_rejects_a_missing_key() -> None:
    data = _valid_manifest()
    del data["annotations"]
    with pytest.raises(ManifestError):
        Manifest.from_dict(data)


def test_manifest_rejects_a_non_integer_version() -> None:
    data = _valid_manifest()
    data["project_version"] = "one"
    with pytest.raises(ManifestError):
        Manifest.from_dict(data)


def test_manifest_rejects_a_non_list_section() -> None:
    data = _valid_manifest()
    data["rules"] = {"rule": 1}
    with pytest.raises(ManifestError):
        Manifest.from_dict(data)


def test_read_manifest_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        read_manifest(tmp_path / "manifest.json")


def test_read_manifest_rejects_broken_json(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError):
        read_manifest(path)


def test_manifest_has_capture_lookup() -> None:
    manifest = Manifest.new("trial")
    assert manifest.has_capture("captures/x.pcapng") is None
    manifest.captures.append({"path": "captures/x.pcapng", "sha256": "abc"})
    assert manifest.has_capture("captures/x.pcapng") == "abc"


# -- investigation shaping ------------------------------------------------


def _result(summary: dict[str, int], messages: list[dict]) -> dict:
    return {
        "rule_id": "r1",
        "rule_version": 1,
        "capture_id": "sha256:aa",
        "summary": summary,
        "messages": messages,
    }


def _summary(**overrides: int) -> dict[str, int]:
    base = {
        "matched": 0,
        "mismatched": 0,
        "incomplete": 0,
        "ambiguous": 0,
        "unknown": 0,
        "uncovered": 0,
    }
    base.update(overrides)
    return base


def test_investigation_confirms_only_without_contradictions() -> None:
    investigation = build_investigation(
        _result(_summary(matched=5), [{"offset": 0, "length": 4, "status": "matched"}]),
        capture_id="sha256:aa",
        source_file="cap.pcapng",
    )
    assert investigation["hypotheses"][0]["status"] == "confirmed_in_scope"
    assert investigation["counterexamples"] == []


def test_investigation_records_ambiguity_as_contradiction() -> None:
    # ``mismatched`` is the only status that contradicts the rule, so it both
    # flips the hypothesis and becomes a counterexample.
    investigation = build_investigation(
        _result(
            _summary(matched=1, mismatched=1),
            [
                {"offset": 0, "length": 4, "status": "matched"},
                {"offset": 4, "length": 4, "status": "mismatched"},
            ],
        ),
        capture_id="sha256:aa",
        source_file="cap.pcapng",
    )
    assert investigation["hypotheses"][0]["status"] == "contradiction"
    assert investigation["counterexamples"][0]["offset"] == 4


def test_an_ambiguous_message_is_listed_but_does_not_contradict() -> None:
    # An unreadable message is not evidence against the rule, so the hypothesis
    # stays in scope; the message is still listed so the reader can inspect it.
    investigation = build_investigation(
        _result(
            _summary(matched=1, ambiguous=1),
            [
                {"offset": 0, "length": 4, "status": "matched"},
                {"offset": 4, "length": 4, "status": "ambiguous"},
            ],
        ),
        capture_id="sha256:aa",
        source_file="cap.pcapng",
    )
    assert investigation["hypotheses"][0]["status"] == "confirmed_in_scope"
    assert investigation["counterexamples"][0]["offset"] == 4


def test_investigation_stays_a_hypothesis_without_evidence() -> None:
    investigation = build_investigation(
        _result(_summary(unknown=2), [{"offset": 0, "length": 4, "status": "unknown"}]),
        capture_id="sha256:aa",
        source_file="cap.pcapng",
    )
    assert investigation["hypotheses"][0]["status"] == "hypothesis"
    assert any("too little data" in q for q in investigation["open_questions"])


def test_investigation_raises_only_open_questions_that_apply() -> None:
    investigation = build_investigation(
        _result(
            _summary(incomplete=1, uncovered=3),
            [{"offset": 0, "length": 4, "status": "incomplete"}],
        ),
        capture_id="sha256:aa",
        source_file="cap.pcapng",
    )
    joined = " ".join(investigation["open_questions"])
    assert "gap" in joined and "not covered" in joined
    assert "ambiguous" not in joined and "too little data" not in joined


def test_counterexample_carries_provenance_packets_when_present() -> None:
    investigation = build_investigation(
        _result(
            _summary(mismatched=1),
            [
                {
                    "offset": 8,
                    "length": 4,
                    "status": "mismatched",
                    "session_id": "s1",
                    "direction": "A_to_B",
                    "provenance_range": {"packets": [3, 4]},
                }
            ],
        ),
        capture_id="sha256:aa",
        source_file="cap.pcapng",
    )
    entry = investigation["counterexamples"][0]
    assert entry["packets"] == [3, 4]
    assert entry["session_id"] == "s1"
    assert entry["direction"] == "A_to_B"


def test_investigation_is_json_serializable() -> None:
    investigation = build_investigation(
        _result(_summary(matched=1), [{"offset": 0, "length": 4, "status": "matched"}]),
        capture_id="sha256:aa",
        source_file="cap.pcapng",
    )
    json.dumps(investigation)
