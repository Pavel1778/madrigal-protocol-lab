"""Pair request and response messages into turns, with a stated confidence.

A binary protocol usually alternates: the client sends a request, the server
sends a reply, then the next request follows. When the messages are framed but
their meaning is unknown, the only reliable structure left is that alternation
order and the time between the two messages.

This module turns that structure into *turns*: a request and the message that
follows it in the opposite direction. It does not claim the reply belongs to the
request. It states what it observed (which direction, how far apart in time,
whether both messages framed cleanly) and derives a confidence from those
observations alone. A pairing with no opposite message is reported as
unanswered rather than guessed.

Confidence is a number in ``[0, 1]`` built as a fixed sum of independent
observations, each weighted and named in ``Turn.basis`` so a reader can see why
the number is what it is. The weights are a design choice, not a measurement;
they are deliberately conservative so a weak pairing cannot reach a high score.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

# Weights for each observation. They sum to at most 1.0 plus the base, so the
# result is clamped. Keeping them in one place makes the reasoning auditable.
BASE_CONFIDENCE = 0.40
WEIGHT_OPPOSITE_DIRECTION = 0.15
WEIGHT_TIME_ORDER = 0.15
WEIGHT_WITHIN_WINDOW = 0.10
WEIGHT_BOTH_FRAMED = 0.10
WEIGHT_BOTH_MATCHED = 0.05
PENALTY_UNCLEAR_TIMING = 0.15
PENALTY_WEAK_MESSAGE = 0.20

#: Statuses that mean the framing could not fully trust the message bytes.
WEAK_STATUSES = frozenset({"ambiguous", "incomplete", "unknown"})

#: Default upper bound, in seconds, for two messages to be considered close.
DEFAULT_WINDOW_SECONDS = 5.0


@dataclass
class Turn:
    """A request and the message that follows it in the other direction.

    Attributes:
        session_id: Session both messages belong to.
        request: The message that opens the turn, or ``None`` for a stray reply.
        response: The message in the opposite direction, or ``None`` if the
            request was never answered in this capture.
        confidence: How strongly the observations support this pairing, in
            ``[0, 1]``. This is not a probability the reply belongs to the
            request; it is a score over the observations named in ``basis``.
        basis: Human-readable observations the confidence rests on.
        gap_seconds: Time between the two messages, or ``None`` when a timestamp
            is missing. Since messages are ordered by time, this is the observed
            delay from request to response.
    """

    session_id: str
    request: Any
    response: Any | None
    confidence: float
    basis: list[str] = field(default_factory=list)
    gap_seconds: float | None = None

    @property
    def answered(self) -> bool:
        """Whether the turn has both a request and a response."""
        return self.request is not None and self.response is not None

    def to_dict(self) -> dict:
        """Return a JSON-ready mapping of the turn."""
        return {
            "session_id": self.session_id,
            "request": _message_dict(self.request),
            "response": _message_dict(self.response),
            "answered": self.answered,
            "confidence": round(self.confidence, 4),
            "basis": list(self.basis),
            "gap_seconds": self.gap_seconds,
        }


@dataclass
class PairingReport:
    """Every turn found in one or more sessions.

    Attributes:
        turns: The turns, in the order the requests appeared.
    """

    turns: list[Turn] = field(default_factory=list)

    @property
    def answered(self) -> list[Turn]:
        """Turns that have a response."""
        return [t for t in self.turns if t.answered]

    def summary(self) -> dict:
        """Counts over the turns, plus confidence statistics."""
        answered = self.answered
        low = [t for t in self.turns if t.confidence < 0.5]
        high = [t for t in self.turns if t.confidence >= 0.8]
        return {
            "turns": len(self.turns),
            "answered": len(answered),
            "unanswered": len(self.turns) - len(answered),
            "high_confidence": len(high),
            "low_confidence": len(low),
            "mean_confidence": (
                round(sum(t.confidence for t in self.turns) / len(self.turns), 4)
                if self.turns
                else 0.0
            ),
        }

    def to_dict(self) -> dict:
        """Return a JSON-ready mapping of the whole report."""
        return {
            "contract_version": 1,
            "kind": "request_response_pairing",
            "turns": [turn.to_dict() for turn in self.turns],
            "summary": self.summary(),
        }


def _message_dict(message: Any | None) -> dict | None:
    if message is None:
        return None
    return {
        "direction": getattr(message, "direction", ""),
        "offset": getattr(message, "offset", 0),
        "length": getattr(message, "length", 0),
        "status": _status_of(message),
        "timestamp": getattr(message, "timestamp", None),
        "bytes_hex": getattr(message, "bytes_hex", ""),
    }


def _status_of(message: Any) -> str:
    status = getattr(message, "status", "")
    return getattr(status, "value", status)


def _timestamp_of(message: Any) -> float | None:
    stamp = getattr(message, "timestamp", None)
    if stamp is None:
        return None
    try:
        return float(stamp)
    except (TypeError, ValueError):
        return None


def _order_key(message: Any) -> tuple:
    stamp = _timestamp_of(message)
    # Messages without a timestamp keep their arrival order: they sort after
    # timestamped ones at the same offset but stay stable overall.
    return (0, stamp, getattr(message, "offset", 0)) if stamp is not None else (
        1,
        0.0,
        getattr(message, "offset", 0),
    )


def build_turns(
    messages: Sequence[Any],
    *,
    session_id: str = "",
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> PairingReport:
    """Pair messages into request/response turns by direction alternation.

    Messages from both directions are ordered together by timestamp (falling
    back to their stream offset when a timestamp is missing). Each message is
    paired with the next message in the *opposite* direction; a message with no
    such follower is reported as an unanswered turn.

    Args:
        messages: Framed messages from both directions of one session.
        session_id: Session the messages belong to, copied onto every turn.
        window_seconds: Time, in seconds, within which a reply is considered
            close to its request.

    Returns:
        A report with one turn per request, each carrying a confidence derived
        from the observations listed in its ``basis``.
    """
    ordered = sorted(messages, key=_order_key)
    turns: list[Turn] = []
    index = 0
    while index < len(ordered):
        current = ordered[index]
        current_dir = getattr(current, "direction", "")
        follower = ordered[index + 1] if index + 1 < len(ordered) else None
        follower_dir = getattr(follower, "direction", "") if follower is not None else ""
        if follower is not None and follower_dir and follower_dir != current_dir:
            turns.append(
                _make_turn(session_id, current, follower, window_seconds)
            )
            index += 2
            continue
        turns.append(_make_turn(session_id, current, None, window_seconds))
        index += 1
    return PairingReport(turns=turns)


def build_turns_for_corpus(
    streams: Iterable[tuple[str, str, Sequence[Any]]],
    *,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> PairingReport:
    """Pair messages of every direction of every session in a corpus.

    ``streams`` yields ``(session_id, direction, messages)``. Messages are
    grouped by session and paired within the session only, so a reply from one
    connection is never matched to a request from another.
    """

    by_session: dict[str, list[Any]] = {}
    for session_id, _direction, messages in streams:
        by_session.setdefault(session_id, []).extend(messages)

    report = PairingReport()
    for session_id in sorted(by_session):
        part = build_turns(
            by_session[session_id], session_id=session_id, window_seconds=window_seconds
        )
        report.turns.extend(part.turns)
    return report


def _make_turn(
    session_id: str,
    request: Any,
    response: Any | None,
    window_seconds: float,
) -> Turn:
    """Score one request/response candidate against its observations."""

    confidence = BASE_CONFIDENCE
    basis: list[str] = []
    gap: float | None = None

    if response is None:
        basis.append("no message follows in the opposite direction")
        return Turn(
            session_id=session_id,
            request=request,
            response=None,
            confidence=0.0,
            basis=basis,
            gap_seconds=None,
        )

    request_dir = getattr(request, "direction", "")
    response_dir = getattr(response, "direction", "")
    if request_dir and response_dir and request_dir != response_dir:
        confidence += WEIGHT_OPPOSITE_DIRECTION
        basis.append(f"opposite directions ({request_dir} then {response_dir})")

    request_ts = _timestamp_of(request)
    response_ts = _timestamp_of(response)
    if request_ts is not None and response_ts is not None:
        # Messages are ordered by timestamp before pairing, so the response
        # never precedes the request; the gap is the observed delay.
        gap = round(response_ts - request_ts, 6)
        confidence += WEIGHT_TIME_ORDER
        basis.append(f"response follows request by {gap:g}s")
        if gap <= window_seconds:
            confidence += WEIGHT_WITHIN_WINDOW
            basis.append(f"within the {window_seconds:g}s window")
    else:
        confidence -= PENALTY_UNCLEAR_TIMING
        basis.append("a timestamp is missing; timing is unknown")

    request_status = _status_of(request)
    response_status = _status_of(response)
    if request_status not in WEAK_STATUSES and response_status not in WEAK_STATUSES:
        confidence += WEIGHT_BOTH_FRAMED
        basis.append("both messages framed without gaps or ambiguity")
    else:
        confidence -= PENALTY_WEAK_MESSAGE
        basis.append(
            f"framing is weak (request {request_status}, response {response_status})"
        )

    if request_status == "matched" and response_status == "matched":
        confidence += WEIGHT_BOTH_MATCHED
        basis.append("both messages matched the rule")

    confidence = max(0.0, min(1.0, confidence))
    return Turn(
        session_id=session_id,
        request=request,
        response=response,
        confidence=confidence,
        basis=basis,
        gap_seconds=gap,
    )


__all__ = [
    "DEFAULT_WINDOW_SECONDS",
    "PairingReport",
    "Turn",
    "build_turns",
    "build_turns_for_corpus",
]
