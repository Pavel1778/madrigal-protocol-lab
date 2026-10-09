"""Framing strategies: split a directional byte stream into messages.

TCP packet boundaries are not message boundaries. A framing strategy walks the
flat byte stream and yields byte ranges, each of which is one candidate
message. A range is ``complete`` when both of its boundaries were found in the
stream; truncated trailing bytes are reported as ``incomplete`` so the caller
can classify them instead of silently dropping them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .stream import DirectionalStream


class FramingError(ValueError):
    """Raised when a framing strategy is malformed."""


#: Values of ``length_covers`` for length-prefixed framing (Task semantics).
#:
#: * ``payload`` (default when the field is absent) — the length value counts
#:   only the payload; the message is
#:   ``length_offset + length_size + length_value`` bytes long. This is the
#:   historical meaning of ``length_includes_payload=false``.
#: * ``payload_and_length_field`` — the length value counts the payload plus
#:   the bytes of the length field, but not the bytes of fields that precede
#:   the length field; the message is
#:   ``length_offset + length_value`` bytes long. This is the historical
#:   meaning of ``length_includes_payload=true``.
#: * ``entire_message`` — the length value counts the whole message; the
#:   message is ``length_value`` bytes long.
LENGTH_COVERS_PAYLOAD = "payload"
LENGTH_COVERS_PAYLOAD_AND_FIELD = "payload_and_length_field"
LENGTH_COVERS_ENTIRE = "entire_message"
LENGTH_COVERS_VALUES = (
    LENGTH_COVERS_PAYLOAD,
    LENGTH_COVERS_PAYLOAD_AND_FIELD,
    LENGTH_COVERS_ENTIRE,
)
LENGTH_COVERS_DEFAULT = LENGTH_COVERS_PAYLOAD


def _normalise_length_covers(spec: dict) -> str:
    covers = spec.get("length_covers")
    if covers is not None:
        covers = str(covers)
        if covers not in LENGTH_COVERS_VALUES:
            raise FramingError(f"unsupported length_covers {covers!r}")
        return covers
    # Backward compatibility with the old boolean. ``length_includes_payload``
    # true meant the length value was the whole message (entire_message); false
    # meant it counted only the payload (payload).
    legacy = spec.get("length_includes_payload")
    if legacy is None:
        return LENGTH_COVERS_DEFAULT
    return LENGTH_COVERS_ENTIRE if legacy else LENGTH_COVERS_PAYLOAD


def _byte_order(name: str) -> str:
    if name in ("big", "be", "network", ">"):
        return "big"
    if name in ("little", "le", "<"):
        return "little"
    raise FramingError(f"unsupported byte_order {name!r}")


def _read_int(data: bytes, offset: int, size: int, order: str) -> int:
    chunk = data[offset : offset + size]
    if len(chunk) != size:
        raise FramingError("not enough bytes for an integer")
    return int.from_bytes(chunk, order)


@dataclass
class Message:
    """A candidate message located in a directional stream.

    Args:
        offset: Byte offset of the message start inside the stream.
        length: Message length in bytes.
        complete: Whether both message boundaries were found in the stream.
        reason: Machine-readable reason when ``complete`` is ``False``.
    """

    offset: int
    length: int
    complete: bool = True
    reason: str | None = None

    @property
    def end(self) -> int:
        """Offset one past the last byte of the message."""
        return self.offset + self.length


@dataclass
class FramingStrategy:
    """Declarative description of how messages are delimited.

    ``type`` is one of ``length_prefixed``, ``fixed_size``, ``marker_based`` or
    ``manual``. Only the parameters relevant to the chosen type are read.

    For ``length_prefixed`` the meaning of the length value is fixed by
    ``length_covers``; when the field is absent it defaults to ``payload``
    (see the ``LENGTH_COVERS_*`` constants). The deprecated boolean
    ``length_includes_payload`` is still accepted for backward compatibility:
    ``true`` maps to ``entire_message`` and ``false`` maps to ``payload``.
    """

    type: str
    length_offset: int = 0
    length_size: int = 2
    byte_order: str = "big"
    length_covers: str = LENGTH_COVERS_DEFAULT
    size: int = 0
    start_bytes: bytes = b""
    end_bytes: bytes = b""
    include_markers: bool = True
    messages: list[Message] = field(default_factory=list)

    @classmethod
    def from_dict(cls, spec: dict) -> "FramingStrategy":
        """Build a strategy from a rule ``framing`` object.

        Args:
            spec: Mapping with a ``type`` key and the parameters for that type.

        Returns:
            The parsed strategy.

        Raises:
            FramingError: If ``spec`` is not an object, the type is unknown, or
                a parameter value is outside its accepted set.
        """
        if not isinstance(spec, dict):
            raise FramingError("framing must be an object")
        ftype = spec.get("type")
        if ftype not in ("length_prefixed", "fixed_size", "marker_based", "manual"):
            raise FramingError(f"unsupported framing type {ftype!r}")
        start = spec.get("start_bytes", b"")
        end = spec.get("end_bytes", b"")
        covers = _normalise_length_covers(spec)
        return cls(
            type=ftype,
            length_offset=int(spec.get("length_offset", 0)),
            length_size=int(spec.get("length_size", 2)),
            byte_order=str(spec.get("byte_order", "big")),
            length_covers=covers,
            size=int(spec.get("size", 0)),
            start_bytes=_as_bytes(start),
            end_bytes=_as_bytes(end),
            include_markers=bool(spec.get("include_markers", True)),
            messages=[
                Message(offset=int(m.get("offset", 0)), length=int(m.get("length", 0)))
                for m in spec.get("messages", [])
            ],
        )


def _as_bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("hex:"):
            return bytes.fromhex(text[4:])
        return text.encode("utf-8")
    if isinstance(value, list):
        return bytes(int(b) & 0xFF for b in value)
    raise FramingError(f"cannot interpret marker value {value!r}")


def frame_stream(stream: bytes | DirectionalStream, strategy: FramingStrategy) -> list[Message]:
    """Split *stream* into candidate messages using *strategy*.

    Args:
        stream: Flat bytes or a directional stream to split.
        strategy: Framing strategy describing how messages are delimited.

    Returns:
        Candidate messages in order. A trailing range whose end was not found
        is returned with ``complete=False`` rather than dropped.

    Raises:
        FramingError: If the strategy has an unsupported type or an invalid
            parameter (for example a non-positive ``size``).

    Example:
        >>> frame_stream(b"\x02\x00\x05", FramingStrategy.from_dict(
        ...     {"type": "length_prefixed", "length_offset": 0, "length_size": 1,
        ...      "length_covers": "entire_message"}))[0].length
        2
    """
    if isinstance(stream, DirectionalStream):
        data = stream.data
    else:
        data = bytes(stream)
    if strategy.type == "length_prefixed":
        return _length_prefixed(data, strategy)
    if strategy.type == "fixed_size":
        return _fixed_size(data, strategy)
    if strategy.type == "marker_based":
        return _marker_based(data, strategy)
    if strategy.type == "manual":
        return _manual(data, strategy)
    raise FramingError(f"unsupported framing type {strategy.type!r}")


def _length_prefixed(data: bytes, strategy: FramingStrategy) -> list[Message]:
    order = _byte_order(strategy.byte_order)
    if strategy.length_size <= 0:
        raise FramingError("length_size must be positive")
    if strategy.length_offset < 0:
        raise FramingError("length_offset must be non-negative")
    header_end = strategy.length_offset + strategy.length_size
    covers = strategy.length_covers
    if covers not in LENGTH_COVERS_VALUES:
        raise FramingError(f"unsupported length_covers {covers!r}")
    prefix = strategy.length_offset
    messages: list[Message] = []
    pos = 0
    total = len(data)
    while pos < total:
        if pos + header_end > total:
            messages.append(
                Message(pos, total - pos, complete=False, reason="length_header_truncated")
            )
            break
        declared = _read_int(data, pos + strategy.length_offset, strategy.length_size, order)
        if covers == LENGTH_COVERS_PAYLOAD:
            length = prefix + strategy.length_size + declared
        elif covers == LENGTH_COVERS_PAYLOAD_AND_FIELD:
            length = prefix + declared
        else:  # LENGTH_COVERS_ENTIRE
            length = declared
        if length < header_end:
            # A length that cannot even hold its own header cannot be advanced
            # over without risking a non-progressing loop.
            messages.append(Message(pos, 0, complete=False, reason="length_too_small"))
            break
        end = pos + length
        if end > total:
            messages.append(
                Message(pos, total - pos, complete=False, reason="payload_truncated")
            )
            break
        messages.append(Message(pos, length, complete=True))
        pos = end
    return messages


def _fixed_size(data: bytes, strategy: FramingStrategy) -> list[Message]:
    if strategy.size <= 0:
        raise FramingError("fixed_size framing requires a positive size")
    messages: list[Message] = []
    pos = 0
    total = len(data)
    while pos < total:
        remaining = total - pos
        if remaining >= strategy.size:
            messages.append(Message(pos, strategy.size, complete=True))
            pos += strategy.size
        else:
            messages.append(Message(pos, remaining, complete=False, reason="short_final_message"))
            break
    return messages


def _marker_based(data: bytes, strategy: FramingStrategy) -> list[Message]:
    start = strategy.start_bytes
    end = strategy.end_bytes
    if not start and not end:
        raise FramingError("marker_based framing requires start_bytes or end_bytes")
    messages: list[Message] = []
    pos = 0
    total = len(data)
    while pos < total:
        if start:
            begin = data.find(start, pos)
            if begin < 0:
                messages.append(
                    Message(pos, total - pos, complete=False, reason="start_marker_not_found")
                )
                break
        else:
            begin = pos
        if end:
            stop = data.find(end, begin + len(start))
            if stop < 0:
                messages.append(
                    Message(begin, total - begin, complete=False, reason="end_marker_not_found")
                )
                break
            body_end = stop + len(end) if strategy.include_markers else stop
        else:
            body_end = total
        messages.append(Message(begin, body_end - begin, complete=True))
        # Always advance past the current message so an empty marker match
        # cannot loop forever.
        pos = body_end if body_end > pos else pos + 1
    return messages


def _manual(data: bytes, strategy: FramingStrategy) -> list[Message]:
    messages: list[Message] = []
    total = len(data)
    for message in strategy.messages:
        if message.offset < 0 or message.length < 0:
            raise FramingError("manual message offset and length must be non-negative")
        end = message.offset + message.length
        complete = end <= total
        messages.append(
            Message(
                message.offset,
                message.length if complete else max(total - message.offset, 0),
                complete=complete,
                reason=None if complete else "beyond_stream_end",
            )
        )
    return messages
