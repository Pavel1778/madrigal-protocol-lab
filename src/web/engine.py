"""Engine wrapper for the web interface.

The web layer never parses a PCAP or frames a stream itself. Given a capture
(a normalized ``*.normalized.json`` contract file, or a raw ``.pcap``/
``.pcapng`` that is normalized first) and an optional rule, this module answers
the questions the pages ask: the session list, one direction's bytes, the rule
verdict per message, the provenance of a byte, and a report.

Everything returned here is plain data, so the templates stay free of engine
types.
"""

from __future__ import annotations

import base64
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.capture.export import export_capture
from src.capture.pipeline import normalize
from src.protocol.engine import MessageResult, apply_rule
from src.protocol.rule import Rule, RuleError, load_rule
from src.protocol.stream import Capture, CaptureError, DirectionalStream, capture_from_dict

HEX_BYTES_PER_LINE = 16

# Byte annotation kinds, kept as strings so the templates compare plainly.
GAP = "gap"
AMBIGUITY = "ambiguity"
MATCHED = "matched"
MISMATCHED = "mismatched"
FIELD = "field"
UNCOVERED = "uncovered"
NOT_APPLICABLE = "not_applicable"


class WebEngineError(ValueError):
    """A caller-facing problem: bad input, unreadable file, no rule."""


@dataclass
class SessionRow:
    """One row of the session list."""

    session_id: str
    endpoints: str
    role_a: str
    role_b: str
    first_ts: float | None
    last_ts: float | None
    directions: list[str]
    direction_bytes: dict[str, int]
    diagnostics: list[dict] = field(default_factory=list)


@dataclass
class MessageRow:
    """One framed message with its rule verdict."""

    offset: int
    length: int
    status: str
    reason: str | None
    fields: list[dict]
    bytes_hex: str


@dataclass
class ByteCell:
    """A rendered hex byte with its annotation and provenance."""

    offset: int
    value: int
    kind: str
    label: str = ""
    packet_index: int | None = None
    seq: int | None = None
    ts: float | None = None


@dataclass
class HexLine:
    """One 16-byte row of the hex view."""

    offset: int
    cells: list[ByteCell]
    ascii: str


