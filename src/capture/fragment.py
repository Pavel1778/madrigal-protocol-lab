"""Reassembly of IPv4 and IPv6 fragments, before the TCP layer.

A fragmented datagram hides its transport header from the parser: only the first
fragment carries the TCP header, and no single fragment is a TCP segment. The
parser therefore reports fragments and moves on. This module sits between the
parser and session building and turns a set of fragments back into one datagram,
so a TCP session that the network split becomes visible.

The two specifications differ on one point, and the difference is kept:

- IPv4 (RFC 791). Fragments are grouped by ``(src, dst, id, protocol)``. The
  fragment offset is in units of eight bytes. A non-final fragment whose payload
  is not a multiple of eight bytes is malformed and is not reassembled. When two
  fragments cover the same bytes with different content the first to arrive is
  kept and the conflict is reported; the specification does not say which
  version wins, so neither is silently dropped.
- IPv6 (RFC 8200, RFC 5722). Fragments are grouped by ``(src, dst, id)``. An
  overlap is not tolerated at all: the datagram is discarded and the conflict is
  reported, which is what RFC 5722 requires to avoid ambiguity.

A datagram is reassembled only when every byte from zero to the declared end is
covered and the final fragment (the one with ``more`` clear) was seen. Anything
less stays a diagnostic and no bytes are guessed: a hole is a hole, not zeroes,
and a missing tail is incomplete, not truncated.

Timers are not applied. The capture is read offline, so a datagram that never
completes in the file is reported as incomplete rather than timed out.
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass, field

FRAGMENT_REASSEMBLED = "ip_fragment_reassembled"
FRAGMENT_INCOMPLETE = "ip_fragment_incomplete"
FRAGMENT_OVERLAP = "ip_fragment_overlap"

_IPPROTO_HOPOPTS = 0
_IPPROTO_ROUTING = 43
_IPPROTO_FRAGMENT = 44
_IPPROTO_AH = 51
_IPPROTO_DSTOPTS = 60

_IP6_EXTENSION = {
    _IPPROTO_HOPOPTS,
    _IPPROTO_ROUTING,
    _IPPROTO_FRAGMENT,
    _IPPROTO_AH,
    _IPPROTO_DSTOPTS,
}


@dataclass(slots=True)
class FragmentSpec:
    """One IP fragment lifted out of a frame.

    ``offset`` is already in bytes, so an IPv4 offset has been scaled by eight.
    ``payload`` holds only the fragment's payload bytes, sliced from the raw
    frame rather than from the library's decoded view, because that view is
    ambiguous for a fragment whose payload happens to be header-shaped.
    """

    version: int
    src: str
    dst: str
    ident: int
    protocol: int
    offset: int
    more: bool
    payload: bytes
    packet_index: int
    timestamp: float

    @property
    def key(self) -> tuple[int, str, str, int, int]:
        """The datagram this fragment belongs to."""

        return (self.version, self.src, self.dst, self.ident, self.protocol)

    @property
    def end(self) -> int:
        return self.offset + len(self.payload)


@dataclass(slots=True)
class ReassembledDatagram:
    """A datagram recovered from its fragments.

    ``payload`` is the whole IP payload and therefore begins with the transport
    header. ``packet_indices`` lists the frames it was built from, and
    ``timestamp`` is the earliest of them, when the datagram started on the wire.
    """

    version: int
    src: str
    dst: str
    protocol: int
    payload: bytes
    packet_indices: list[int]
    timestamp: float
    ident: int = 0


@dataclass(slots=True)
class FragmentResult:
    """What a pass produced: whole datagrams and the problems it found."""

    datagrams: list[ReassembledDatagram] = field(default_factory=list)
    diagnostics: list[tuple[str, dict[str, object]]] = field(default_factory=list)


def ipv6_fragment_span(buf: bytes) -> tuple[int, int, int, int, bool] | None:
    """Locate the IPv6 fragment header in a raw datagram.

    Returns ``(header_offset, next_header, ident, offset_bytes, more)`` or
    ``None`` when the datagram is not fragmented. The extension chain is walked
    by hand because a fragment header can follow other extension headers, and
    the decoded view of a fragmented payload is not reliable enough to measure
    the transport offset from.
    """

    if len(buf) < 40:
        return None
    next_header = buf[6]
    cursor = 40
    while next_header in _IP6_EXTENSION:
        if cursor + 2 > len(buf):
            return None
        if next_header == _IPPROTO_FRAGMENT:
            if cursor + 8 > len(buf):
                return None
            nxt = buf[cursor]
            raw_off = struct.unpack_from("!H", buf, cursor + 2)[0]
            ident = struct.unpack_from("!I", buf, cursor + 4)[0]
            return cursor, nxt, ident, (raw_off >> 3) * 8, bool(raw_off & 0x1)
        if next_header == _IPPROTO_AH:
            step = (buf[cursor + 1] + 2) * 4
        else:
            step = (buf[cursor + 1] + 1) * 8
        following = buf[cursor]
        cursor += step
        next_header = following
    return None


def extract_fragment(
    version: int, ip_bytes: bytes, packet_index: int, timestamp: float
) -> FragmentSpec | None:
    """Return a fragment description, or ``None`` when the frame is whole."""

    if version == 6:
        return _extract6(ip_bytes, packet_index, timestamp)
    return _extract4(ip_bytes, packet_index, timestamp)


def _extract6(
    ip_bytes: bytes, packet_index: int, timestamp: float
) -> FragmentSpec | None:
    if len(ip_bytes) < 40:
        return None
    span = ipv6_fragment_span(ip_bytes)
    if span is None:
        return None
    header_offset, next_header, ident, offset, more = span
    plen = struct.unpack_from("!H", ip_bytes, 4)[0]
    declared_end = min(40 + plen, len(ip_bytes))
    payload = ip_bytes[header_offset + 8 : declared_end]
    return FragmentSpec(
        version=6,
        src=socket.inet_ntop(socket.AF_INET6, ip_bytes[8:24]),
        dst=socket.inet_ntop(socket.AF_INET6, ip_bytes[24:40]),
        ident=ident,
        protocol=next_header,
        offset=offset,
        more=more,
        payload=payload,
        packet_index=packet_index,
        timestamp=timestamp,
    )


def _extract4(
    ip_bytes: bytes, packet_index: int, timestamp: float
) -> FragmentSpec | None:
    if len(ip_bytes) < 20:
        return None
    ihl = (ip_bytes[0] & 0x0F) * 4
    if ihl < 20 or len(ip_bytes) < ihl:
        return None
    flags_frag = struct.unpack_from("!H", ip_bytes, 6)[0]
    more = bool(flags_frag & 0x2000)
    offset = (flags_frag & 0x1FFF) * 8
    if not more and offset == 0:
        return None
    total_length = struct.unpack_from("!H", ip_bytes, 2)[0]
    declared_end = min(total_length, len(ip_bytes))
    return FragmentSpec(
        version=4,
        src=socket.inet_ntop(socket.AF_INET, ip_bytes[12:16]),
        dst=socket.inet_ntop(socket.AF_INET, ip_bytes[16:20]),
        ident=struct.unpack_from("!H", ip_bytes, 4)[0],
        protocol=ip_bytes[9],
        offset=offset,
        more=more,
        payload=ip_bytes[ihl:declared_end],
        packet_index=packet_index,
        timestamp=timestamp,
    )


def build_ip_datagram(datagram: ReassembledDatagram) -> bytes:
    """Wrap a reassembled payload in a synthetic IP header.

    The payload already starts at the transport header, so a minimal header is
    enough for the transport parser, which reads the version, the addresses, the
    protocol, and a length matching the payload. Fields the parser does not read
    (the IPv4 checksum, the IPv6 flow label) are set to zero.
    """

    payload = datagram.payload
    if datagram.version == 6:
        header = bytearray(40)
        header[0] = 0x60
        struct.pack_into("!H", header, 4, len(payload))
        header[6] = datagram.protocol
        header[7] = 64
        header[8:24] = socket.inet_pton(socket.AF_INET6, datagram.src)
        header[24:40] = socket.inet_pton(socket.AF_INET6, datagram.dst)
        return bytes(header) + payload

    header = bytearray(20)
    header[0] = 0x45
    struct.pack_into("!H", header, 2, 20 + len(payload))
    header[8] = 64
    header[9] = datagram.protocol
    header[12:16] = socket.inet_aton(datagram.src)
    header[16:20] = socket.inet_aton(datagram.dst)
    struct.pack_into("!H", header, 10, _header_checksum(header))
    return bytes(header) + payload


def _header_checksum(header: bytes) -> int:
    """The one's-complement checksum of an IPv4 header."""

    total = 0
    for i in range(0, len(header), 2):
        total += (header[i] << 8) | header[i + 1]
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


