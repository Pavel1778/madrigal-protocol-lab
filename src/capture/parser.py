"""Reading of PCAP and PCAPNG captures into a stream of network packets.

Both container formats are read with :mod:`dpkt`. It handles classic pcap and
pcapng without an external process, unlike PyShark which shells out to tshark
and would require tshark on every machine that opens a capture. dpkt is also
lighter and faster than scapy for the reference workload of up to 250k packets.

Only IPv4 over Ethernet (raw IP and the Linux cooked and BSD loopback families
are also accepted) is interpreted. Other link-layer types and IPv6 packets are
reported as diagnostics rather than raising, so a mixed capture still yields
every TCP session that can be read.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

import dpkt

# TCP flag bits, re-exported for callers that classify packets.
TH_FIN = 0x01
TH_SYN = 0x02
TH_RST = 0x04
TH_PSH = 0x08
TH_ACK = 0x10

_DLT_NULL = 0
_DLT_EN10MB = 1
_DLT_RAW = 12
_DLT_LOOP = 108
_DLT_LINUX_SLL = 113

_SUPPORTED_LINKTYPES = {_DLT_NULL, _DLT_EN10MB, _DLT_RAW, _DLT_LOOP, _DLT_LINUX_SLL}

_PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"


@dataclass(slots=True)
class Diagnostic:
    """A note about data that could not be read, or about a stream defect.

    Diagnostics never stop the read. They exist so that unreadable data, gaps,
    and conflicting overlaps are shown explicitly instead of being silently
    dropped or filled with guessed bytes.
    """

    type: str
    packet_index: int | None = None
    offset: int | None = None
    length: int | None = None
    detail: str = ""

    def to_contract(self) -> dict[str, object]:
        out: dict[str, object] = {"type": self.type}
        if self.offset is not None:
            out["offset"] = self.offset
        if self.length is not None:
            out["length"] = self.length
        if self.packet_index is not None:
            out["packet_index"] = self.packet_index
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass(slots=True)
class Packet:
    """One TCP segment with the header fields needed for reassembly.

    ``seq`` and ``ack`` are the raw 32-bit values from the header. ``payload``
    holds only the TCP payload. ``index`` is the position of this packet among
    the packets yielded, which is the identifier used for provenance.
    ``checksum_valid`` is ``None`` unless checksum verification was requested.
    """

    index: int
    timestamp: float
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    seq: int
    ack: int
    flags: int
    payload: bytes
    is_truncated: bool = False
    checksum_valid: bool | None = None

    @property
    def syn(self) -> bool:
        return bool(self.flags & TH_SYN)

    @property
    def fin(self) -> bool:
        return bool(self.flags & TH_FIN)

    @property
    def rst(self) -> bool:
        return bool(self.flags & TH_RST)

    @property
    def ack_flag(self) -> bool:
        return bool(self.flags & TH_ACK)

    @property
    def payload_len(self) -> int:
        return len(self.payload)


def _open_reader(path: Path) -> tuple[BinaryIO, "dpkt.pcap.Reader | dpkt.pcapng.Reader"]:
    """Open ``path`` as pcap or pcapng and return the handle and reader."""

    with path.open("rb") as probe:
        magic = probe.read(4)

    handle = path.open("rb")
    try:
        if magic == _PCAPNG_MAGIC:
            reader: dpkt.pcap.Reader | dpkt.pcapng.Reader = dpkt.pcapng.Reader(handle)
        else:
            reader = dpkt.pcap.Reader(handle)
    except Exception:
        handle.close()
        raise
    return handle, reader


def _ip_to_str(raw: bytes) -> str:
    return ".".join(str(b) for b in raw)


def _layer3_ip(linktype: int, buf: bytes) -> "bytes | Diagnostic":
    """Return the IPv4 datagram bytes of a frame, or a diagnostic.

    IPv6 and non-IP frames are returned as diagnostics, never as data.
    """

    if linktype == _DLT_EN10MB:
        eth = dpkt.ethernet.Ethernet(buf)
        if isinstance(eth.data, dpkt.ip6.IP6):
            return Diagnostic("ipv6_ignored", detail="IPv6 packet skipped")
        if not isinstance(eth.data, dpkt.ip.IP):
            return Diagnostic("non_ip", detail=f"non-IPv4 ethertype {eth.type:#06x}")
        return bytes(eth.data)
    if linktype == _DLT_RAW:
        if len(buf) < 1:
            return Diagnostic("truncated_frame", detail="empty raw frame")
        if buf[0] >> 4 != 4:
            return Diagnostic("ipv6_ignored", detail="non-IPv4 raw frame")
        return buf
    if linktype in (_DLT_NULL, _DLT_LOOP):
        if len(buf) < 4:
            return Diagnostic("truncated_frame", detail="short loopback header")
        return buf[4:]
    if linktype == _DLT_LINUX_SLL:
        if len(buf) < 16:
            return Diagnostic("truncated_frame", detail="short cooked header")
        return buf[16:]
    return Diagnostic("unsupported_linktype", detail=f"datalink {linktype}")


@dataclass(slots=True)
class _TcpRecord:
    src_ip: str
    dst_ip: str
    tcp: dpkt.tcp.TCP
    payload: bytes
    truncated: bool


def _parse_tcp(ip_bytes: bytes) -> "_TcpRecord | Diagnostic":
    """Parse an IPv4 datagram into a TCP record or a diagnostic."""

    try:
        ip = dpkt.ip.IP(ip_bytes)
    except (dpkt.UnpackError, struct.error) as exc:
        return Diagnostic("truncated_frame", detail=f"IPv4 parse failed: {exc}")
    if isinstance(ip.data, dpkt.ip6.IP6):
        return Diagnostic("ipv6_ignored", detail="IPv6 packet skipped")
    if not isinstance(ip.data, dpkt.tcp.TCP):
        return Diagnostic("non_tcp", detail=f"IP protocol {ip.p}")
    tcp = ip.data
    payload = bytes(tcp.data)
    header_bytes = max(ip.hl * 4 + tcp.off * 4, 0)
    expected_payload = max(int(ip.len) - header_bytes, 0)
    return _TcpRecord(
        src_ip=_ip_to_str(ip.src),
        dst_ip=_ip_to_str(ip.dst),
        tcp=tcp,
        payload=payload,
        truncated=len(payload) < expected_payload,
    )


def read_capture(
    path: Path,
    diagnostics: list[Diagnostic] | None = None,
    *,
    verify_checksums: bool = False,
) -> Iterator[Packet]:
    """Read ``path`` and yield every TCP/IPv4 packet in file order.

    If a list is passed as ``diagnostics``, notes about skipped link types,
    IPv6, and non-TCP frames are appended to it; the iterator is unaffected
    either way.

    Checksum offloading on the sending host leaves wrong checksums in many
    captured files, so checksums are not verified by default. When
    ``verify_checksums`` is true, ``Packet.checksum_valid`` is set per packet
    and the caller decides what to do with a mismatch.
    """

    if diagnostics is None:
        diagnostics = []

    handle, reader = _open_reader(path)
    try:
        linktype = reader.datalink() if callable(reader.datalink) else reader.datalink
        linktype = int(linktype)
        if linktype not in _SUPPORTED_LINKTYPES:
            diagnostics.append(
                Diagnostic("unsupported_linktype", detail=f"datalink {linktype}")
            )
            return
        index = 0
        packet_index = 0
        for timestamp, buf in reader:
            packet_index += 1
            ip_bytes = _layer3_ip(linktype, buf)
            if isinstance(ip_bytes, Diagnostic):
                ip_bytes.packet_index = packet_index
                diagnostics.append(ip_bytes)
                continue
            record = _parse_tcp(ip_bytes)
            if isinstance(record, Diagnostic):
                record.packet_index = packet_index
                diagnostics.append(record)
                continue
            tcp = record.tcp
            checksum_valid: bool | None = None
            if verify_checksums:
                try:
                    checksum_valid = bool(tcp.sum == 0 or _tcp_checksum_ok(ip_bytes))
                except Exception:
                    checksum_valid = None
            yield Packet(
                index=index,
                timestamp=float(timestamp),
                src_ip=record.src_ip,
                src_port=int(tcp.sport),
                dst_ip=record.dst_ip,
                dst_port=int(tcp.dport),
                seq=int(tcp.seq),
                ack=int(tcp.ack),
                flags=int(tcp.flags),
                payload=record.payload,
                is_truncated=record.truncated,
                checksum_valid=checksum_valid,
            )
            index += 1
    finally:
        handle.close()


def _tcp_checksum_ok(ip_bytes: bytes) -> bool:
    """Return whether the TCP checksum of an IPv4 datagram is correct."""

    ip = dpkt.ip.IP(ip_bytes)
    tcp = ip.data
    if not isinstance(tcp, dpkt.tcp.TCP):
        return True
    saved = tcp.sum
    tcp.sum = 0
    computed = dpkt.in_cksum(bytes(tcp))
    tcp.sum = saved
    return computed == saved
