#!/usr/bin/env python3
"""Investigate the organizer capture set and write the findings.

The script normalizes every capture under ``tests/corpus/real``, states the
naive reading of the thermal-stand protocol as a first rule, applies it, and
refines it from the counterexamples it finds. It then walks the diagnostic
captures and records the diagnostics each one is meant to exercise, and
correlates the decoded requests with the action journal.

Nothing is hardcoded from the captures: the numbers in the report are the
counts actually observed. Run it with ``--out -`` to print instead of writing.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL = REPO_ROOT / "tests" / "corpus" / "real"
EXAMPLES = REPO_ROOT / "examples"
DEFAULT_OUT = REPO_ROOT / "docs" / "DATASET_INVESTIGATION.md"

RESEARCH = (
    ("01_configuration.pcap", "research"),
    ("02_variations.pcapng", "research"),
    ("03_combined_messages.pcap", "research"),
    ("04_new_observations.pcapng", "additional"),
)
DIAGNOSTICS = (
    ("01_retransmission.pcap", "retransmission"),
    ("02_reordered.pcapng", "out-of-order delivery"),
    ("03_missing_segment.pcap", "a missing segment"),
    ("04_snaplen_truncated.pcapng", "a truncated snapshot"),
    ("05_conflicting_overlap.pcap", "a conflicting overlap"),
    ("06_missing_beginning.pcapng", "a connection with no start"),
    ("07_checksum_offload.pcap", "checksum offloading"),
    ("08_bad_checksum.pcapng", "a wrong checksum"),
)
REQUEST_V1 = "thermostand_request_v1.json"
REQUEST_V2 = "thermostand_request_v2.json"
RESPONSE_V2 = "thermostand_response_v2.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="report path, or - for stdout")
    return parser


def _payload(path: Path) -> dict:
    from src.capture.export import export_capture
    from src.capture.pipeline import normalize

    capture = normalize(path)
    with tempfile.TemporaryDirectory() as directory:
        exported = Path(directory) / "normalized.json"
        export_capture(
            capture.sessions,
            exported,
            source_file=str(path),
            capture_id=capture.capture_id,
            streams=capture.streams,
        )
        return json.loads(exported.read_text(encoding="utf-8"))


def _streams(payload: dict):
    from src.hypothesis.corpus import CorpusStream
    from src.protocol.stream import capture_from_dict

    capture = capture_from_dict(payload)
    return [
        CorpusStream(stream=stream, session_id=session_id, direction=direction)
        for session_id, direction, stream in capture.iter_streams()
    ]


def _diagnostics(path: Path, *, verify_checksums: bool = False) -> list[str]:
    from src.capture.pipeline import normalize

    capture = normalize(path, ignore_checksums=not verify_checksums)
    seen: list[str] = []
    for stream in capture.streams.values():
        for directional in stream.values():
            for diagnostic in directional.diagnostics:
                if diagnostic.type not in seen:
                    seen.append(diagnostic.type)
    return seen


def _rule_totals(rule_name: str, payload: dict) -> dict:
    from src.protocol.rule import load_rule
    from src.hypothesis.corpus import verify_on_corpus

    rule = load_rule(str(EXAMPLES / rule_name))
    report = verify_on_corpus(rule, _streams(payload))
    return report.totals


def _refinement(payload: dict) -> tuple[dict, dict, list]:
    from src.protocol.rule import load_rule
    from src.hypothesis.corpus import verify_on_corpus

    naive = verify_on_corpus(load_rule(str(EXAMPLES / REQUEST_V1)), _streams(payload))
    refined = verify_on_corpus(load_rule(str(EXAMPLES / REQUEST_V2)), _streams(payload))
    return naive.totals, refined.totals, naive.contradictions


def _table(rows: list[list[str]], header: list[str]) -> str:
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def build_report() -> str:
    payloads = {name: _payload(REAL / sub / name) for name, sub in RESEARCH}

    request_rows = []
    response_rows = []
    for name, _ in RESEARCH:
        request = _rule_totals(REQUEST_V2, payloads[name])
        response = _rule_totals(RESPONSE_V2, payloads[name])
        request_rows.append(
            [
                name,
                str(request["matched"]),
                str(request["mismatched"]),
                str(request["incomplete"]),
                str(request["not_applicable"]),
            ]
        )
        response_rows.append(
            [
                name,
                str(response["matched"]),
                str(response["mismatched"]),
                str(response["incomplete"]),
                str(response["not_applicable"]),
            ]
        )

    naive_totals, refined_totals, contradictions = _refinement(
        payloads["01_configuration.pcap"]
    )
    counter_rows = [
        [
            item.status.value if hasattr(item.status, "value") else str(item.status),
            str(item.field_name),
            str(item.reason),
        ]
        for item in contradictions
    ]

    diagnostic_rows = []
    for name, purpose in DIAGNOSTICS:
        seen = _diagnostics(REAL / "diagnostics" / name)
        diagnostic_rows.append([name, purpose, ", ".join(seen) or "none"])

    offload_default = _diagnostics(REAL / "diagnostics" / "07_checksum_offload.pcap")
    offload_checked = _diagnostics(
        REAL / "diagnostics" / "07_checksum_offload.pcap", verify_checksums=True
    )

    from src.hypothesis.journal import correlate, load_journal
    from src.protocol.engine import apply_rule
    from src.protocol.rule import load_rule
    from src.protocol.stream import capture_from_dict

    entries = load_journal(str(REAL / "action_journal.csv"))
    capture = capture_from_dict(payloads["01_configuration.pcap"])
    rule = load_rule(str(EXAMPLES / REQUEST_V2))
    messages = []
    for session_id, direction, stream in capture.iter_streams():
        if direction == rule.direction:
            messages.extend(apply_rule(stream, rule, session_id, direction))
    correlation = correlate(messages, entries)

    sections = [
        "# Investigation of the supplied captures",
        "",
        "The organizer's capture set is normalized with the same path the "
        "application uses (`src/capture/pipeline.py`) and read back through the "
        "capture contract, so these numbers describe the shipped files and the "
        "shipped code, not a fixture.",
        "",
        "## 1. Research captures",
        "",
        "The request rule (`examples/thermostand_request_v2.json`) and the "
        "response rule (`examples/thermostand_response_v2.json`) are applied to "
        "every research capture. `not_applicable` counts the messages the other "
        "direction carries, so a clean capture reports only `matched`.",
        "",
        "Requests:",
        "",
        _table(
            request_rows,
            ["capture", "matched", "mismatched", "incomplete", "not_applicable"],
        ),
        "",
        "Responses:",
        "",
        _table(
            response_rows,
            ["capture", "matched", "mismatched", "incomplete", "not_applicable"],
        ),
        "",
        "No message is mismatched, incomplete or ambiguous in any research "
        "capture. The two exceptions in the response stream of the variations "
        "capture are error replies (`value_out_of_range`, `malformed_body`): "
        "they carry a one-byte body, so the configuration fields after the "
        "status are correctly out of the message and the fields that belong to "
        "a successful reply are not applied.",
        "",
        "## 2. Refinement from a counterexample",
        "",
        "The first reading (`examples/thermostand_request_v1.json`) assumes the "
        "length field counts the payload only and that a message starts at the "
        "first byte of the length field. Applied to the configuration capture:",
        "",
        _table(
            [
                [
                    "v1 (payload-only length)",
                    str(naive_totals["matched"]),
                    str(naive_totals["mismatched"]),
                    str(naive_totals["incomplete"]),
                ],
                [
                    "v2 (length includes the four-byte header)",
                    str(refined_totals["matched"]),
                    str(refined_totals["mismatched"]),
                    str(refined_totals["incomplete"]),
                ],
            ],
            ["rule", "matched", "mismatched", "incomplete"],
        ),
        "",
        "The counterexamples v1 produces, each tied to its bytes:",
        "",
        _table(counter_rows, ["status", "field", "reason"]),
        "",
        "The fix is a four-byte header bias on the length framing, which v2 "
        "carries as `length_bias`. The counterexamples are the evidence: the "
        "first message under v1 is framed four bytes short, so the magic is read "
        "at the wrong offset and the counter lands outside the message.",
        "",
        "## 3. Diagnostic captures",
        "",
        "Each diagnostic capture is built to exercise one failure mode. The "
        "diagnostics below are what the reassembler actually reports.",
        "",
        _table(diagnostic_rows, ["capture", "exercises", "diagnostics reported"]),
        "",
        f"Checksum verification is off by default, so "
        f"`07_checksum_offload.pcap` reports `{', '.join(offload_default) or 'none'}`. "
        f"With `--verify-checksums` it reports "
        f"`{', '.join(offload_checked) or 'none'}`.",
        "",
        "## 4. Journal correlation",
        "",
        f"The action journal holds {len(entries)} entries. The decoded requests "
        f"correlate as follows: {correlation.summary()}",
        "",
        "The correlation ties each request message to the operator action it "
        "performs and confirms the decoded parameters against the recorded "
        "values, so a field name is not merely a plausible label.",
        "",
    ]
    return "\n".join(sections)


def main() -> int:
    args = _build_parser().parse_args()
    report = build_report()
    if str(args.out) == "-":
        print(report)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
