"""End-to-end capture normalization: file in, sessions and streams out.

This module ties the parser, session identification, and reassembly together so
that callers (the CLI, the tests, and the UI) do not repeat the same order of
steps.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.capture.export import capture_id_from_bytes, sha256_file
from src.capture.parser import Diagnostic, Packet, read_capture
from src.capture.reassembly import DirectionalStream, reassemble
from src.capture.session import Direction, Session, build_sessions

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NormalizedCapture:
    """Sessions, their streams, and the diagnostics from reading the file."""

    capture_id: str
    source_file: Path
    sessions: list[Session] = field(default_factory=list)
    streams: dict[str, dict[Direction, DirectionalStream]] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def packets_read(self) -> int:
        return sum(len(s.packet_indices) for s in self.sessions)


def normalize(
    path: Path,
    *,
    capture_id: str | None = None,
    ignore_checksums: bool = True,
) -> NormalizedCapture:
    """Read ``path`` and return its sessions and reassembled streams."""

    diagnostics: list[Diagnostic] = []
    packets = list(read_capture(path, diagnostics))
    logger.info("read %d packet(s) from %s", len(packets), path)
    result = normalize_packets(
        packets,
        source_file=path,
        capture_id=capture_id if capture_id is not None else sha256_file(path),
        diagnostics=diagnostics,
        ignore_checksums=ignore_checksums,
    )
    logger.info(
        "normalised %s: %d session(s), %d diagnostic(s)",
        path,
        len(result.sessions),
        len(result.diagnostics),
    )
    return result


def normalize_bytes(
    data: bytes,
    *,
    source_file: Path,
    ignore_checksums: bool = True,
) -> NormalizedCapture:
    """Normalize an in-memory capture. Used by tests and fixture generation."""

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pcapng", delete=False) as handle:
        handle.write(data)
        tmp_path = Path(handle.name)
    try:
        return normalize(
            tmp_path,
            capture_id=capture_id_from_bytes(data),
            ignore_checksums=ignore_checksums,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


def normalize_packets(
    packets: list[Packet],
    *,
    source_file: Path,
    capture_id: str,
    diagnostics: list[Diagnostic] | None = None,
    ignore_checksums: bool = True,
) -> NormalizedCapture:
    """Build sessions and streams from already-read packets."""

    sessions = build_sessions(packets)
    by_index = {p.index: p for p in packets}
    streams: dict[str, dict[Direction, DirectionalStream]] = {}
    for session in sessions:
        members = [by_index[i] for i in session.packet_indices if i in by_index]
        by_direction: dict[Direction, DirectionalStream] = {}
        for direction in (Direction.A_TO_B, Direction.B_TO_A):
            by_direction[direction] = reassemble(
                session, direction, members, ignore_checksums=ignore_checksums
            )
        streams[session.session_id] = by_direction
    return NormalizedCapture(
        capture_id=capture_id,
        source_file=source_file,
        sessions=sessions,
        streams=streams,
        diagnostics=list(diagnostics or []),
    )
