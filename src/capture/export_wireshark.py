"""Export of reassembled streams as a pcap for side-by-side inspection.

Each session becomes two packets: one carrying the whole stream in each
direction. The result is the same view Wireshark's "Follow TCP Stream" gives,
but written to a capture that can be opened next to the original for
comparison. The output is classic pcap for widest compatibility.

The payloads are the reassembled bytes, so holes are already omitted and
retransmissions are already collapsed; the provenance in the normalized capture
is what maps any byte back to its packet in the original file.
"""

from __future__ import annotations

import socket
from pathlib import Path

import dpkt

from src.capture.reassembly import DirectionalStream, reassemble
from src.capture.session import Direction, Session

_PCAP_SNAPLEN = 262144

# Values used for the packet headers of an exported stream. They cannot be
# recovered from the stream itself, so they are fixed and documented rather
# than guessed.
_DEFAULT_ISN_CLIENT = 1
_DEFAULT_ISN_SERVER = 1
_CLIENT_MAC = b"\x02\x00\x00\x00\x00\x01"
_SERVER_MAC = b"\x02\x00\x00\x00\x00\x02"


def _frame(
    src_ip: str,
    src_port: int,
    dst_ip: str,
    dst_port: int,
    seq: int,
    ack: int,
    payload: bytes,
    *,
    forward: bool,
) -> bytes:
    tcp = dpkt.tcp.TCP(
        sport=src_port,
        dport=dst_port,
        seq=seq & 0xFFFFFFFF,
        ack=ack & 0xFFFFFFFF,
        flags=dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
        win=64240,
        data=payload,
    )
    tcp.off = 5
    ip = dpkt.ip.IP(
        src=socket.inet_aton(src_ip),
        dst=socket.inet_aton(dst_ip),
        p=dpkt.ip.IP_PROTO_TCP,
        data=bytes(tcp),
    )
    ip.len = len(bytes(ip))
    src_mac, dst_mac = (_CLIENT_MAC, _SERVER_MAC) if forward else (_SERVER_MAC, _CLIENT_MAC)
    eth = dpkt.ethernet.Ethernet(
        src=src_mac,
        dst=dst_mac,
        type=dpkt.ethernet.ETH_TYPE_IP,
        data=ip,
    )
    return bytes(eth)


def export_reassembled_pcap(
    sessions: list[Session],
    out_path: Path,
    *,
    streams: dict[str, dict[Direction, DirectionalStream]] | None = None,
    packets: list | None = None,
) -> int:
    """Write reassembled streams to ``out_path`` as classic pcap.

    One packet is written per session direction, so a session with data in both
    directions becomes two packets. When ``streams`` is omitted, each session is
    reassembled from ``packets`` (or from the packets carried on the session).

    Returns the number of packets written.
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("wb") as handle:
        writer = dpkt.pcap.Writer(handle, snaplen=_PCAP_SNAPLEN)
        for session in sessions:
            session_streams = (streams or {}).get(session.session_id)
            if session_streams is None:
                source = packets if packets is not None else []
                session_streams = {
                    Direction.A_TO_B: reassemble(
                        session, Direction.A_TO_B, source
                    ),
                    Direction.B_TO_A: reassemble(
                        session, Direction.B_TO_A, source
                    ),
                }

            endpoint_a, endpoint_b = session.endpoints
            isn_a = session.isn_a if session.isn_a is not None else _DEFAULT_ISN_CLIENT
            isn_b = session.isn_b if session.isn_b is not None else _DEFAULT_ISN_SERVER
            first_ts = session.first_ts if session.first_ts is not None else 0.0
            last_ts = session.last_ts if session.last_ts is not None else first_ts

            a_stream = session_streams.get(Direction.A_TO_B)
            if a_stream is not None and len(a_stream.bytes_):
                writer.writepkt(
                    _frame(
                        endpoint_a.ip,
                        endpoint_a.port,
                        endpoint_b.ip,
                        endpoint_b.port,
                        isn_a,
                        isn_b,
                        bytes(a_stream.bytes_),
                        forward=True,
                    ),
                    ts=first_ts,
                )
                written += 1

            b_stream = session_streams.get(Direction.B_TO_A)
            if b_stream is not None and len(b_stream.bytes_):
                writer.writepkt(
                    _frame(
                        endpoint_b.ip,
                        endpoint_b.port,
                        endpoint_a.ip,
                        endpoint_a.port,
                        isn_b,
                        isn_a,
                        bytes(b_stream.bytes_),
                        forward=False,
                    ),
                    ts=last_ts,
                )
                written += 1
    return written
