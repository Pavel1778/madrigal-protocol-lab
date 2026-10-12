"""Reading of PCAP and PCAPNG captures into a stream of network packets.

Both container formats are read with :mod:`dpkt`. It handles classic pcap and
pcapng without an external process, unlike PyShark which shells out to tshark
and would require tshark on every machine that opens a capture. dpkt is also
lighter and faster than scapy for the reference workload of up to 250k packets.

IPv4 and IPv6 over Ethernet (raw IP and the Linux cooked and BSD loopback
families are also accepted) are interpreted. Other link-layer types are
reported as diagnostics rather than raising, so a mixed capture still yields
every TCP session that can be read. Fragmented datagrams of either version are
reported as ``ip_fragment`` and not reassembled: reassembly is a separate task.
"""

from __future__ import annotations

import io
import logging
import socket
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import dpkt

logger = logging.getLogger(__name__)

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

# IPv6 next-header value for the fragment header (RFC 8200).
_IPPROTO_FRAGMENT = 44

_SUPPORTED_LINKTYPES = {_DLT_NULL, _DLT_EN10MB, _DLT_RAW, _DLT_LOOP, _DLT_LINUX_SLL}

_PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"

# Classic pcap starts with one of four magic byte orders.
_PCAP_MAGICS = (
    b"\xd4\xc3\xb2\xa1",
    b"\xa1\xb2\xc3\xd4",
    b"\x4d\x3c\xb2\xa1",
    b"\xa1\xb2\x3c\x4d",
)


def _looks_like_capture(path: Path) -> bool:
    """Whether the first bytes mark the file as a pcap or pcapng capture."""

    try:
        with path.open("rb") as handle:
            magic = handle.read(4)
    except OSError:
        return False
    return magic == _PCAPNG_MAGIC or magic in _PCAP_MAGICS


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


def _open_reader(path: Path) -> tuple[BinaryIO, dpkt.pcap.Reader | dpkt.pcapng.Reader]:
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


def _ip6_to_str(raw: bytes) -> str:
    return socket.inet_ntop(socket.AF_INET6, raw)


def _layer3_ip(linktype: int, buf: bytes) -> tuple[int, bytes] | Diagnostic:
    """Return ``(version, datagram)`` of a frame, or a diagnostic.

    ``version`` is 4 or 6. Non-IP frames and frames too short to hold a header
    are returned as diagnostics, never as data.
    """

    if linktype == _DLT_EN10MB:
        eth = dpkt.ethernet.Ethernet(buf)
        if isinstance(eth.data, dpkt.ip6.IP6):
            return 6, bytes(eth.data)
        if not isinstance(eth.data, dpkt.ip.IP):
            return Diagnostic("non_ip", detail=f"non-IP ethertype {eth.type:#06x}")
        return 4, bytes(eth.data)
    if linktype == _DLT_RAW:
        if len(buf) < 1:
            return Diagnostic("truncated_frame", detail="empty raw frame")
        version = buf[0] >> 4
        if version not in (4, 6):
            return Diagnostic("non_ip", detail=f"raw frame IP version {version}")
        return version, buf
    if linktype in (_DLT_NULL, _DLT_LOOP):
        if len(buf) < 4:
            return Diagnostic("truncated_frame", detail="short loopback header")
        return _raw_version(buf[4:])
    if linktype == _DLT_LINUX_SLL:
        if len(buf) < 16:
            return Diagnostic("truncated_frame", detail="short cooked header")
        return _raw_version(buf[16:])
    return Diagnostic("unsupported_linktype", detail=f"datalink {linktype}")


def _raw_version(payload: bytes) -> tuple[int, bytes] | Diagnostic:
    """Read the IP version of a headerless datagram, or report why not."""

    if not payload:
        return Diagnostic("truncated_frame", detail="empty IP datagram")
    version = payload[0] >> 4
    if version not in (4, 6):
        return Diagnostic("non_ip", detail=f"IP version {version}")
    return version, payload


@dataclass(slots=True)
class _TcpRecord:
    src_ip: str
    dst_ip: str
    tcp: dpkt.tcp.TCP
    payload: bytes
    truncated: bool


def _parse_tcp(ip_bytes: bytes, version: int = 4) -> _TcpRecord | Diagnostic:
    """Parse an IP datagram into a TCP record or a diagnostic.

    IPv4 and IPv6 are both accepted. A fragmented datagram of either version is
    reported as ``ip_fragment`` and not reassembled.
    """

    if version == 6:
        return _parse_tcp6(ip_bytes)
    return _parse_tcp4(ip_bytes)


def _parse_tcp4(ip_bytes: bytes) -> _TcpRecord | Diagnostic:
    """Parse an IPv4 datagram into a TCP record or a diagnostic."""

    try:
        ip = dpkt.ip.IP(ip_bytes)
    except (dpkt.UnpackError, struct.error) as exc:
        return Diagnostic("truncated_frame", detail=f"IPv4 parse failed: {exc}")
    if isinstance(ip.data, dpkt.ip6.IP6):
        return Diagnostic("non_ip", detail="IPv6 packet on an IPv4 datagram")
    if ip.offset or ip.mf:
        # Fragments are reported, not reassembled. Only the first fragment
        # carries a TCP header, and the specification excludes reassembly.
        return Diagnostic(
            "ip_fragment",
            detail=f"IP fragment at offset {ip.offset} ignored",
        )
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


