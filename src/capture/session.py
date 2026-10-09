"""Identification of TCP sessions as connection instances.

A session is one instance of a connection, not a reusable 5-tuple bucket. When
the same addresses and ports are used again for a new connection, that is a
separate session. The instance boundary is taken from the handshake: a SYN with
a fresh initial sequence number starts a new instance, as does payload that
appears after a previously observed close without a SYN.

The two sides are named A and B. A is the initiator when a SYN without ACK was
observed, otherwise the source of the first packet of the instance. Roles are
reported as ``client`` and ``server`` only when the handshake proves them; with
no SYN both roles stay ``unknown`` and no meaning is assigned to either side.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum

from src.capture.parser import Packet


class Direction(str, Enum):
    """The two directions of a session."""

    A_TO_B = "A_to_B"
    B_TO_A = "B_to_A"

    @property
    def opposite(self) -> Direction:
        return Direction.B_TO_A if self is Direction.A_TO_B else Direction.A_TO_B


@dataclass(frozen=True, slots=True)
class Endpoint:
    ip: str
    port: int

    def to_contract(self) -> dict[str, object]:
        return {"ip": self.ip, "port": self.port}


@dataclass(slots=True)
class Session:
    """One connection instance and the packets that belong to it."""

    session_id: str
    endpoints: tuple[Endpoint, Endpoint]
    syn_seen: bool = False
    fin_seen: bool = False
    rst_seen: bool = False
    isn_a: int | None = None
    isn_b: int | None = None
    first_ts: float | None = None
    last_ts: float | None = None
    packet_indices: list[int] = field(default_factory=list)
    role_a: str = "unknown"
    role_b: str = "unknown"

    def endpoint_index(self, ip: str, port: int) -> int:
        """Return 0 for endpoint A and 1 for endpoint B."""

        if self.endpoints[0] == Endpoint(ip, port):
            return 0
        return 1

    def direction_of(self, packet: Packet) -> Direction:
        if self.endpoint_index(packet.src_ip, packet.src_port) == 0:
            return Direction.A_TO_B
        return Direction.B_TO_A

    def to_contract(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "endpoints": [ep.to_contract() for ep in self.endpoints],
            "role_a": self.role_a,
            "role_b": self.role_b,
            "syn_seen": self.syn_seen,
            "fin_seen": self.fin_seen,
            "rst_seen": self.rst_seen,
            "isn_a": self.isn_a,
            "isn_b": self.isn_b,
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "packet_indices": list(self.packet_indices),
        }


def _pair_key(packet: Packet) -> frozenset[Endpoint]:
    return frozenset(
        (
            Endpoint(packet.src_ip, packet.src_port),
            Endpoint(packet.dst_ip, packet.dst_port),
        )
    )


def _initiator(packet: Packet) -> tuple[Endpoint, Endpoint]:
    """Order the endpoints with the sender of ``packet`` as A."""

    return (
        Endpoint(packet.src_ip, packet.src_port),
        Endpoint(packet.dst_ip, packet.dst_port),
    )


def _is_new_handshake(session: Session, packet: Packet, a_endpoint: Endpoint) -> bool:
    """Decide whether ``packet`` starts a new instance rather than continuing one."""

    if not packet.syn or packet.ack_flag:
        return False
    if not session.syn_seen:
        return False
    # A retransmitted SYN repeats the same initial sequence number.
    if packet.src_ip == a_endpoint.ip and packet.src_port == a_endpoint.port:
        return session.isn_a is not None and packet.seq != session.isn_a
    return session.isn_b is not None and packet.seq != session.isn_b


def _is_reuse_after_close(session: Session, packet: Packet) -> bool:
    """A closed instance followed by payload but no SYN means the port was reused."""

    if not (session.fin_seen or session.rst_seen):
        return False
    if packet.syn:
        return False
    return packet.payload_len > 0


class SessionTracker:
    """Assigns packets to connection instances as they arrive.

    This is the incremental form of :func:`build_sessions`: the same rules
    decide where one instance ends and the next begins, but state is carried
    across calls so a caller can feed packets in blocks. ``add`` returns the
    session the packet joined and, when the packet superseded a previous
    instance on the same address pair, that finished instance.
    """

    def __init__(self) -> None:
        self._sessions: list[Session] = []
        self._by_id: dict[str, Session] = {}
        self._current: dict[frozenset[Endpoint], Session] = {}
        self._counter = 0

    def add(self, packet: Packet) -> tuple[Session, Session | None]:
        key = _pair_key(packet)
        session = self._current.get(key)
        evicted: Session | None = None

        if session is not None and (
            _is_new_handshake(session, packet, session.endpoints[0])
            or _is_reuse_after_close(session, packet)
        ):
            evicted = session
            session = None

        if session is None:
            self._counter += 1
            a, b = _initiator(packet)
            session = Session(session_id=f"s{self._counter}", endpoints=(a, b))
            self._sessions.append(session)
            self._by_id[session.session_id] = session
            self._current[key] = session

        _absorb(session, packet)
        return session, evicted

    @property
    def sessions(self) -> list[Session]:
        """Every session seen so far, in order of first appearance."""

        return list(self._sessions)

    def by_id(self, session_id: str) -> Session:
        return self._by_id[session_id]

    def open_sessions(self) -> list[Session]:
        """The sessions still being filled, in order of first appearance."""

        seen: dict[str, Session] = {}
        for session in self._current.values():
            seen[session.session_id] = session
        return [s for s in self._sessions if s.session_id in seen]


def build_sessions(packets: Sequence[Packet] | Iterable[Packet]) -> list[Session]:
    """Group packets into TCP connection instances, in order of first appearance."""

    tracker = SessionTracker()
    for packet in packets:
        tracker.add(packet)
    return tracker.sessions


def _absorb(session: Session, packet: Packet) -> None:
    """Fold one packet into ``session`` and update its state."""

    if session.first_ts is None:
        session.first_ts = packet.timestamp
    session.last_ts = packet.timestamp
    session.packet_indices.append(packet.index)

    side = session.endpoint_index(packet.src_ip, packet.src_port)

    if packet.syn:
        session.syn_seen = True
        if packet.syn and not packet.ack_flag:
            session.role_a = "client"
            session.role_b = "server"
        if side == 0 and session.isn_a is None:
            session.isn_a = packet.seq
        elif side == 1 and session.isn_b is None:
            session.isn_b = packet.seq
    if packet.fin:
        session.fin_seen = True
    if packet.rst:
        session.rst_seen = True
