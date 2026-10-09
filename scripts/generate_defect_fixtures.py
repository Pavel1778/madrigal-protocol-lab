"""Generate the deformed capture fixtures used by the robustness tests.

These captures are damaged at the container or network layer rather than at the
TCP layer: a cut header, a cut packet, mixed link types, an unsupported link
type, mixed IP versions, and IP fragments. Each isolates one way a capture can
be malformed and is used to check that reading continues past the damage.

Run it to (re)write the files under ``tests/fixtures/defects``:

    python scripts/generate_defect_fixtures.py
"""

from __future__ import annotations

import argparse
import io
import socket
import struct
from pathlib import Path

import dpkt

from scripts.generate_fixture import (
    ack_pkt,
    data_a,
    data_b,
    fin_a,
    ipv6_frame,
    segment,
    syn,
    syn_ack,
)

_DLT_EN10MB = 1
_DLT_RAW = 101
_DLT_IEEE802_11 = 105

_BASE_TS = 1_700_000_000.0


def _block(block_type: int, body: bytes) -> bytes:
    """Wrap ``body`` in a pcapng block, little endian, padded to 4 bytes."""

    padding = (4 - len(body) % 4) % 4
    body = body + b"\x00" * padding
    total = 12 + len(body)
    return struct.pack("<II", block_type, total) + body + struct.pack("<I", total)


def _section() -> bytes:
    body = struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1)
    return _block(0x0A0D0D0A, body)


def _interface(linktype: int) -> bytes:
    return _block(1, struct.pack("<HHI", linktype, 0, 65535))


def _enhanced_packet(interface: int, timestamp: float, frame: bytes) -> bytes:
    seconds = int(timestamp)
    micros = int((timestamp - seconds) * 1_000_000)
    body = struct.pack(
        "<IIIII",
        interface,
        micros >> 32,
        micros & 0xFFFFFFFF,
        len(frame),
        len(frame),
    )
    return _block(6, body + frame)


def _pcapng(interfaces: list[int], packets: list[tuple[int, bytes]]) -> bytes:
    """Build a pcapng file with the given interfaces and (interface, frame) pairs."""

    out = bytearray(_section())
    for linktype in interfaces:
        out += _interface(linktype)
    for offset, (interface, frame) in enumerate(packets):
        out += _enhanced_packet(interface, _BASE_TS + offset * 0.001, frame)
    return bytes(out)


def _exchange() -> list[bytes]:
    return [
        syn(1000),
        syn_ack(5000, 1001),
        ack_pkt(1001, 5001),
        data_a(1001, b"HELLO"),
        data_b(5001, b"WORLD"),
        fin_a(1006),
    ]


def build_truncated_header() -> bytes:
    """A pcapng whose section header block stops two thirds of the way in."""

    return _pcapng([_DLT_EN10MB], [(0, frame) for frame in _exchange()])[:12]


def build_truncated_packet() -> bytes:
    """A packet whose captured bytes stop in the middle of its payload.

    The declared lengths still describe the full segment, so the reader reports
    a short payload rather than a broken frame.
    """

    frames = _exchange()
    cut = frames[3][:-3]
    return _pcapng([_DLT_EN10MB], [(0, f) for f in [*frames[:3], cut, *frames[4:]]])


def build_mixed_link_types() -> bytes:
    """One interface declared as Ethernet, one as raw IP, both used."""

    ethernet_frames = _exchange()
    raw = segment(
        src_ip="10.0.0.1",
        src_port=40000,
        dst_ip="10.0.0.2",
        dst_port=9000,
        seq=1001,
        ack=5001,
        flags=dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
        payload=b"RAW",
    )
    ip_bytes = raw[14:]
    packets: list[tuple[int, bytes]] = [(0, f) for f in ethernet_frames]
    packets.insert(3, (1, ip_bytes))
    return _pcapng([_DLT_EN10MB, _DLT_RAW], packets)


def build_unsupported_link_type() -> bytes:
    """A capture whose only interface is 802.11."""

    return _pcapng([_DLT_IEEE802_11], [(0, b"\x08\x00" + b"\x00" * 20)])


def build_mixed_ip_versions() -> bytes:
    """An IPv6 frame and a normal IPv4 exchange in one file."""

    packets = [(0, ipv6_frame())] + [(0, f) for f in _exchange()]
    return _pcapng([_DLT_EN10MB], packets)


def build_fragmented_ip() -> bytes:
    """IP fragments alongside a clean exchange, written as classic pcap."""

    def fragment(payload: bytes, more: bool, offset: int) -> bytes:
        ip = dpkt.ip.IP(
            src=socket.inet_aton("10.0.0.1"),
            dst=socket.inet_aton("10.0.0.2"),
            p=dpkt.ip.IP_PROTO_TCP,
            data=payload,
        )
        ip.len = len(bytes(ip))
        ip.mf = 1 if more else 0
        ip.offset = offset
        eth = dpkt.ethernet.Ethernet(
            src=b"\x02\x00\x00\x00\x00\x01",
            dst=b"\x02\x00\x00\x00\x00\x02",
            type=dpkt.ethernet.ETH_TYPE_IP,
            data=ip,
        )
        return bytes(eth)

    frames = [
        fragment(b"AAAA", True, 0),
        fragment(b"BBBB", True, 3),
        fragment(b"CC", False, 6),
        *_exchange(),
    ]
    buf = io.BytesIO()
    writer = dpkt.pcap.Writer(buf)
    for offset, frame in enumerate(frames):
        writer.writepkt(frame, ts=_BASE_TS + offset * 0.001)
    data = buf.getvalue()
    buf.close()
    return data


BUILDERS = {
    "truncated_header.pcapng": build_truncated_header,
    "truncated_packet.pcapng": build_truncated_packet,
    "mixed_link_types.pcapng": build_mixed_link_types,
    "unsupported_link_type.pcapng": build_unsupported_link_type,
    "mixed_ip_versions.pcapng": build_mixed_ip_versions,
    "fragmented_ip.pcap": build_fragmented_ip,
}


def generate(out_dir: Path) -> list[Path]:
    """Write every defect fixture into ``out_dir`` and return the paths."""

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, builder in BUILDERS.items():
        path = out_dir / name
        path.write_bytes(builder())
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deformed capture fixtures.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "tests"
        / "fixtures"
        / "defects",
        help="output directory",
    )
    args = parser.parse_args(argv)
    for path in generate(args.out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
