"""Generate the synthetic capture fixtures used by the test suite.

Each fixture isolates one behaviour of the capture engine: a clean handshake, a
retransmission, out-of-order delivery, a hole, a conflicting overlap, a
connection with no observed start, and message boundaries that do not line up
with packet boundaries.

Run it to (re)write the files under ``tests/fixtures``:

    python scripts/generate_fixture.py
"""

from __future__ import annotations

import argparse
import io
import socket
from pathlib import Path

import dpkt

_CLIENT_MAC = b"\x02\x00\x00\x00\x00\x01"
_SERVER_MAC = b"\x02\x00\x00\x00\x00\x02"
_CLIENT_IP = "10.0.0.1"
_SERVER_IP = "10.0.0.2"
_CLIENT_PORT = 40000
_SERVER_PORT = 9000
_BASE_TS = 1_700_000_000.0


def _ipv4(src: str, dst: str, payload: bytes) -> dpkt.ip.IP:
    return dpkt.ip.IP(
        src=socket.inet_aton(src),
        dst=socket.inet_aton(dst),
        p=dpkt.ip.IP_PROTO_TCP,
        data=payload,
    )


def segment(
    *,
    src_ip: str,
    src_port: int,
    dst_ip: str,
    dst_port: int,
    seq: int,
    ack: int,
    flags: int,
    payload: bytes = b"",
) -> bytes:
    """Build one Ethernet frame carrying a TCP segment."""

    tcp = dpkt.tcp.TCP(
        sport=src_port,
        dport=dst_port,
        seq=seq & 0xFFFFFFFF,
        ack=ack & 0xFFFFFFFF,
        flags=flags,
        win=64240,
        data=payload,
    )
    tcp.off = 5
    ip = _ipv4(src_ip, dst_ip, bytes(tcp))
    ip.len = len(bytes(ip))
    forward = src_ip == _CLIENT_IP
    eth = dpkt.ethernet.Ethernet(
        src=_CLIENT_MAC if forward else _SERVER_MAC,
        dst=_SERVER_MAC if forward else _CLIENT_MAC,
        type=dpkt.ethernet.ETH_TYPE_IP,
        data=ip,
    )
    return bytes(eth)


def ipv6_frame(payload: bytes = b"\x00" * 8) -> bytes:
    """Build one Ethernet frame carrying an IPv6 packet."""

    ip6 = dpkt.ip6.IP6(src=b"\x00" * 15 + b"\x01", dst=b"\x00" * 15 + b"\x02")
    ip6.nxt = dpkt.ip.IP_PROTO_TCP
    ip6.data = payload
    ip6.plen = len(payload)
    eth = dpkt.ethernet.Ethernet(
        src=_CLIENT_MAC,
        dst=_SERVER_MAC,
        type=dpkt.ethernet.ETH_TYPE_IP6,
        data=ip6,
    )
    return bytes(eth)


def syn(seq: int, isn_b: int | None = None) -> bytes:
    return segment(
        src_ip=_CLIENT_IP,
        src_port=_CLIENT_PORT,
        dst_ip=_SERVER_IP,
        dst_port=_SERVER_PORT,
        seq=seq,
        ack=0,
        flags=dpkt.tcp.TH_SYN,
    )


def syn_ack(seq: int, ack: int) -> bytes:
    return segment(
        src_ip=_SERVER_IP,
        src_port=_SERVER_PORT,
        dst_ip=_CLIENT_IP,
        dst_port=_CLIENT_PORT,
        seq=seq,
        ack=ack,
        flags=dpkt.tcp.TH_SYN | dpkt.tcp.TH_ACK,
    )


def ack_pkt(seq: int, ack: int) -> bytes:
    return segment(
        src_ip=_CLIENT_IP,
        src_port=_CLIENT_PORT,
        dst_ip=_SERVER_IP,
        dst_port=_SERVER_PORT,
        seq=seq,
        ack=ack,
        flags=dpkt.tcp.TH_ACK,
    )


def data_a(seq: int, payload: bytes, ack: int = 5001) -> bytes:
    return segment(
        src_ip=_CLIENT_IP,
        src_port=_CLIENT_PORT,
        dst_ip=_SERVER_IP,
        dst_port=_SERVER_PORT,
        seq=seq,
        ack=ack,
        flags=dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
        payload=payload,
    )


def data_b(seq: int, payload: bytes, ack: int = 1001) -> bytes:
    return segment(
        src_ip=_SERVER_IP,
        src_port=_SERVER_PORT,
        dst_ip=_CLIENT_IP,
        dst_port=_CLIENT_PORT,
        seq=seq,
        ack=ack,
        flags=dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
        payload=payload,
    )


def fin_a(seq: int) -> bytes:
    return segment(
        src_ip=_CLIENT_IP,
        src_port=_CLIENT_PORT,
        dst_ip=_SERVER_IP,
        dst_port=_SERVER_PORT,
        seq=seq,
        ack=5001,
        flags=dpkt.tcp.TH_FIN | dpkt.tcp.TH_ACK,
    )


