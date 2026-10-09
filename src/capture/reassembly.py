"""Reassembly of one direction of a TCP session into a byte stream.

The stream is rebuilt from the payloads of a single direction, ordered by
sequence number rather than by capture time, so out-of-order delivery and
retransmissions are handled without relying on the order packets appear in the
file.

Rules applied here, all of them deliberately conservative:

- Identical retransmissions do not add bytes. The bytes are kept once and the
  retransmitting packet is recorded as an additional provenance range, so no
  observation is lost and none is duplicated.
- Out-of-order segments are placed by their sequence number; the byte order in
  the stream is the byte order of the conversation, not of the file.
- A hole between two observed segments becomes a ``gap`` diagnostic. It is not
  filled with zero bytes or any other guess. The stream holds only bytes that
  were actually observed, so the physical offset of a later segment does not
  include the missing bytes; the gap diagnostic records where the hole sits and
  how long it was.
- When two segments claim the same sequence range with different bytes, the
  first observed version stays in the stream and the conflict is recorded as an
  ``ambiguity`` diagnostic carrying both versions. The stream is never silently
  overwritten.
- A missing SYN leaves the roles unknown; the sequence base is then taken from
  the first observed payload instead of an initial sequence number.
- The 32-bit sequence wrap is handled with modular arithmetic against a
  per-direction reference, so a stream that crosses 2**32 stays ordered.

Checksum verification is off by default because checksum offloading on the
sending host leaves wrong checksums in many captured files. When it is turned
on, a bad checksum is reported as a ``checksum_offload`` diagnostic.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field

from src.capture.parser import Diagnostic, Packet
from src.capture.provenance import Provenance, Range
from src.capture.session import Direction, Session

SEQ_MASK = 0xFFFFFFFF


@dataclass(slots=True)
class DirectionalStream:
    """The reassembled bytes of one direction plus their provenance.

    ``bytes_`` holds only observed bytes. ``gap_spans`` lists the holes that
    were not observed, so a consumer can still tell where the missing data
    would have been: each hole is reported as a diagnostic with a physical
    ``offset`` and its ``length``, measured in the same sequence space as the
    surrounding provenance ranges.
    """

    direction: Direction
    bytes_: bytearray = field(default_factory=bytearray)
    provenance: Provenance = field(default_factory=Provenance)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    packet_indices: list[int] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.bytes_)

    def gaps(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.type == "gap"]

    def ambiguities(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.type == "ambiguity"]


@dataclass(slots=True)
class _Run:
    """One contiguous, observed run of stream bytes before final layout."""

    start: int
    data: bytes
    packet_index: int
    seq: int
    ts: float

    @property
    def end(self) -> int:
        return self.start + len(self.data)


def _direction_isn(session: Session, direction: Direction) -> int | None:
    if direction is Direction.A_TO_B:
        return session.isn_a
    return session.isn_b


def _abs_seq(raw: int, reference: int) -> int:
    return reference + ((raw - reference) & SEQ_MASK)


def _suffix_start(runs: list[_Run], start: int) -> int:
    """First index of the suffix of ``runs`` whose end is past ``start``."""

    k = len(runs)
    while k > 0 and runs[k - 1].end > start:
        k -= 1
    return k


def _record_overlap(
    runs: list[_Run],
    packet: Packet,
    abs_start: int,
    incoming: bytes,
    run: _Run,
    overlap_lo: int,
    overlap_hi: int,
    extra_sources: list[tuple[int, int, int, float]],
    diagnostics: list[Diagnostic],
) -> None:
    """Compare an overlapping span and keep the existing bytes."""

    existing = run.data[overlap_lo - run.start : overlap_hi - run.start]
    if incoming == existing:
        extra_sources.append(
            (overlap_lo, overlap_hi - overlap_lo, packet.index, packet.timestamp)
        )
        return
    diagnostics.append(
        Diagnostic(
            type="ambiguity",
            packet_index=packet.index,
            offset=overlap_lo,
            length=overlap_hi - overlap_lo,
            detail=(
                f"conflicting overlap at seq {overlap_lo}: "
                f"kept {existing.hex()}, rejected {incoming.hex()}"
            ),
        )
    )


def _insert_payload(
    runs: list[_Run],
    packet: Packet,
    abs_start: int,
    extra_sources: list[tuple[int, int, int, float]],
    diagnostics: list[Diagnostic],
) -> None:
    """Merge one packet's payload into the run list.

    New bytes are appended as runs. Overlapping bytes are compared against what
    is already there; the existing bytes stay and the overlap is recorded either
    as an extra source (identical) or as an ambiguity (conflicting).
    """

    data = packet.payload
    abs_end = abs_start + len(data)
    if not data:
        return

    pieces: list[tuple[int, bytes]] = []
    cursor = abs_start
    k = _suffix_start(runs, abs_start)
    while k < len(runs) and runs[k].start < abs_end:
        run = runs[k]
        if run.start > cursor:
            up_to = min(run.start, abs_end)
            pieces.append((cursor, data[cursor - abs_start : up_to - abs_start]))
            cursor = up_to
        overlap_lo = max(cursor, run.start)
        overlap_hi = min(abs_end, run.end)
        if overlap_lo < overlap_hi:
            _record_overlap(
                runs,
                packet,
                abs_start,
                data[overlap_lo - abs_start : overlap_hi - abs_start],
                run,
                overlap_lo,
                overlap_hi,
                extra_sources,
                diagnostics,
            )
            cursor = overlap_hi
        k += 1

    if cursor < abs_end:
        pieces.append((cursor, data[cursor - abs_start :]))

    for piece_start, piece in pieces:
        delta = piece_start - abs_start
        runs.append(
            _Run(
                start=piece_start,
                data=piece,
                packet_index=packet.index,
                seq=(packet.seq + delta) & SEQ_MASK,
                ts=packet.timestamp,
            )
        )


def _finalize(runs: list[_Run]) -> tuple[bytearray, list[int]]:
    """Concatenate runs and return the bytes and each run's physical offset."""

    buf = bytearray()
    offsets: list[int] = []
    for run in runs:
        offsets.append(len(buf))
        buf.extend(run.data)
    return buf, offsets


