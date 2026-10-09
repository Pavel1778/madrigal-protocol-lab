"""Generate the research corpus used for rule authoring and demonstrations.

The corpus is not the unit-test fixture set. The fixtures isolate one behaviour
each; the corpus is a small but realistic set of related captures of a single
device, together with an action journal that ties every transaction to the
packet timestamps in the captures.

Contents (written to ``tests/corpus`` by default):

- ``corpus_capture_01.pcapng`` — the primary recording: one device, three TCP
  sessions covering reads, writes, and measurements with variable-length
  responses.
- ``corpus_capture_02.pcapng`` — a second recording of the same device with
  different parameters and values, meant for applying a rule to new data.
- ``corpus_capture_defects.pcapng`` — a recording carrying the usual capture
  defects: a retransmission, out-of-order delivery, a gap, and a conflicting
  overlap.
- ``corpus_journal.md`` — the action journal, one line per transaction in the
  form ``timestamp | action | parameter | result``.
- ``README.md`` — what the corpus is and how to use it.

The corpus is generated deterministically from a fixed seed, so regenerating it
reproduces the same bytes. Use ``--scale`` to build a larger corpus on demand;
that larger corpus is for local experiments and is not committed.

Wire protocol (undocumented, binary, over TCP):

    request:  byte 0   command      0x01 read, 0x02 write, 0x03 measurement
              byte 1   flags        reserved, zero in this corpus
              byte 2-3 payload_len  big-endian, length of the payload
              byte 4.. payload

    response: byte 0   command      echo of the request command
              byte 1   status       0x00 ok, 0x01 error
              byte 2-3 body_len     big-endian, length of the body
              byte 4.. body

    read request payload:      param_id (1 byte)
    read response body:        param_id (1 byte) + value (2 bytes, big-endian)

    write request payload:     param_id (1 byte) + value (2 bytes, big-endian)
    write response body:       param_id (1 byte) + applied value (2 bytes)

    measurement request:       sensor_id (1 byte)
    measurement response body: sensor_id (1 byte) + sample_count (1 byte)
                               + sample_count * 2 bytes (big-endian)
"""

from __future__ import annotations

import argparse
import io
import random
from dataclasses import dataclass, field
from pathlib import Path

import dpkt

from scripts.generate_fixture import segment

# --- protocol -----------------------------------------------------------------

CMD_READ = 0x01
CMD_WRITE = 0x02
CMD_MEASURE = 0x03

STATUS_OK = 0x00
STATUS_ERROR = 0x01

FLAG_NONE = 0x00

PARAM_IDS = {
    "temperature": 0x10,
    "humidity": 0x11,
    "voltage": 0x12,
    "gain": 0x13,
    "threshold": 0x14,
    "mode": 0x15,
    "sample_rate": 0x16,
}
PARAM_NAMES = {v: k for k, v in PARAM_IDS.items()}

SENSOR_IDS = {
    "channel_a": 0x20,
    "channel_b": 0x21,
    "probe": 0x22,
}
SENSOR_NAMES = {v: k for k, v in SENSOR_IDS.items()}

_CLIENT_IP = "10.0.0.1"
_SERVER_IP = "10.0.0.2"
_BASE_TS = 1_700_000_000.0


def request(command: int, payload: bytes, flags: int = FLAG_NONE) -> bytes:
    return bytes([command, flags]) + len(payload).to_bytes(2, "big") + payload


def response(command: int, status: int, body: bytes) -> bytes:
    return bytes([command, status]) + len(body).to_bytes(2, "big") + body


def read_request(param_id: int) -> bytes:
    return request(CMD_READ, bytes([param_id]))


def read_response(param_id: int, value: int) -> bytes:
    return response(CMD_READ, STATUS_OK, bytes([param_id]) + value.to_bytes(2, "big"))


def write_request(param_id: int, value: int) -> bytes:
    return request(CMD_WRITE, bytes([param_id]) + value.to_bytes(2, "big"))


def write_response(param_id: int, value: int) -> bytes:
    return response(CMD_WRITE, STATUS_OK, bytes([param_id]) + value.to_bytes(2, "big"))


def measure_request(sensor_id: int) -> bytes:
    return request(CMD_MEASURE, bytes([sensor_id]))


def measure_response(sensor_id: int, samples: list[int]) -> bytes:
    body = bytes([sensor_id, len(samples)]) + b"".join(
        s.to_bytes(2, "big") for s in samples
    )
    return response(CMD_MEASURE, STATUS_OK, body)


