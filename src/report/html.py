"""Render an investigation as a self-contained HTML page.

The page follows ``docs/STYLE.md``: the dark palette, Tektur for headings and
Montserrat for text, 4 px corners, status colors only for statuses. It carries
no external requests, so it can be copied to another machine and still render.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from src.report.model import normalize, status_label

_STATUS_CLASS = {
    "observation": "status-observation",
    "hypothesis": "status-hypothesis",
    "confirmed_in_scope": "status-confirmed",
    "contradiction": "status-contradiction",
    "unknown": "status-unknown",
    "ambiguous": "status-ambiguous",
    "not_applicable": "status-na",
    "outdated": "status-outdated",
}

_STYLESHEET = """
:root {
  --bg: #131516;
  --panel: #1D1D1D;
  --card: #E8E8E8;
  --accent: #6D071F;
  --text: #E0E0E0;
  --muted: #9F9F9F;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: Montserrat, system-ui, sans-serif;
  font-weight: 400;
  line-height: 1.3;
}
main { max-width: 980px; margin: 0 auto; padding: 32px 24px 64px; }
h1, h2, h3 { font-family: Tektur, system-ui, sans-serif; font-weight: 600; }
h1 { font-size: 1.8rem; margin: 0 0 8px; }
h2 {
  font-size: 1.2rem;
  margin: 32px 0 12px;
  border-bottom: 1px solid var(--accent);
  padding-bottom: 6px;
}
h3 { font-size: 1rem; font-weight: 500; margin: 20px 0 6px; }
section, .card {
  background: var(--panel);
  border-radius: 4px;
  padding: 16px;
  margin: 12px 0;
}
dl { margin: 0; }
dt { color: var(--muted); font-size: 0.8rem; }
dd { margin: 0 0 8px; }
code {
  font-family: "DejaVu Sans Mono", ui-monospace, monospace;
  background: #000;
  padding: 1px 4px;
  border-radius: 4px;
}
.status {
  display: inline-block;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 0.72rem;
  font-weight: 600;
  color: #131516;
}
.status-observation { background: #9F9F9F; }
.status-hypothesis { background: #E0C25B; }
.status-confirmed { background: #6FA96F; }
.status-contradiction { background: #B5544F; }
.status-unknown { background: #7A7A7A; }
.status-ambiguous { background: #E0C25B; }
.status-na { background: #9F9F9F; }
.status-outdated { background: #5A5A5A; color: #E0E0E0; }
ul { margin: 6px 0; padding-left: 20px; }
.muted { color: var(--muted); }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #2A2A2A; }
th { color: var(--muted); font-weight: 600; font-size: 0.8rem; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _scope_html(scope: dict[str, Any]) -> str:
    if not scope:
        return '<p class="muted">Scope was not recorded.</p>'
    rows = []
    for key in sorted(scope):
        value = scope[key]
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value) if value else "none"
        rows.append(f"<tr><th>{_esc(key)}</th><td>{_esc(value)}</td></tr>")
    return f"<table>{''.join(rows)}</table>"


def _hypothesis_html(item: dict[str, Any]) -> str:
    status = str(item.get("status", "unknown"))
    cls = _STATUS_CLASS.get(status, "status-unknown")
    parts = [
        f"<h3>{_esc(item.get('id', '?'))} &ndash; {_esc(item.get('statement', 'no statement recorded'))}</h3>"
    ]
    parts.append(
        f'<p><span class="status {cls}">{_esc(status_label(status))}</span></p>'
    )
    facts = []
    if item.get("rule_id") is not None:
        version = item.get("rule_version")
        suffix = f" (version {version})" if version is not None else ""
        facts.append(f"Rule: {_esc(item['rule_id'])}{_esc(suffix)}")
    if item.get("evidence"):
        facts.append(f"Evidence: {_esc(item['evidence'])}")
    counterexamples = item.get("counterexamples") or []
    if counterexamples:
        facts.append(
            "Counterexamples: " + _esc(", ".join(str(c) for c in counterexamples))
        )
    if facts:
        parts.append("<ul>" + "".join(f"<li>{fact}</li>" for fact in facts) + "</ul>")
    return f"<section>{''.join(parts)}</section>"


def _counterexample_html(item: dict[str, Any]) -> str:
    parts = [f"<h3>{_esc(item.get('id', '?'))}</h3>", "<dl>"]
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
            parts.append(f"<dt>{_esc(key)}</dt><dd>{_esc(item[key])}</dd>")
    if item.get("bytes_hex"):
        parts.append(f"<dt>bytes</dt><dd><code>{_esc(item['bytes_hex'])}</code></dd>")
    if item.get("detail"):
        parts.append(f"<dt>detail</dt><dd>{_esc(item['detail'])}</dd>")
    parts.append("</dl>")
    return f"<section>{''.join(parts)}</section>"


def render_html(investigation: dict[str, Any], out_path: Path) -> None:
    """Write ``investigation`` as a self-contained HTML page to ``out_path``."""

    model = normalize(investigation)

    hypothesis_html = (
        "".join(_hypothesis_html(item) for item in model["hypotheses"])
        or '<p class="muted">No hypotheses were recorded.</p>'
    )

    if model["counterexamples"]:
        note = (
            '<p class="muted">A match on examples is not proof of meaning. '
            "Each entry below is data on which a rule does not hold.</p>"
        )
        counterexample_html = note + "".join(
            _counterexample_html(item) for item in model["counterexamples"]
        )
    else:
        counterexample_html = (
            '<p class="muted">No counterexamples were found in the checked corpus.</p>'
        )

    if model["rule_versions"]:
        rows = []
        for item in model["rule_versions"]:
            rows.append(
                "<tr>"
                f"<td>{_esc(item.get('rule_id', '?'))}</td>"
                f"<td>{_esc(item.get('version', '?'))}</td>"
                f"<td>{_esc(item.get('created_at', ''))}</td>"
                f"<td>{_esc(item.get('note', ''))}</td>"
                "</tr>"
            )
        version_html = (
            "<table><thead><tr><th>Rule</th><th>Version</th><th>Created</th>"
            f"<th>Note</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
        )
    else:
        version_html = '<p class="muted">No rule versions were recorded.</p>'

    if model["open_questions"]:
        questions = "".join(f"<li>{_esc(q)}</li>" for q in model["open_questions"])
        questions_html = f"<ul>{questions}</ul>"
    else:
        questions_html = '<p class="muted">No open questions were recorded.</p>'

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(model["title"])}</title>
<style>{_STYLESHEET}</style>
</head>
<body>
<main>
<h1>{_esc(model["title"])}</h1>
<p class="muted">Contract version {_esc(investigation.get("contract_version", 1))}</p>

<h2>Scope</h2>
{_scope_html(model["scope"])}

<h2>Hypotheses</h2>
{hypothesis_html}

<h2>Counterexamples</h2>
{counterexample_html}

<h2>Rule versions</h2>
{version_html}

<h2>Open questions</h2>
{questions_html}
</main>
</body>
</html>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")