def fin_b(seq: int) -> bytes:
    return segment(
        src_ip=_SERVER_IP,
        src_port=_SERVER_PORT,
        dst_ip=_CLIENT_IP,
        dst_port=_CLIENT_PORT,
        seq=seq,
        ack=1002,
        flags=dpkt.tcp.TH_FIN | dpkt.tcp.TH_ACK,
    )


def _write_pcapng(frames: list[bytes]) -> bytes:
    buf = io.BytesIO()
    writer = dpkt.pcapng.Writer(buf)
    for offset, frame in enumerate(frames):
        writer.writepkt(frame, ts=_BASE_TS + offset * 0.001)
    data = buf.getvalue()
    buf.close()
    return data


def build_normal() -> bytes:
    """A clean handshake, one message each way, and a clean close."""

    return _write_pcapng(
        [
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1001, b"HELLO"),
            data_b(5001, b"WORLD"),
            fin_a(1006),
            fin_b(5006),
        ]
    )


def build_retransmission() -> bytes:
    """The same payload sent twice, then the next payload."""

    return _write_pcapng(
        [
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1001, b"AB"),
            data_a(1001, b"AB"),
            data_a(1003, b"CD"),
            fin_a(1005),
        ]
    )


def build_out_of_order() -> bytes:
    """Two segments delivered in the wrong order."""

    return _write_pcapng(
        [
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1003, b"CD"),
            data_a(1001, b"AB"),
            fin_a(1005),
        ]
    )


def build_gap() -> bytes:
    """A hole of four bytes between two observed segments."""

    return _write_pcapng(
        [
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1001, b"AB"),
            data_a(1007, b"GH"),
            fin_a(1009),
        ]
    )


def build_overlap_conflict() -> bytes:
    """An overlap whose second version disagrees with the bytes already seen."""

    return _write_pcapng(
        [
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1001, b"ABCD"),
            data_a(1003, b"XY"),
            fin_a(1005),
        ]
    )


def build_no_syn() -> bytes:
    """A connection whose start was not captured."""

    return _write_pcapng(
        [
            data_a(1001, b"HELLO"),
            data_b(5001, b"WORLD"),
            fin_a(1006),
        ]
    )


def build_message_split() -> bytes:
    """One length-prefixed message split across two segments.

    The message is a two-byte big-endian length followed by that many bytes.
    The length and the first two body bytes arrive in the first segment; the
    rest arrives in the second.
    """

    body = b"PAYLOAD"
    message = len(body).to_bytes(2, "big") + body
    return _write_pcapng(
        [
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1001, message[:4]),
            data_a(1005, message[4:]),
            fin_a(1009),
        ]
    )


def build_two_messages() -> bytes:
    """Two length-prefixed messages inside one segment."""

    first = (3).to_bytes(2, "big") + b"AAA"
    second = (2).to_bytes(2, "big") + b"BB"
    return _write_pcapng(
        [
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1001, first + second),
            fin_a(1006),
        ]
    )


def build_port_reuse() -> bytes:
    """Two separate connections that reuse the same address and port pair."""

    return _write_pcapng(
        [
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1001, b"ONE"),
            fin_a(1004),
            # New connection instance on the same tuple, different ISN.
            syn(90000),
            syn_ack(70000, 90001),
            ack_pkt(90001, 70001),
            data_a(90001, b"TWO"),
            fin_a(90004),
        ]
    )


def build_seq_wrap() -> bytes:
    """A stream whose sequence space crosses the 32-bit boundary."""

    start = 0xFFFFFFFE
    return _write_pcapng(
        [
            syn(start - 1),
            syn_ack(5000, start),
            ack_pkt(start, 5001),
            data_a(start, b"AB"),
            data_a((start + 2) & 0xFFFFFFFF, b"CD"),
            fin_a((start + 4) & 0xFFFFFFFF),
        ]
    )


def build_ipv6_mixed() -> bytes:
    """One IPv6 frame ahead of a normal IPv4 session."""

    return _write_pcapng(
        [
            ipv6_frame(),
            syn(1000),
            syn_ack(5000, 1001),
            ack_pkt(1001, 5001),
            data_a(1001, b"HELLO"),
            fin_a(1006),
        ]
    )


BUILDERS = {
    "normal.pcapng": build_normal,
    "retransmission.pcapng": build_retransmission,
    "ooo.pcapng": build_out_of_order,
    "gap.pcapng": build_gap,
    "overlap_conflict.pcapng": build_overlap_conflict,
    "no_syn.pcapng": build_no_syn,
    "message_split_across_packets.pcapng": build_message_split,
    "two_messages_in_one_packet.pcapng": build_two_messages,
    "port_reuse.pcapng": build_port_reuse,
    "seq_wrap.pcapng": build_seq_wrap,
    "ipv6_mixed.pcapng": build_ipv6_mixed,
}


def generate(out_dir: Path) -> list[Path]:
    """Write every fixture into ``out_dir`` and return the paths."""

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, builder in BUILDERS.items():
        path = out_dir / name
        path.write_bytes(builder())
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic capture fixtures.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "fixtures",
        help="output directory",
    )
    args = parser.parse_args(argv)
    for path in generate(args.out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
