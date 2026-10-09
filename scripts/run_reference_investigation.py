#!/usr/bin/env python3
"""Reproducible reference investigation over the protocol corpus.

Applies a first interpretation (rule v1) to a corpus, surfaces the messages it
gets wrong as counterexamples, refines the rule into v2 using the observed
values, re-checks both corpus captures and writes a markdown report. The report
is the basis for the presentation section of REPORT.md.

Nothing here is hardcoded from the corpus: paths come from argparse or the
environment, and the refinement is derived from the counterexamples actually
found. When the corpus or a rule is missing the script stops with an error; it
never fabricates a report.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_DIR = REPO_ROOT / "tests" / "corpus"
DEFAULT_CORPUS = ("corpus_capture_01.pcapng", "corpus_capture_02.pcapng")
DEFAULT_RULE = REPO_ROOT / "rules" / "rule_v1.json"
DEFAULT_OUT = REPO_ROOT / "docs" / "REFERENCE_INVESTIGATION.md"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=_env_path("MADRIGAL_CORPUS_DIR", DEFAULT_CORPUS_DIR),
        help="directory holding the corpus captures",
    )
    parser.add_argument(
        "--capture",
        action="append",
        default=None,
        help="capture file name inside --corpus-dir; repeatable (default: the "
        "two reference captures)",
    )
    parser.add_argument(
        "--rule",
        type=Path,
        default=_env_path("MADRIGAL_RULE", DEFAULT_RULE),
        help="rule to start from (becomes rule v1)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_env_path("MADRIGAL_REPORT", DEFAULT_OUT),
        help="markdown report to write",
    )
    parser.add_argument(
        "--refine-fields",
        default="command,value,parameter_value",
        help="comma-separated candidate field names to widen when refining",
    )
    return parser


def _load_capture_payload(capture_path: Path) -> dict:
    from src.capture.pipeline import normalize
    from src.capture.export import export_capture
    import json
    import tempfile

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


def _apply(rule, payload: dict):
    from src.protocol.engine import apply_rule
    from src.protocol.result import build_result
    from src.protocol.stream import capture_from_dict

    capture = capture_from_dict(payload)
    messages = []
    for session_id, direction, stream in capture.iter_streams():
        if not rule.applies_to(direction):
            continue
        messages.extend(apply_rule(stream, rule, session_id, direction))
    return capture.capture_hash, build_result(rule, capture.capture_hash, messages)


def _refine(rule, counterexamples, candidate_fields):
    """Widen the rule from the values it failed on.

    For each field named in *candidate_fields* that appears as a counterexample,
    the observed value is added to that field's ``expected`` set. The rule is
    then bumped one version. Returns ``(revised_rule, changes)``.
    """
    from dataclasses import replace

    values: dict[str, set] = {}
    for counter in counterexamples:
        name = counter.get("field_name")
        if not name or name not in candidate_fields:
            continue
        raw = counter.get("bytes_hex")
        if not raw:
            continue
        field = counter.get("field_offset")
        width = counter.get("field_length")
        if field is None or not width:
            continue
        field_bytes = bytes.fromhex(raw)[field : field + width]
        values.setdefault(name, set()).add(int.from_bytes(field_bytes, "big"))

    if not values:
        return None, []

    fields = []
    changes = []
    for spec in rule.fields:
        if spec.name in values:
            current = list(spec.expected or [])
            added = sorted(v for v in values[spec.name] if v not in current)
            if added:
                changes.append((spec.name, current, added))
                fields.append(replace(spec, expected=current + added))
                continue
        fields.append(spec)
    if not changes:
        return None, []
    return rule.bump_version(fields=fields), changes


def _format_report(header, sections) -> str:
    lines = [header, ""]
    for title, body in sections:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    captures = args.capture or list(DEFAULT_CORPUS)
    capture_paths = [args.corpus_dir / name for name in captures]
    missing = [str(p) for p in capture_paths if not p.is_file()]
    if missing:
        raise SystemExit(
            "corpus not ready, waiting for Agent 1; missing: " + ", ".join(missing)
        )
    if not args.rule.is_file():
        raise SystemExit(f"rule not found: {args.rule}")

    from src.protocol.rule import load_rule
    from src.hypothesis.corpus import CorpusStream, verify_on_corpus
    from src.hypothesis.versioning import compare_reports

    candidate_fields = {name.strip() for name in args.refine_fields.split(",") if name.strip()}

    rule_v1 = load_rule(str(args.rule))
    payloads = {path: _load_capture_payload(path) for path in capture_paths}
    primary = capture_paths[0]

    from src.protocol.stream import capture_from_dict

    def corpus_streams(payload):
        capture = capture_from_dict(payload)
        return [
            CorpusStream.from_bytes(stream.data, session_id, direction)
            for session_id, direction, stream in capture.iter_streams()
        ], capture.capture_hash

    primary_streams, primary_id = corpus_streams(payloads[primary])
    report_v1 = verify_on_corpus(rule_v1, primary_streams)

    revised, changes = _refine(rule_v1, [c.to_dict() for c in report_v1.contradictions], candidate_fields)
    report_v2 = None
    comparison = None
    if revised is not None:
        report_v2 = verify_on_corpus(revised, primary_streams)
        comparison = compare_reports(report_v1, report_v2)

    sections = []

    obs = [
        f"- Corpus: {primary.name} (capture_id {primary_id}).",
        f"- Rule v{rule_v1.rule_version} scope: {rule_v1.direction or 'both directions'}.",
        f"- Messages framed: {report_v1.total}.",
        "- Counts: "
        + ", ".join(f"{k}={v}" for k, v in report_v1.counts().items()),
    ]
    sections.append(("Observations", "\n".join(obs)))

    if report_v1.contradictions:
        lines = [f"{len(report_v1.contradictions)} counterexamples against rule v1:", ""]
        for counter in report_v1.contradictions:
            lines.append(
                f"- status={counter.status.value} session={counter.session_id} "
                f"direction={counter.direction} message_offset={counter.message_offset} "
                f"field={counter.field_name} reason={counter.reason}"
            )
            lines.append(f"  bytes_hex={counter.bytes_hex}")
            provenance = counter.provenance_range
            if provenance:
                lines.append(f"  provenance={provenance}")
        sections.append(("Counterexamples", "\n".join(lines)))
    else:
        sections.append(("Counterexamples", "None within the tested corpus."))

    if revised is not None and report_v2 is not None and comparison is not None:
        lines = [
            f"Rule refined to v{revised.rule_version}. Changes:",
            "",
        ]
        for name, before, added in changes:
            lines.append(f"- field {name}: expected {before} -> {before + added}")
        lines += [
            "",
            f"Counts after refinement: "
            + ", ".join(f"{k}={v}" for k, v in report_v2.counts().items()),
            f"Resolved counterexamples: {len(comparison.resolved)}.",
            f"Introduced counterexamples: {len(comparison.introduced)}.",
        ]
        sections.append(("Refinement", "\n".join(lines)))

        if len(capture_paths) > 1:
            secondary = capture_paths[1]
            secondary_streams, secondary_id = corpus_streams(payloads[secondary])
            report_secondary = verify_on_corpus(revised, secondary_streams)
            lines = [
                f"Rule v{revised.rule_version} applied to {secondary.name} "
                f"(capture_id {secondary_id}).",
                "Counts: " + ", ".join(f"{k}={v}" for k, v in report_secondary.counts().items()),
                f"Counterexamples: {len(report_secondary.contradictions)}.",
            ]
            sections.append(("Applicability", "\n".join(lines)))
    else:
        sections.append(("Refinement", "No refinement was needed."))

    open_questions = [
        "- Field meanings marked `hypothesis: true` remain assumptions.",
        "- Behaviour outside the tested captures is unknown; the rule is only "
        "confirmed within the tested domain.",
    ]
    sections.append(("Open questions", "\n".join(open_questions)))

    header = "# Reference investigation"
    text = _format_report(header, sections)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
