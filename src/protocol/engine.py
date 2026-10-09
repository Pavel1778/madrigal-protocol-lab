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
from .checksums import compute as checksum_compute
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
    context: dict | None = None,
) -> FieldResult:
    """Decode one field. ``context`` holds already-decoded values by name."""
    context = context if context is not None else {}
    condition = field.condition if field.type == "conditional" else None
    spec = field.inner if condition is not None else field

    if condition is not None and not _evaluate_condition(condition, context):
        return FieldResult(
            message_offset=message.offset,
            message_length=message.length,
            field_name=field.name,
            field_type="conditional",
            field_offset=field.offset,
            field_length=0,
            value=None,
            status=Status.UNCOVERED,
            hypothesis=field.hypothesis,
            session_id=session_id,
            direction=direction,
            reason="condition_not_met",
        )

    start = message.offset + spec.offset
    if spec.type == "string" and spec.terminated:
        length = _terminated_length(data, start, message.end)
        end = start + length
    elif spec.type == "array" and spec.count_field is not None:
        count = _context_int(context, spec.count_field)
        elem = FIELD_TYPES.get(spec.element_type or "", spec.element_length if spec.element_type == "bytes" else None)
        length = (count * elem) if (count is not None and elem is not None) else None
        end = start + length if length is not None else message.end
    elif spec.type == "computed":
        end = start + spec.size
    else:
        end = start + spec.size

    base = dict(
        message_offset=message.offset,
        message_length=message.length,
        field_name=field.name,
        field_type=field.type,
        field_offset=spec.offset,
        field_length=max(end - start, 0),
        hypothesis=field.hypothesis,
        session_id=session_id,
        direction=direction,
        provenance_range=_provenance_for(stream, min(start, len(data)), min(end, len(data))),
    )

    if spec.type == "padding":
        return FieldResult(value=None, status=Status.UNCOVERED, reason="padding", **base)

    if spec.type == "computed":
        return _decode_computed(field, spec, data, message, start, context, **base)

    if end > message.end or end > len(data):
        if field.missing_ok:
            return FieldResult(value=None, status=Status.UNCOVERED, reason="field_absent", **base)
        return FieldResult(value=None, status=Status.INCOMPLETE, reason="field_beyond_message", **base)
    if stream.has_gap(start, end):
        return FieldResult(value=None, status=Status.INCOMPLETE, reason="gap_in_field_range", **base)
    if stream.has_ambiguity(start, end):
        return FieldResult(value=None, status=Status.AMBIGUOUS, reason="ambiguity_in_field_range", **base)

    if spec.type == "checksum":
        return _decode_checksum(field, spec, data, message, start, end, context, **base)

    chunk = data[start:end]
    value = _decode_value(spec, data, start, end, context)
    status = Status.MATCHED
    reason = None
    if spec.expected is not None and value not in spec.expected:
        status = Status.MISMATCHED
        reason = f"value {value!r} not in expected {spec.expected!r}"
    return FieldResult(value=value, status=status, reason=reason, **base)


def _terminated_length(data: bytes, start: int, limit: int) -> int:
    if start >= len(data):
        return 0
    limit = min(limit, len(data))
    idx = data.find(b"\x00", start, limit)
    if idx == -1:
        return limit - start
    return idx - start + 1


def _context_int(context: dict, name: str) -> int | None:
    value = context.get(name)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    return None


def _evaluate_condition(condition: dict, context: dict):
    name = condition.get("field")
    op = condition.get("op")
    left = context.get(name)
    right = condition.get("value")
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "bit_set":
        return isinstance(left, int) and (left & int(right or 0)) != 0
    if op == "bit_clear":
        return isinstance(left, int) and (left & int(right or 0)) == 0
    if op == "gt":
        return isinstance(left, int) and left > int(right or 0)
    if op == "lt":
        return isinstance(left, int) and left < int(right or 0)
    return False


def _decode_checksum(field, spec, data, message, start, end, context, **base):
    stored = int.from_bytes(data[start:end], spec.byte_order)
    range_start = message.offset + (spec.start if spec.start is not None else 0)
    range_end = message.offset + (spec.end if spec.end is not None else message.length)
    range_start = max(range_start, message.offset)
    range_end = min(range_end, message.end, len(data))
    if range_start >= range_end:
        return FieldResult(value=stored, status=Status.INCOMPLETE, reason="checksum_range_empty", **base)
    computed = checksum_compute(spec.algorithm, data[range_start:range_end])
    if computed == stored:
        return FieldResult(value=stored, status=Status.MATCHED, reason=None, **base)
    return FieldResult(
        value=stored,
        status=Status.MISMATCHED,
        reason=f"checksum {stored} != computed {computed} ({spec.algorithm})",
        **base,
    )