# --- dialogue builder ---------------------------------------------------------


@dataclass
class JournalEntry:
    timestamp: float
    action: str
    parameter: str
    result: str


@dataclass
class Dialogue:
    """Builds one TCP session and records its transactions."""

    client_ip: str
    server_ip: str
    client_port: int
    server_port: int
    client_isn: int
    server_isn: int
    flags_base: int
    ts: float
    frames: list[tuple[float, bytes]] = field(default_factory=list)
    journal: list[JournalEntry] = field(default_factory=list)
    last_request_ts: float = field(init=False)
    _seq_a: int = field(init=False)
    _seq_b: int = field(init=False)

    def __post_init__(self) -> None:
        self._seq_a = self.client_isn + 1
        self._seq_b = self.server_isn + 1
        self.last_request_ts = self.ts

    def _tick(self) -> float:
        self.ts += 0.001
        return self.ts

    def _client_frame(self, seq: int, ack: int, flags: int, payload: bytes) -> bytes:
        return segment(
            src_ip=self.client_ip,
            src_port=self.client_port,
            dst_ip=self.server_ip,
            dst_port=self.server_port,
            seq=seq,
            ack=ack,
            flags=flags,
            payload=payload,
        )

    def _server_frame(self, seq: int, ack: int, flags: int, payload: bytes) -> bytes:
        return segment(
            src_ip=self.server_ip,
            src_port=self.server_port,
            dst_ip=self.client_ip,
            dst_port=self.client_port,
            seq=seq,
            ack=ack,
            flags=flags,
            payload=payload,
        )

    def handshake(self) -> None:
        self.frames.append(
            (
                self._tick(),
                self._client_frame(
                    self.client_isn, 0, dpkt.tcp.TH_SYN, b""
                ),
            )
        )
        self.frames.append(
            (
                self._tick(),
                self._server_frame(
                    self.server_isn,
                    self.client_isn + 1,
                    dpkt.tcp.TH_SYN | dpkt.tcp.TH_ACK,
                    b"",
                ),
            )
        )
        self.frames.append(
            (
                self._tick(),
                self._client_frame(
                    self.client_isn + 1,
                    self.server_isn + 1,
                    dpkt.tcp.TH_ACK,
                    b"",
                ),
            )
        )

    def exchange(self, req: bytes, resp: bytes) -> None:
        """One request from the client followed by one response from the device."""

        ts = self._tick()
        self.frames.append(
            (
                ts,
                self._client_frame(
                    self._seq_a,
                    self._seq_b,
                    dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
                    req,
                ),
            )
        )
        self.last_request_ts = ts
        self._seq_a += len(req)

        self.frames.append(
            (
                self._tick(),
                self._server_frame(
                    self._seq_b,
                    self._seq_a,
                    dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
                    resp,
                ),
            )
        )
        self._seq_b += len(resp)

    def raw_client(self, payload: bytes) -> None:
        ts = self._tick()
        self.last_request_ts = ts
        self.frames.append(
            (
                ts,
                self._client_frame(
                    self._seq_a,
                    self._seq_b,
                    dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
                    payload,
                ),
            )
        )
        self._seq_a += len(payload)

    def raw_server(self, payload: bytes) -> None:
        self.frames.append(
            (
                self._tick(),
                self._server_frame(
                    self._seq_b,
                    self._seq_a,
                    dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH,
                    payload,
                ),
            )
        )
        self._seq_b += len(payload)

    def client_segment(self, seq: int, payload: bytes, when: float | None = None) -> float:
        """Inject a client segment at an explicit sequence number."""

        when = self._tick() if when is None else when
        self.frames.append(
            (
                when,
                self._client_frame(
                    seq, self._seq_b, dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH, payload
                ),
            )
        )
        return when

    def server_segment(self, seq: int, payload: bytes, when: float | None = None) -> float:
        """Inject a server segment at an explicit sequence number."""

        when = self._tick() if when is None else when
        self.frames.append(
            (
                when,
                self._server_frame(
                    seq, self._seq_a, dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH, payload
                ),
            )
        )
        return when

    def close(self) -> None:
        self.frames.append(
            (
                self._tick(),
                self._client_frame(
                    self._seq_a, self._seq_b, dpkt.tcp.TH_FIN | dpkt.tcp.TH_ACK, b""
                ),
            )
        )
        self.frames.append(
            (
                self._tick(),
                self._server_frame(
                    self._seq_b, self._seq_a + 1, dpkt.tcp.TH_FIN | dpkt.tcp.TH_ACK, b""
                ),
            )
        )

    def record(self, action: str, parameter: str, result: str) -> None:
        self.journal.append(
            JournalEntry(
                timestamp=self.last_request_ts,
                action=action,
                parameter=parameter,
                result=result,
            )
        )


