import base64
import json
import os

import pytest

from src.protocol.stream import (
    CaptureError,
    DirectionalStream,
    Hole,
    capture_from_dict,
    load_capture,
)


def _capture_dict():
    stream = b"\x04\x00\x00\x08\x00\x15\x00\x00"
    return {
        "contract_version": 1,
        "capture_id": "sha256:" + "aa" * 32,
        "source_file": "captures/cap.pcapng",
        "sessions": [
            {
                "session_id": "s1",
                "endpoints": [
                    {"ip": "10.0.0.1", "port": 5000},
                    {"ip": "10.0.0.2", "port": 6000},
                ],
                "directions": {
                    "A_to_B": {
                        "bytes_b64": base64.b64encode(stream).decode(),
                        "provenance": [
                            {"offset": 0, "length": 8, "packet_index": 4, "seq": 1, "ts": 2.0}
                        ],
                        "diagnostics": [],
                    },
                    "B_to_A": {"bytes_b64": "", "provenance": [], "diagnostics": []},
                },
            }
        ],
    }


def test_from_direction_decodes_base64_and_diagnostics():
    direction = {
        "bytes_b64": base64.b64encode(b"abcdefgh").decode(),
        "provenance": [{"offset": 0, "length": 4, "packet_index": 1}],
        "diagnostics": [{"type": "gap", "offset": 4, "length": 2}],
    }
    stream = DirectionalStream.from_direction(direction)
    assert stream.data == b"abcdefgh"
    assert stream.has_gap(4, 6) is True
    assert stream.has_gap(0, 2) is False
    assert stream.has_ambiguity(0, 8) is False
    assert stream.provenance[0].packet_index == 1


def test_invalid_base64_raises():
    with pytest.raises(CaptureError):
        DirectionalStream.from_direction({"bytes_b64": "not-base64!!"})


def test_hole_overlap():
    hole = Hole(type="gap", offset=10, length=5)
    assert hole.end == 15
    assert hole.overlaps(12, 14) is True
    assert hole.overlaps(15, 20) is False


def test_capture_stream_and_iter():
    capture = capture_from_dict(_capture_dict())
    stream = capture.stream("s1", "A_to_B")
    assert stream.data[0] == 4
    assert [(sid, direction) for sid, direction, _ in capture.iter_streams()] == [
        ("s1", "A_to_B"),
        ("s1", "B_to_A"),
    ]


def test_capture_missing_session_and_direction_raise():
    capture = capture_from_dict(_capture_dict())
    with pytest.raises(CaptureError):
        capture.stream("missing", "A_to_B")
    with pytest.raises(CaptureError):
        capture.stream("s1", "C_to_D")


def test_capture_hash_uses_capture_id():
    capture = capture_from_dict(_capture_dict())
    assert capture.capture_hash == "sha256:" + "aa" * 32


def test_capture_hash_is_derived_without_capture_id():
    raw = _capture_dict()
    raw["capture_id"] = ""
    capture = capture_from_dict(raw)
    assert capture.capture_hash.startswith("sha256:")
    assert len(capture.capture_hash) == len("sha256:") + 64


def test_load_capture_from_file(tmp_path):
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(_capture_dict()), encoding="utf-8")
    capture = load_capture(str(path))
    assert capture.source_file == "captures/cap.pcapng"
    assert capture.sessions[0]["session_id"] == "s1"


def test_missing_sessions_raises():
    with pytest.raises(CaptureError):
        capture_from_dict({"contract_version": 1})


def test_unknown_contract_version_raises():
    with pytest.raises(CaptureError):
        capture_from_dict({"contract_version": 2, "sessions": []})


def test_non_integer_contract_version_raises():
    with pytest.raises(CaptureError):
        capture_from_dict({"contract_version": "one", "sessions": []})


def test_absent_contract_version_defaults_to_one():
    capture = capture_from_dict({"sessions": []})
    assert capture.contract_version == 1


def test_example_rule_matches_rule_schema():
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema_path = os.path.join(here, "docs", "schemas", "rule.schema.json")
    example_path = os.path.join(here, "src", "protocol", "examples", "set_parameter_request.json")
    if not (os.path.exists(schema_path) and os.path.exists(example_path)):
        pytest.skip("rule schema or example not present")
    import jsonschema

    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    with open(example_path, "r", encoding="utf-8") as handle:
        example = json.load(handle)
    jsonschema.Draft202012Validator(schema).validate(example)


def test_example_rule_matches_capture_schema(tmp_path):
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    capture_schema_path = os.path.join(here, "docs", "schemas", "capture.schema.json")
    if not os.path.exists(capture_schema_path):
        pytest.skip("capture schema not present")
    import jsonschema

    with open(capture_schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    jsonschema.Draft202012Validator(schema).validate(_capture_dict())
