"""Generate a synthetic PCAP matching the reference load profile.

The profile from the specification is Linux x86-64, 4 vCPU, 8 GB RAM, up to
100 MiB PCAP, 250k packets, 1000 TCP sessions, 100k messages, responses up to
64 KiB. This script builds a capture of that shape so the engine can be
measured against it.

The capture is written to a scratch location and is never committed. Defaults
match the profile; use the flags to build a smaller capture for a quick check.

    python -m scripts.generate_benchmark_pcap --out .benchmark/profile.pcapng
"""

from __future__ import annotations

import argparse
import io
import random
from pathlib import Path

import dpkt

from scripts.generate_fixture import segment

_CLIENT_IP = "10.1.0.1"
_SERVER_IP = "10.1.0.2"
_BASE_TS = 1_700_000_000.0

PROFILE_PACKETS = 250_000
PROFILE_SESSIONS = 1_000
PROFILE_TARGET_MIB = 100
PROFILE_MAX_RESPONSE = 64 * 1024


def _frame(
    forward: bool,
    client_port: int,
    seq_a: int,
    seq_b: int,
    flags: int,
    payload: bytes,
) -> bytes:
    if forward:
        return segment(
            src_ip=_CLIENT_IP,
            src_port=client_port,
            dst_ip=_SERVER_IP,
            dst_port=9000,
            seq=seq_a,
            ack=seq_b,
            flags=flags,
            payload=payload,
        )
    return segment(
        src_ip=_SERVER_IP,
        src_port=9000,
        dst_ip=_CLIENT_IP,
        dst_port=client_port,
        seq=seq_b,
        ack=seq_a,
        flags=flags,
        payload=payload,
    )


def build(
    packets: int,
    sessions: int,
    target_mib: int,
    max_response: int,
    seed: int = 7,
) -> bytes:
    """Build a capture with the requested shape and return its bytes.

    Payload size per exchange is chosen so that, once the session and message
    counts are fixed, the total comes close to ``target_mib``.
    """

    rng = random.Random(seed)
    target_bytes = target_mib * 1024 * 1024

    per_session = max(packets // sessions, 8)
    # Rough payload budget per response, leaving room for headers and pcapng
    # block overhead. Only half of the data packets are responses, and the
    # response size is drawn between half and all of the budget.
    data_packets = sessions * per_session
    payload_budget = max(2 * target_bytes // max(data_packets, 1), 16)
    payload_size = min(payload_budget, max_response)

    buf = io.BytesIO()
    writer = dpkt.pcapng.Writer(buf)
    ts = _BASE_TS
    written = 0

    for session in range(sessions):
        if written >= packets:
            break
        client_port = 40000 + (session % 20000)
        isn_a = rng.randint(0, 0x7FFFFFFF)
        isn_b = rng.randint(0, 0x7FFFFFFF)
        seq_a = isn_a + 1
        seq_b = isn_b + 1

        handshake = [
            (isn_a, 0, dpkt.tcp.TH_SYN, b"", True),
            (isn_b, isn_a + 1, dpkt.tcp.TH_SYN | dpkt.tcp.TH_ACK, b"", False),
            (isn_a + 1, isn_b + 1, dpkt.tcp.TH_ACK, b"", True),
        ]
        for seq, ack, flags, payload, forward in handshake:
            ts += 0.0005
            frame = segment(
                src_ip=_CLIENT_IP if forward else _SERVER_IP,
                src_port=client_port if forward else 9000,
                dst_ip=_SERVER_IP if forward else _CLIENT_IP,
                dst_port=9000 if forward else client_port,
                seq=seq,
                ack=ack,
                flags=flags,
                payload=payload,
            )
            writer.writepkt(frame, ts=ts)
            written += 1

        exchanges = (per_session - 4) // 2
        for _ in range(exchanges):
            if written + 2 > packets:
                break
            size = rng.randint(payload_size // 2, payload_size) if payload_size > 8 else 8
            request = bytes(rng.getrandbits(8) for _ in range(8))
            response = bytes(rng.getrandbits(8) for _ in range(size))

            ts += 0.0005
            writer.writepkt(
                _frame(
                    True,
                    client_port,
                    seq_a,
                    seq_b,
                    dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
                    request,
                ),
                ts=ts,
            )
            seq_a += len(request)
            written += 1

            ts += 0.0005
            writer.writepkt(
                _frame(
                    False,
                    client_port,
                    seq_a,
                    seq_b,
                    dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
                    response,
                ),
                ts=ts,
            )
            seq_b += len(response)
            written += 1

        ts += 0.0005
        writer.writepkt(
            _frame(True, client_port, seq_a, seq_b, dpkt.tcp.TH_FIN | dpkt.tcp.TH_ACK, b""),
            ts=ts,
        )
        written += 1

    data = buf.getvalue()
    buf.close()
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a benchmark capture.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(".benchmark") / "profile.pcapng",
        help="output capture path",
    )
    parser.add_argument("--packets", type=int, default=PROFILE_PACKETS)
    parser.add_argument("--sessions", type=int, default=PROFILE_SESSIONS)
    parser.add_argument("--target-mib", type=int, default=PROFILE_TARGET_MIB)
    parser.add_argument("--max-response", type=int, default=PROFILE_MAX_RESPONSE)
    args = parser.parse_args(argv)

    data = build(args.packets, args.sessions, args.target_mib, args.max_response)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(f"{args.out}: {len(data)} bytes ({len(data) / (1024 * 1024):.2f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
