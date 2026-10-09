"""Render an investigation as Markdown.

The report states plainly, for each hypothesis, what was observed, what was
assumed, where a rule was checked, and where it was contradicted. It never
presents a match on examples as proof of meaning. See ``docs/INTEGRATION.md``
for the investigation dictionary shape.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from src.report.model import normalize, status_label


def _scope_lines(scope: dict[str, Any]) -> list[str]:
    if not scope:
        return ["Scope was not recorded."]
    lines: list[str] = []
    for key in sorted(scope):
        value = scope[key]
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value) if value else "none"
        lines.append(f"- {key}: {value}")
    return lines


def _hypothesis_lines(item: dict[str, Any]) -> list[str]:
    hid = item.get("id", "?")
    statement = item.get("statement", "no statement recorded")
    status = status_label(str(item.get("status", "unknown")))
    out = [f"### {hid} - {statement}", "", f"- Status: {status}"]
    if item.get("rule_id") is not None:
        version = item.get("rule_version")
        suffix = f" (version {version})" if version is not None else ""
        out.append(f"- Rule: {item['rule_id']}{suffix}")
    if item.get("evidence"):
        out.append(f"- Evidence: {item['evidence']}")
    counterexamples = item.get("counterexamples") or []
    if counterexamples:
        joined = ", ".join(str(c) for c in counterexamples)
        out.append(f"- Counterexamples: {joined}")
    out.append("")
    return out


def _counterexample_lines(item: dict[str, Any]) -> list[str]:
    cid = item.get("id", "?")
    out = [f"### {cid}", ""]
    for key in (
        "rule_id",
        "rule_version",
        "capture_id",
        "session_id",
        "direction",
        "offset",
        "length",
    ):
        if item.get(key) is not None:
            out.append(f"- {key}: {item[key]}")
    if item.get("bytes_hex"):
        out.append(f"- bytes: `{item['bytes_hex']}`")
    if item.get("detail"):
        out.append(f"- Detail: {item['detail']}")
    out.append("")
    return out


def _version_lines(item: dict[str, Any]) -> str:
    rule_id = item.get("rule_id", "?")
    version = item.get("version", "?")
    line = f"- {rule_id} version {version}"
    if item.get("created_at"):
        line += f" - {item['created_at']}"
    if item.get("note"):
        line += f": {item['note']}"
    return line


def render_markdown(investigation: dict[str, Any], out_path: Path) -> None:
    """Write ``investigation`` as Markdown to ``out_path``."""

    model = normalize(investigation)
    lines: list[str] = [f"# {model['title']}", ""]

    lines += ["## Scope", ""]
    lines += _scope_lines(model["scope"])
    lines.append("")

    lines += ["## Hypotheses", ""]
    if model["hypotheses"]:
        for item in model["hypotheses"]:
            lines += _hypothesis_lines(item)
    else:
        lines += ["No hypotheses were recorded.", ""]

    lines += ["## Counterexamples", ""]
    if model["counterexamples"]:
        lines += [
            "A match on examples is not proof of meaning. Each entry below is",
            "data on which a rule does not hold.",
            "",
        ]
        for item in model["counterexamples"]:
            lines += _counterexample_lines(item)
    else:
        lines += ["No counterexamples were found in the checked corpus.", ""]

    lines += ["## Rule versions", ""]
    if model["rule_versions"]:
        lines += [_version_lines(item) for item in model["rule_versions"]]
        lines.append("")
    else:
        lines += ["No rule versions were recorded.", ""]

    lines += ["## Open questions", ""]
    if model["open_questions"]:
        lines += [f"- {question}" for question in model["open_questions"]]
        lines.append("")
    else:
        lines += ["No open questions were recorded.", ""]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def render(investigation: dict[str, Any]) -> str:
    """Return the Markdown text without writing it to disk."""

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "report.md"
        render_markdown(investigation, path)
        return path.read_text(encoding="utf-8")