class FragmentReassembler:
    """Collects fragments and yields whole datagrams as they close.

    One instance handles a whole capture, so fragments of a datagram may be
    separated by unrelated traffic. A datagram is produced as soon as its bytes
    are complete; ``finish`` reports and drops the rest.
    """

    def __init__(self) -> None:
        self._groups: dict[tuple[int, str, str, int, int], list[FragmentSpec]] = {}
        self.diagnostics: list[tuple[str, dict[str, object]]] = []

    def add(self, spec: FragmentSpec) -> ReassembledDatagram | None:
        """Add a fragment; return a datagram if this fragment completes one."""

        self._groups.setdefault(spec.key, []).append(spec)
        return self._attempt(spec.key)

    def _attempt(
        self, key: tuple[int, str, str, int, int]
    ) -> ReassembledDatagram | None:
        group = self._groups[key]
        version = key[0]
        terminal = [f for f in group if not f.more]
        if not terminal:
            return None
        if version == 4 and any(f.more and len(f.payload) % 8 != 0 for f in group):
            return None

        end = max(f.end for f in terminal)
        buffer, conflicts = _place(group, end)
        if conflicts and version == 6:
            del self._groups[key]
            self.diagnostics.append(
                (
                    FRAGMENT_OVERLAP,
                    _overlap_detail(key, group, conflicts, discarded=True),
                )
            )
            return None
        if buffer is None:
            return None
        if conflicts:
            self.diagnostics.append(
                (
                    FRAGMENT_OVERLAP,
                    _overlap_detail(key, group, conflicts, discarded=False),
                )
            )
        del self._groups[key]
        return ReassembledDatagram(
            version=version,
            src=key[1],
            dst=key[2],
            protocol=key[4],
            payload=bytes(buffer),
            packet_indices=sorted(f.packet_index for f in group),
            timestamp=min(f.timestamp for f in group),
            ident=key[3],
        )

    def finish(self) -> list[tuple[str, dict[str, object]]]:
        """Report and drop every datagram that never completed."""

        for key, group in self._groups.items():
            version = key[0]
            terminal = [f for f in group if not f.more]
            end = max((f.end for f in terminal), default=max(f.end for f in group))
            hole = _first_hole(group, end)
            detail = "no final fragment was observed"
            offset: int | None = None
            length: int | None = None
            if version == 4 and any(f.more and len(f.payload) % 8 != 0 for f in group):
                detail = "non-final IPv4 fragment length is not a multiple of 8"
            elif hole is not None:
                offset, length = hole
                detail = f"missing {length} byte(s) at offset {offset}"
            entry: dict[str, object] = {
                "packet_index": min(f.packet_index for f in group),
                "detail": detail,
            }
            if offset is not None:
                entry["offset"] = offset
                entry["length"] = length
            self.diagnostics.append((FRAGMENT_INCOMPLETE, entry))
        self._groups.clear()
        return self.diagnostics