def _physical_offset(
    runs: list[_Run], offsets: list[int], abs_offset: int
) -> int | None:
    """Map an absolute sequence position to a physical stream offset."""

    starts = [run.start for run in runs]
    pos = bisect_right(starts, abs_offset) - 1
    if pos < 0:
        return None
    run = runs[pos]
    if run.start <= abs_offset < run.end:
        return offsets[pos] + (abs_offset - run.start)
    return None


def reassemble(
    session: Session,
    direction: Direction,
    packets: list[Packet] | tuple[Packet, ...],
    *,
    ignore_checksums: bool = True,
) -> DirectionalStream:
    """Reassemble one direction of ``session`` from ``packets``.

    ``packets`` may contain the whole session; packets that do not belong to
    ``direction`` are ignored. The result carries every observed byte once and
    a provenance range for every observed byte, plus diagnostics for gaps,
    ambiguities, truncation, and checksum problems.
    """

    transport = [p for p in packets if session.direction_of(p) is direction]
    payloads = [p for p in transport if p.payload_len > 0]
    diagnostics: list[Diagnostic] = []

    if not ignore_checksums:
        for p in transport:
            if p.checksum_valid is False:
                diagnostics.append(
                    Diagnostic(
                        type="checksum_offload",
                        packet_index=p.index,
                        detail="TCP checksum mismatch",
                    )
                )

    stream = DirectionalStream(direction=direction)
    stream.packet_indices = sorted({p.index for p in transport})
    if not payloads:
        stream.diagnostics = diagnostics
        return stream

    isn = _direction_isn(session, direction)
    reference = isn if isn is not None else payloads[0].seq
    ordered = sorted(payloads, key=lambda p: (_abs_seq(p.seq, reference), p.index))

    runs: list[_Run] = []
    extra_sources: list[tuple[int, int, int, float]] = []
    for packet in ordered:
        _insert_payload(
            runs,
            packet,
            _abs_seq(packet.seq, reference),
            extra_sources,
            diagnostics,
        )

    buf, offsets = _finalize(runs)

    provenance = Provenance()
    for run, physical in zip(runs, offsets, strict=True):
        provenance.add(
            Range(
                offset=physical,
                length=len(run.data),
                packet_index=run.packet_index,
                seq=run.seq,
                ts=run.ts,
            )
        )
    for abs_offset, length, packet_index, ts in extra_sources:
        source_offset = _physical_offset(runs, offsets, abs_offset)
        if source_offset is None:
            continue
        provenance.add(
            Range(
                offset=source_offset,
                length=length,
                packet_index=packet_index,
                seq=abs_offset & SEQ_MASK,
                ts=ts,
            )
        )
    provenance.ranges.sort(key=lambda r: (r.offset, r.packet_index))

    gap_diagnostics = _gap_diagnostics(runs, offsets, isn, reference)
    stream.bytes_ = buf
    stream.provenance = provenance
    stream.diagnostics = gap_diagnostics + _physical_ambiguities(
        diagnostics, runs, offsets
    )
    return stream


def _physical_ambiguities(
    diagnostics: list[Diagnostic],
    runs: list[_Run],
    offsets: list[int],
) -> list[Diagnostic]:
    """Rewrite ambiguity diagnostics so ``offset`` is a physical stream offset."""

    out: list[Diagnostic] = []
    for diag in diagnostics:
        if diag.type != "ambiguity":
            out.append(diag)
            continue
        physical = (
            _physical_offset(runs, offsets, diag.offset)
            if diag.offset is not None
            else None
        )
        out.append(
            Diagnostic(
                type=diag.type,
                packet_index=diag.packet_index,
                offset=physical,
                length=diag.length,
                detail=diag.detail,
            )
        )
    return out


def _gap_diagnostics(
    runs: list[_Run],
    offsets: list[int],
    isn: int | None,
    reference: int,
) -> list[Diagnostic]:
    """Report every hole between observed runs, including the leading one."""

    out: list[Diagnostic] = []
    if not runs:
        return out

    if isn is not None:
        expected = _abs_seq(isn, reference) + 1
        missing = runs[0].start - expected
    elif offsets and offsets[0] > 0:
        missing = offsets[0]
    else:
        missing = 0
    if missing > 0:
        out.append(
            Diagnostic(
                type="gap",
                offset=0,
                length=missing,
                detail="unobserved bytes before the first segment",
            )
        )

    for index in range(1, len(runs)):
        prev, nxt = runs[index - 1], runs[index]
        missing = nxt.start - prev.end
        if missing > 0:
            out.append(
                Diagnostic(
                    type="gap",
                    offset=offsets[index],
                    length=missing,
                    detail=(
                        f"missing {missing} bytes between seq {prev.end} "
                        f"and {nxt.start}"
                    ),
                )
            )
    return out
