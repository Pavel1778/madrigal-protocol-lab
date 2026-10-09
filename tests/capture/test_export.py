"""Tests for the normalized capture export and its schema."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.capture.export import export_capture, sha256_file
from src.capture.pipeline import normalize

from .conftest import SCHEMAS, fixture


def _validator() -> Draft202012Validator:
    schema = json.loads((SCHEMAS / "capture.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def test_export_matches_schema(tmp_path: Path) -> None:
    capture = normalize(fixture("normal.pcapng"))
    out = tmp_path / "normal.json"
    export_capture(
        capture.sessions,
        out,
        source_file="captures/normal.pcapng",
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    _validator().validate(data)


def test_export_carries_bytes_and_provenance(tmp_path: Path) -> None:
    capture = normalize(fixture("normal.pcapng"))
    out = tmp_path / "normal.json"
    export_capture(
        capture.sessions,
        out,
        source_file="captures/normal.pcapng",
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    session = data["sessions"][0]
    a_to_b = session["directions"]["A_to_B"]
    assert base64.b64decode(a_to_b["bytes_b64"]) == b"HELLO"
    first = a_to_b["provenance"][0]
    assert first["packet_index"] == 3
    assert first["seq"] == 1001


def test_export_reports_gaps(tmp_path: Path) -> None:
    capture = normalize(fixture("gap.pcapng"))
    out = tmp_path / "gap.json"
    export_capture(
        capture.sessions,
        out,
        source_file="captures/gap.pcapng",
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    diagnostics = data["sessions"][0]["directions"]["A_to_B"]["diagnostics"]
    assert [d["type"] for d in diagnostics] == ["gap"]
    assert diagnostics[0]["length"] == 4
    _validator().validate(data)


def test_capture_id_is_content_hash(tmp_path: Path) -> None:
    path = fixture("normal.pcapng")
    digest = sha256_file(path)
    assert digest.startswith("sha256:") and len(digest) == 7 + 64
    capture = normalize(path)
    assert capture.capture_id == digest


def test_capture_id_does_not_depend_on_the_path(tmp_path: Path) -> None:
    # A capture copied elsewhere is the same capture: the identifier follows the
    # bytes, so a project can be moved and still match its manifest (R5).
    original = fixture("normal.pcapng")
    moved = tmp_path / "elsewhere" / "renamed.pcapng"
    moved.parent.mkdir()
    moved.write_bytes(original.read_bytes())
    assert normalize(moved).capture_id == normalize(original).capture_id


def test_export_is_deterministic(tmp_path: Path) -> None:
    capture = normalize(fixture("normal.pcapng"))
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    for out in (first, second):
        export_capture(
            capture.sessions,
            out,
            source_file="captures/normal.pcapng",
            capture_id=capture.capture_id,
            streams=capture.streams,
        )
    assert first.read_bytes() == second.read_bytes()