def _place(
    group: list[FragmentSpec], end: int
) -> tuple[bytearray | None, list[tuple[int, int]]]:
    """Place every fragment, keeping first-arrival bytes.

    Returns the buffer (``None`` when a hole remains) and the merged spans where
    two fragments disagreed.
    """

    buffer = bytearray(end)
    filled = bytearray(end)
    conflicts: list[tuple[int, int]] = []
    for spec in group:
        chunk = spec.payload[: max(end - spec.offset, 0)]
        for i, byte in enumerate(chunk):
            position = spec.offset + i
            if filled[position]:
                if buffer[position] != byte:
                    conflicts.append((position, position + 1))
                continue
            buffer[position] = byte
            filled[position] = 1
    if any(filled[i] == 0 for i in range(end)):
        return None, _merge(conflicts)
    return buffer, _merge(conflicts)


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def _overlap_detail(
    key: tuple[int, str, str, int, int],
    group: list[FragmentSpec],
    conflicts: list[tuple[int, int]],
    *,
    discarded: bool,
) -> dict[str, object]:
    span = conflicts[0]
    length = sum(hi - lo for lo, hi in conflicts)
    known = "RFC 5722: datagram discarded" if discarded else "kept first arrival"
    return {
        "packet_index": min(f.packet_index for f in group),
        "offset": span[0],
        "length": length,
        "detail": (
            f"conflicting IP fragment overlap ({known}), "
            f"version {key[0]} id {key[3]}"
        ),
    }


def _first_hole(group: list[FragmentSpec], end: int) -> tuple[int, int] | None:
    """First uncovered span in ``[0, end)``, or ``None`` when fully covered."""

    spans = _merge(sorted((f.offset, min(f.end, end)) for f in group))
    cursor = 0
    for lo, hi in spans:
        if lo > cursor:
            return cursor, lo - cursor
        cursor = max(cursor, hi)
    if cursor < end:
        return cursor, end - cursor
    return None
