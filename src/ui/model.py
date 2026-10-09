"""Presentation model bridging the protocol engine to the widgets.

The GUI never parses a capture. It reads a normalized capture JSON (the
contract in ``docs/CONTRACT.md``), and through this module asks the protocol
engine to frame a direction and decode a rule. Everything a widget needs is
summarised here as plain data, so the widgets stay free of engine types.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..hypothesis.corpus import CorpusStream
from ..hypothesis.status import Status
from ..protocol.engine import MessageResult, apply_rule
from ..protocol.rule import Rule, load_rule_text
from ..protocol.stream import Capture, capture_from_dict

PROVENANCE = "provenance"
GAP = "gap"
AMBIGUITY = "ambiguity"
FIELD = "field"
MATCHED = "matched"
MISMATCHED = "mismatched"
INCOMPLETE = "incomplete"
AMBIGUOUS = "ambiguous"
UNCOVERED = "uncovered"
NOT_APPLICABLE = "not_applicable"
HYPOTHESIS = "hypothesis"


@dataclass
class Diagnostic:
    session_id: str
    direction: str
    type: str
    offset: int
    length: int
    detail: str | None = None


@dataclass
class SessionInfo:
    session_id: str
    endpoints: str
    role_a: str
    role_b: str
    first_ts: float | None
    last_ts: float | None
    direction_bytes: dict[str, int] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    packet_count: int = 0


@dataclass
class ByteAnnotation:
    """What is known about one byte of a stream, for the hex view."""

    kind: str
    label: str = ""
    value: object | None = None
    status: str | None = None
    is_hypothesis: bool = False


class CaptureModel:
    """Read-only view over one normalized capture."""

    def __init__(self, capture: Capture, path: Path | None = None) -> None:
        self.capture = capture
        self.path = path
        self._sessions: list[SessionInfo] = self._read_sessions()
        self._diagnostics: list[Diagnostic] = self._read_diagnostics()

    @classmethod
    def from_file(cls, path: str | Path) -> "CaptureModel":
        path = Path(path)
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return cls(capture_from_dict(raw), path=path)

    @property
    def capture_id(self) -> str:
        return self.capture.capture_id

    @property
    def source_file(self) -> str:
        return self.capture.source_file

    @property
    def sessions(self) -> list[SessionInfo]:
        return self._sessions

    @property
    def diagnostics(self) -> list[Diagnostic]:
        return self._diagnostics

    def session(self, session_id: str) -> SessionInfo | None:
        return next((s for s in self._sessions if s.session_id == session_id), None)

    def directions(self, session_id: str) -> list[str]:
        for session in self.capture.sessions:
            if str(session.get("session_id")) == session_id:
                return [n for n in ("A_to_B", "B_to_A") if n in session.get("directions", {})]
        return []

    def stream(self, session_id: str, direction: str):
        return self.capture.stream(session_id, direction)

    def _read_sessions(self) -> list[SessionInfo]:
        infos: list[SessionInfo] = []
        diagnostics = self._read_diagnostics()
        for session in self.capture.sessions:
            sid = str(session.get("session_id", ""))
            endpoints = session.get("endpoints", [])
            label = " -> ".join(
                f"{e.get('ip', '?')}:{e.get('port', '?')}" for e in endpoints
            )
            direction_bytes = {
                name: len(self.capture.stream(sid, name).data)
                for name in self.directions(sid)
            }
            infos.append(
                SessionInfo(
                    session_id=sid,
                    endpoints=label,
                    role_a=str(session.get("role_a", "unknown")),
                    role_b=str(session.get("role_b", "unknown")),
                    first_ts=session.get("first_ts"),
                    last_ts=session.get("last_ts"),
                    direction_bytes=direction_bytes,
                    diagnostics=[d for d in diagnostics if d.session_id == sid],
                    packet_count=len(session.get("packet_indices", []) or []),
                )
            )
        return infos

    def _read_diagnostics(self) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for session in self.capture.sessions:
            sid = str(session.get("session_id", ""))
            for direction, payload in session.get("directions", {}).items():
                for entry in payload.get("diagnostics", []) or []:
                    diagnostics.append(
                        Diagnostic(
                            session_id=sid,
                            direction=direction,
                            type=str(entry.get("type", "unknown")),
                            offset=int(entry.get("offset", 0)),
                            length=int(entry.get("length", 0)),
                            detail=entry.get("detail"),
                        )
                    )
        return diagnostics


class RuleApplication:
    """Result of applying one rule to one direction of one session."""

    def __init__(
        self,
        session_id: str,
        direction: str,
        rule: Rule,
        messages: list[MessageResult],
    ) -> None:
        self.session_id = session_id
        self.direction = direction
        self.rule = rule
        self.messages = messages

    @property
    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for message in self.messages:
            counts[message.status.value] = counts.get(message.status.value, 0) + 1
        return counts

    @property
    def counterexamples(self) -> list[MessageResult]:
        return [m for m in self.messages if m.status == Status.MISMATCHED]

    def message_at(self, offset: int) -> MessageResult | None:
        return next((m for m in self.messages if m.offset == offset), None)


class RuleModel:
    """A rule plus the run that produced the current verdicts.

    The rule keeps its own version. Re-editing the rule produces a new version
    and marks the previous application as outdated, so an old verdict is never
    shown as current.
    """

    def __init__(self, rule: Rule, text: str, path: Path | None = None) -> None:
        self.rule = rule
        self.text = text
        self.path = path
        self.root: RuleApplication | None = None
        self.previous: RuleApplication | None = None
        self.previous_rule: Rule | None = None
        self.corpus_report = None
        self.previous_report = None
        self.errors: str | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> "RuleModel":
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        rule = _rule_from_text(text)
        return cls(rule, text, path=path)

    def reload(self, text: str) -> None:
        """Adopt edited text as a new rule version; the old run goes outdated.

        Reloading identical text is a no-op, so re-running the same rule does
        not mark its own previous result outdated.
        """
        new_rule = _rule_from_text(text)
        if new_rule.to_dict() == self.rule.to_dict():
            self.text = text
            self.errors = None
            return
        if new_rule.rule_version == self.rule.rule_version:
            new_rule = new_rule.bump_version()
        self.text = text
        self.rule = new_rule
        self.previous = self.root
        self.previous_report = self.corpus_report
        self.corpus_report = None
        self.root = None
        self.errors = None

    def apply(self, model: CaptureModel, session_id: str | None = None, direction: str | None = None) -> RuleApplication:
        self.errors = None
        target_direction = direction or self.rule.direction or "A_to_B"
        target_session = session_id or (model.sessions[0].session_id if model.sessions else "")
        stream = model.stream(target_session, target_direction)
        messages = apply_rule(stream, self.rule, target_session, target_direction)
        self.root = RuleApplication(target_session, target_direction, self.rule, messages)
        if self.previous is not None:
            self.previous = _mark_outdated(self.previous)
        return self.root


def _rule_from_text(text: str) -> Rule:
    raw = load_rule_text(text)
    from ..protocol.rule import parse_rule

    return parse_rule(raw)


def _mark_outdated(application: RuleApplication) -> RuleApplication:
    stale = RuleApplication(
        application.session_id,
        application.direction,
        application.rule,
        [
            MessageResult(
                offset=m.offset,
                length=m.length,
                status=Status.OUTDATED,
                fields=m.fields,
                complete=m.complete,
                session_id=m.session_id,
                direction=m.direction,
                reason="superseded_by_newer_rule",
                bytes_hex=m.bytes_hex,
            )
            for m in application.messages
        ],
    )
    return stale


def verify_rule_on_corpus(
    rule: Rule,
    model: CaptureModel,
    directions: tuple[str, ...] = ("A_to_B", "B_to_A"),
) -> dict:
    """Summarise one rule over every direction of the capture.

    This mirrors the corpus verification shape: per-status counts plus the
    counterexamples, so the GUI can show a rule's reach without the caller
    assembling it from message lists.
    """
    from ..hypothesis.corpus import verify_on_corpus

    streams: list[CorpusStream] = []
    for session in model.sessions:
        for direction in model.directions(session.session_id):
            if directions and direction not in directions:
                continue
            data = model.stream(session.session_id, direction).data
            streams.append(CorpusStream.from_bytes(data, session.session_id, direction))
    report = verify_on_corpus(rule, streams)
    return report
