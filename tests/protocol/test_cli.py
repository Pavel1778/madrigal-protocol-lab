import base64
import json
import struct

from src.protocol.cli import main
from src.protocol.result import validate_result


def _message(command, value, declared=8):
    return struct.pack(">BBHH", command, 0, declared, value) + b"\x00\x00"


def _capture(stream_a, stream_b=b"", capture_id=None, source_file="captures/cap.pcapng"):
    capture_id = capture_id or "sha256:" + "ef" * 32
    payload = {
        "contract_version": 1,
        "capture_id": capture_id,
        "source_file": source_file,
        "sessions": [
            {
                "session_id": "s1",
                "endpoints": [
                    {"ip": "10.0.0.1", "port": 5000},
                    {"ip": "10.0.0.2", "port": 6000},
                ],
                "directions": {
                    "A_to_B": {
                        "bytes_b64": base64.b64encode(stream_a).decode(),
                        "provenance": [
                            {
                                "offset": 0,
                                "length": len(stream_a),
                                "packet_index": 3,
                                "seq": 1000,
                                "ts": 1.5,
                            }
                        ],
                        "diagnostics": [],
                    },
                    "B_to_A": {
                        "bytes_b64": base64.b64encode(stream_b).decode(),
                        "provenance": [],
                        "diagnostics": [],
                    },
                },
            }
        ],
    }
    return payload


RULE = {
    "schema_version": 1,
    "rule_id": "r1",
    "rule_version": 2,
    "name": "set_parameter_request",
    "scope": {"direction": "A_to_B"},
    "framing": {
        "type": "length_prefixed",
        "length_offset": 2,
        "length_size": 2,
        "byte_order": "big",
        "length_includes_payload": True,
    },
    "fields": [
        {"name": "command", "offset": 0, "type": "uint8", "expected": [4]},
        {"name": "payload_length", "offset": 2, "type": "uint16", "byte_order": "big"},
        {"name": "value", "offset": 4, "type": "uint16", "byte_order": "big"},
    ],
}


def _write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_cli_apply_writes_valid_result(tmp_path):
    stream = _message(4, 21) + _message(9, 22)
    capture_path = _write(tmp_path, "capture.json", _capture(stream))
    rule_path = _write(tmp_path, "rule.json", RULE)
    out_path = str(tmp_path / "result.json")

    code = main(["apply", "--rule", rule_path, "--capture", capture_path, "--out", out_path])
    assert code == 0

    payload = json.loads(open(out_path, encoding="utf-8").read())
    assert payload["rule_id"] == "r1"
    assert payload["rule_version"] == 2
    assert payload["capture_id"] == "sha256:" + "ef" * 32
    assert payload["summary"]["matched"] == 1
    assert payload["summary"]["mismatched"] == 1
    assert payload["messages"][0]["fields"]["command"] == 4
    validate_result(payload)


def test_cli_apply_honours_session_and_direction(tmp_path):
    capture_path = _write(tmp_path, "capture.json", _capture(_message(4, 1), _message(4, 2)))
    rule_path = _write(tmp_path, "rule.json", RULE)
    out_path = str(tmp_path / "result.json")
    code = main(
        [
            "apply",
            "--rule",
            rule_path,
            "--capture",
            capture_path,
            "--out",
            out_path,
            "--direction",
            "B_to_A",
        ]
    )
    assert code == 0
    payload = json.loads(open(out_path, encoding="utf-8").read())
    assert payload["summary"]["not_applicable"] == 1


def test_cli_verify_reports_counterexamples(tmp_path):
    stream = _message(4, 21) + _message(7, 22)
    capture_path = _write(tmp_path, "capture.json", _capture(stream))
    rule_path = _write(tmp_path, "rule.json", RULE)
    out_path = str(tmp_path / "report.json")
    code = main(["verify", "--rule", rule_path, "--capture", capture_path, "--out", out_path])
    assert code == 0
    report = json.loads(open(out_path, encoding="utf-8").read())
    assert report["rule_id"] == "r1"
    assert report["counts"]["mismatched"] == 1
    assert report["contradictions"][0]["message_offset"] == 8


def test_cli_accepts_yaml_rule(tmp_path):
    stream = _message(4, 21)
    capture_path = _write(tmp_path, "capture.json", _capture(stream))
    rule_text = """
schema_version: 1
rule_id: r2
rule_version: 1
scope: {direction: A_to_B}
framing: {type: fixed_size, size: 8}
fields:
  - {name: command, offset: 0, type: uint8, expected: [4]}
  - {name: value, offset: 4, type: uint16, byte_order: big}
"""
    rule_path = tmp_path / "rule.yaml"
    rule_path.write_text(rule_text, encoding="utf-8")
    out_path = str(tmp_path / "result.json")
    code = main(["apply", "--rule", str(rule_path), "--capture", capture_path, "--out", out_path])
    assert code == 0
    payload = json.loads(open(out_path, encoding="utf-8").read())
    assert payload["summary"]["matched"] == 1
    assert payload["messages"][0]["fields"]["value"] == 21


def test_cli_missing_capture_returns_error(tmp_path, capsys):
    rule_path = _write(tmp_path, "rule.json", RULE)
    try:
        main(["apply", "--rule", rule_path, "--capture", str(tmp_path / "missing.json"), "--out", "x"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")
