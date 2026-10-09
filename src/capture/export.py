"""Export of a set of sessions to the normalized capture contract.

The JSON is written incrementally: the header is written first and each session
is serialized as it is produced, so a large capture does not have to be turned
into one in-memory Python object before it can be written. See
``docs/CONTRACT.md`` and ``docs/schemas/capture.schema.json``.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Iterable, Sequence

from src.capture.reassembly import DirectionalStream
from src.capture.session import Direction, Session

CONTRACT_VERSION = 1


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Return ``sha256:<digest>`` for the contents of ``path``."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def capture_id_from_bytes(data: bytes) -> str:
    """Return ``sha256:<digest>`` for an in-memory capture."""

    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _stream_to_contract(stream: DirectionalStream) -> dict[str, object]:
    return {
        "bytes_b64": base64.b64encode(bytes(stream.bytes_)).decode("ascii"),
        "provenance": [r.to_contract() for r in stream.provenance.ranges],
        "diagnostics": [d.to_contract() for d in stream.diagnostics],
    }


def session_to_contract(
    session: Session,
    streams: dict[Direction, DirectionalStream],
) -> dict[str, object]:
    """Build the contract object for one session from its two streams."""

    out = session.to_contract()
    directions: dict[str, object] = {}
    for direction in (Direction.A_TO_B, Direction.B_TO_A):
        stream = streams.get(direction)
        if stream is not None:
            directions[direction.value] = _stream_to_contract(stream)
    out["directions"] = directions
    return out


def export_capture(
    sessions: Sequence[Session] | Iterable[Session],
    out_path: Path,
    *,
    source_file: str,
    capture_id: str,
    streams: dict[str, dict[Direction, DirectionalStream]] | None = None,
) -> None:
    """Write the normalized capture to ``out_path``.

    ``streams`` maps a session id to its two directional streams. When it is
    omitted, the streams carried on each session are used if present.
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        handle.write("{")
        handle.write('"contract_version":')
        handle.write(str(CONTRACT_VERSION))
        handle.write(',"capture_id":')
        handle.write(json.dumps(capture_id))
        handle.write(',"source_file":')
        handle.write(json.dumps(source_file))
        handle.write(',"sessions":[')
        first = True
        for session in sessions:
            if not first:
                handle.write(",")
            first = False
            session_streams = (streams or {}).get(session.session_id, {})
            payload = session_to_contract(session, session_streams)
            json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"))
        handle.write("]}")
        handle.write("\n")