def _write_pcapng(frames: list[tuple[float, bytes]]) -> bytes:
    buf = io.BytesIO()
    writer = dpkt.pcapng.Writer(buf)
    for ts, frame in frames:
        writer.writepkt(frame, ts=ts)
    data = buf.getvalue()
    buf.close()
    return data


def _port_pair(index: int) -> tuple[int, int]:
    return 40000 + index * 7, 9000


# --- capture builders ---------------------------------------------------------


def build_capture_01(scale: int) -> tuple[bytes, list[JournalEntry]]:
    """Primary recording: reads, writes, and measurements on one device."""

    rng = random.Random(101)
    journal: list[JournalEntry] = []
    frames: list[tuple[float, bytes]] = []
    ts = _BASE_TS

    # Session 1: reads of several parameters.
    client_port, server_port = _port_pair(0)
    dialogue = Dialogue(
        client_ip=_CLIENT_IP,
        server_ip=_SERVER_IP,
        client_port=client_port,
        server_port=server_port,
        client_isn=1000,
        server_isn=50000,
        flags_base=0,
        ts=ts,
    )
    dialogue.handshake()
    for _ in range(scale):
        for name in ("temperature", "humidity", "voltage"):
            value = rng.randint(0, 4095)
            dialogue.exchange(
                read_request(PARAM_IDS[name]), read_response(PARAM_IDS[name], value)
            )
            dialogue.record("read", name, str(value))
    dialogue.close()
    frames.extend(dialogue.frames)
    journal.extend(dialogue.journal)
    ts = dialogue.ts

    # Session 2: writes of a parameter, with the device echoing the applied value.
    client_port, server_port = _port_pair(1)
    dialogue = Dialogue(
        client_ip=_CLIENT_IP,
        server_ip=_SERVER_IP,
        client_port=client_port,
        server_port=server_port,
        client_isn=20000,
        server_isn=60000,
        flags_base=0,
        ts=ts + 1.0,
    )
    dialogue.handshake()
    for _ in range(scale):
        for name in ("gain", "threshold", "mode"):
            value = rng.randint(0, 255)
            dialogue.exchange(
                write_request(PARAM_IDS[name], value),
                write_response(PARAM_IDS[name], value),
            )
            dialogue.record("write", name, f"applied {value}")
    dialogue.close()
    frames.extend(dialogue.frames)
    journal.extend(dialogue.journal)
    ts = dialogue.ts

    # Session 3: measurements with variable-length responses.
    client_port, server_port = _port_pair(2)
    dialogue = Dialogue(
        client_ip=_CLIENT_IP,
        server_ip=_SERVER_IP,
        client_port=client_port,
        server_port=server_port,
        client_isn=30000,
        server_isn=70000,
        flags_base=0,
        ts=ts + 1.0,
    )
    dialogue.handshake()
    for index in range(scale):
        name = ("channel_a", "channel_b", "probe")[index % 3]
        sample_count = rng.randint(1, 64)
        samples = [rng.randint(0, 4095) for _ in range(sample_count)]
        dialogue.exchange(
            measure_request(SENSOR_IDS[name]),
            measure_response(SENSOR_IDS[name], samples),
        )
        dialogue.record("measure", name, f"{sample_count} samples")
    dialogue.close()
    frames.extend(dialogue.frames)
    journal.extend(dialogue.journal)

    return _write_pcapng(frames), journal


