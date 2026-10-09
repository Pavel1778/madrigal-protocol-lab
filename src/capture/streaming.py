"""Streaming normalization for large captures.

The regular pipeline reads every packet into memory, groups the whole capture
into sessions, and reassembles each one. That is fast and simple, but peak
memory grows with the capture. This module processes a capture in blocks and
writes each session to the output as soon as it can no longer receive packets,
so closed sessions do not stay resident.

The result is the same normalized capture as the regular pipeline. The sessions
are written on their own lines of a single JSON document, which keeps the file
valid JSON while allowing it to be produced incrementally.

When a session can be written
------------------------------
A session is written when any of these holds:

- it is superseded on its address pair, because a new handshake or payload
  after a close started a new connection instance;
- it was closed (FIN or RST) and ``close_linger`` further packets have been
  seen since, so trailing acknowledgements are still captured;
- its buffered packet count passes ``max_session_packets``;
- the capture ends.

The linger is what makes the result identical to the regular pipeline: a close
is not treated as the end of the data immediately, so the reciprocal FIN and
any final acks are still part of the session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from src.capture.export import CONTRACT_VERSION, session_to_contract, sha256_file
from src.capture.parser import Packet, read_capture
from src.capture.reassembly import DirectionalStream, reassemble
from src.capture.session import Direction, Session, SessionTracker


@dataclass
class StreamingStats:
    """Counters reported at the end of a streaming run."""

    packets: int = 0
    sessions: int = 0
    flushes: int = 0


class _Writer:
    """Writes sessions to a single JSON document as they are finalized."""

    def __init__(self, out_path: Path, capture_id: str, source_file: str) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = out_path.open("w", encoding="utf-8")
        self._handle.write("{")
        self._handle.write('"contract_version":')
        self._handle.write(str(CONTRACT_VERSION))
        self._handle.write(',"capture_id":')
        self._handle.write(json.dumps(capture_id))
        self._handle.write(',"source_file":')
        self._handle.write(json.dumps(source_file))
        self._handle.write(',"sessions":[\n')
        self._first = True

    def write(
        self, session: Session, streams: dict[Direction, DirectionalStream]
    ) -> None:
        if not self._first:
            self._handle.write(",\n")
        self._first = False
        payload = session_to_contract(session, streams)
        json.dump(payload, self._handle, ensure_ascii=True, separators=(",", ":"))

    def close(self) -> None:
        self._handle.write("\n]}\n")
        self._handle.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def process_streaming(
    path: Path,
    out_path: Path,
    chunk_size: int = 10000,
    *,
    close_linger: int = 16,
    max_session_packets: int = 200_000,
    source_file: str | None = None,
) -> StreamingStats:
    """Normalize ``path`` into ``out_path`` without holding every session at once.

    ``chunk_size`` bounds how many packets are read from the file per block.
    ``close_linger`` is how many packets may follow a close before the session
    is written; ``max_session_packets`` is a safety valve for a session that
    stays open and grows without bound. ``source_file`` is the value recorded
    in the output; it defaults to the input path and can be set to a relative
    path so a project export stays portable.
    """

    stats = StreamingStats()
    tracker = SessionTracker()
    buffers: dict[str, list[Packet]] = {}
    closed_at: dict[str, int] = {}
    flushed: set[str] = set()
    global_index = 0

    capture_id = sha256_file(path)
    recorded_source = source_file if source_file is not None else str(path)
    with _Writer(out_path, capture_id, recorded_source) as writer:

        def flush(session: Session) -> None:
            if session.session_id in flushed:
                return
            flushed.add(session.session_id)
            packets = buffers.pop(session.session_id, [])
            streams = {
                Direction.A_TO_B: reassemble(session, Direction.A_TO_B, packets),
                Direction.B_TO_A: reassemble(session, Direction.B_TO_A, packets),
            }
            session.packet_indices = [p.index for p in packets]
            writer.write(session, streams)
            stats.flushes += 1

        block: list[Packet] = []
        for packet in read_capture(path):
            block.append(packet)
            if len(block) < chunk_size:
                continue
            _consume_block(
                block,
                tracker,
                buffers,
                closed_at,
                flush,
                stats,
                global_index,
                close_linger,
                max_session_packets,
            )
            global_index += len(block)
            block = []
        if block:
            _consume_block(
                block,
                tracker,
                buffers,
                closed_at,
                flush,
                stats,
                global_index,
                close_linger,
                max_session_packets,
            )
            global_index += len(block)

        # Anything still buffered is written at the end, in session order.
        for session in tracker.sessions:
            if session.session_id in buffers:
                flush(session)

    stats.sessions = len(tracker.sessions)
    return stats


def _consume_block(
    block: list[Packet],
    tracker: SessionTracker,
    buffers: dict[str, list[Packet]],
    closed_at: dict[str, int],
    flush,
    stats: StreamingStats,
    base_index: int,
    close_linger: int,
    max_session_packets: int,
) -> None:
    for offset, packet in enumerate(block):
        stats.packets += 1
        position = base_index + offset
        session, evicted = tracker.add(packet)
        buffers.setdefault(session.session_id, []).append(packet)

        if evicted is not None:
            flush(evicted)

        if session.fin_seen or session.rst_seen:
            closed_at.setdefault(session.session_id, position)

        session_id = session.session_id
        closed = closed_at.get(session_id)
        if (closed is not None and position - closed >= close_linger) or len(
            buffers[session_id]
        ) >= max_session_packets:
            flush(session)
