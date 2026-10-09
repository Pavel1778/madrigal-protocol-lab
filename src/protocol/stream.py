"""Directional stream model and normalized capture loading.

A stream is one direction of one TCP session: the reassembled bytes plus the
list of byte ranges that are known to be missing (gaps) or contradictory
(ambiguity). The framing and rule engine never touch a capture file directly;
they work on ``DirectionalStream``.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field


class CaptureError(ValueError):
    """Raised when a normalized capture does not match the contract."""


CONTRACT_VERSION = 1


@dataclass(frozen=True)
class Hole:
    """A range inside a stream that is not backed by observed bytes.

    ``type`` is the diagnostic type from the capture contract, for example
    ``gap`` or ``ambiguity``. For provenance ranges ``packet_index`` ties the
    range to the source packet.
    """

    type: str
    offset: int
    length: int
    detail: str | None = None
    packet_index: int | None = None
    ts: float | None = None
    seq: int | None = None

    @property
    def end(self) -> int:
        """Offset one past the last byte of the hole."""
        return self.offset + self.length

    def overlaps(self, start: int, end: int) -> bool:
        """Whether the half-open range ``[start, end)`` meets this hole."""
        return start < self.end and self.offset < end


@dataclass
class DirectionalStream:
    """One direction of a session as a flat byte sequence.

    ``offset`` values used by the framing and rule engine are always relative
    to the start of this directional stream. The synthetic in-memory
    constructor is meant for tests and for byte sequences produced outside a
    capture.
    """

    data: bytes
    diagnostics: list[Hole] = field(default_factory=list)
    provenance: list[Hole] = field(default_factory=list)

    def holes(self, start: int, end: int) -> list[Hole]:
        """Diagnostics that overlap the half-open range ``[start, end)``."""
        return [h for h in self.diagnostics if h.overlaps(start, end)]

    def has_gap(self, start: int, end: int) -> bool:
        """Whether a ``gap`` diagnostic overlaps ``[start, end)``."""
        return any(h.type == "gap" for h in self.holes(start, end))

    def has_ambiguity(self, start: int, end: int) -> bool:
        """Whether an ``ambiguity`` diagnostic overlaps ``[start, end)``."""
        return any(h.type == "ambiguity" for h in self.holes(start, end))

    @property
    def covered(self) -> int:
        """Number of bytes that are not inside a gap."""
        covered = len(self.data)
        for hole in self.diagnostics:
            if hole.type == "gap":
                covered -= min(hole.length, len(self.data))
        return max(covered, 0)

    @classmethod
    def from_bytes(cls, data: bytes) -> "DirectionalStream":
        """Wrap raw bytes as a stream with no diagnostics or provenance.

        Args:
            data: The reassembled bytes of one direction.

        Returns:
            A stream whose ``data`` is a copy of ``data``.
        """
        return cls(data=bytes(data))

    @classmethod
    def from_direction(cls, direction: dict) -> "DirectionalStream":
        """Build a stream from one ``directions`` entry of a capture.

        Args:
            direction: Mapping with base64 ``bytes_b64``, ``diagnostics`` and
                ``provenance`` lists, as defined by the capture contract.

        Returns:
            The corresponding directional stream.

        Raises:
            CaptureError: If ``bytes_b64`` is not valid base64.
        """
        raw = direction.get("bytes_b64", "")
        try:
            data = base64.b64decode(raw, validate=True)
        except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
            raise CaptureError(f"bytes_b64 is not valid base64: {exc}") from exc
        diagnostics = [_hole(d) for d in direction.get("diagnostics", [])]
        provenance = [_hole(p) for p in direction.get("provenance", [])]
        return cls(data=data, diagnostics=diagnostics, provenance=provenance)


def _hole(entry: dict) -> Hole:
    return Hole(
        type=str(entry.get("type", "unknown")),
        offset=int(entry.get("offset", 0)),
        length=int(entry.get("length", 0)),
        detail=entry.get("detail"),
        packet_index=entry.get("packet_index"),
        ts=_optional_float(entry.get("ts")),
        seq=_optional_int(entry.get("seq")),
    )


def _optional_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class Capture:
    """A normalized capture: sessions, each with its two directions."""

    contract_version: int
    capture_id: str
    source_file: str
    sessions: list[dict]
    _directions: dict[tuple[str, str], DirectionalStream] = field(default_factory=dict)

    def stream(self, session_id: str, direction: str) -> DirectionalStream:
        """Return one direction of one session as a stream (cached).

        Args:
            session_id: Session identifier from the capture.
            direction: ``"A_to_B"`` or ``"B_to_A"``.

        Returns:
            The directional stream, decoded on first use.

        Raises:
            CaptureError: If the session or the direction is not in the capture.
        """
        key = (session_id, direction)
        if key in self._directions:
            return self._directions[key]
        for session in self.sessions:
            if str(session.get("session_id")) != session_id:
                continue
            directions = session.get("directions", {})
            if direction not in directions:
                raise CaptureError(
                    f"session {session_id!r} has no direction {direction!r}"
                )
            stream = DirectionalStream.from_direction(directions[direction])
            self._directions[key] = stream
            return stream
        raise CaptureError(f"capture has no session {session_id!r}")

    def iter_streams(self) -> list[tuple[str, str, DirectionalStream]]:
        """Every ``(session_id, direction, stream)`` present in the capture."""
        result = []
        for session in self.sessions:
            sid = str(session.get("session_id", ""))
            for name in ("A_to_B", "B_to_A"):
                if name in session.get("directions", {}):
                    result.append((sid, name, self.stream(sid, name)))
        return result

    @property
    def capture_hash(self) -> str:
        """Deterministic identity for the capture content.

        Uses ``capture_id`` when present, otherwise hashes the serialized
        normalized capture so a result is still tied to the exact input.
        """
        if self.capture_id:
            return self.capture_id
        payload = json.dumps(
            {"source_file": self.source_file, "sessions": self.sessions},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_capture(path: str) -> Capture:
    """Load a normalized capture JSON file.

    Args:
        path: Path to a ``*.normalized.json`` capture.

    Returns:
        The parsed capture.

    Raises:
        CaptureError: If the file does not match the capture contract.
        OSError: If the file cannot be read.
    """
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return capture_from_dict(raw)


def capture_from_dict(raw: dict) -> Capture:
    """Build a capture from an already-parsed normalized capture mapping.

    Args:
        raw: Mapping with ``contract_version`` and ``sessions``.

    Returns:
        The parsed capture.

    Raises:
        CaptureError: If the mapping is not an object, the contract version is
            unsupported, or ``sessions`` is missing.
    """
    if not isinstance(raw, dict):
        raise CaptureError("normalized capture must be a JSON object")
    version = raw.get("contract_version", CONTRACT_VERSION)
    try:
        version = int(version)
    except (TypeError, ValueError):
        raise CaptureError(f"contract_version must be an integer, got {version!r}") from None
    if version != CONTRACT_VERSION:
        raise CaptureError(
            f"unsupported contract_version {version}; this build reads version {CONTRACT_VERSION}"
        )
    if "sessions" not in raw:
        raise CaptureError("normalized capture is missing 'sessions'")
    return Capture(
        contract_version=version,
        capture_id=str(raw.get("capture_id", "")),
        source_file=str(raw.get("source_file", "")),
        sessions=list(raw.get("sessions", [])),
    )
