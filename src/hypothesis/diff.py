"""Diff two rule versions and two verification reports.

``diff_rules`` describes what changed between two rules: added, removed and
changed fields, plus framing and scope changes. ``diff_reports`` describes what
that change did to a verification: which counterexamples were resolved,
introduced or left unchanged, and how the matched count and coverage moved.

The two are independent: a rule diff answers "what did I edit", a report diff
answers "what did the edit achieve". Both are the evidence a version comparison
needs; neither rewrites any source bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import VerificationReport


@dataclass
class FieldChange:
    """A single attribute that changed on one field."""

    field_name: str
    path: str
    old: object
    new: object

    def to_dict(self) -> dict:
        return {"field_name": self.field_name, "path": self.path, "old": self.old, "new": self.new}


@dataclass
class RuleDiff:
    rule_id: str
    version_a: int
    version_b: int
    added_fields: list[str] = field(default_factory=list)
    removed_fields: list[str] = field(default_factory=list)
    changed_fields: list[FieldChange] = field(default_factory=list)
    changed_framing: list[FieldChange] = field(default_factory=list)
    scope_changes: list[FieldChange] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (
            self.added_fields
            or self.removed_fields
            or self.changed_fields
            or self.changed_framing
            or self.scope_changes
        )

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "added_fields": list(self.added_fields),
            "removed_fields": list(self.removed_fields),
            "changed_fields": [c.to_dict() for c in self.changed_fields],
            "changed_framing": [c.to_dict() for c in self.changed_framing],
            "scope_changes": [c.to_dict() for c in self.scope_changes],
        }


@dataclass
class ReportDiff:
    version_a: int
    version_b: int
    resolved_counterexamples: list[dict] = field(default_factory=list)
    introduced_counterexamples: list[dict] = field(default_factory=list)
    unchanged_mismatches: list[dict] = field(default_factory=list)
    matched_delta: int = 0
    coverage_delta: float = 0.0

    def to_dict(self) -> dict:
        return {
            "version_a": self.version_a,
            "version_b": self.version_b,
            "resolved_counterexamples": self.resolved_counterexamples,
            "introduced_counterexamples": self.introduced_counterexamples,
            "unchanged_mismatches": self.unchanged_mismatches,
            "matched_delta": self.matched_delta,
            "coverage_delta": self.coverage_delta,
        }


def _field_map(rule) -> dict:
    return {spec.name: spec for spec in rule.fields}


def _spec_paths(spec_a, spec_b) -> list[tuple[str, object, object]]:
    """Attribute-level differences between two versions of the same field."""
    a = spec_a.to_dict()
    b = spec_b.to_dict()
    keys = sorted(set(a) | set(b))
    changes = []
    for key in keys:
        if a.get(key) != b.get(key):
            changes.append((key, a.get(key), b.get(key)))
    return changes


def diff_rules(rule_a, rule_b) -> RuleDiff:
    """Compare two rules field by field, plus framing and scope."""
    fields_a = _field_map(rule_a)
    fields_b = _field_map(rule_b)

    added = [name for name in fields_b if name not in fields_a]
    removed = [name for name in fields_a if name not in fields_b]

    changed: list[FieldChange] = []
    for name in fields_a:
        if name in fields_b:
            for path, old, new in _spec_paths(fields_a[name], fields_b[name]):
                changed.append(FieldChange(field_name=name, path=path, old=old, new=new))

    framing: list[FieldChange] = []
    keys = sorted(set(rule_a.framing) | set(rule_b.framing))
    for key in keys:
        old = rule_a.framing.get(key)
        new = rule_b.framing.get(key)
        if old != new:
            framing.append(FieldChange(field_name="", path=key, old=old, new=new))

    scope: list[FieldChange] = []
    keys = sorted(set(rule_a.scope) | set(rule_b.scope))
    for key in keys:
        old = rule_a.scope.get(key)
        new = rule_b.scope.get(key)
        if old != new:
            scope.append(FieldChange(field_name="", path=key, old=old, new=new))

    return RuleDiff(
        rule_id=rule_b.rule_id,
        version_a=rule_a.rule_version,
        version_b=rule_b.rule_version,
        added_fields=added,
        removed_fields=removed,
        changed_fields=changed,
        changed_framing=framing,
        scope_changes=scope,
    )


def _key(counter: dict) -> tuple:
    return (
        counter.get("session_id"),
        counter.get("direction"),
        counter.get("message_offset"),
        counter.get("status"),
    )


def _coverage(report: VerificationReport) -> float:
    total = report.total
    if total <= 0:
        return 0.0
    not_applicable = report.totals.get("not_applicable", 0)
    return (total - not_applicable) / total


def diff_reports(report_a: VerificationReport, report_b: VerificationReport) -> ReportDiff:
    """Compare two verification reports for the same rule id."""
    a_items = [c.to_dict() for c in report_a.contradictions]
    b_items = [c.to_dict() for c in report_b.contradictions]
    a_keys = {_key(item) for item in a_items}
    b_keys = {_key(item) for item in b_items}

    resolved = [item for item in a_items if _key(item) not in b_keys]
    introduced = [item for item in b_items if _key(item) not in a_keys]
    unchanged = [
        item
        for item in b_items
        if _key(item) in a_keys and item.get("status") == "mismatched"
    ]

    return ReportDiff(
        version_a=report_a.rule_version,
        version_b=report_b.rule_version,
        resolved_counterexamples=resolved,
        introduced_counterexamples=introduced,
        unchanged_mismatches=unchanged,
        matched_delta=report_b.totals.get("matched", 0) - report_a.totals.get("matched", 0),
        coverage_delta=round(_coverage(report_b) - _coverage(report_a), 6),
    )


def format_rule_diff(diff: RuleDiff) -> str:
    """Human-readable rendering of a rule diff."""
    lines = [f"rule {diff.rule_id}: v{diff.version_a} -> v{diff.version_b}"]
    for name in diff.added_fields:
        lines.append(f"  + field {name}")
    for name in diff.removed_fields:
        lines.append(f"  - field {name}")
    for change in diff.changed_fields:
        lines.append(f"  ~ field {change.field_name}.{change.path}: {change.old!r} -> {change.new!r}")
    for change in diff.changed_framing:
        lines.append(f"  ~ framing.{change.path}: {change.old!r} -> {change.new!r}")
    for change in diff.scope_changes:
        lines.append(f"  ~ scope.{change.path}: {change.old!r} -> {change.new!r}")
    if diff.is_empty:
        lines.append("  (no differences)")
    return "\n".join(lines)


def format_report_diff(diff: ReportDiff) -> str:
    """Human-readable rendering of a report diff."""
    lines = [f"report v{diff.version_a} -> v{diff.version_b}"]
    lines.append(f"  resolved counterexamples: {len(diff.resolved_counterexamples)}")
    lines.append(f"  introduced counterexamples: {len(diff.introduced_counterexamples)}")
    lines.append(f"  unchanged mismatches: {len(diff.unchanged_mismatches)}")
    lines.append(f"  matched delta: {diff.matched_delta:+d}")
    lines.append(f"  coverage delta: {diff.coverage_delta:+.3f}")
    return "\n".join(lines)
