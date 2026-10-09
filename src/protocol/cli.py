"""Command line interface for replaying a rule against a normalized capture.

    python -m src.protocol.cli apply --rule rule.json --capture normalized.json --out result.json
    python -m src.protocol.cli verify --rule rule.json --capture normalized.json --out report.json
    python -m src.protocol.cli diff --rule-a v1.json --rule-b v2.json
    python -m src.protocol.cli metrics --report r1.json --out metrics.json
    python -m src.protocol.cli correlate --capture normalized.json --journal journal.md
    python -m src.protocol.cli export --rule rule.json --format kaitai --out out/
    python -m src.protocol.cli alternatives --report r1.json --corpus normalized.json --field value

``apply`` produces a contract result for one directional stream. ``verify``
applies the rule to every stream in the capture and reports the classification
counts together with the counterexamples.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from ..hypothesis.alternatives import AlternativesReport, analyze_field, suggest_alternatives
from ..hypothesis.corpus import CorpusStream, VerificationReport, verify_on_corpus
from ..hypothesis.diff import diff_reports, diff_rules, format_report_diff, format_rule_diff
from ..hypothesis.journal import correlate, load_journal
from ..hypothesis.metrics import compute_metrics
from .engine import Counterexample, MessageResult, apply_rule
from .export import export_kaitai, export_python
from .result import build_result, write_result
from .rule import Rule, load_rule
from .stream import CaptureError, load_capture


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.protocol.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    apply = sub.add_parser("apply", help="apply one rule to one directional stream")
    apply.add_argument("--rule", required=True, help="path to a rule (JSON or YAML)")
    apply.add_argument("--capture", required=True, help="path to a normalized capture")
    apply.add_argument("--out", required=True, help="path to write the result to")
    apply.add_argument("--session", default=None, help="session id (default: first session)")
    apply.add_argument("--direction", default=None, help="A_to_B or B_to_A (default: rule scope or A_to_B)")

    verify = sub.add_parser("verify", help="verify one rule on every stream of a capture")
    verify.add_argument("--rule", required=True, help="path to a rule (JSON or YAML)")
    verify.add_argument("--capture", required=True, help="path to a normalized capture")
    verify.add_argument("--out", default=None, help="path to write the report to (default: stdout)")

    diff = sub.add_parser("diff", help="diff two rules and two verification reports")
    diff.add_argument("--rule-a", required=True, help="path to the older rule")
    diff.add_argument("--rule-b", required=True, help="path to the newer rule")
    diff.add_argument("--report-a", default=None, help="verification report for rule A")
    diff.add_argument("--report-b", default=None, help="verification report for rule B")
    diff.add_argument("--out", default=None, help="path to write the JSON diff to (default: stdout)")

    metrics = sub.add_parser("metrics", help="compute quality metrics for a verification report")
    metrics.add_argument("--report", required=True, help="verification report JSON")
    metrics.add_argument("--out", default=None, help="path to write metrics JSON to (default: stdout)")

    correlate = sub.add_parser("correlate", help="correlate stream messages with an action journal")
    correlate.add_argument("--rule", required=True, help="path to a rule to decode messages")
    correlate.add_argument("--capture", required=True, help="path to a normalized capture")
    correlate.add_argument("--journal", required=True, help="path to a journal file")
    correlate.add_argument("--session", default=None, help="session id (default: first session)")
    correlate.add_argument("--direction", default=None, help="A_to_B or B_to_A (default: A_to_B)")
    correlate.add_argument("--window-ms", type=int, default=500, help="time window in milliseconds")
    correlate.add_argument("--out", default=None, help="path to write correlations JSON to (default: stdout)")

    export = sub.add_parser("export", help="export a rule as a Kaitai .ksy or a Python parser")
    export.add_argument("--rule", required=True, help="path to a rule (JSON or YAML)")
    export.add_argument("--format", required=True, choices=["kaitai", "python"])
    export.add_argument("--out", required=True, help="output file or directory")

    alternatives = sub.add_parser(
        "alternatives", help="suggest alternative explanations for a hypothesis field"
    )
    alternatives.add_argument("--rule", required=True, help="the rule that produced the report")
    alternatives.add_argument("--report", required=True, help="report JSON from the verify command")
    alternatives.add_argument("--corpus", default=None, help="normalized capture for the corpus")
    alternatives.add_argument("--journal", default=None, help="journal file for correlation")
    alternatives.add_argument("--field", default=None, help="hypothesis field name")
    alternatives.add_argument(
        "--all",
        action="store_true",
        help="report every hypothesis field instead of one field",
    )
    alternatives.add_argument("--out", default=None, help="path to write JSON to (default: stdout)")
    return parser


def _select_stream(capture, session: str | None, direction: str | None):
    streams = capture.iter_streams()
    if not streams:
        raise CaptureError("capture has no directional streams")
    if session is None and direction is None:
        return streams[0]
    chosen = [
        item
        for item in streams
        if (session is None or item[0] == session) and (direction is None or item[1] == direction)
    ]
    if not chosen:
        raise CaptureError("no stream matches the requested session and direction")
    return chosen[0]


def _cmd_apply(args) -> int:
    rule = load_rule(args.rule)
    capture = load_capture(args.capture)
    direction = args.direction or rule.direction or "A_to_B"
    session_id, direction, stream = _select_stream(capture, args.session, direction)
    messages = apply_rule(stream, rule, session_id, direction)
    result = build_result(rule, capture.capture_hash, messages)
    write_result(result, args.out)
    counts = result.summary
    print(
        f"{args.out}: rule {rule.rule_id} v{rule.rule_version}, "
        f"{counts.get('matched', 0)} matched, {counts.get('mismatched', 0)} mismatched",
        file=sys.stderr,
    )
    return 0


def _cmd_verify(args) -> int:
    rule = load_rule(args.rule)
    capture = load_capture(args.capture)
    corpus = [
        CorpusStream(stream=stream, session_id=session_id, direction=direction)
        for session_id, direction, stream in capture.iter_streams()
    ]
    report = verify_on_corpus(rule, corpus)
    payload = report.to_dict()
    payload["capture_id"] = capture.capture_hash
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    print(
        f"rule {rule.rule_id} v{rule.rule_version}: {report.total} messages, "
        f"{len(report.contradictions)} counterexamples",
        file=sys.stderr,
    )
    return 0


def _cmd_diff(args) -> int:
    rule_a = load_rule(args.rule_a)
    rule_b = load_rule(args.rule_b)
    rule_diff = diff_rules(rule_a, rule_b)
    payload: dict = {"rule_diff": rule_diff.to_dict()}
    print(format_rule_diff(rule_diff), file=sys.stderr)

    if args.report_a and args.report_b:
        report_a = _load_report(args.report_a)
        report_b = _load_report(args.report_b)
        report_diff = diff_reports(report_a, report_b)
        payload["report_diff"] = report_diff.to_dict()
        print(format_report_diff(report_diff), file=sys.stderr)

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    return 0


def _load_report(path: str) -> VerificationReport:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return report_from_dict(payload)


def report_from_dict(payload: dict) -> VerificationReport:
    """Rebuild a report from the JSON produced by ``verify``."""
    from ..hypothesis.status import Status
    from .engine import FieldResult, MessageResult

    messages = []
    for item in payload.get("messages", []):
        fields = [
            FieldResult(
                message_offset=int(item.get("offset", 0)),
                message_length=int(item.get("length", 0)),
                field_name=str(name),
                field_type="unknown",
                field_offset=0,
                field_length=0,
                value=value,
                status=Status.MATCHED,
            )
            for name, value in (item.get("fields") or {}).items()
        ]
        messages.append(
            MessageResult(
                offset=int(item.get("offset", 0)),
                length=int(item.get("length", 0)),
                status=Status(item.get("status", "unknown")),
                fields=fields,
                session_id=str(item.get("session_id", "")),
                direction=str(item.get("direction", "")),
            )
        )
    return VerificationReport(
        rule_id=str(payload.get("rule_id", "")),
        rule_version=int(payload.get("rule_version", 1)),
        totals=dict(payload.get("counts", {})),
        total=int(payload.get("total", 0)),
        contradictions=[_counterexample(item) for item in payload.get("contradictions", [])],
        messages=messages,
        summary=str(payload.get("summary", "")),
        stream_bytes=int(payload.get("stream_bytes", 0)),
    )


def _cmd_metrics(args) -> int:
    report = _load_report(args.report)
    metrics = compute_metrics(report)
    text = json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    print(
        f"rule {metrics.rule_id} v{metrics.rule_version}: coverage {metrics.coverage:.3f}, "
        f"precision {metrics.precision:.3f}, counterexample density {metrics.counterexample_density:.1f}/100",
        file=sys.stderr,
    )
    return 0


def _cmd_correlate(args) -> int:
    rule = load_rule(args.rule)
    capture = load_capture(args.capture)
    session_id, direction, stream = _select_stream(
        capture, args.session, args.direction or rule.direction or "A_to_B"
    )
    entries = load_journal(args.journal)
    messages = apply_rule(stream, rule, session_id, direction)
    report = correlate(messages, entries, args.window_ms)
    text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    print(report.summary(), file=sys.stderr)
    return 0


def _cmd_export(args) -> int:
    import os

    rule = load_rule(args.rule)
    if args.format == "kaitai":
        text = export_kaitai(rule)
        suffix = ".ksy"
    else:
        text = export_python(rule)
        suffix = ".py"

    target = args.out
    if os.path.isdir(target) or target.endswith(os.sep):
        os.makedirs(target, exist_ok=True)
        stem = (rule.name or rule.rule_id).replace("/", "_")
        target = os.path.join(target, stem + suffix)
    directory = os.path.dirname(os.path.abspath(target))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"{target}: rule {rule.rule_id} v{rule.rule_version} as {args.format}", file=sys.stderr)
    return 0


def _cmd_alternatives(args) -> int:
    payload = json.load(open(args.report, "r", encoding="utf-8"))
    rule = load_rule(args.rule)
    messages = _messages_from_payload(payload)
    correlations = None
    if args.journal:
        entries = load_journal(args.journal)
        correlations = correlate(messages, entries).correlated

    if args.all:
        report = suggest_alternatives(rule, messages, correlations=correlations)
    else:
        if not args.field:
            print("provide --field NAME or --all", file=sys.stderr)
            return 2
        report = AlternativesReport(rule_id=rule.rule_id, rule_version=rule.rule_version)
        report.fields.append(
            analyze_field(rule, messages, args.field, correlations=correlations)
        )
    text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    for field_report in report.fields:
        best = field_report.best or "none"
        print(
            f"field {field_report.field_name}: "
            f"{len(field_report.alternatives)} alternatives, best {best}",
            file=sys.stderr,
        )
    return 0


def _messages_from_payload(payload: dict) -> list:
    from ..hypothesis.status import Status
    from .engine import FieldResult, MessageResult

    messages = []
    for item in payload.get("messages", []):
        if "message_offset" in item and "field_name" in item:
            continue
        status = Status(item.get("status", "unknown"))
        fields = [
            FieldResult(
                message_offset=int(item.get("offset", 0)),
                message_length=int(item.get("length", 0)),
                field_name=str(name),
                field_type="unknown",
                field_offset=0,
                field_length=0,
                value=value,
                status=Status.MATCHED,
            )
            for name, value in (item.get("fields") or {}).items()
        ]
        messages.append(
            MessageResult(
                offset=int(item.get("offset", 0)),
                length=int(item.get("length", 0)),
                status=status,
                fields=fields,
                session_id=str(item.get("session_id", "")),
                direction=str(item.get("direction", "")),
                bytes_hex=item.get("bytes_hex", ""),
            )
        )
    return messages


def _counterexample(item: dict) -> Counterexample:
    from ..hypothesis.status import Status

    return Counterexample(
        status=Status(item["status"]),
        reason=item.get("reason"),
        session_id=str(item.get("session_id", "")),
        direction=str(item.get("direction", "")),
        message_offset=int(item.get("message_offset", 0)),
        message_length=int(item.get("message_length", 0)),
        field_name=item.get("field_name"),
        field_offset=item.get("field_offset"),
        field_length=item.get("field_length"),
        bytes_hex=item.get("bytes_hex"),
        provenance_range=item.get("provenance_range"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "apply":
            return _cmd_apply(args)
        if args.command == "verify":
            return _cmd_verify(args)
        if args.command == "diff":
            return _cmd_diff(args)
        if args.command == "metrics":
            return _cmd_metrics(args)
        if args.command == "correlate":
            return _cmd_correlate(args)
        if args.command == "export":
            return _cmd_export(args)
        if args.command == "alternatives":
            return _cmd_alternatives(args)
    except (CaptureError, ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    parser.exit(2, "error: no command\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
