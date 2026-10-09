"""Guards for the reference normalized exports handed to the protocol module.

The committed files must stay valid against the capture schema and must still
match what the capture module produces from the corpus, so the protocol module
never works against a stale export.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.capture.export import export_capture
from src.capture.pipeline import normalize

ROOT = Path(__file__).resolve().parent.parent.parent
REFERENCES = ROOT / "tests" / "corpus" / "reference_export"
CORPUS = ROOT / "tests" / "corpus"
SCHEMA = ROOT / "docs" / "schemas" / "capture.schema.json"

RECORDS = (
    "corpus_capture_01",
    "corpus_capture_02",
    "corpus_capture_defects",
)


@pytest.mark.parametrize("stem", RECORDS)
def test_reference_export_is_valid_and_current(stem: str, tmp_path: Path) -> None:
    committed = json.loads(
        (REFERENCES / f"{stem}.normalized.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(
        committed
    )

    # Rebuild from the capture and require the same content.
    capture = normalize(CORPUS / f"{stem}.pcapng")
    rebuilt = tmp_path / f"{stem}.json"
    export_capture(
        capture.sessions,
        rebuilt,
        source_file=f"tests/corpus/{stem}.pcapng",
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    assert json.loads(rebuilt.read_text(encoding="utf-8")) == committed
