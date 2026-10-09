"""End-to-end investigation pipeline.

This ties the capture engine, the portable project, and the report together so
that one call (or one CLI command) takes a PCAP/PCAPNG file and leaves behind a
project directory with the normalized capture, an investigation, and the two
report forms.

The pipeline never invents an interpretation. Without a rule it records the
capture and writes a report that states plainly that no rule was applied. With
a rule it produces the normalized capture, then applies the rule through the
protocol engine when that engine is present, and derives the investigation from
the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.capture.export import sha256_file
from src.capture.pipeline import normalize
from src.capture.streaming import process_streaming
from src.project.project import Project

# The normalized capture and the application result live under results/ so the
# manifest can point at them and they travel with the project.
NORMALIZED_NAME = "normalized.json"
RESULT_NAME = "result.json"
REPORT_MD_NAME = "REPORT.md"
REPORT_HTML_NAME = "REPORT.html"


class PipelineError(RuntimeError):
    """Raised when the pipeline cannot complete a requested step."""


@dataclass
class PipelineOutcome:
    """What the pipeline produced, for the caller to print or assert on."""

    project: Project
    normalized: Path
    result: Path | None = None
    report_md: Path | None = None
    report_html: Path | None = None
    wireshark: Path | None = None
    sessions: int = 0
    packets: int = 0
    streaming: bool = False


def _write_normalized(
    pcap: Path,
    out_path: Path,
    *,
    source_file: str,
    streaming: bool,
    chunk_size: int,
) -> int:
    """Write the normalized capture and return the number of sessions."""

    if streaming:
        stats = process_streaming(
            pcap, out_path, chunk_size=chunk_size, source_file=source_file
        )
        return stats.sessions

    capture = normalize(pcap)
    from src.capture.export import export_capture

    export_capture(
        capture.sessions,
        out_path,
        source_file=source_file,
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    return len(capture.sessions)


def _apply_rule(normalized: Path, rule_path: Path, out_path: Path) -> dict[str, Any]:
    """Apply a rule to a normalized capture, writing the result JSON.

    The protocol engine is imported lazily so this package does not depend on
    it at import time; the pipeline reports a clear error if it is absent.
    """

    try:
        from src.protocol.engine import apply_rule
        from src.protocol.result import build_result, write_result
        from src.protocol.rule import load_rule
        from src.protocol.stream import load_capture
    except ImportError as exc:  # pragma: no cover - depends on the other stage
        raise PipelineError(
            "the protocol engine (src.protocol) is required to apply a rule "
            "and is not available in this checkout"
        ) from exc

    rule = load_rule(str(rule_path))
    capture = load_capture(str(normalized))
    messages: list[Any] = []
    for session_id, direction, stream in capture.iter_streams():
        if not rule.applies_to(direction):
            continue
        messages.extend(apply_rule(stream, rule, session_id, direction))
    result = build_result(rule, capture.capture_hash, messages)
    write_result(result, str(out_path))
    return result.to_dict()


def build_investigation(
    result: dict[str, Any],
    *,
    capture_id: str,
    source_file: str,
) -> dict[str, Any]:
    """Derive an investigation dictionary from a contract result.

    The statements are deliberately modest: a rule that frames messages is
    reported as holding in the tested scope, and any message the rule could not
    confirm becomes a counterexample or an open question rather than being
    dropped. See ``src/report/model.py`` for the shape.
    """

    summary = result.get("summary") or {}
    messages = result.get("messages") or []
    matched = int(summary.get("matched", 0))
    mismatched = int(summary.get("mismatched", 0))
    incomplete = int(summary.get("incomplete", 0))
    ambiguous = int(summary.get("ambiguous", 0))
    uncovered = int(summary.get("uncovered", 0))
    unknown = int(summary.get("unknown", 0))

    if matched and not mismatched:
        status = "confirmed_in_scope"
    elif mismatched:
        status = "contradiction"
    elif incomplete or ambiguous:
        status = "ambiguous"
    else:
        status = "hypothesis"

    rule_id = result.get("rule_id", "rule")
    rule_version = result.get("rule_version", 1)

    counterexamples: list[dict[str, Any]] = []
    contradictory_statuses = {"mismatched", "ambiguous", "incomplete"}
    for message in messages:
        message_status = message.get("status")
        if message_status not in contradictory_statuses:
            continue
        entry: dict[str, Any] = {
            "id": f"c{len(counterexamples) + 1}",
            "rule_id": rule_id,
            "rule_version": rule_version,
            "capture_id": capture_id,
            "offset": message.get("offset"),
            "length": message.get("length"),
            "detail": f"message classified {message_status}",
        }
        if message.get("session_id"):
            entry["session_id"] = message["session_id"]
        if message.get("direction"):
            entry["direction"] = message["direction"]
        provenance = message.get("provenance_range") or {}
        if provenance.get("packets"):
            entry["packets"] = provenance["packets"]
        counterexamples.append(entry)

    open_questions: list[str] = []
    if incomplete:
        open_questions.append(
            f"{incomplete} message(s) fall on a gap and cannot be read whole"
        )
    if ambiguous:
        open_questions.append(
            f"{ambiguous} message(s) fall on an ambiguous overlap; the bytes are kept in both versions"
        )
    if uncovered:
        open_questions.append(f"{uncovered} message(s) are not covered by the rule")
    if unknown:
        open_questions.append(f"{unknown} message(s) have too little data to classify")

    return {
        "title": f"Investigation of {source_file}",
        "scope": {
            "capture_id": capture_id,
            "source_file": source_file,
            "rule_id": rule_id,
            "rule_version": rule_version,
        },
        "hypotheses": [
            {
                "id": "h1",
                "statement": (
                    f"rule {rule_id} frames the stream into messages that follow "
                    "the declared structure"
                ),
                "status": status,
                "rule_id": rule_id,
                "rule_version": rule_version,
                "evidence": f"{matched} message(s) matched",
                "counterexamples": [c["id"] for c in counterexamples],
            }
        ],
        "counterexamples": counterexamples,
        "rule_versions": [
            {"rule_id": rule_id, "version": rule_version, "note": "applied by the pipeline"}
        ],
        "open_questions": open_questions,
    }


def _capture_only_investigation(capture_id: str, source_file: str, sessions: int) -> dict[str, Any]:
    """An honest investigation when no rule was applied."""

    return {
        "title": f"Capture of {source_file}",
        "scope": {
            "capture_id": capture_id,
            "source_file": source_file,
            "sessions": sessions,
        },
        "hypotheses": [],
        "counterexamples": [],
        "rule_versions": [],
        "open_questions": [
            "No interpretation rule was applied; the message structure is not described yet",
        ],
    }


def run_pipeline(
    pcap: Path,
    project_path: Path,
    *,
    name: str | None = None,
    rule_path: Path | None = None,
    report_path: Path | None = None,
    html: bool = True,
    wireshark: bool = False,
    streaming: bool = False,
    chunk_size: int = 10000,
    force: bool = False,
) -> PipelineOutcome:
    """Run the full path from ``pcap`` to a project and a report.

    ``project_path`` must not exist unless ``force`` is set, in which case it is
    removed first. ``report_path`` writes the Markdown report outside the
    project as well; the project always gets its own copy under ``reports/``.
    """

    pcap = Path(pcap)
    if not pcap.is_file():
        raise PipelineError(f"no capture at {pcap}")
    project_path = Path(project_path)
    if project_path.exists():
        if not force:
            raise PipelineError(f"{project_path} already exists; pass force to replace it")
        import shutil

        shutil.rmtree(project_path)

    project = Project.create(project_path, name or f"{project_path.name} investigation")
    relative_capture = project.add_capture(pcap)

    normalized = project.path("results", NORMALIZED_NAME)
    sessions = _write_normalized(
        project.path(relative_capture),
        normalized,
        source_file=relative_capture,
        streaming=streaming,
        chunk_size=chunk_size,
    )

    outcome = PipelineOutcome(
        project=project,
        normalized=normalized,
        sessions=sessions,
        streaming=streaming,
    )

    capture_id = sha256_file(project.path(relative_capture))

    if rule_path is not None:
        result_path = project.path("results", RESULT_NAME)
        result = _apply_rule(normalized, Path(rule_path), result_path)
        outcome.result = result_path
        investigation = build_investigation(
            result, capture_id=capture_id, source_file=relative_capture
        )
    else:
        investigation = _capture_only_investigation(
            capture_id, relative_capture, sessions
        )

    from src.report import render_html, render_markdown

    project_report = project.path("reports", REPORT_MD_NAME)
    render_markdown(investigation, project_report)
    outcome.report_md = project_report
    if report_path is not None:
        render_markdown(investigation, Path(report_path))

    if html:
        project_html = project.path("reports", REPORT_HTML_NAME)
        render_html(investigation, project_html)
        outcome.report_html = project_html

    if wireshark:
        from src.capture.export_wireshark import export_reassembled_pcap

        capture = normalize(project.path(relative_capture))
        out = project.path("results", "reassembled.pcap")
        export_reassembled_pcap(capture.sessions, out, streams=capture.streams)
        outcome.wireshark = out

    project.manifest.results.append(
        {"path": f"results/{NORMALIZED_NAME}", "kind": "normalized_capture"}
    )
    if outcome.result is not None:
        project.manifest.results.append(
            {"path": f"results/{RESULT_NAME}", "kind": "application_result"}
        )
    project.manifest.results.append(
        {"path": f"reports/{REPORT_MD_NAME}", "kind": "report"}
    )
    project.save()
    return outcome
