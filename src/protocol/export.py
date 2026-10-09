"""Export a rule as a Kaitai Struct .ksy description or a standalone Python parser.

The engine already reads a stream. The export turns the same declarative rule
into two external forms: a Kaitai Struct schema that other tooling can open, and
a self-contained Python module with no dependency on this project. Both describe
one message layout; the framing strategy is preserved so a caller can split a
stream before parsing.

What cannot be exported is as important as what can. Kaitai and the generated
Python parser read bytes; they do not decide whether a checksum is correct or
whether a value matches a hypothesis. Those checks stay in the engine, and the
exported forms mark such fields as commented rather than pretending to verify
them.
"""

from __future__ import annotations

import json

from .checksums import ALGORITHMS
from .rule import Rule

_KAITAI_TYPES = {
    "uint8": "u1",
    "uint16": "u2",
    "uint32": "u4",
    "int8": "s1",
    "int16": "s2",
    "int32": "s4",
}

_ENDIAN = {"big": "be", "little": "le"}


def export_kaitai(rule: Rule) -> str:
    """Return a Kaitai Struct YAML document describing one message."""
    lines: list[str] = []
    endian = _ENDIAN.get(str(rule.framing.get("byte_order", "big")), "be")
    lines.append("meta:")
    lines.append(f"  id: {_identifier(rule.name or rule.rule_id)}")
    lines.append(f"  endian: {endian}")
    lines.append("seq:")
    for index, field in enumerate(rule.fields):
        lines.extend(_kaitai_field(field, index, rule))
    if rule.framing.get("type") == "marker_based":
        start = rule.framing.get("start_bytes")
        if start is not None:
            lines.append("doc: |")
            lines.append("  Framing: marker_based. The stream starts with the marker below.")
            lines.append(f"  Marker: {_marker(start)!r}")
    return "\n".join(lines) + "\n"


def _kaitai_field(field, index: int, rule: Rule) -> list[str]:
    out: list[str] = []
    ftype = field.type
    field_id = "pad_%d" % index if ftype == "padding" else _identifier(field.name)
    out.append(f"  - id: {field_id}")

    if ftype in _KAITAI_TYPES:
        out.append(f"    type: {_KAITAI_TYPES[ftype]}")
    elif ftype == "bytes" or ftype == "padding":
        out.append("    type: bytes")
        out.append(f"    size: {field.size}")
    elif ftype == "enum":
        out.append(f"    type: {_KAITAI_TYPES.get('uint8', 'u1')}")
        out.append(f"    enum: {_identifier(field.name)}")
    elif ftype == "bitmask":
        width = (field.bit_offset or 0) + (field.bit_length or 0)
        out.append(f"    type: b{field.bit_length or 1}")
        out.append(f"    size: {(width + 7) // 8}")
    elif ftype == "string":
        out.append("    type: str")
        if field.terminated:
            out.append("    terminator: 0")
            out.append("    encoding: UTF-8")
        else:
            out.append(f"    size: {field.size}")
            out.append("    encoding: UTF-8")
    elif ftype == "array":
        out.append(f"    type: {_KAITAI_TYPES.get(field.element_type or 'uint8', 'u1')}"
                   if field.element_type != "bytes" else "    type: bytes")
        if field.element_type == "bytes":
            out.append(f"    size: {field.element_length or 1}")
        out.append("    repeat: expr")
        out.append(f"    repeat-expr: {field.count if field.count is not None else 1}")
    else:
        # checksum, computed and conditional fields are read as raw values; the
        # verifying logic stays in the engine.
        out.append(f"    type: {_KAITAI_TYPES.get('uint8', 'u1') if field.size == 1 else 'u2' if field.size == 2 else 'u4'}")
        out.append("    doc: raw value; the engine checks this field, the schema does not")

    if field.type == "conditional" and field.inner is not None:
        condition = _kaitai_condition(field)
        if condition:
            out.append(f"    if: {condition}")
    return out


def _kaitai_condition(field) -> str | None:
    condition = field.condition or {}
    name = _identifier(str(condition.get("field", "")))
    op = condition.get("op")
    value = condition.get("value")
    if not name:
        return None
    if op in ("bit_set", "bit_clear"):
        expr = f"_io._parent.{name}"
        return expr if op == "bit_set" else f"not {expr}"
    if op in ("eq", "ne"):
        sign = "==" if op == "eq" else "!="
        return f"{name} {sign} {value}"
    return None


