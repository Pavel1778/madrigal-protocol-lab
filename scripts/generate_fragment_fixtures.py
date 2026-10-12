"""Generate the IP-fragmentation fixtures used by the capture tests.

These captures carry well-formed fragments, unlike the two defect fixtures that
exist only to show that a malformed fragment is reported. Each builder isolates
one behaviour of the reassembler: an ordinary split, a duplicate fragment, a
conflicting overlap for IPv4 and for IPv6, a hole, and a non-final fragment
whose length is not a multiple of eight.

Every file also carries an ordinary exchange, so a test can check that the
reassembled session and the plain one both come out of the same capture.

Run it to (re)write the files under ``tests/fixtures/defects``:

    python scripts/generate_fragment_fixtures.py
"""

from __future__ import annotations

import argparse
import socket
from pathlib import Path

import dpkt

from scripts.generate_defect_fixtures import _DLT_EN10MB, _exchange, _pcapng

_CLIENT_MAC = b"\x02\x00\x00\x00\x00\x01"
_SERVER_MAC = b"\x02\x00\x00\x00\x00\x02"

_FRAG_SRC = "10.0.0.9"
_FRAG_DST = "10.0.0.10"
_IPV6_SRC = "2001:db8::9"
_IPV6_DST = "2001:db8::a"

_ID = 0x4D2


def _tcp_bytes(seq: int, payload: bytes, *, flags: int = 0x18) -> bytes:
    """A TCP segment slice that the fragments of a datagram carry."""

    tcp = dpkt.tcp.TCP(
        sport=40001,
        dport=9001,
        seq=seq & 0xFFFFFFFF,
        ack=0,
        flags=flags,
        win=64240,
        data=payload,
    )
    tcp.off = 5
    return bytes(tcp)


def _ipv4_fragment(chunk: bytes, offset: int, more: bool) -> bytes:
    ip = dpkt.ip.IP(
        src=socket.inet_aton(_FRAG_SRC),
        dst=socket.inet_aton(_FRAG_DST),
        p=dpkt.ip.IP_PROTO_TCP,
        data=chunk,
    )
    ip.len = len(bytes(ip))
    ip.id = _ID
    ip.mf = 1 if more else 0
    ip.offset = offset // 8
    eth = dpkt.ethernet.Ethernet(
        src=_CLIENT_MAC,
        dst=_SERVER_MAC,
        type=dpkt.ethernet.ETH_TYPE_IP,
        data=ip,
    )
    return bytes(eth)


def _ipv6_fragment(chunk: bytes, offset: int, more: bool) -> bytes:
    frag = dpkt.ip6.IP6FragmentHeader()
    frag.nxt = dpkt.ip.IP_PROTO_TCP
    frag.frag_off = offset // 8
    frag.m_flag = 1 if more else 0
    frag.id = _ID
    frag.data = chunk
    ip6 = dpkt.ip6.IP6(
        src=socket.inet_pton(socket.AF_INET6, _IPV6_SRC),
        dst=socket.inet_pton(socket.AF_INET6, _IPV6_DST),
    )
    ip6.nxt = 44
    ip6.data = bytes(frag)
    ip6.plen = len(bytes(frag))
    eth = dpkt.ethernet.Ethernet(
        src=_CLIENT_MAC,
        dst=_SERVER_MAC,
        type=dpkt.ethernet.ETH_TYPE_IP6,
        data=ip6,
    )
    return bytes(eth)


def _split(segment: bytes, sizes: list[int]) -> list[tuple[bytes, int, bool]]:
    """Cut ``segment`` into fragments of the given sizes (multiple of eight)."""

    parts: list[tuple[bytes, int, bool]] = []
    offset = 0
    for index, size in enumerate(sizes):
        chunk = segment[offset : offset + size]
        last = index == len(sizes) - 1
        parts.append((chunk, offset, not last))
        offset += size
    return parts


def _ipv4_datagram(segment: bytes, sizes: list[int]) -> list[bytes]:
    return [_ipv4_fragment(c, o, m) for c, o, m in _split(segment, sizes)]


def _ipv6_datagram(segment: bytes, sizes: list[int]) -> list[bytes]:
    return [_ipv6_fragment(c, o, m) for c, o, m in _split(segment, sizes)]


def _payload(tag: bytes, size: int = 24) -> bytes:
    """A deterministic payload of exactly ``size`` bytes."""

    repeats = (size + len(tag) - 1) // len(tag)
    return (tag * repeats)[:size]


