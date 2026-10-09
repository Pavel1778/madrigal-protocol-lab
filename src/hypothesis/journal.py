"""Correlate decoded messages with an externally recorded action journal.

A journal is the researcher's own log of what a human did at the keyboard
("set temperature to 21"), written separately from the capture. Placing a
message next to a journal entry that happened at almost the same moment is
evidence for the message's meaning: a parameter value seen on the wire can be
compared with the value the user intended.

Correlation is a temporal suggestion, not a proof. An empty window, a missing
timestamp or a mismatched value are all reported as such; nothing is inferred
when the evidence is absent.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from ..protocol.engine import MessageResult


class JournalError(ValueError):
    """Raised when a journal line cannot be parsed."""


@dataclass
class JournalEntry:
    """One action recorded by the researcher."""

    timestamp: float
    action: str
    params: dict = field(default_factory=dict)
    line_number: int = 0
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "params": dict(self.params),
            "line_number": self.line_number,
        }


@dataclass
class Correlation:
    """A message paired with a journal entry inside the time window."""

    session_id: str
    direction: str
    message_offset: int
    message_timestamp: float
    entry: JournalEntry
    delta_ms: float
    message_values: dict = field(default_factory=dict)
    matched_fields: dict = field(default_factory=dict)
    value_agreements: list[str] = field(default_factory=list)
    value_conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "direction": self.direction,
            "message_offset": self.message_offset,
            "message_timestamp": self.message_timestamp,
            "delta_ms": self.delta_ms,
            "action": self.entry.action,
            "entry_timestamp": self.entry.timestamp,
            "entry_line": self.entry.line_number,
            "message_values": self.message_values,
            "matched_fields": self.matched_fields,
            "value_agreements": self.value_agreements,
            "value_conflicts": self.value_conflicts,
        }


@dataclass
class CorrelationReport:
    window_ms: int
    correlated: list[Correlation] = field(default_factory=list)
    messages_without_timestamp: int = 0
    messages_without_entry: int = 0
    entries_without_message: list[JournalEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "window_ms": self.window_ms,
            "correlated": [c.to_dict() for c in self.correlated],
            "messages_without_timestamp": self.messages_without_timestamp,
            "messages_without_entry": self.messages_without_entry,
            "entries_without_message": [e.to_dict() for e in self.entries_without_message],
            "summary": self.summary(),
        }

    def summary(self) -> str:
        matched = len(self.correlated)
        total = matched + self.messages_without_entry + self.messages_without_timestamp
        return (
            f"{matched} of {total} messages correlated, "
            f"{len(self.entries_without_message)} journal entries unmatched"
        )


def parse_timestamp(text: str) -> float:
    """Parse a timestamp as epoch seconds or ISO-8601."""
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        pass
    candidate = text.replace("Z", "+00:00")
    try:
        parsed = _dt.datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise JournalError(f"unrecognised timestamp {text!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.timestamp()


def parse_journal(text: str) -> list[JournalEntry]:
    """Parse a pipe-delimited journal.

    Each non-comment line is either ``<timestamp> | <action> | key=value | ...``
    or ``<timestamp> | <action> | <parameter> | <result>``. The two forms are
    told apart by whether the third field contains ``=``. A ``#`` starts a
    comment and blank lines are ignored.
    """
    entries: list[JournalEntry] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("```"):
            continue
        if not line or line.startswith("#"):
            continue
        if not line[0].isdigit():
            # Prose around the data block is not an entry.
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            raise JournalError(f"line {number}: expected 'timestamp | action [| ...]'")
        timestamp = parse_timestamp(parts[0])
        action = parts[1]
        tail = [part for part in parts[2:] if part]
        params: dict = {}
        if len(tail) == 1 and "=" not in tail[0]:
            params["parameter"] = _coerce(tail[0])
        elif len(tail) == 2 and "=" not in tail[0]:
            params["parameter"] = _coerce(tail[0])
            params["result"] = _coerce(tail[1])
        else:
            for chunk in tail:
                if "=" not in chunk:
                    raise JournalError(f"line {number}: parameter {chunk!r} is not key=value")
                key, _, value = chunk.partition("=")
                params[key.strip()] = _coerce(value.strip())
        entries.append(
            JournalEntry(
                timestamp=timestamp,
                action=action,
                params=params,
                line_number=number,
                raw=raw,
            )
        )
    return entries


def load_journal(path: str) -> list[JournalEntry]:
    with open(path, "r", encoding="utf-8") as handle:
        return parse_journal(handle.read())


def _coerce(value: str):
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def correlate(
    messages: list[MessageResult],
    entries: list[JournalEntry],
    window_ms: int = 500,
) -> CorrelationReport:
    """Pair every timestamped message with journal entries inside the window."""
    if window_ms < 0:
        raise ValueError("window_ms must not be negative")
    report = CorrelationReport(window_ms=window_ms)
    used: set[int] = set()
    window = window_ms / 1000.0

    ordered = sorted(entries, key=lambda e: e.timestamp)
    for message in messages:
        if message.timestamp is None:
            report.messages_without_timestamp += 1
            continue
        nearby = [
            entry
            for entry in ordered
            if abs(entry.timestamp - message.timestamp) <= window and id(entry) not in used
        ]
        if not nearby:
            report.messages_without_entry += 1
            continue
        entry = min(nearby, key=lambda e: abs(e.timestamp - message.timestamp))
        used.add(id(entry))
        report.correlated.append(_pair(message, entry))

    report.entries_without_message = [e for e in ordered if id(e) not in used]
    return report


def _pair(message: MessageResult, entry: JournalEntry) -> Correlation:
    values = message.field_values()
    matched_fields = {
        name: value
        for name, value in values.items()
        if name.lower() in {k.lower() for k in entry.params}
    }
    agreements: list[str] = []
    conflicts: list[str] = []
    for name, value in matched_fields.items():
        for key, param in entry.params.items():
            if key.lower() != name.lower():
                continue
            if param == value:
                agreements.append(f"{name}={value}")
            else:
                conflicts.append(f"{name}={value} (journal {key}={param})")
    return Correlation(
        session_id=message.session_id,
        direction=message.direction,
        message_offset=message.offset,
        message_timestamp=message.timestamp,
        entry=entry,
        delta_ms=round(abs(entry.timestamp - message.timestamp) * 1000, 6),
        message_values=values,
        matched_fields=matched_fields,
        value_agreements=agreements,
        value_conflicts=conflicts,
    )
