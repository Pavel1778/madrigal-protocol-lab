"""Command line interface for replaying a rule against a normalized capture.

    python -m src.protocol.cli apply --rule rule.json --capture normalized.json --out result.json
    python -m src.protocol.cli verify --rule rule.json --capture normalized.json --out report.json

``apply`` produces a contract result for one directional stream. ``verify``
applies the rule to every stream in the capture and reports the classification
counts together with the counterexamples.
"""

from __future__ import annotations

import argparse
import json
import sys

from ..hypothesis.corpus import CorpusStream, verify_on_corpus
from .engine import apply_rule
from .result import build_result, write_result
from .rule import load_rule
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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "apply":
            return _cmd_apply(args)
        if args.command == "verify":
            return _cmd_verify(args)
    except (CaptureError, ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    parser.exit(2, "error: no command\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
