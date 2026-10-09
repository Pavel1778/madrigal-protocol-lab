"""Apply a declarative rule to a directional stream.

The engine frames the stream, decodes the declared fields of every framed
message, and classifies the message. It never mutates the input bytes: a rule
change produces a new result, it does not rewrite a stream. Every field result
keeps the byte range it was read from so a value can be traced back to a
message, and through the message to the source packets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..hypothesis.status import Status
from .framing import FramingStrategy, Message, frame_stream
from .rule import FIELD_TYPES, FieldSpec, Rule
from .stream import DirectionalStream

_SIGNED = {"int8", "int16", "int32"}


@dataclass
class FieldResult:
    """The outcome of reading one declared field from one message."""

    message_offset: int
    message_length: int
    field_name: str
    field_type: str
    field_offset: int
    field_length: int
    value: object
    status: Status
    hypothesis: bool = False
    provenance_range: dict | None = None
    session_id: str = ""
    direction: str = ""
    reason: str | None = None

    def to_dict(self) -> dict:
        out = {
            "message_offset": self.message_offset,
            "message_length": self.message_length,
            "field_name": self.field_name,
            "field_type": self.field_type,
            "field_offset": self.field_offset,
            "field_length": self.field_length,
            "value": _jsonable(self.value),
            "status": self.status.value,
        }
        if self.hypothesis:
            out["hypothesis"] = True
        if self.provenance_range is not None:
            out["provenance_range"] = self.provenance_range
        if self.session_id:
            out["session_id"] = self.session_id
        if self.direction:
            out["direction"] = self.direction
        if self.reason:
            out["reason"] = self.reason
        return out


@dataclass
class MessageResult:
    """A framed message together with the results for each declared field."""

    offset: int
    length: int
    status: Status
    fields: list[FieldResult] = field(default_factory=list)
    complete: bool = True
    session_id: str = ""
    direction: str = ""
    reason: str | None = None
    bytes_hex: str = ""

    @property
    def end(self) -> int:
        return self.offset + self.length

    def field_values(self) -> dict:
        return {f.field_name: _jsonable(f.value) for f in self.fields}

    def counterexample(self) -> "Counterexample | None":
        """Return a counterexample for this message, or ``None`` if matched."""
        if self.status in (Status.MATCHED, Status.UNCOVERED, Status.UNKNOWN, Status.NOT_APPLICABLE):
            return None
        bad = next(
            (f for f in self.fields if f.status in (Status.MISMATCHED, Status.INCOMPLETE)),
            None,
        )
        amb = next((f for f in self.fields if f.status == Status.AMBIGUOUS), None)
        field_hit = bad if bad is not None else amb
        return Counterexample(
            status=self.status,
            reason=self.reason or (field_hit.reason if field_hit else None),
            session_id=self.session_id,
            direction=self.direction,
            message_offset=self.offset,
            message_length=self.length,
            field_name=field_hit.field_name if field_hit else None,
            field_offset=field_hit.field_offset if field_hit else None,
            field_length=field_hit.field_length if field_hit else None,
            bytes_hex=self.bytes_hex,
            provenance_range=(field_hit.provenance_range if field_hit else None),
        )


@dataclass
class Counterexample:
    """A message (or a field inside it) that contradicts a rule."""

    status: Status
    reason: str | None
    session_id: str
    direction: str
    message_offset: int
    message_length: int
    field_name: str | None = None
    field_offset: int | None = None
    field_length: int | None = None
    bytes_hex: str | None = None
    provenance_range: dict | None = None

    def to_dict(self) -> dict:
        out = {
            "status": self.status.value,
            "session_id": self.session_id,
            "direction": self.direction,
            "message_offset": self.message_offset,
            "message_length": self.message_length,
        }
        for key in ("reason", "field_name", "field_offset", "field_length", "bytes_hex"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.provenance_range is not None:
            out["provenance_range"] = self.provenance_range
        return out


def _jsonable(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    return value


def _provenance_for(stream: DirectionalStream, start: int, end: int) -> dict | None:
    if not stream.provenance:
        return None
    overlapping = [p for p in stream.provenance if start < p.end and p.offset < end]
    if not overlapping:
        return None
    packets = sorted({p.packet_index for p in overlapping if p.packet_index is not None})
    return {
        "offset": start,
        "length": end - start,
        "packets": packets,
    }


def _decode_field(
    field: FieldSpec,
    data: bytes,
    stream: DirectionalStream,
    message: Message,
    session_id: str,
    direction: str,
) -> FieldResult:
    start = message.offset + field.offset
    end = start + field.size
    base = dict(
        message_offset=message.offset,
        message_length=message.length,
        field_name=field.name,
        field_type=field.type,
        field_offset=field.offset,
        field_length=max(end - start, 0),
        hypothesis=field.hypothesis,
        session_id=session_id,
        direction=direction,
        provenance_range=_provenance_for(stream, min(start, len(data)), min(end, len(data))),
    )
    if end > message.end or end > len(data):
        if field.missing_ok:
            return FieldResult(value=None, status=Status.UNCOVERED, reason="field_absent", **base)
        return FieldResult(value=None, status=Status.INCOMPLETE, reason="field_beyond_message", **base)
    if stream.has_gap(start, end):
        return FieldResult(value=None, status=Status.INCOMPLETE, reason="gap_in_field_range", **base)
    if stream.has_ambiguity(start, end):
        return FieldResult(value=None, status=Status.AMBIGUOUS, reason="ambiguity_in_field_range", **base)

    chunk = data[start:end]
    value = _decode_value(field, chunk)
    status = Status.MATCHED
    reason = None
    if field.expected is not None and value not in field.expected:
        status = Status.MISMATCHED
        reason = f"value {value!r} not in expected {field.expected!r}"
    return FieldResult(value=value, status=status, reason=reason, **base)


def _decode_value(field: FieldSpec, chunk: bytes):
    if field.type == "bytes":
        return chunk.hex()
    if field.type == "enum":
        raw = int.from_bytes(chunk, field.byte_order)
        if field.enum:
            for name, number in field.enum.items():
                if number == raw:
                    return name
        return raw
    if field.type in FIELD_TYPES:
        return int.from_bytes(chunk, field.byte_order, signed=field.type in _SIGNED)
    raise ValueError(f"unsupported field type {field.type!r}")


def _message_status(message: Message, fields: list[FieldResult]) -> tuple[Status, str | None]:
    if not message.complete:
        return Status.INCOMPLETE, message.reason
    for candidate in (Status.MISMATCHED, Status.AMBIGUOUS, Status.INCOMPLETE):
        if any(f.status == candidate for f in fields):
            return candidate, next((f.reason for f in fields if f.status == candidate), None)
    # Every declared field was absent by design: the message carries no
    # interpreted value, so it is uncovered rather than matched.
    if fields and all(f.status == Status.UNCOVERED for f in fields):
        return Status.UNCOVERED, "no_declared_field_present"
    return Status.MATCHED, None


def apply_rule(
    stream: DirectionalStream | bytes,
    rule: Rule,
    session_id: str = "",
    direction: str = "A_to_B",
) -> list[MessageResult]:
    """Frame *stream* and decode *rule* fields for every framed message.

    ``FieldResult`` instances live inside the returned ``MessageResult`` list;
    use :func:`flatten_fields` for a flat per-field view. When the rule scope
    does not cover ``direction``, every framed message is marked
    ``not_applicable`` instead of being decoded.
    """
    if not isinstance(stream, DirectionalStream):
        stream = DirectionalStream.from_bytes(stream)
    data = stream.data
    strategy = FramingStrategy.from_dict(rule.framing)
    messages = frame_stream(data, strategy)
    if not rule.applies_to(direction):
        return [
            MessageResult(
                offset=m.offset,
                length=m.length,
                status=Status.NOT_APPLICABLE,
                complete=m.complete,
                session_id=session_id,
                direction=direction,
                reason="rule_scope_excludes_direction",
            )
            for m in messages
        ]

    results: list[MessageResult] = []
    for message in messages:
        fields = [
            _decode_field(f, data, stream, message, session_id, direction)
            for f in rule.fields
        ]
        status, reason = _message_status(message, fields)
        result = MessageResult(
            offset=message.offset,
            length=message.length,
            status=status,
            fields=fields,
            complete=message.complete,
            session_id=session_id,
            direction=direction,
            reason=reason,
            bytes_hex=data[message.offset : message.end].hex(),
        )
        results.append(result)
    return results


def flatten_fields(results: list[MessageResult]) -> list[FieldResult]:
    return [f for message in results for f in message.fields]


def apply_rule_fields(
    stream: DirectionalStream | bytes,
    rule: Rule,
    session_id: str = "",
    direction: str = "A_to_B",
) -> list[FieldResult]:
    """Apply *rule* and return a flat list of per-field results."""
    return flatten_fields(apply_rule(stream, rule, session_id, direction))