class WebEngine:
    """Read-only facade over one capture and one rule."""

    def __init__(
        self,
        capture: Capture,
        capture_path: Path,
        rule: Rule | None = None,
        rule_path: Path | None = None,
    ) -> None:
        self._capture = capture
        self.capture_path = capture_path
        self._rule = rule
        self.rule_path = rule_path

    # -- construction ------------------------------------------------------

    @classmethod
    def open(
        cls, capture: str | Path, rule: str | Path | None = None
    ) -> "WebEngine":
        """Open a capture (normalized JSON or raw PCAP) and an optional rule.

        Raises:
            WebEngineError: If a path is missing, unreadable or malformed. The
                message is written for a person, not a traceback.
        """
        capture_path = Path(capture)
        data = _read_capture(capture_path)
        try:
            parsed = capture_from_dict(data)
        except CaptureError as exc:
            raise WebEngineError(f"capture does not match the contract: {exc}") from exc

        parsed_rule: Rule | None = None
        rule_path: Path | None = None
        if rule is not None:
            rule_path = Path(rule)
            try:
                parsed_rule = load_rule(str(rule_path))
            except FileNotFoundError as exc:
                raise WebEngineError(f"rule not found: {rule_path}") from exc
            except (RuleError, OSError) as exc:
                raise WebEngineError(f"could not read the rule: {exc}") from exc
        return cls(parsed, capture_path, parsed_rule, rule_path)

    # -- properties --------------------------------------------------------

    @property
    def capture_id(self) -> str:
        return self._capture.capture_id

    @property
    def source_file(self) -> str:
        return self._capture.source_file

    @property
    def has_rule(self) -> bool:
        return self._rule is not None

    @property
    def rule_id(self) -> str:
        return self._rule.rule_id if self._rule else ""

    @property
    def rule_version(self) -> int:
        return self._rule.rule_version if self._rule else 0

    # -- sessions ----------------------------------------------------------

    def sessions(self) -> list[SessionRow]:
        """Every session in the capture, in contract order."""
        rows: list[SessionRow] = []
        for session in self._capture.sessions:
            sid = str(session.get("session_id", ""))
            endpoints = session.get("endpoints", []) or []
            label = " -> ".join(
                f"{e.get('ip', '?')}:{e.get('port', '?')}" for e in endpoints
            )
            directions = [
                name
                for name in ("A_to_B", "B_to_A")
                if name in (session.get("directions", {}) or {})
            ]
            byte_counts = {
                name: len(self._stream(sid, name).data) for name in directions
            }
            diagnostics = [
                {
                    "direction": name,
                    "type": str(entry.get("type", "unknown")),
                    "offset": int(entry.get("offset", 0)),
                    "length": int(entry.get("length", 0)),
                }
                for name in directions
                for entry in (session.get("directions", {}) or {})
                .get(name, {})
                .get("diagnostics", [])
            ]
            rows.append(
                SessionRow(
                    session_id=sid,
                    endpoints=label,
                    role_a=str(session.get("role_a", "unknown")),
                    role_b=str(session.get("role_b", "unknown")),
                    first_ts=session.get("first_ts"),
                    last_ts=session.get("last_ts"),
                    directions=directions,
                    direction_bytes=byte_counts,
                    diagnostics=diagnostics,
                )
            )
        return rows

    def session(self, session_id: str) -> SessionRow | None:
        """One session row, or ``None`` when the id is unknown."""
        return next((s for s in self.sessions() if s.session_id == session_id), None)

    def directions(self, session_id: str) -> list[str]:
        """Directions of one session, in ``A_to_B``/``B_to_A`` order."""
        row = self.session(session_id)
        return row.directions if row is not None else []

    def _stream(self, session_id: str, direction: str) -> DirectionalStream:
        try:
            return self._capture.stream(session_id, direction)
        except CaptureError as exc:
            raise WebEngineError(str(exc)) from exc

    # -- hex ---------------------------------------------------------------

    def hex_lines(self, session_id: str, direction: str) -> list[HexLine]:
        """The direction's bytes as hex lines, decorated with annotations."""
        stream = self._stream(session_id, direction)
        kinds = self._byte_kinds(stream, session_id, direction)
        provenance = _provenance_by_offset(stream)
        lines: list[HexLine] = []
        data = stream.data
        for start in range(0, len(data), HEX_BYTES_PER_LINE):
            chunk = data[start : start + HEX_BYTES_PER_LINE]
            cells: list[ByteCell] = []
            for index, value in enumerate(chunk):
                offset = start + index
                kind, label = kinds.get(offset, (UNCOVERED, ""))
                prov = provenance.get(offset, (None, None, None))
                cells.append(
                    ByteCell(
                        offset=offset,
                        value=value,
                        kind=kind,
                        label=label,
                        packet_index=prov[0],
                        seq=prov[1],
                        ts=prov[2],
                    )
                )
            ascii_part = "".join(_printable(value) for value in chunk)
            lines.append(HexLine(offset=start, cells=cells, ascii=ascii_part))
        return lines

    def _byte_kinds(
        self, stream: DirectionalStream, session_id: str, direction: str
    ) -> dict[int, tuple[str, str]]:
        """Map a byte offset to its ``(kind, label)``.

        Diagnostics (gap, ambiguity) win over field verdicts, because missing
        bytes are not a rule result. Without a rule every observed byte is
        ``uncovered``.
        """
        kinds: dict[int, tuple[str, str]] = {}
        for hole in stream.diagnostics:
            kind = GAP if hole.type == "gap" else AMBIGUITY
            for offset in range(hole.offset, min(hole.end, len(stream.data))):
                kinds[offset] = (kind, hole.type)
        if self._rule is None:
            return kinds
        for message in self.messages(session_id, direction):
            if message.status == NOT_APPLICABLE:
                continue
            for fld in message.fields:
                start = message.offset + int(fld.field_offset)
                end = start + int(fld.field_length)
                for offset in range(start, min(end, len(stream.data))):
                    if kinds.get(offset, ("",))[0] in (GAP, AMBIGUITY):
                        continue
                    kinds[offset] = (fld.status.value, fld.field_name)
        return kinds

    # -- messages ----------------------------------------------------------

    def messages(self, session_id: str, direction: str) -> list[MessageResult]:
        """Frame the direction and classify each message against the rule.

        With no rule loaded, every framed message reports ``uncovered``: the
        bytes are seen but no interpretation covers them.
        """
        stream = self._stream(session_id, direction)
        if self._rule is None:
            return _framed_uncovered(stream, session_id, direction)
        return apply_rule(stream, self._rule, session_id, direction)

    def message_rows(self, session_id: str, direction: str) -> list[MessageRow]:
        """The messages as plain rows for the template."""
        rows: list[MessageRow] = []
        for message in self.messages(session_id, direction):
            rows.append(
                MessageRow(
                    offset=message.offset,
                    length=message.length,
                    status=message.status.value,
                    reason=message.reason,
                    fields=[
                        {
                            "name": f.field_name,
                            "type": f.field_type,
                            "offset": f.field_offset,
                            "length": f.field_length,
                            "value": _jsonable(f.value),
                            "status": f.status.value,
                        }
                        for f in message.fields
                    ],
                    bytes_hex=message.bytes_hex,
                )
            )
        return rows

    def message_at(
        self, session_id: str, direction: str, offset: int
    ) -> MessageResult | None:
        """The message starting at ``offset``, or ``None``."""
        return next(
            (m for m in self.messages(session_id, direction) if m.offset == offset),
            None,
        )

    # -- provenance --------------------------------------------------------

    def provenance(self, session_id: str, direction: str, offset: int) -> dict | None:
        """Description of the byte at ``offset``: origin packet, seq and time.

        Returns ``None`` when the offset is outside the stream.
        """
        stream = self._stream(session_id, direction)
        data = stream.data
        if offset < 0 or offset >= len(data):
            return None
        packet_index, seq, ts = _provenance_by_offset(stream).get(
            offset, (None, None, None)
        )
        kind, label = self._byte_kinds(stream, session_id, direction).get(
            offset, (UNCOVERED, "")
        )
        message = self.message_at(session_id, direction, offset) if self._rule else None
        return {
            "offset": offset,
            "byte": data[offset],
            "hex": f"{data[offset]:02x}",
            "ascii": _printable(data[offset]),
            "packet_index": packet_index,
            "seq": seq,
            "ts": ts,
            "kind": kind,
            "label": label,
            "in_gap": kind == GAP,
            "in_ambiguity": kind == AMBIGUITY,
            "message_offset": message.offset if message else None,
            "message_status": message.status.value if message else None,
        }

    # -- report ------------------------------------------------------------

    def report_html(self, session_id: str | None = None, direction: str | None = None) -> str:
        """Render the current interpretation as a self-contained HTML page."""
        from src.report.html import _STYLESHEET  # the same brand stylesheet

        sessions = self.sessions()
        target = self.session(session_id) if session_id else (sessions[0] if sessions else None)
        counters: list[dict] = []
        rows_html: list[str] = []
        if target is not None:
            for name in target.directions:
                if direction and name != direction:
                    continue
                for message in self.messages(target.session_id, name):
                    if message.status == MISMATCHED:
                        counters.append(
                            {
                                "rule_id": self.rule_id,
                                "rule_version": self.rule_version,
                                "capture_id": self.capture_id,
                                "session_id": target.session_id,
                                "direction": name,
                                "offset": message.offset,
                                "length": message.length,
                                "bytes_hex": message.bytes_hex,
                                "detail": message.reason or "",
                            }
                        )
                    rows_html.append(
                        "<tr>"
                        f"<td>{target.session_id}</td><td>{name}</td>"
                        f"<td>{message.offset}</td><td>{message.length}</td>"
                        f"<td class='status-{message.status.value}'>{message.status.value}</td>"
                        f"<td>{_escape(message.bytes_hex)}</td></tr>"
                    )
        scope = {
            "capture": self.source_file or str(self.capture_path),
            "capture_id": self.capture_id,
            "rule": self.rule_id or "(none)",
            "rule_version": self.rule_version,
            "session": target.session_id if target else "(none)",
            "direction": direction or "all",
        }
        investigation = {
            "title": "Web interpretation report",
            "scope": scope,
            "counterexamples": counters,
            "rule_versions": (
                [
                    {
                        "rule_id": self.rule_id,
                        "version": self.rule_version,
                        "note": "loaded for this session",
                    }
                ]
                if self._rule
                else []
            ),
        }
        body = _report_body(investigation, rows_html)
        return _report_page(_STYLESHEET, body)


