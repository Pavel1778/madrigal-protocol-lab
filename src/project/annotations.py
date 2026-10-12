"""Researcher annotations bound to byte ranges and to messages.

An annotation is a note a researcher attaches to a specific range of a capture:
"these bytes are the temperature setpoint", "this message is the reply to the
previous request", "this field is still unverified". Unlike a rule, an
annotation is not applied to new data; it records what a human concluded while
looking at one capture.

Each annotation keeps the same provenance a rule result keeps: the capture, the
session, the direction and the byte range. That is what lets the report cite
the exact bytes an annotation refers to, and what lets a reader jump from the
report back to the packet.

Annotations live in ``annotations.sqlite`` inside the project. The database is
opened lazily, so creating a project does not need the sqlite driver to be
present, and the file stays a valid empty database until the first write.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .manifest import utc_now

#: Kinds an annotation may take. The set is fixed so a report can reason about
#: every annotation without a free-form tag.
ANNOTATION_KINDS = (
    "observation",
    "hypothesis",
    "confirmed",
    "contradiction",
    "question",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    offset INTEGER NOT NULL,
    length INTEGER NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


class AnnotationError(ValueError):
    """Raised when an annotation is malformed or the store is unusable."""


@dataclass
class Annotation:
    """A note attached to a byte range in one capture.

    Attributes:
        capture_id: Identity of the capture the range belongs to.
        session_id: Session the range belongs to.
        direction: ``A_to_B`` or ``B_to_A``.
        offset: Offset of the first byte of the range in the directional stream.
        length: Number of bytes in the range.
        kind: One of :data:`ANNOTATION_KINDS`.
        text: The note itself.
        created_at: When the annotation was recorded.
        id: Database identity; ``None`` until the annotation is stored.
    """

    capture_id: str
    session_id: str
    direction: str
    offset: int
    length: int
    kind: str
    text: str
    created_at: str = ""
    id: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in ANNOTATION_KINDS:
            raise AnnotationError(f"unknown annotation kind {self.kind!r}")
        if self.offset < 0:
            raise AnnotationError("annotation offset must be non-negative")
        if self.length < 0:
            raise AnnotationError("annotation length must be non-negative")
        if not self.text.strip():
            raise AnnotationError("annotation text must not be empty")

    @property
    def end(self) -> int:
        """Offset one past the last annotated byte."""
        return self.offset + self.length

    def to_dict(self) -> dict:
        """Return a JSON-ready mapping of the annotation."""
        return {
            "id": self.id,
            "capture_id": self.capture_id,
            "session_id": self.session_id,
            "direction": self.direction,
            "offset": self.offset,
            "length": self.length,
            "kind": self.kind,
            "text": self.text,
            "created_at": self.created_at,
        }


class AnnotationStore:
    """The ``annotations.sqlite`` file of one project.

    The connection is opened on first use and closed by :meth:`close`. Passing
    a :class:`~pathlib.Path` to a file that does not exist yet creates a valid
    empty database when the first write happens.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        """Location of the underlying database file."""
        return self._path

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init(self) -> None:
        """Create the schema if it is missing."""
        conn = self._connect()
        conn.execute(_SCHEMA)
        conn.commit()

    def close(self) -> None:
        """Close the connection if it is open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> AnnotationStore:
        self.init()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def add(self, annotation: Annotation) -> Annotation:
        """Store ``annotation`` and return it with its assigned id."""
        self.init()
        stamps = annotation.created_at or utc_now()
        conn = self._connect()
        cursor = conn.execute(
            """
            INSERT INTO annotations
                (capture_id, session_id, direction, offset, length, kind, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                annotation.capture_id,
                annotation.session_id,
                annotation.direction,
                annotation.offset,
                annotation.length,
                annotation.kind,
                annotation.text,
                stamps,
            ),
        )
        conn.commit()
        annotation.id = int(cursor.lastrowid)
        annotation.created_at = stamps
        return annotation

    def clear(self) -> int:
        """Remove every annotation and return how many were removed."""
        self.init()
        conn = self._connect()
        count = conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
        conn.execute("DELETE FROM annotations")
        conn.commit()
        return int(count)

    def list(
        self,
        capture_id: str | None = None,
        session_id: str | None = None,
        direction: str | None = None,
    ) -> list[Annotation]:
        """Return annotations, optionally filtered, ordered by byte offset."""
        self.init()
        conn = self._connect()
        where: list[str] = []
        params: list[str] = []
        if capture_id is not None:
            where.append("capture_id = ?")
            params.append(capture_id)
        if session_id is not None:
            where.append("session_id = ?")
            params.append(session_id)
        if direction is not None:
            where.append("direction = ?")
            params.append(direction)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = conn.execute(
            f"SELECT * FROM annotations {clause} ORDER BY session_id, direction, offset",
            params,
        ).fetchall()
        return [_row_to_annotation(row) for row in rows]

    def count(self) -> int:
        """Number of stored annotations."""
        self.init()
        conn = self._connect()
        return int(conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0])


def _row_to_annotation(row: sqlite3.Row) -> Annotation:
    return Annotation(
        id=row["id"],
        capture_id=row["capture_id"],
        session_id=row["session_id"],
        direction=row["direction"],
        offset=row["offset"],
        length=row["length"],
        kind=row["kind"],
        text=row["text"],
        created_at=row["created_at"],
    )


__all__ = [
    "ANNOTATION_KINDS",
    "Annotation",
    "AnnotationError",
    "AnnotationStore",
]