def build_fragment_reassembled() -> bytes:
    """An IPv4 datagram split into three fragments, delivered out of order."""

    segment = _tcp_bytes(1000, _payload(b"ALFA"))
    frames = _ipv4_datagram(segment, [16, 16, len(segment) - 32])
    packets = [(0, frames[1]), (0, frames[2]), (0, frames[0])]
    packets += [(0, frame) for frame in _exchange()]
    return _pcapng([_DLT_EN10MB], packets)


def build_fragment_ipv6_reassembled() -> bytes:
    """An IPv6 datagram split into two fragments."""

    segment = _tcp_bytes(2000, _payload(b"BRAV"))
    frames = _ipv6_datagram(segment, [16, len(segment) - 16])
    packets = [(0, frame) for frame in frames] + [(0, f) for f in _exchange()]
    return _pcapng([_DLT_EN10MB], packets)


def build_fragment_duplicate() -> bytes:
    """A datagram whose middle fragment is sent twice, byte for byte."""

    segment = _tcp_bytes(3000, _payload(b"DELT"))
    frames = _ipv4_datagram(segment, [16, 16, len(segment) - 32])
    packets = [
        (0, frames[0]),
        (0, frames[1]),
        (0, frames[1]),
        (0, frames[2]),
    ]
    packets += [(0, frame) for frame in _exchange()]
    return _pcapng([_DLT_EN10MB], packets)


def build_fragment_overlap_ipv4() -> bytes:
    """Two IPv4 fragments claim the same bytes with different content."""

    segment = _tcp_bytes(4000, _payload(b"ECHO"))
    frames = _ipv4_datagram(segment, [16, 16, len(segment) - 32])
    # A second copy of the head fragment, longer than the real one, so it covers
    # bytes 16..24 with different content.
    overlapping = _ipv4_fragment(b"\xff" * 24, 0, True)
    packets = [
        (0, frames[0]),
        (0, overlapping),
        (0, frames[1]),
        (0, frames[2]),
    ]
    packets += [(0, frame) for frame in _exchange()]
    return _pcapng([_DLT_EN10MB], packets)


def build_fragment_overlap_ipv6() -> bytes:
    """Two IPv6 fragments overlap, which RFC 5722 says to discard."""

    segment = _tcp_bytes(5000, _payload(b"FOXT"))
    frames = _ipv6_datagram(segment, [16, 16, len(segment) - 32])
    # A second head fragment covering the first 16 bytes with different bytes.
    overlapping = _ipv6_fragment(b"\x00" * 16, 0, True)
    packets = [
        (0, frames[0]),
        (0, overlapping),
        (0, frames[1]),
        (0, frames[2]),
    ]
    packets += [(0, frame) for frame in _exchange()]
    return _pcapng([_DLT_EN10MB], packets)


def build_fragment_incomplete_missing() -> bytes:
    """A datagram whose middle fragment was never captured."""

    segment = _tcp_bytes(6000, _payload(b"GOLF"))
    frames = _ipv4_datagram(segment, [16, 16, len(segment) - 32])
    packets = [(0, frames[0]), (0, frames[2])]
    packets += [(0, frame) for frame in _exchange()]
    return _pcapng([_DLT_EN10MB], packets)


def build_fragment_misaligned() -> bytes:
    """A non-final IPv4 fragment whose length is not a multiple of eight."""

    segment = _tcp_bytes(7000, _payload(b"HOTE"))
    frames = _ipv4_datagram(segment, [16, 16, len(segment) - 32])
    # Rebuild the first fragment with a 12-byte payload: 12 is not a multiple
    # of eight, so the datagram is malformed and must not be reassembled.
    bad_first = _ipv4_fragment(segment[:12], 0, True)
    packets = [(0, bad_first), (0, frames[1]), (0, frames[2])]
    packets += [(0, frame) for frame in _exchange()]
    return _pcapng([_DLT_EN10MB], packets)


BUILDERS = {
    "fragment_reassembled.pcapng": build_fragment_reassembled,
    "fragment_ipv6_reassembled.pcapng": build_fragment_ipv6_reassembled,
    "fragment_duplicate.pcapng": build_fragment_duplicate,
    "fragment_overlap_ipv4.pcapng": build_fragment_overlap_ipv4,
    "fragment_overlap_ipv6.pcapng": build_fragment_overlap_ipv6,
    "fragment_incomplete_missing.pcapng": build_fragment_incomplete_missing,
    "fragment_misaligned.pcapng": build_fragment_misaligned,
}


def generate(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, builder in BUILDERS.items():
        path = out_dir / name
        path.write_bytes(builder())
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "defects",
    )
    args = parser.parse_args(argv)
    for path in generate(args.out_dir):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