def _decode_computed(field, spec, data, message, start, context, **base):
    stored = int.from_bytes(data[start:start + spec.size], spec.byte_order)
    computed = _evaluate_expression(spec.expression, context)
    if computed is None:
        return FieldResult(value=stored, status=Status.INCOMPLETE, reason="computed_operand_missing", **base)
    if computed == stored:
        return FieldResult(value=stored, status=Status.MATCHED, reason=None, **base)
    return FieldResult(
        value=stored,
        status=Status.MISMATCHED,
        reason=f"value {stored} != computed {computed}",
        **base,
    )


def _evaluate_expression(expression: dict | None, context: dict):
    if not expression:
        return None
    op = expression.get("op")
    value = expression.get("value")
    names = expression.get("fields") or expression.get("children") or []
    values = []
    for name in names:
        item = context.get(name)
        if not isinstance(item, int) or isinstance(item, bool):
            return None
        values.append(item)
    if op == "const":
        return int(value) if value is not None else None
    if op == "sum_of_values":
        return sum(values) + int(value or 0)
    if op == "xor":
        acc = 0
        for item in values:
            acc ^= item
        return acc ^ int(value or 0)
    if op == "add":
        return sum(values) + int(value or 0)
    if op == "sub":
        if not values:
            return None
        acc = values[0]
        for item in values[1:]:
            acc -= item
        return acc - int(value or 0)
    return None


def _decode_value(field: FieldSpec, data: bytes, start: int, end: int, context: dict):
    if field.type == "bytes":
        return data[start:end].hex()
    if field.type == "padding":
        return None
    if field.type == "enum":
        raw = int.from_bytes(data[start:end], field.byte_order)
        if field.enum:
            for name, number in field.enum.items():
                if number == raw:
                    return name
        return raw
    if field.type == "bitmask":
        raw = int.from_bytes(data[start:end], field.byte_order)
        return (raw >> (field.bit_offset or 0)) & ((1 << (field.bit_length or 0)) - 1)
    if field.type == "string":
        raw = data[start:end]
        if field.terminated:
            raw = raw.split(b"\x00", 1)[0]
        else:
            raw = raw.rstrip(b"\x00")
        return raw.decode(field.encoding, errors="replace")
    if field.type == "array":
        count = field.count
        if field.count_field is not None:
            count = _context_int(context, field.count_field) or 0
        count = int(count or 0)
        elem_size = field.element_length if field.element_type == "bytes" else FIELD_TYPES.get(field.element_type or "")
        if not elem_size:
            return []
        values = []
        for i in range(count):
            chunk = data[start + i * elem_size : start + (i + 1) * elem_size]
            if len(chunk) < elem_size:
                break
            if field.element_type == "bytes":
                values.append(chunk.hex())
            else:
                values.append(int.from_bytes(chunk, field.byte_order, signed=(field.element_type or "") in _SIGNED))
        return values
    if field.type in FIELD_TYPES:
        return int.from_bytes(data[start:end], field.byte_order, signed=field.type in _SIGNED)
    raise ValueError(f"unsupported field type {field.type!r}")


def _message_status(message: Message, fields: list[FieldResult]) -> tuple[Status, str | None]:
    if not message.complete:
        return Status.INCOMPLETE, message.reason
    for candidate in (Status.MISMATCHED, Status.AMBIGUOUS, Status.INCOMPLETE):
        if any(f.status == candidate for f in fields):
            return candidate, next((f.reason for f in fields if f.status == candidate), None)
    # A message where no field produced an interpreted value carries no
    # reading: padding, absent-by-design and unmet-condition fields only.
    if fields and not any(f.status in (Status.MATCHED, Status.MISMATCHED) for f in fields):
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
        context: dict = {}
        fields: list[FieldResult] = []
        for f in rule.fields:
            decoded = _decode_field(f, data, stream, message, session_id, direction, context)
            fields.append(decoded)
            context[f.name] = decoded.value
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