def _read_capture(path: Path) -> dict:
    """Return the normalized capture mapping for ``path``.

    A ``*.normalized.json`` file is read as is. A raw ``.pcap``/``.pcapng`` is
    normalized on the fly with the capture engine, into a temporary JSON file,
    so the web layer never duplicates the parser.
    """
    if not path.is_file():
        raise WebEngineError(f"capture not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WebEngineError(f"capture is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise WebEngineError(f"could not read the capture: {exc}") from exc
    if suffix in (".pcap", ".pcapng"):
        try:
            normalized = normalize(path)
        except Exception as exc:  # noqa: BLE001 - any parser failure is caller-facing
            raise WebEngineError(f"could not normalize the capture: {exc}") from exc
        return _normalized_to_dict(normalized)
    raise WebEngineError(
        f"unsupported capture type {suffix!r}; expected .json, .pcap or .pcapng"
    )


def _normalized_to_dict(normalized) -> dict:
    """Serialize a :class:`NormalizedCapture` to the contract mapping.

    Uses the engine's own export so the shape matches what a normalized file
    would contain, without writing to the caller's directory.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "capture.normalized.json"
        export_capture(
            normalized.sessions,
            out,
            source_file=str(normalized.source_file),
            capture_id=normalized.capture_id,
            streams=normalized.streams,
        )
        return json.loads(out.read_text(encoding="utf-8"))


def _framed_uncovered(
    stream: DirectionalStream, session_id: str, direction: str
) -> list[MessageResult]:
    """Frame a stream with no rule and mark every message ``uncovered``."""
    from src.hypothesis.status import Status
    from src.protocol.framing import FramingStrategy, frame_stream

    strategy = FramingStrategy.from_dict({"type": "manual"})
    messages = frame_stream(stream.data, strategy)
    return [
        MessageResult(
            offset=m.offset,
            length=m.length,
            status=Status.UNCOVERED,
            complete=m.complete,
            session_id=session_id,
            direction=direction,
            reason="no_rule_loaded",
            bytes_hex=stream.data[m.offset : m.end].hex(),
        )
        for m in messages
    ]


def _provenance_by_offset(
    stream: DirectionalStream,
) -> dict[int, tuple[int | None, int | None, float | None]]:
    """Map every byte offset to ``(packet_index, seq, ts)`` from provenance."""
    mapping: dict[int, tuple[int | None, int | None, float | None]] = {}
    for hole in stream.provenance:
        for offset in range(hole.offset, min(hole.end, len(stream.data))):
            mapping[offset] = (
                getattr(hole, "packet_index", None),
                getattr(hole, "seq", None),
                getattr(hole, "ts", None),
            )
    return mapping


def _printable(byte: int) -> str:
    return chr(byte) if 32 <= byte < 127 else "."


def _jsonable(value):
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _escape(text: str) -> str:
    import html

    return html.escape(str(text))


def _report_body(investigation: dict, rows_html: list[str]) -> str:
    scope = investigation["scope"]
    scope_rows = "".join(
        f"<tr><th>{_escape(key)}</th><td>{_escape(value)}</td></tr>"
        for key, value in scope.items()
    )
    counters = investigation["counterexamples"]
    if counters:
        counter_html = "<ul>" + "".join(
            "<li>"
            f"{_escape(c['session_id'])} {_escape(c['direction'])} offset "
            f"{c['offset']} len {c['length']} <code>{_escape(c['bytes_hex'])}</code>"
            "</li>"
            for c in counters
        ) + "</ul>"
    else:
        counter_html = '<p class="muted">No counterexamples for this selection.</p>'
    table = (
        "<table><thead><tr><th>session</th><th>direction</th><th>offset</th>"
        "<th>length</th><th>status</th><th>bytes</th></tr></thead><tbody>"
        + ("".join(rows_html) or '<tr><td colspan="6" class="muted">no messages</td></tr>')
        + "</tbody></table>"
    )
    return f"""<h1>{_escape(investigation['title'])}</h1>
<p class="muted">Generated by the local web interface. The bytes are the source of truth.</p>
<h2>Scope</h2>
<table>{scope_rows}</table>
<h2>Messages</h2>
{table}
<h2>Counterexamples</h2>
{counter_html}
"""


def _report_page(stylesheet: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Interpretation report</title>
<style>{stylesheet}</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""