def build_capture_02(scale: int) -> tuple[bytes, list[JournalEntry]]:
    """Second recording of the same device, different values and actions."""

    rng = random.Random(202)
    journal: list[JournalEntry] = []
    frames: list[tuple[float, bytes]] = []
    ts = _BASE_TS + 86_400.0

    # Session 1: reads with a different value range.
    client_port, server_port = _port_pair(3)
    dialogue = Dialogue(
        client_ip=_CLIENT_IP,
        server_ip=_SERVER_IP,
        client_port=client_port,
        server_port=server_port,
        client_isn=100000,
        server_isn=200000,
        flags_base=0,
        ts=ts,
    )
    dialogue.handshake()
    for _ in range(scale):
        for name in ("temperature", "sample_rate"):
            value = rng.randint(4096, 8191)
            dialogue.exchange(
                read_request(PARAM_IDS[name]), read_response(PARAM_IDS[name], value)
            )
            dialogue.record("read", name, str(value))
    dialogue.close()
    frames.extend(dialogue.frames)
    journal.extend(dialogue.journal)
    ts = dialogue.ts

    # Session 2: writes to different parameters.
    client_port, server_port = _port_pair(4)
    dialogue = Dialogue(
        client_ip=_CLIENT_IP,
        server_ip=_SERVER_IP,
        client_port=client_port,
        server_port=server_port,
        client_isn=110000,
        server_isn=210000,
        flags_base=0,
        ts=ts + 1.0,
    )
    dialogue.handshake()
    for _ in range(scale):
        for name in ("humidity", "voltage"):
            value = rng.randint(1000, 3999)
            dialogue.exchange(
                write_request(PARAM_IDS[name], value),
                write_response(PARAM_IDS[name], value),
            )
            dialogue.record("write", name, f"applied {value}")
    dialogue.close()
    frames.extend(dialogue.frames)
    journal.extend(dialogue.journal)

    return _write_pcapng(frames), journal


def build_capture_defects() -> tuple[bytes, list[JournalEntry]]:
    """A recording that carries the usual capture defects."""

    rng = random.Random(303)
    journal: list[JournalEntry] = []
    frames: list[tuple[float, bytes]] = []
    ts = _BASE_TS + 172_800.0

    client_port, server_port = _port_pair(5)
    dialogue = Dialogue(
        client_ip=_CLIENT_IP,
        server_ip=_SERVER_IP,
        client_port=client_port,
        server_port=server_port,
        client_isn=300000,
        server_isn=400000,
        flags_base=0,
        ts=ts,
    )
    dialogue.handshake()

    # A normal read first, so the recording starts from a clean transaction.
    value = rng.randint(0, 4095)
    dialogue.exchange(
        read_request(PARAM_IDS["temperature"]),
        read_response(PARAM_IDS["temperature"], value),
    )
    dialogue.record("read", "temperature", str(value))

    # A request that is retransmitted byte for byte.
    req = read_request(PARAM_IDS["humidity"])
    request_ts = dialogue.ts + 0.001
    dialogue.client_segment(dialogue._seq_a, req, when=request_ts)
    dialogue._seq_a += len(req)
    dialogue.server_segment(
        dialogue._seq_b, read_response(PARAM_IDS["humidity"], 1234)
    )
    dialogue._seq_b += 4 + 3
    dialogue.last_request_ts = request_ts
    dialogue.record("read", "humidity", "1234")
    # The same request repeated with the same bytes and the same sequence number.
    dialogue.client_segment(dialogue._seq_a - len(req), req, when=request_ts + 0.001)

    # A request whose two segments arrive out of order.
    message = write_request(PARAM_IDS["gain"], 200)
    first, second = message[:3], message[3:]
    request_ts = dialogue.ts + 0.002
    dialogue.client_segment(
        dialogue._seq_a + len(first), second, when=request_ts + 0.001
    )
    dialogue.client_segment(dialogue._seq_a, first, when=request_ts)
    dialogue._seq_a += len(message)
    dialogue.server_segment(dialogue._seq_b, write_response(PARAM_IDS["gain"], 200))
    dialogue._seq_b += 4 + 3
    dialogue.last_request_ts = request_ts
    dialogue.record("write", "gain", "applied 200")

    # A request that lost a segment, leaving a permanent gap in that direction,
    # followed by the answer the device still produced.
    request_ts = dialogue.ts + 0.004
    partial = read_request(PARAM_IDS["voltage"])[:2]
    dialogue.client_segment(dialogue._seq_a, partial, when=request_ts)
    dialogue._seq_a += 4
    dialogue.server_segment(dialogue._seq_b, read_response(PARAM_IDS["voltage"], 777))
    dialogue._seq_b += 4 + 3
    dialogue.last_request_ts = request_ts
    dialogue.record("read", "voltage", "777")

    # A measurement response whose bytes are partly contradicted afterwards.
    samples = [rng.randint(0, 4095) for _ in range(8)]
    good = measure_response(SENSOR_IDS["channel_a"], samples)
    request_ts = dialogue.ts + 0.005
    dialogue.client_segment(
        dialogue._seq_a, measure_request(SENSOR_IDS["channel_a"]), when=request_ts
    )
    dialogue._seq_a += 4 + 1
    dialogue.server_segment(dialogue._seq_b, good, when=request_ts + 0.001)
    rejected = b"\xff\xff"
    dialogue.server_segment(
        dialogue._seq_b + 4, rejected, when=request_ts + 0.002
    )
    dialogue._seq_b += len(good)
    dialogue.last_request_ts = request_ts
    dialogue.record("measure", "channel_a", "8 samples")

    dialogue.close()
    frames.extend(dialogue.frames)
    journal.extend(dialogue.journal)
    return _write_pcapng(frames), journal


