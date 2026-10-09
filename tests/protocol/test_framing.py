import struct

import pytest

from src.protocol.framing import FramingError, FramingStrategy, frame_stream


def _length_prefixed_stream(field_length, covers):
    spec = {
        "type": "length_prefixed",
        "length_offset": 2,
        "length_size": 2,
        "byte_order": "big",
        "length_covers": covers,
    }
    return FramingStrategy.from_dict(spec), field_length


def _message(payload: bytes, declared: int) -> bytes:
    return bytes([0x10, 0x00]) + struct.pack(">H", declared) + payload


def test_length_prefixed_entire_message():
    strategy, _ = _length_prefixed_stream(None, "entire_message")
    first = _message(b"abcd", 8)
    second = _message(b"ef", 6)
    messages = frame_stream(first + second, strategy)
    assert [(m.offset, m.length, m.complete) for m in messages] == [
        (0, 8, True),
        (8, 6, True),
    ]


def test_length_prefixed_payload_only_length():
    strategy, _ = _length_prefixed_stream(None, "payload")
    first = _message(b"abcd", 4)
    messages = frame_stream(first + _message(b"ef", 2), strategy)
    assert [(m.offset, m.length) for m in messages] == [(0, 8), (8, 6)]


def test_length_prefixed_payload_and_length_field():
    strategy, _ = _length_prefixed_stream(None, "payload_and_length_field")
    # declared 6 = payload (4) + length field (2); the two leading bytes are a
    # prefix that is not counted by the length value, so the message is 2 + 6.
    first = _message(b"abcd", 6)
    messages = frame_stream(first + _message(b"ef", 4), strategy)
    assert [(m.offset, m.length) for m in messages] == [(0, 8), (8, 6)]


def test_length_covers_changes_message_size_for_same_input():
    data = _message(b"abcd", 6) + _message(b"efgh", 4)
    sizes = {}
    for covers in ("payload", "payload_and_length_field", "entire_message"):
        strategy = _length_prefixed_stream(None, covers)[0]
        messages = frame_stream(data, strategy)
        assert messages[0].complete is True
        sizes[covers] = messages[0].length
    assert sizes["payload"] == 10
    assert sizes["payload_and_length_field"] == 8
    assert sizes["entire_message"] == 6


def test_length_covers_defaults_to_payload():
    strategy = FramingStrategy.from_dict(
        {"type": "length_prefixed", "length_offset": 2, "length_size": 2}
    )
    assert strategy.length_covers == "payload"
    messages = frame_stream(_message(b"abcd", 4), strategy)
    assert messages[0].length == 8


def test_legacy_length_includes_payload_boolean_still_maps():
    includes = FramingStrategy.from_dict(
        {"type": "length_prefixed", "length_offset": 2, "length_size": 2, "length_includes_payload": True}
    )
    excludes = FramingStrategy.from_dict(
        {"type": "length_prefixed", "length_offset": 2, "length_size": 2, "length_includes_payload": False}
    )
    assert includes.length_covers == "entire_message"
    assert excludes.length_covers == "payload"


def _boundary_strategy(covers):
    return FramingStrategy.from_dict(
        {
            "type": "length_prefixed",
            "length_offset": 0,
            "length_size": 2,
            "byte_order": "big",
            "length_covers": covers,
        }
    )


def _header(declared: int) -> bytes:
    return struct.pack(">H", declared)


def test_boundary_zero_length_yields_header_only_message():
    # payload: total = 0 + 2 + 0 = 2 (the header itself), a complete message.
    messages = frame_stream(_header(0), _boundary_strategy("payload"))
    assert len(messages) == 1
    assert messages[0].complete is True
    assert messages[0].length == 2

    # payload_and_length_field and entire_message: a declared length of zero
    # cannot hold the two-byte header, so framing is diagnosed and stops.
    for covers in ("payload_and_length_field", "entire_message"):
        messages = frame_stream(_header(0), _boundary_strategy(covers))
        assert len(messages) == 1, covers
        assert messages[0].complete is False, covers
        assert messages[0].reason == "length_too_small", covers


def test_boundary_one_length_yields_minimal_message():
    # payload with one payload byte: total = 0 + 2 + 1 = 3.
    messages = frame_stream(_header(1) + b"x", _boundary_strategy("payload"))
    assert len(messages) == 1
    assert messages[0].complete is True
    assert messages[0].length == 3

    # entire_message with the smallest length that holds its own header.
    messages = frame_stream(_header(2), _boundary_strategy("entire_message"))
    assert len(messages) == 1
    assert messages[0].complete is True
    assert messages[0].length == 2


