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
    is a binary search over an index built once and reused, so a click in a hex
    view of a large stream stays cheap.
    """

    ranges: list[Range] = field(default_factory=list)
    _primary: list[Range] | None = field(default=None, repr=False, compare=False)
    _starts: list[int] | None = field(default=None, repr=False, compare=False)

    def add(self, rng: Range) -> None:
        self.ranges.append(rng)
        self._primary = None
        self._starts = None

    def _index(self) -> tuple[list[Range], list[int]]:
        """Return the primary ranges and their start offsets, built once."""

        if self._primary is None or self._starts is None:
            primary = [r for r in self.ranges if not r.is_retransmission]
            primary.sort(key=lambda r: r.offset)
            self._primary = primary
            self._starts = [r.offset for r in primary]
        return self._primary, self._starts

    def lookup(self, offset: int) -> Range | None:
        """Return the range containing ``offset``, or ``None`` if uncovered.

        A gap in the stream has no range, so a missing result means the offset
        falls inside a gap or past the end.

        Retransmission ranges annotate bytes that a primary range already
        covers, and they may start at the same offset as that range while being
        shorter. Searching only the primary ranges keeps the answer the packet
        that actually produced the byte and avoids a short annotation shadowing
        the range that contains ``offset``.
        """

        primary, starts = self._index()
        pos = bisect_right(starts, offset) - 1
        if pos < 0:
            return None
        candidate = primary[pos]
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
