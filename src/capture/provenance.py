"""Byte-level provenance for a reassembled directional stream.

Every contiguous run of stream bytes is tied to the packet it came from: the
packet index, the absolute TCP sequence number of the first byte, and the
timestamp. This is what lets the UI jump from a decoded field back to the exact
packet on the wire, and it is the core of requirement R1.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field

SEQ_MOD = 1 << 32


@dataclass(slots=True)
class Range:
    """A contiguous run of bytes in the reassembled stream.

    ``offset`` is the position in the directional stream. ``packet_index`` is
    the index of the source packet. ``seq`` is the absolute (unwrapped)
    sequence number of the first byte of the run. ``ts`` is the packet
    timestamp in epoch seconds.
    """

    offset: int
    length: int
    packet_index: int
    seq: int
    ts: float
    is_retransmission: bool = False

    @property
    def end(self) -> int:
        return self.offset + self.length

    def to_contract(self) -> dict[str, object]:
        return {
            "offset": self.offset,
            "length": self.length,
            "packet_index": self.packet_index,
            "seq": self.seq,
            "ts": self.ts,
        }


@dataclass(slots=True)
class Provenance:
    """An ordered set of ranges covering a directional stream.

    Ranges are appended in stream order by :mod:`reassembly`. Lookup by offset
    is a binary search, so a click in a hex view of a large stream stays cheap.
    """

    ranges: list[Range] = field(default_factory=list)

    def add(self, rng: Range) -> None:
        self.ranges.append(rng)

    def lookup(self, offset: int) -> Range | None:
        """Return the range containing ``offset``, or ``None`` if uncovered.

        A gap in the stream has no range, so a missing result means the offset
        falls inside a gap or past the end.
        """

        starts = [r.offset for r in self.ranges]
        pos = bisect_right(starts, offset) - 1
        if pos < 0:
            return None
        candidate = self.ranges[pos]
        if candidate.offset <= offset < candidate.end:
            return candidate
        return None

    def split(self, start: int, end: int) -> list[Range]:
        """Return the portions of the covered ranges within ``[start, end)``.

        Used to map a message or field span back to the packets it touches.
        """

        out: list[Range] = []
        for rng in self.ranges:
            lo = max(rng.offset, start)
            hi = min(rng.end, end)
            if lo >= hi:
                continue
            out.append(
                Range(
                    offset=lo,
                    length=hi - lo,
                    packet_index=rng.packet_index,
                    seq=rng.seq + (lo - rng.offset),
                    ts=rng.ts,
                )
            )
        return out
