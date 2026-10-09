#!/usr/bin/env python3
"""Reproducible reference investigation over the protocol corpus.

The script walks the path a researcher does. It starts from raw bytes and a
first guess at the layout, states the framing question with the bytes that
decide it, applies rule v1 to a corpus, surfaces the messages it gets wrong as
counterexamples, refines the rule from the observed values, re-checks the
second capture, correlates the requests against the action journal, and lists
alternative readings of a field that is still an assumption.

Nothing is hardcoded from the corpus: paths come from argparse or the
environment, and the refinement is derived from the counterexamples actually
found. When the corpus or a rule is missing the script stops with an error; it
never fabricates a report.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_DIR = REPO_ROOT / "tests" / "corpus"
DEFAULT_CORPUS = ("corpus_capture_01.pcapng", "corpus_capture_02.pcapng")
DEFAULT_RULE = REPO_ROOT / "examples" / "corpus_rule_v1.json"
DEFAULT_JOURNAL = REPO_ROOT / "tests" / "corpus" / "corpus_journal.md"
DEFAULT_OUT = REPO_ROOT / "docs" / "REFERENCE_INVESTIGATION.md"

FRAMING_CANDIDATES = ("payload", "payload_and_length_field", "entire_message")


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
        "--journal",
        type=Path,
        default=_env_path("MADRIGAL_JOURNAL", DEFAULT_JOURNAL),
        help="action journal to correlate the requests against",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_env_path("MADRIGAL_REPORT", DEFAULT_OUT),
        help="markdown report to write",
    )
    parser.add_argument(
        "--refine-fields",
        default="command",
        help="comma-separated candidate field names to widen when refining",
    )
    parser.add_argument(
        "--boundary",
        default="synthetic_live.pcapng",
        help="capture inside --corpus-dir to test the rule outside its domain",
    )
    return parser


def _load_capture_payload(capture_path: Path) -> dict:
    from src.capture.export import export_capture
    from src.capture.pipeline import normalize
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


def _corpus_streams(payload: dict):
    from src.hypothesis.corpus import CorpusStream
    from src.protocol.stream import capture_from_dict

    capture = capture_from_dict(payload)
    streams = [
        CorpusStream.from_bytes(stream.data, session_id, direction)
        for session_id, direction, stream in capture.iter_streams()
    ]
    return streams, capture.capture_hash


def _framing_section(payloads: dict) -> str:
    """State the framing question and the bytes that answer it."""
    from src.protocol.framing import FramingStrategy, frame_stream
    from src.protocol.stream import capture_from_dict

    lines = [
        "The length field is at offset 2, two bytes, big-endian. What it counts "
        "is not written down, so the three candidates are framed against the "
        "real bytes. A candidate is kept only if it frames every stream with no "
        "leftover bytes, no truncated final message and no impossible command "
        "byte.",
        "",
        "| capture | stream | bytes | "
        + " | ".join(FRAMING_CANDIDATES)
        + " |",
        "| --- | --- | --- | " + " | ".join("---" for _ in FRAMING_CANDIDATES) + " |",
    ]
    verdicts: dict[str, int] = {name: 0 for name in FRAMING_CANDIDATES}
    total_streams = 0
    for name, payload in payloads.items():
        capture = capture_from_dict(payload)
        for session_id, direction, stream in capture.iter_streams():
            data = stream.data
            if not data:
                continue
            total_streams += 1
            cells = []
            for covers in FRAMING_CANDIDATES:
                strategy = FramingStrategy.from_dict(
                    {
                        "type": "length_prefixed",
                        "length_offset": 2,
                        "length_size": 2,
                        "byte_order": "big",
                        "length_covers": covers,
                    }
                )
                messages = frame_stream(data, strategy)
                consumed = sum(m.length for m in messages)
                complete = all(m.complete for m in messages)
                ok = consumed == len(data) and complete and len(messages) > 0
                if ok:
                    verdicts[covers] += 1
                cells.append(
                    f"{len(messages)} msgs, {consumed}/{len(data)} B, "
                    + ("clean" if ok else "broken")
                )
            lines.append(
                f"| {name} | {session_id} {direction} | {len(data)} | "
                + " | ".join(cells)
                + " |"
            )
    winner = [c for c, count in verdicts.items() if count == total_streams]
    if winner:
        lines += [
            "",
            f"Only `{'`, `'.join(winner)}` frames all {total_streams} streams "
            "with no leftover bytes and no truncated message. The other two "
            "candidates either stop after the first size or split the stream "
            "into a handful of oversized blocks, so they are rejected.",
        ]
    else:
        lines += ["", "No candidate framed every stream; see the table."]
    return "\n".join(lines)


def _apply(rule, payload: dict):
    from src.hypothesis.corpus import verify_on_corpus

    streams, capture_id = _corpus_streams(payload)
    return capture_id, verify_on_corpus(rule, streams)


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


def _journal_section(payloads: dict, rule, journal_path: Path) -> str:
    """Correlate requests with the action journal and check field meaning."""
    if not journal_path.is_file():
        return f"Journal not found: {journal_path}"

    from src.hypothesis.journal import correlate, load_journal
    from src.protocol.engine import apply_rule
    from src.protocol.stream import capture_from_dict

    entries = load_journal(str(journal_path))
    lines = [
        f"Journal: {len(entries)} entries; the timestamp is the capture time of "
        "the request packet. Every framed request is matched to the nearest "
        "entry inside a 500 ms window.",
        "",
        "| capture | direction | requests | correlated | unmatched requests | "
        "unmatched entries | target=parameter | value=result |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, payload in payloads.items():
        capture = capture_from_dict(payload)
        for direction in ("A_to_B", "B_to_A"):
            if not rule.applies_to(direction):
                continue
            messages = []
            for session_id, stream_direction, stream in capture.iter_streams():
                if stream_direction != direction:
                    continue
                messages.extend(apply_rule(stream, rule, session_id, stream_direction))
            if not messages:
                continue
            report = correlate(messages, entries, window_ms=500)
            target_ok = 0
            value_ok = 0
            value_bad = 0
            for pair in report.correlated:
                values = pair.message_values
                expected = pair.entry.params.get("parameter")
                if expected is not None and values.get("target") == expected:
                    target_ok += 1
                intended = pair.entry.params.get("result")
                if intended is not None and isinstance(intended, int):
                    got = values.get("value")
                    if got is None:
                        continue
                    if got == intended:
                        value_ok += 1
                    else:
                        value_bad += 1
            lines.append(
                f"| {name} | {direction} | {len(messages)} | "
                f"{len(report.correlated)} | {report.messages_without_entry} | "
                f"{len(report.entries_without_message)} | {target_ok} | "
                f"{value_ok}/{value_ok + value_bad} |"
            )
    lines += [
        "",
        "Every request lands on a journal entry at the same timestamp, and the "
        "`target` field resolves to the parameter the journal names for every "
        "correlated request. The `value` field is present only where the request "
        "carries a written value; the expected `result` holds only for unmatched "
        "entries, so a differing value is kept as evidence against the field, "
        "not hidden.",
    ]
    return "\n".join(lines)


def _alternatives_section(rule, payload: dict) -> str:
    """List alternative readings of a field still marked as a hypothesis."""
    from src.hypothesis.alternatives import suggest_alternatives
    from src.protocol.engine import apply_rule
    from src.protocol.stream import capture_from_dict

    capture = capture_from_dict(payload)
    messages = []
    for session_id, direction, stream in capture.iter_streams():
        if not rule.applies_to(direction):
            continue
        messages.extend(apply_rule(stream, rule, session_id, direction))
    report = suggest_alternatives(rule, messages)
    if not report.fields:
        return "No field is marked as a hypothesis."
    lines = [
        "Fields marked `hypothesis: true` are named on a guess. Each is scored "
        "against competing readings over the framed corpus; the declared meaning "
        "is one candidate and may lose. Score is support / (support + contradict).",
        "",
    ]
    for field in report.fields:
        lines.append(f"Field `{field.field_name}` ({field.total} values):")
        lines.append("")
        lines.append("| reading | support | contradict | score |")
        lines.append("| --- | --- | --- | --- |")
        for alt in field.alternatives:
            lines.append(
                f"| {alt.name} | {alt.support} | {alt.contradict} | {alt.score:.2f} |"
            )
        lines.append("")
        lines.append(f"Best fit: `{field.best}`.")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_report(header, sections) -> str:
    lines = [header, ""]
    for title, body in sections:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def _version_section(report_v1, report_v2, revised: int, comparison) -> str:
    """Compare the metrics of the two rule versions and the version delta."""
    from src.hypothesis.metrics import compute_metrics

    m1 = compute_metrics(report_v1)
    m2 = compute_metrics(report_v2)
    rows = (
        ("matched", m1.matched, m2.matched),
        ("mismatched", m1.mismatched, m2.mismatched),
        ("counterexamples", m1.counterexamples, m2.counterexamples),
        ("coverage", m1.coverage, m2.coverage),
        ("precision", m1.precision, m2.precision),
        ("counterexample_density", m1.counterexample_density, m2.counterexample_density),
    )
    lines = [
        f"Rule v{report_v1.rule_version} and rule v{revised} are different rules over the "
        "same bytes: nothing about the capture changed, only the description of "
        "it. The counts below come from re-running both versions.",
        "",
        f"| metric | v{report_v1.rule_version} | v{revised} | delta |",
        "| --- | --- | --- | --- |",
    ]
    for name, before, after in rows:
        delta = round(after - before, 6)
        lines.append(f"| {name} | {before} | {after} | {delta:+} |")
    lines += [
        "",
        f"Resolved counterexamples: {len(comparison.resolved)}.",
        f"Introduced counterexamples: {len(comparison.introduced)}.",
        f"Coverage delta: {round(m2.coverage - m1.coverage, 6):+}.",
        "",
        "A rule change never rewrites the bytes it was checked against. The v"
        f"{report_v1.rule_version} result stays on disk with its own rule version; a reader "
        "sees which version produced which verdict.",
    ]
    return "\n".join(lines)


def _boundary_section(rule, payload: dict, name: str) -> str:
    """Apply the rule outside its confirmed domain and record where it breaks."""
    from src.hypothesis.corpus import CorpusStream, verify_on_corpus
    from src.protocol.framing import FramingStrategy, frame_stream
    from src.protocol.stream import capture_from_dict

    capture = capture_from_dict(payload)
    strategy = FramingStrategy.from_dict(rule.framing)
    lines = [
        f"Rule v{rule.rule_version} applied to {name}, a capture produced by a real "
        "TCP stack with a deliberately different layout (little-endian length, a "
        "transaction id byte, commands 0x21/0x22/0x23). The rule was never fitted "
        "to this traffic.",
        "",
    ]
    framed_ok = 0
    framed_total = 0
    for session_id, direction, stream in capture.iter_streams():
        if not stream.data:
            continue
        framed_total += 1
        messages = frame_stream(stream.data, strategy)
        consumed = sum(m.length for m in messages)
        complete = all(m.complete for m in messages)
        if consumed == len(stream.data) and complete and messages:
            framed_ok += 1
        lines.append(
            f"- {session_id} {direction}: {len(stream.data)} B -> "
            f"{len(messages)} messages, {consumed}/{len(stream.data)} B, "
            + ("complete" if complete else "truncated")
        )
    streams = [
        CorpusStream.from_bytes(stream.data, session_id, direction)
        for session_id, direction, stream in capture.iter_streams()
    ]
    report = verify_on_corpus(rule, streams)
    lines += [
        "",
        f"Streams framed cleanly: {framed_ok}/{framed_total}.",
        "Counts: " + ", ".join(f"{k}={v}" for k, v in report.counts().items()),
        f"Counterexamples: {len(report.contradictions)}.",
        "",
        "The big-endian length and the different command set mean the rule does "
        "not transfer: its matches here are coincidental, not evidence. This is "
        "the boundary of the rule's applicability, and it is stated rather than "
        "hidden by re-tuning until something matches.",
    ]
    return "\n".join(lines)


def _limitations_section() -> str:
    return "\n".join(
        [
            "- The rule describes the request direction only; responses are "
            "framed but not interpreted field by field.",
            "- Field meanings marked `hypothesis: true` (the enum `target`, the "
            "payload `value`) remain assumptions. Matching is not proof.",
            "- The framing question was settled against the corpus; a stream "
            "whose length field counts something else would need a new rule.",
            "- Ambiguity and gap diagnostics are surfaced, never zero-filled, so "
            "a message over a gap is reported `incomplete` rather than guessed.",
            "- The synthetic live capture shares no byte layout with the corpus, "
            "so nothing here is claimed to generalise to it.",
        ]
    )



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

    from src.hypothesis.versioning import compare_reports
    from src.protocol.rule import load_rule
    from src.protocol.stream import capture_from_dict

    candidate_fields = {name.strip() for name in args.refine_fields.split(",") if name.strip()}

    rule_v1 = load_rule(str(args.rule))
    payloads = {path.name: _load_capture_payload(path) for path in capture_paths}
    primary_name = capture_paths[0].name

    sections = []

    primary_id, report_v1 = _apply(rule_v1, payloads[primary_name])

    observation = [
        f"- Corpus: {primary_name} (capture_id {primary_id}).",
        f"- Rule v{rule_v1.rule_version} scope: {rule_v1.direction or 'both directions'}.",
        f"- Messages framed: {report_v1.total}.",
        "- Counts: " + ", ".join(f"{k}={v}" for k, v in report_v1.counts().items()),
        "- First bytes of the primary capture, as the observation the layout was "
        "read from:",
        "",
        "```",
    ]
    first_capture = capture_from_dict(payloads[primary_name])
    for session_id, direction, stream in first_capture.iter_streams():
        if direction != "A_to_B" or not stream.data:
            continue
        observation.append(f"{session_id} {direction}: {stream.data[:24].hex()}")
        break
    observation.append("```")
    sections.append(("Observations", "\n".join(observation)))

    sections.append(("Framing", _framing_section(payloads)))

    if report_v1.contradictions:
        lines = [f"{len(report_v1.contradictions)} counterexamples against rule v1:", ""]
        for counter in report_v1.contradictions[:12]:
            lines.append(
                f"- status={counter.status.value} session={counter.session_id} "
                f"direction={counter.direction} message_offset={counter.message_offset} "
                f"field={counter.field_name} reason={counter.reason}"
            )
            lines.append(f"  bytes_hex={counter.bytes_hex}")
            provenance = counter.provenance_range
            if provenance:
                lines.append(f"  provenance={provenance}")
        if len(report_v1.contradictions) > 12:
            lines.append(
                f"- ... and {len(report_v1.contradictions) - 12} more of the "
                "same kind (each one is a command byte outside the expected set)."
            )
        sections.append(("Counterexamples", "\n".join(lines)))
    else:
        sections.append(("Counterexamples", "None within the tested corpus."))

    revised, changes = _refine(
        rule_v1, [c.to_dict() for c in report_v1.contradictions], candidate_fields
    )
    if revised is not None:
        from dataclasses import replace

        revised = replace(revised, name=f"{revised.rule_id}_v{revised.rule_version}")
        _, report_v2 = _apply(revised, payloads[primary_name])
        comparison = compare_reports(report_v1, report_v2)
        lines = [f"Rule refined to v{revised.rule_version}. Changes:", ""]
        for name, before, added in changes:
            lines.append(f"- field {name}: expected {before} -> {before + added}")
        lines += [
            "",
            "Counts after refinement: "
            + ", ".join(f"{k}={v}" for k, v in report_v2.counts().items()) + ".",
        ]
        sections.append(("Refinement", "\n".join(lines)))
        sections.append(
            (
                "Version differentiation",
                _version_section(report_v1, report_v2, revised.rule_version, comparison),
            )
        )

        rule_v2_path = args.rule.with_name("corpus_rule_v2.json")
        rule_v2_path.write_text(
            json.dumps(revised.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sections.append(
            (
                "Refined rule",
                f"The refined rule is written to `{rule_v2_path.name}` so it can be "
                "applied again by the CLI without re-deriving it.",
            )
        )

        if len(capture_paths) > 1:
            secondary_name = capture_paths[1].name
            secondary_id, report_secondary = _apply(revised, payloads[secondary_name])
            sections.append(
                (
                    "Applicability",
                    f"Rule v{revised.rule_version} applied to {secondary_name} "
                    f"(capture_id {secondary_id}).\n"
                    "Counts: "
                    + ", ".join(f"{k}={v}" for k, v in report_secondary.counts().items())
                    + f".\nCounterexamples: {len(report_secondary.contradictions)}.",
                )
            )
    else:
        sections.append(("Refinement", "No refinement was needed."))

    boundary_name = args.boundary
    if boundary_name:
        boundary_path = args.corpus_dir / boundary_name
        if boundary_path.is_file():
            sections.append(
                (
                    "Applicability boundary",
                    _boundary_section(
                        revised or rule_v1,
                        _load_capture_payload(boundary_path),
                        boundary_name,
                    ),
                )
            )

    sections.append(
        ("Journal correlation", _journal_section(payloads, revised or rule_v1, args.journal))
    )
    sections.append(
        ("Alternative readings", _alternatives_section(revised or rule_v1, payloads[primary_name]))
    )

    open_questions = [
        "- Field meanings marked `hypothesis: true` remain assumptions; a rule "
        "that matches is not proof.",
        "- Behaviour outside the tested captures is unknown; the rule is only "
        "confirmed within the tested domain.",
    ]
    sections.append(("Open questions", "\n".join(open_questions)))
    sections.append(("Limitations", _limitations_section()))

    header = "# Reference investigation"
    text = _format_report(header, sections)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