# --- journal and readme -------------------------------------------------------


def render_journal(entries: list[JournalEntry]) -> str:
    lines = [
        "# Action journal",
        "",
        "One line per transaction: `timestamp | action | parameter | result`.",
        "The timestamp is the capture time of the request packet in epoch seconds,",
        "so it can be matched against the captures.",
        "",
        "```",
    ]
    for entry in entries:
        lines.append(
            f"{entry.timestamp:.3f} | {entry.action} | {entry.parameter} | {entry.result}"
        )
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


README = """# Research corpus

Recordings of a single device that speaks an undocumented binary protocol over
TCP, together with the action journal for the recorded transactions.

## Contents

| File | Description |
| ---- | ----------- |
| `corpus_capture_01.pcapng` | Primary recording: reads, writes, and measurements across three TCP sessions. |
| `corpus_capture_02.pcapng` | Second recording of the same device with different parameters and values. |
| `corpus_capture_defects.pcapng` | Recording with a retransmission, out-of-order delivery, a gap, and a conflicting overlap. |
| `corpus_journal.md` | Action journal, one line per transaction. |

## Protocol

The device uses a length-prefixed binary protocol. Every message starts with a
one-byte command, a one-byte flag or status, and a two-byte big-endian length.

- Requests from the client: `command (0x01 read, 0x02 write, 0x03 measurement)`,
  `flags`, `payload_len`, `payload`.
- Responses from the device: the same command, a `status` byte (`0x00` ok),
  `body_len`, `body`.

Read and write payloads carry a parameter id and, for a write, a two-byte
value. Measurement responses carry a sensor id, a sample count, and that many
two-byte samples, so their length varies between messages.

## How to use

Normalize a capture and match it against the journal:

```
python -m src.capture.cli --pcap tests/corpus/corpus_capture_01.pcapng \\
    --out /tmp/corpus_01.json --source-name captures/corpus_capture_01.pcapng
```

The normalized JSON follows `docs/CONTRACT.md`. To tie a transaction to the
wire, take its timestamp from `corpus_journal.md`, find the packet with that
timestamp in the capture, and use the provenance ranges in the JSON to move
from a stream offset to that packet.

The corpus is generated by `scripts/generate_corpus.py`. Regenerating it
reproduces the same bytes, so it is safe to check in.
"""


# --- entry point --------------------------------------------------------------


def generate(out_dir: Path, scale: int = 20) -> dict[str, int]:
    """Write the corpus into ``out_dir`` and return the byte size per file."""

    out_dir.mkdir(parents=True, exist_ok=True)
    sizes: dict[str, int] = {}

    capture_01, journal_01 = build_capture_01(scale)
    capture_02, journal_02 = build_capture_02(max(scale // 2, 1))
    capture_defects, journal_defects = build_capture_defects()

    files = {
        "corpus_capture_01.pcapng": capture_01,
        "corpus_capture_02.pcapng": capture_02,
        "corpus_capture_defects.pcapng": capture_defects,
        "corpus_journal.md": render_journal(
            journal_01 + journal_02 + journal_defects
        ).encode("utf-8"),
        "README.md": README.encode("utf-8"),
    }
    for name, data in files.items():
        path = out_dir / name
        path.write_bytes(data)
        sizes[name] = len(data)
    return sizes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the research corpus.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "corpus",
        help="output directory",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=20,
        help="transactions per action group; larger values make a larger corpus",
    )
    args = parser.parse_args(argv)

    sizes = generate(args.out, scale=args.scale)
    total = sum(sizes.values())
    for name, size in sizes.items():
        print(f"{name}: {size} bytes")
    print(f"total: {total} bytes ({total / (1024 * 1024):.2f} MiB)")
    if total > 10 * 1024 * 1024:
        print("WARNING: corpus exceeds 10 MiB; reduce --scale before committing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
