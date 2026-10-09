"""Render the hypotheses of an investigation as a narrative section.

This is a template, not a model: every sentence is filled from numbers that are
already in the investigation dictionary, and a clause is dropped rather than
guessed when its figure is absent. It reads the same dictionary shape as
``src.report.model`` (see ``docs/INTEGRATION.md``), so the hypotheses listed
there can be written up without a second description of the data.

Per hypothesis, these optional keys are used when present:

- ``statement`` / ``id``: the heading.
- ``field`` / ``offset``: the byte the hypothesis is about.
- ``observation`` or ``evidence``: the observation the hypothesis came from.
- ``corpus_total``, ``corpus_matched``, ``corpus_contradicted``,
  ``corpus_uncovered``: the corpus check for this hypothesis.
- ``alternatives``: a list of ``{"name", "support", "contradict", "score"}``.
- ``applicability``: where the rule applies.
- ``not_tested_on``: where it has not been checked.
"""

from __future__ import annotations

from typing import Any

from src.report.model import normalize


def render_hypothesis_narrative(investigation: dict[str, Any]) -> str:
    """Render each hypothesis of *investigation* as a Markdown section.

    Args:
        investigation: An investigation dictionary in the shape described in
            ``src/report/model.py``. Missing sections are treated as empty.

    Returns:
        The hypotheses as a Markdown string, one ``##`` section each, ending in
        a newline. An empty string when there are no hypotheses.
    """
    model = normalize(investigation)
    hypotheses = model["hypotheses"]
    if not hypotheses:
        return ""
    scope_text = _scope_text(model.get("scope"))
    blocks = []
    for index, item in enumerate(hypotheses, 1):
        blocks.append(_hypothesis_block(index, item, scope_text))
    return "\n".join(blocks).rstrip() + "\n"


def _hypothesis_block(index: int, item: dict[str, Any], scope_text: str) -> str:
    heading = str(item.get("statement") or item.get("id") or f"hypothesis {index}")
    lines = [f"## Hypothesis {index}: {heading}", ""]

    field = item.get("field")
    offset = item.get("offset")
    if field is not None and offset is not None:
        lines.append(f"Field `{field}` at offset {offset}.")

    observation = item.get("observation") or item.get("evidence")
    if observation:
        lines.append(str(observation).strip())

    check = _corpus_check(item)
    if check:
        lines.append(check)

    alternatives = item.get("alternatives") or []
    best = _best_alternative(alternatives)
    if best:
        lines.append(best)

    applicability = item.get("applicability") or scope_text
    not_tested_on = item.get("not_tested_on")
    if applicability:
        sentence = f"Applicability: {applicability}."
        if not_tested_on:
            sentence += f" Not checked on {not_tested_on}."
        lines.append(sentence)

    lines.append("")
    return "\n".join(lines)


def _corpus_check(item: dict[str, Any]) -> str:
    """One sentence with the corpus counts, or empty when none are present."""
    keys = ("corpus_total", "corpus_matched", "corpus_contradicted", "corpus_uncovered")
    if not any(item.get(key) is not None for key in keys):
        return ""
    total = _number(item.get("corpus_total"))
    matched = _number(item.get("corpus_matched"))
    contradicted = _number(item.get("corpus_contradicted"))
    uncovered = _number(item.get("corpus_uncovered"))
    parts = []
    if total is not None:
        parts.append(f"over {total} messages")
    if matched is not None:
        parts.append(f"matched {matched}")
    if contradicted is not None:
        parts.append(f"contradicted {contradicted}")
    if uncovered is not None:
        parts.append(f"uncovered {uncovered}")
    return "Corpus check " + ", ".join(parts) + "."


def _best_alternative(alternatives: list) -> str:
    """Describe the highest-scoring alternative reading, or empty."""
    scored = [a for a in alternatives if isinstance(a, dict) and a.get("score") is not None]
    if not scored:
        return ""
    best = max(scored, key=lambda a: a["score"])
    name = best.get("name", "unknown")
    support = _number(best.get("support"))
    contradict = _number(best.get("contradict"))
    score = best.get("score")
    detail = f"support {support}, contradict {contradict}" if support is not None else "support unknown"
    if score is not None:
        detail += f", score {round(float(score), 2)}"
    verdict = "requires manual review" if (contradict or 0) > 0 else "not contradicted in the corpus"
    return f"Best alternative reading: {name} ({detail}); {verdict}."


def _scope_text(scope: Any) -> str:
    """A short applicability phrase from the investigation scope, or empty."""
    if not scope:
        return ""
    if isinstance(scope, str):
        return scope
    if isinstance(scope, dict):
        pieces = [f"{key} {value}" for key, value in scope.items()]
        return ", ".join(pieces)
    return ""


def _number(value: Any) -> int | None:
    """Return *value* as an int, or None when it is not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)