def _parse_tcp6(ip_bytes: bytes) -> _TcpRecord | Diagnostic:
    """Parse an IPv6 datagram into a TCP record or a diagnostic.

    ``dpkt`` walks the extension-header chain and leaves the transport header in
    ``ip.data``. The chain is kept in ``ip.extension_hdrs``; a fragment header
    there (protocol 44) marks a fragmented datagram, which is reported and not
    reassembled.
    """

    try:
        ip = dpkt.ip6.IP6(ip_bytes)
    except (dpkt.UnpackError, struct.error) as exc:
        return Diagnostic("truncated_frame", detail=f"IPv6 parse failed: {exc}")
    fragment = ip.extension_hdrs.get(_IPPROTO_FRAGMENT)
    if fragment is not None and (fragment.frag_off or fragment.m_flag):
        return Diagnostic(
            "ip_fragment",
            detail=f"IPv6 fragment at offset {fragment.frag_off} ignored",
        )
    if not isinstance(ip.data, dpkt.tcp.TCP):
        return Diagnostic("non_tcp", detail=f"IPv6 next header {ip.nxt}")
    tcp = ip.data
    payload = bytes(tcp.data)
    header_bytes = max(tcp.off * 4, 0)
    expected_payload = max(int(ip.plen) - header_bytes, 0)
    return _TcpRecord(
        src_ip=_ip6_to_str(ip.src),
        dst_ip=_ip6_to_str(ip.dst),
        tcp=tcp,
        payload=payload,
        truncated=len(payload) < expected_payload,
    )


def _pcapng_linktypes(path: Path) -> list[int]:
    """Collect every interface link type declared in a pcapng file.

    ``dpkt`` keeps only the first Interface Description Block, so a file whose
    interfaces declare different link types would otherwise look uniform. This
    walks the block stream for the declared types and ignores the per-packet
    type, which is a different field.
    """

    with path.open("rb") as handle:
        if handle.read(4) != _PCAPNG_MAGIC:
            return []
        handle.seek(8)
        bom = handle.read(4)
        little = bom == b"\x4d\x3c\x2b\x1a"
        endian = "<" if little else ">"
        # Skip the section header block before walking the rest.
        handle.seek(0)
        header = handle.read(8)
        if len(header) < 8:
            return []
        _, shb_len = struct.unpack(f"{endian}II", header)
        handle.seek(shb_len)
        linktypes: list[int] = []
        while True:
            header = handle.read(8)
            if len(header) < 8:
                break
            block_type, block_len = struct.unpack(f"{endian}II", header)
            if block_len < 12:
                break
            if block_type == 1 and block_len >= 20:
                body = handle.read(block_len - 8)
                if len(body) < 12:
                    break
                linktypes.append(struct.unpack(f"{endian}H", body[:2])[0])
            else:
                handle.seek(block_len - 8, io.SEEK_CUR)
    return linktypes


def _read_rows(path: Path, torn: list[str]) -> Iterator[tuple[float, bytes]]:
    """Yield ``(timestamp, frame)`` without letting a torn tail escape.

    A capture whose last block was cut short raises from the underlying reader
    at the point of the tear. The rows before the tear are still valid, so they
    are yielded and the reason is appended to ``torn``.
    """

    handle, reader = _open_reader(path)
    try:
        while True:
            try:
                row = next(reader)
            except StopIteration:
                return
            except Exception as exc:
                torn.append(str(exc))
                return
            yield row
    finally:
        handle.close()


