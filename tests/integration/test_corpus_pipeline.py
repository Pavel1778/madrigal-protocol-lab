"""End-to-end pipeline: capture -> protocol -> result on the shared corpus.

The corpus is produced by the capture module and lives in ``tests/corpus/``.
Until Agent 1 publishes it, every test below is skipped with an explicit
reason; nothing here fabricates corpus data.

Run with the corpus present:

    python -m pytest tests/integration -v
"""

from __future__ import annotations

import importlib.util
import json
import os

import pytest

from src.protocol.engine import apply_rule
from src.protocol.result import build_result
from src.protocol.rule import load_rule
from src.protocol.stream import load_capture

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS_DIR = os.path.join(REPO_ROOT, "tests", "corpus")
CORPUS_PCAP = os.path.join(CORPUS_DIR, "corpus_capture_01.pcapng")
CORPUS_RULE = os.path.join(REPO_ROOT, "examples", "corpus_rule_v1.json")
CAPTURE_SCHEMA = os.path.join(REPO_ROOT, "docs", "schemas", "capture.schema.json")
RESULT_SCHEMA = os.path.join(REPO_ROOT, "docs", "schemas", "result.schema.json")

CORPUS_READY = (
    os.path.isfile(CORPUS_PCAP)
    and os.path.isfile(CORPUS_RULE)
    and os.path.isdir(os.path.join(REPO_ROOT, "src", "capture"))
    and importlib.util.find_spec("src.capture.pipeline") is not None
)

corpus_required = pytest.mark.skipif(
    not CORPUS_READY,
    reason="corpus not ready, waiting for Agent 1",
)


def _validate(schema_path: str, payload: dict) -> None:
    if not os.path.isfile(schema_path):
        pytest.skip(f"schema not present: {schema_path}")
    import jsonschema

    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    jsonschema.Draft202012Validator(schema).validate(payload)


@corpus_required
def test_capture_to_result_pipeline(tmp_path):
    from src.capture.export import export_capture
    from src.capture.pipeline import normalize

    # 1. Read the corpus capture and reassemble its sessions.
    capture = normalize(__import__("pathlib").Path(CORPUS_PCAP))

    # 2. Export the normalized capture and validate it against the contract.
    normalized_path = tmp_path / "normalized.json"
    export_capture(
        capture.sessions,
        normalized_path,
        source_file=str(CORPUS_PCAP),
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    with open(normalized_path, "r", encoding="utf-8") as handle:
        normalized = json.load(handle)
    _validate(CAPTURE_SCHEMA, normalized)

    # 3. Load it into the protocol engine and apply the corpus rule.
    loaded = load_capture(str(normalized_path))
    rule = load_rule(CORPUS_RULE)
    messages = []
    for session_id, direction, stream in loaded.iter_streams():
        if not rule.applies_to(direction):
            continue
        messages.extend(apply_rule(stream, rule, session_id, direction))
    assert messages, "the corpus rule framed no messages"

    # 4. Build the contract result and validate it.
    result = build_result(rule, loaded.capture_hash, messages)
    payload = result.to_dict()
    _validate(RESULT_SCHEMA, payload)

    # 5. At least one message matched, and every counterexample is tied to bytes.
    summary = payload["summary"]
    assert summary["matched"] > 0
    for message in payload["messages"]:
        if message["status"] == "mismatched":
            provenance = message.get("provenance_range")
            assert provenance is not None, "mismatched message without provenance"
            assert provenance.get("offset") is not None
            assert provenance.get("length")