def _marker(value) -> bytes:
    if isinstance(value, str):
        return bytes.fromhex(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return b""


def _identifier(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(name)).strip("_")
    if not cleaned:
        return "field"
    if cleaned[0].isdigit():
        cleaned = "f_" + cleaned
    return cleaned


def export_python(rule: Rule) -> str:
    """Return a standalone Python module that frames and parses the layout."""
    payload = json.dumps(rule.to_dict(), ensure_ascii=False, sort_keys=True)
    header = (
        '"""Standalone parser generated from rule %s v%s.\n\n'
        "Frames a directional byte stream and reads the declared fields. The\n"
        "module has no dependency on the project that produced it.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "import json\n"
        "import struct\n\n"
        "RULE = json.loads(r'''%s''')\n"
        "CHECKSUM_ALGORITHMS = %r\n\n"
    ) % (rule.rule_id, rule.rule_version, payload, list(ALGORITHMS))
    return header + _PY_BODY


_PY_BODY = '''

def frame(data):
    """Split a byte stream into message spans (offset, length)."""
    framing = RULE.get("framing") or {"type": "manual"}
    kind = framing.get("type")
    out = []
    if kind == "fixed_size":
        size = int(framing["size"])
        if size <= 0:
            return []
        for offset in range(0, len(data), size):
            out.append((offset, min(size, len(data) - offset)))
        return out
    if kind == "length_prefixed":
        return _frame_length_prefixed(data, framing)
    if kind == "marker_based":
        return _frame_marker(data, framing)
    if kind == "manual":
        return [(int(m["offset"]), int(m["length"])) for m in framing.get("messages", [])]
    raise ValueError("unknown framing type %r" % (kind,))


def _frame_length_prefixed(data, framing):
    offset_at = int(framing.get("length_offset", 0))
    size = int(framing.get("length_size", 1))
    order = framing.get("byte_order", "big")
    covers = framing.get("length_covers", "payload")
    out = []
    i = 0
    while i < len(data):
        if i + offset_at + size > len(data):
            out.append((i, len(data) - i))
            break
        value = int.from_bytes(data[i + offset_at:i + offset_at + size], order)
        if covers == "entire_message":
            total = value
        elif covers == "payload_and_length_field":
            total = offset_at + value
        else:
            total = offset_at + size + value
        total = max(total, offset_at + size)
        length = min(total, len(data) - i)
        out.append((i, length))
        if length <= 0:
            out.append((i, len(data) - i))
            break
        i += length
    return out


def _frame_marker(data, framing):
    start = _marker_bytes(framing.get("start_bytes"))
    end = _marker_bytes(framing.get("end_bytes"))
    if not start:
        return [(0, len(data))]
    out = []
    i = 0
    while True:
        begin = data.find(start, i)
        if begin == -1:
            break
        if end:
            stop = data.find(end, begin + len(start))
            stop = len(data) if stop == -1 else stop + len(end)
        else:
            stop = len(data)
        out.append((begin, stop - begin))
        i = stop
    return out


def _marker_bytes(value):
    if value is None:
        return b""
    if isinstance(value, str):
        return bytes.fromhex(value)
    return bytes(value)


def _decode_number(chunk, kind, order):
    signed = kind in ("int8", "int16", "int32")
    return int.from_bytes(chunk, order, signed=signed)


def _compute(algorithm, data):
    if algorithm == "xor":
        value = 0
        for byte in data:
            value ^= byte
        return value
    if algorithm == "sum":
        return sum(data) & 0xFF
    if algorithm == "crc8":
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        return crc
    if algorithm == "crc16":
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
        return crc
    raise ValueError("unknown checksum %r" % (algorithm,))


def _field_size(field):
    ftype = field.get("type")
    sizes = {"uint8": 1, "uint16": 2, "uint32": 4, "int8": 1, "int16": 2, "int32": 4}
    if ftype in sizes:
        return sizes[ftype]
    if ftype == "enum":
        return 1
    if ftype == "bitmask":
        width = int(field.get("bit_offset", 0)) + int(field.get("bit_length", 1))
        return (width + 7) // 8
    if ftype == "conditional":
        return _field_size(field.get("field", {}))
    return int(field.get("length", 0))


def parse_message(data, offset, length):
    """Read the declared fields of one message into a dict."""
    end = offset + length
    context = {}
    values = {}
    statuses = {}
    for field in RULE.get("fields", []):
        spec = field
        if field.get("type") == "conditional":
            if not _condition(field.get("condition"), context):
                values[field["name"]] = None
                statuses[field["name"]] = "uncovered"
                context[field["name"]] = None
                continue
            spec = field.get("field", {})
        start = offset + int(spec.get("offset", 0))
        order = spec.get("byte_order", RULE.get("framing", {}).get("byte_order", "big"))
        if spec.get("type") == "string" and spec.get("terminated"):
            stop = data.find(b"\\x00", start, end)
            stop = end if stop == -1 else stop + 1
        elif spec.get("type") == "array" and spec.get("count_field"):
            count = _as_int(context.get(spec["count_field"])) or 0
            elem = (int(spec.get("element_length", 1)) if spec.get("element_type") == "bytes"
                    else _field_size({"type": spec.get("element_type", "uint8")}))
            stop = start + count * elem
        else:
            stop = start + _field_size(spec)
        if stop > end:
            values[field["name"]] = None
            statuses[field["name"]] = "incomplete"
            context[field["name"]] = None
            continue
        chunk = data[start:stop]
        ftype = spec.get("type")
        if ftype == "padding":
            values[field["name"]] = None
            statuses[field["name"]] = "uncovered"
        elif ftype == "bytes":
            values[field["name"]] = chunk.hex()
            statuses[field["name"]] = "matched"
        elif ftype == "enum":
            raw = _decode_number(chunk, "uint8", order)
            name = next((k for k, v in (spec.get("enum") or {}).items() if v == raw), raw)
            values[field["name"]] = name
            statuses[field["name"]] = "matched"
        elif ftype == "bitmask":
            raw = _decode_number(chunk, "uint8", order)
            values[field["name"]] = (raw >> int(spec.get("bit_offset", 0))) & ((1 << int(spec.get("bit_length", 1))) - 1)
            statuses[field["name"]] = "matched"
        elif ftype == "string":
            text = chunk.split(b"\\x00", 1)[0] if spec.get("terminated") else chunk.rstrip(b"\\x00")
            values[field["name"]] = text.decode(spec.get("encoding", "utf-8") or "utf-8", errors="replace")
            statuses[field["name"]] = "matched"
        elif ftype == "array":
            values[field["name"]] = _decode_array(data, start, spec, context, order)
            statuses[field["name"]] = "matched"
        elif ftype == "checksum":
            stored = int.from_bytes(chunk, order)
            width = len(chunk)
            rstart = offset + int(spec.get("start", 0))
            rend = offset + int(spec.get("end", length))
            computed = _compute(spec.get("algorithm"), data[rstart:rend])
            values[field["name"]] = stored
            statuses[field["name"]] = "matched" if computed == stored else "mismatched"
        elif ftype == "computed":
            stored = int.from_bytes(chunk, order)
            computed = _expression(spec.get("expression"), context)
            values[field["name"]] = stored
            statuses[field["name"]] = "matched" if computed == stored else ("incomplete" if computed is None else "mismatched")
        else:
            values[field["name"]] = _decode_number(chunk, ftype or "uint8", order)
            statuses[field["name"]] = "matched"
        context[field["name"]] = values[field["name"]]
    return values, statuses


def _decode_array(data, start, spec, context, order):
    count = spec.get("count")
    if spec.get("count_field"):
        count = _as_int(context.get(spec["count_field"])) or 0
    count = int(count or 0)
    etype = spec.get("element_type", "uint8")
    size = int(spec.get("element_length", 1)) if etype == "bytes" else _field_size({"type": etype})
    out = []
    for i in range(count):
        chunk = data[start + i * size:start + (i + 1) * size]
        if len(chunk) < size:
            break
        out.append(chunk.hex() if etype == "bytes" else _decode_number(chunk, etype, order))
    return out


def _as_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _condition(condition, context):
    if not condition:
        return False
    left = context.get(condition.get("field"))
    op = condition.get("op")
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


def _expression(expression, context):
    if not expression:
        return None
    op = expression.get("op")
    value = expression.get("value")
    names = expression.get("fields") or []
    values = []
    for name in names:
        item = _as_int(context.get(name))
        if item is None:
            return None
        values.append(item)
    if op == "const":
        return int(value) if value is not None else None
    if op in ("sum_of_values", "add"):
        return sum(values) + int(value or 0)
    if op == "xor":
        acc = 0
        for item in values:
            acc ^= item
        return acc ^ int(value or 0)
    if op == "sub":
        if not values:
            return None
        acc = values[0]
        for item in values[1:]:
            acc -= item
        return acc - int(value or 0)
    return None


def parse_stream(data, session_id="", direction="A_to_B"):
    """Frame the stream and parse every message."""
    messages = []
    for offset, length in frame(data):
        values, statuses = parse_message(data, offset, length)
        messages.append({
            "offset": offset,
            "length": length,
            "fields": values,
            "field_status": statuses,
            "session_id": session_id,
            "direction": direction,
        })
    return messages
'''