def read_capture(
    path: Path,
    diagnostics: list[Diagnostic] | None = None,
    *,
    verify_checksums: bool = False,
) -> Iterator[Packet]:
    """Read ``path`` and yield every TCP/IP packet in file order.

    A capture with defects is read as far as it can be, and every part that
    could not be read becomes a diagnostic of type ``truncated_frame``,
    ``unsupported_linktype``, ``non_ip``, ``ip_fragment``, or ``non_tcp``.
    A file that is not a capture at all raises ``ValueError``.

    If a list is passed as ``diagnostics``, notes about skipped link types,
    fragments, and non-TCP frames are appended to it; the iterator is
    unaffected either way.

    Checksum offloading on the sending host leaves wrong checksums in many
    captured files, so checksums are not verified by default. When
    ``verify_checksums`` is true, ``Packet.checksum_valid`` is set per packet
    and the caller decides what to do with a mismatch.
    """

    if diagnostics is None:
        diagnostics = []

    _report_mixed_linktypes(path, diagnostics)

    try:
        handle, reader = _open_reader(path)
    except OSError:
        # A missing file, a directory, or a permission problem: the path itself
        # is wrong, which is the caller's error, not a capture defect.
        raise
    except Exception as exc:
        if _looks_like_capture(path):
            # A recognizable but damaged file is reported, not raised.
            logger.warning("capture header is invalid: %s", exc)
            diagnostics.append(
                Diagnostic(
                    "truncated_frame", detail=f"capture header is invalid: {exc}"
                )
            )
            return
        # Not a capture at all. A file too short to hold a magic number makes
        # dpkt raise NeedData; normalise every such failure to ValueError so a
        # caller has one exception to handle.
        raise ValueError(f"{path} is not a readable capture: {exc}") from exc
    try:
        linktype = _reader_datalink(reader)
        if linktype not in _SUPPORTED_LINKTYPES:
            diagnostics.append(
                Diagnostic("unsupported_linktype", detail=f"datalink {linktype}")
            )
            return
        index = 0
        torn: list[str] = []
        for packet_index, (timestamp, buf) in enumerate(_read_rows(path, torn), start=1):
            packet = _packet_from_row(
                linktype,
                buf,
                index=index,
                packet_index=packet_index,
                timestamp=timestamp,
                verify_checksums=verify_checksums,
                diagnostics=diagnostics,
            )
            if packet is None:
                continue
            yield packet
            index += 1
    finally:
        handle.close()
    if torn:
        diagnostics.append(
            Diagnostic(
                "truncated_frame",
                detail=f"capture ended mid-block: {torn[0]}",
            )
        )


def _report_mixed_linktypes(path: Path, diagnostics: list[Diagnostic]) -> None:
    """Note a capture that declares more than one link type."""

    declared = _pcapng_linktypes(path)
    if len(set(declared)) > 1:
        logger.warning("capture declares link types %s", sorted(set(declared)))
        diagnostics.append(
            Diagnostic(
                "unsupported_linktype",
                detail=f"capture mixes link types {sorted(set(declared))}",
            )
        )


def _reader_datalink(reader: Any) -> int:
    """Return the link type of an open reader as an int."""

    value = reader.datalink() if callable(reader.datalink) else reader.datalink
    return int(value)


def _packet_from_row(
    linktype: int,
    buf: bytes,
    *,
    index: int,
    packet_index: int,
    timestamp: Any,
    verify_checksums: bool,
    diagnostics: list[Diagnostic],
) -> Packet | None:
    """Turn one raw frame into a packet, or record why it was skipped.

    Returns ``None`` when the frame is non-IP or non-TCP; the reason is
    appended to ``diagnostics``.
    """

    layer3 = _layer3_ip(linktype, buf)
    if isinstance(layer3, Diagnostic):
        layer3.packet_index = packet_index
        diagnostics.append(layer3)
        return None
    version, ip_bytes = layer3
    record = _parse_tcp(ip_bytes, version)
    if isinstance(record, Diagnostic):
        record.packet_index = packet_index
        diagnostics.append(record)
        return None
    tcp = record.tcp
    if record.truncated:
        diagnostics.append(
            Diagnostic(
                "truncated_packet",
                packet_index=packet_index,
                detail="captured payload is shorter than the header declares",
            )
        )
    checksum_valid = (
        _checksum_state(tcp, ip_bytes, version) if verify_checksums else None
    )
    return Packet(
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


def _checksum_state(tcp: Any, ip_bytes: bytes, version: int = 4) -> bool | None:
    """Return the TCP checksum verdict, or ``None`` when it cannot be read."""

    try:
        if tcp.sum == 0:
            return True
        return _tcp_checksum_ok(ip_bytes, version)
    except Exception:
        return None


def _tcp_checksum_ok(ip_bytes: bytes, version: int = 4) -> bool:
    """Return whether the TCP checksum of an IP datagram is correct."""

    if version == 6:
        return _tcp_checksum_ok6(ip_bytes)
    return _tcp_checksum_ok4(ip_bytes)


def _tcp_checksum_ok4(ip_bytes: bytes) -> bool:
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


def _tcp_checksum_ok6(ip_bytes: bytes) -> bool:
    """Return whether the TCP checksum of an IPv6 datagram is correct.

    The pseudo-header is built here because dpkt 1.9.8 ships no IPv6 checksum
    helper. A datagram whose extension headers are present is left unverified:
    the transport offset inside the pseudo-header would have to be recomputed.
    """

    ip = dpkt.ip6.IP6(ip_bytes)
    tcp = ip.data
    if not isinstance(tcp, dpkt.tcp.TCP):
        return True
    if ip.extension_hdrs:
        return True
    saved = tcp.sum
    tcp.sum = 0
    tcp_bytes = bytes(tcp)
    tcp.sum = saved
    pseudo = (
        bytes(ip.src)
        + bytes(ip.dst)
        + struct.pack("!I", len(tcp_bytes))
        + b"\x00\x00\x00"
        + bytes([ip.nxt])
    )
    return dpkt.in_cksum(pseudo + tcp_bytes) == saved
