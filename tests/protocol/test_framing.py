import struct

import pytest

from src.protocol.framing import FramingError, FramingStrategy, frame_stream


def _length_prefixed_stream(field_length, includes_payload):
    spec = {
        "type": "length_prefixed",
        "length_offset": 2,
        "length_size": 2,
        "byte_order": "big",
        "length_includes_payload": includes_payload,
    }
    return FramingStrategy.from_dict(spec), field_length


def _message(payload: bytes, declared: int) -> bytes:
    return bytes([0x10, 0x00]) + struct.pack(">H", declared) + payload


def test_length_prefixed_includes_payload():
    strategy, _ = _length_prefixed_stream(None, True)
    first = _message(b"abcd", 8)
    second = _message(b"ef", 6)
    messages = frame_stream(first + second, strategy)
    assert [(m.offset, m.length, m.complete) for m in messages] == [
        (0, 8, True),
        (8, 6, True),
    ]


def test_length_prefixed_payload_only_length():
    strategy, _ = _length_prefixed_stream(None, False)
    first = _message(b"abcd", 4)
    messages = frame_stream(first + _message(b"ef", 2), strategy)
    assert [(m.offset, m.length) for m in messages] == [(0, 8), (8, 6)]


def test_length_prefixed_truncated_payload_is_incomplete():
    strategy, _ = _length_prefixed_stream(None, True)
    data = _message(b"abcd", 8) + _message(b"xy", 10)
    messages = frame_stream(data, strategy)
    assert messages[0].complete is True
    assert messages[1].complete is False
    assert messages[1].reason == "payload_truncated"
    assert messages[1].offset == 8


def test_length_prefixed_message_split_across_packet_boundary():
    strategy, _ = _length_prefixed_stream(None, True)
    packet_one = _message(b"ab", 12)
    packet_two = b"cdefgh"
    messages = frame_stream(packet_one + packet_two, strategy)
    assert len(messages) == 1
    assert messages[0].length == 12
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
    strategy = FramingStrategy.from_dict(
        {"type": "length_prefixed", "length_size": 2, "byte_order": "big"}
    )
    messages = frame_stream(b"\x00\x00abc", strategy)
    assert messages[0].reason == "zero_length"
    assert messages[0].complete is False