def test_boundary_length_beyond_stream_is_incomplete_and_stops():
    for covers in ("payload", "payload_and_length_field", "entire_message"):
        data = _header(64)  # declares far more than remains
        messages = frame_stream(data, _boundary_strategy(covers))
        assert len(messages) == 1, covers
        assert messages[0].complete is False, covers
        assert messages[0].reason == "payload_truncated", covers
        assert messages[0].offset == 0, covers
        assert messages[0].length == len(data), covers


def test_length_covers_rejects_unknown_value():
    with pytest.raises(FramingError):
        FramingStrategy.from_dict(
            {"type": "length_prefixed", "length_covers": "not_a_value"}
        )


def test_length_prefixed_truncated_covers_payload():
    strategy, _ = _length_prefixed_stream(None, "payload")
    messages = frame_stream(_message(b"abcd", 4) + _message(b"xy", 10), strategy)
    assert messages[0].complete is True
    assert messages[0].length == 8
    assert messages[1].complete is False
    assert messages[1].reason == "payload_truncated"
    assert messages[1].offset == 8
    assert messages[1].length == 6


def test_length_prefixed_message_split_across_packet_boundary():
    strategy, _ = _length_prefixed_stream(None, "payload")
    # The message declares 4 payload bytes after a two-byte length field; the
    # TCP packet boundary falls in the middle of the message.
    packet_one = _message(b"", 4)
    packet_two = b"cdef"
    messages = frame_stream(packet_one + packet_two, strategy)
    assert len(messages) == 1
    assert messages[0].length == 8
    assert messages[0].complete is True


def test_fixed_size():
    strategy = FramingStrategy.from_dict({"type": "fixed_size", "size": 4})
    messages = frame_stream(b"aaabbbccc", strategy)
    assert [(m.offset, m.length, m.complete) for m in messages] == [
        (0, 4, True),
        (4, 4, True),
        (8, 1, False),
    ]
    assert messages[-1].reason == "short_final_message"


def test_marker_based():
    strategy = FramingStrategy.from_dict(
        {"type": "marker_based", "start_bytes": "hex:aa55", "end_bytes": "hex:0d0a"}
    )
    data = bytes.fromhex("aa550102030d0a") + bytes.fromhex("aa55090d0a")
    messages = frame_stream(data, strategy)
    assert [(m.offset, m.length) for m in messages] == [(0, 7), (7, 5)]


def test_marker_based_missing_end_marker_is_incomplete():
    strategy = FramingStrategy.from_dict(
        {"type": "marker_based", "start_bytes": "hex:aa55", "end_bytes": "hex:0d0a"}
    )
    data = bytes.fromhex("aa55010203")
    messages = frame_stream(data, strategy)
    assert len(messages) == 1
    assert messages[0].complete is False
    assert messages[0].reason == "end_marker_not_found"


def test_manual():
    strategy = FramingStrategy.from_dict(
        {"type": "manual", "messages": [{"offset": 0, "length": 4}, {"offset": 6, "length": 8}]}
    )
    data = b"aaaabbbbbbcc"
    messages = frame_stream(data, strategy)
    assert [(m.offset, m.length, m.complete) for m in messages] == [
        (0, 4, True),
        (6, 6, False),
    ]
    assert messages[-1].reason == "beyond_stream_end"


def test_empty_stream_yields_no_messages():
    strategy = FramingStrategy.from_dict({"type": "fixed_size", "size": 4})
    assert frame_stream(b"", strategy) == []


def test_unsupported_framing_type_raises():
    with pytest.raises(FramingError):
        FramingStrategy.from_dict({"type": "magic"})


def test_zero_length_prefix_does_not_loop_forever():
    # Default length_covers is payload, so a declared length of zero still
    # yields the length field itself and framing advances past it.
    strategy = FramingStrategy.from_dict(
        {"type": "length_prefixed", "length_size": 2, "byte_order": "big"}
    )
    messages = frame_stream(b"\x00\x00abc", strategy)
    assert messages[0].length == 2
    assert messages[0].complete is True
    assert messages[-1].offset >= 2

    # With entire_message a zero length cannot hold its own header, so framing
    # is diagnosed and stops instead of looping.
    strategy = FramingStrategy.from_dict(
        {"type": "length_prefixed", "length_size": 2, "byte_order": "big", "length_covers": "entire_message"}
    )
    messages = frame_stream(b"\x00\x00abc", strategy)
    assert messages[0].reason == "length_too_small"
    assert messages[0].complete is False
