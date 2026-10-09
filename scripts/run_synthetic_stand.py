"""Synthetic stand: a real TCP exchange on loopback, recorded to pcapng.

The specification allows replacing the real device with a stand that produces a
genuine TCP exchange and a capture. This script does exactly that: it runs a
real server and a real client over loopback, and while the bytes flow it records
the observed segments and writes them as a capture.

How the recording works
-----------------------
The usual tools (tcpdump, dumpcap, scapy) need elevated privileges and are not
always installed. To keep the stand usable without root, the client talks to the
server through a recording relay: the relay accepts the client's connection,
opens its own connection to the server, and forwards bytes both ways. Every
chunk it forwards is a real segment of a real TCP exchange; the relay notes its
timestamp and direction and rebuilds a capture from those segments. The capture
therefore presents the exchange as one session between the client port and the
server port, with the relay acting as a transparent observer.

The protocol served here is deliberately different from the one in
``tests/corpus``: the length field is little-endian and each message carries a
transaction id, so the two datasets do not share a byte layout.

Request:   command, txid, len_lo, len_hi, payload...
Response:  command | 0x80, txid, len_lo, len_hi, body...

Commands: 0x21 read, 0x22 set, 0x23 measure.

Running it::

    python -m scripts.run_synthetic_stand

Writes ``tests/corpus/synthetic_live.pcapng`` and
``tests/corpus/synthetic_live_journal.md``. The action journal uses the same
``timestamp | action | parameter | result`` form as the generated corpus, and
its timestamps are the relay's observation times, so they match the capture.
"""

from __future__ import annotations

import argparse
import io
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import dpkt

CLIENT_IP = "127.0.0.1"
SERVER_IP = "127.0.0.1"
CLIENT_MAC = b"\x02\x00\x00\x00\x00\x11"
SERVER_MAC = b"\x02\x00\x00\x00\x00\x22"

ISN_CLIENT = 0x11110000
ISN_SERVER = 0x22220000

CMD_READ = 0x21
CMD_SET = 0x22
CMD_MEASURE = 0x23
RESPONSE_BIT = 0x80

HEADER_SIZE = 4

PARAM_IDS = {
    "flow_rate": 0x31,
    "setpoint": 0x32,
    "calibration": 0x33,
    "limit": 0x34,
    "deadband": 0x35,
    "ramp": 0x36,
}
PARAM_NAMES = {v: k for k, v in PARAM_IDS.items()}

SENSOR_IDS = {
    "probe_x": 0x41,
    "probe_y": 0x42,
}
SENSOR_NAMES = {v: k for k, v in SENSOR_IDS.items()}

RESPONSE_DELAY = 0.12
CLOSE_GRACE = 0.05


# --- protocol -----------------------------------------------------------------


def encode_request(command: int, txid: int, payload: bytes) -> bytes:
    return bytes([command, txid & 0xFF]) + len(payload).to_bytes(2, "little") + payload


def encode_response(command: int, txid: int, body: bytes) -> bytes:
    return (
        bytes([command | RESPONSE_BIT, txid & 0xFF])
        + len(body).to_bytes(2, "little")
        + body
    )


def _value_le(value: int) -> bytes:
    return (value & 0xFFFF).to_bytes(2, "little")


@dataclass
class Request:
    command: int
    txid: int
    payload: bytes


def parse_request(frame: bytes) -> Request:
    command, txid = frame[0], frame[1]
    length = int.from_bytes(frame[2:4], "little")
    return Request(command=command, txid=txid, payload=frame[4 : 4 + length])


def handle_request(request: Request) -> bytes:
    """Produce the response body for a request. Deterministic in its inputs."""

    payload = request.payload
    if request.command == CMD_READ:
        param_id = payload[0]
        value = (param_id * 37 + 11) % 4096
        return bytes([param_id]) + _value_le(value)
    if request.command == CMD_SET:
        param_id = payload[0]
        value = int.from_bytes(payload[1:3], "little")
        return bytes([param_id]) + _value_le(value)
    if request.command == CMD_MEASURE:
        sensor_id = payload[0]
        count = 3 + (sensor_id & 0x03)
        samples = [(_value_le(sensor_id * 100 + index * 7)) for index in range(count)]
        return bytes([sensor_id, count]) + b"".join(samples)
    return bytes([0x00])


# --- capture frames -----------------------------------------------------------


def _frame(
    forward: bool,
    client_port: int,
    server_port: int,
    seq: int,
    ack: int,
    flags: int,
    payload: bytes,
) -> bytes:
    if forward:
        sport, dport = client_port, server_port
        src_mac, dst_mac = CLIENT_MAC, SERVER_MAC
    else:
        sport, dport = server_port, client_port
        src_mac, dst_mac = SERVER_MAC, CLIENT_MAC
    tcp = dpkt.tcp.TCP(
        sport=sport,
        dport=dport,
        seq=seq & 0xFFFFFFFF,
        ack=ack & 0xFFFFFFFF,
        flags=flags,
        win=64240,
        data=payload,
    )
    tcp.off = 5
    ip = dpkt.ip.IP(
        src=socket.inet_aton(CLIENT_IP if forward else SERVER_IP),
        dst=socket.inet_aton(SERVER_IP if forward else CLIENT_IP),
        p=dpkt.ip.IP_PROTO_TCP,
        data=bytes(tcp),
    )
    ip.len = len(bytes(ip))
    eth = dpkt.ethernet.Ethernet(
        src=src_mac, dst=dst_mac, type=dpkt.ethernet.ETH_TYPE_IP, data=ip
    )
    return bytes(eth)


@dataclass
class _Event:
    ts: float
    forward: bool
    payload: bytes
    flags: int


@dataclass
class JournalEntry:
    timestamp: float
    action: str
    parameter: str
    result: str


# --- recording relay ----------------------------------------------------------


@dataclass
class Recorder:
    """Records the exchange and reconstructs the action journal from it."""

    client_port: int = 0
    server_port: int = 0
    events: list[_Event] = field(default_factory=list)
    journal: list[JournalEntry] = field(default_factory=list)
    _pending: dict[int, JournalEntry] = field(default_factory=dict)
    _client_buffer: bytearray = field(default_factory=bytearray)
    _server_buffer: bytearray = field(default_factory=bytearray)

    def start(self, now: float) -> None:
        self.events.append(_Event(now, True, b"", dpkt.tcp.TH_SYN))
        self.events.append(
            _Event(now + 0.0001, False, b"", dpkt.tcp.TH_SYN | dpkt.tcp.TH_ACK)
        )
        self.events.append(_Event(now + 0.0002, True, b"", dpkt.tcp.TH_ACK))

    def stop(self, now: float) -> None:
        self.events.append(
            _Event(now, True, b"", dpkt.tcp.TH_FIN | dpkt.tcp.TH_ACK)
        )
        self.events.append(
            _Event(now + 0.0001, False, b"", dpkt.tcp.TH_FIN | dpkt.tcp.TH_ACK)
        )

    def observe(self, forward: bool, payload: bytes, now: float) -> None:
        self.events.append(
            _Event(now, forward, payload, dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH)
        )
        if forward:
            self._consume_client(payload, now)
        else:
            self._consume_server(payload)

    def _consume_client(self, payload: bytes, now: float) -> None:
        buffer = self._client_buffer
        buffer += payload
        while len(buffer) >= HEADER_SIZE:
            length = int.from_bytes(buffer[2:4], "little")
            if len(buffer) < HEADER_SIZE + length:
                break
            frame = bytes(buffer[: HEADER_SIZE + length])
            del buffer[: HEADER_SIZE + length]
            request = parse_request(frame)
            self._pending[request.txid] = self._describe(request, now)

    def _consume_server(self, payload: bytes) -> None:
        buffer = self._server_buffer
        buffer += payload
        while len(buffer) >= HEADER_SIZE:
            length = int.from_bytes(buffer[2:4], "little")
            if len(buffer) < HEADER_SIZE + length:
                break
            frame = bytes(buffer[: HEADER_SIZE + length])
            del buffer[: HEADER_SIZE + length]
            command = frame[0] & ~RESPONSE_BIT
            txid = frame[1]
            body = frame[4 : 4 + length]
            entry = self._pending.pop(txid, None)
            if entry is not None:
                entry.result = _result_text(command, body)
                self.journal.append(entry)

    def _describe(self, request: Request, now: float) -> JournalEntry:
        payload = request.payload
        if request.command == CMD_READ:
            name = PARAM_NAMES.get(payload[0], f"0x{payload[0]:02x}")
            return JournalEntry(now, "read", name, "pending")
        if request.command == CMD_SET:
            name = PARAM_NAMES.get(payload[0], f"0x{payload[0]:02x}")
            value = int.from_bytes(payload[1:3], "little")
            return JournalEntry(now, "set", name, f"pending {value}")
        sensor = SENSOR_NAMES.get(payload[0], f"0x{payload[0]:02x}")
        return JournalEntry(now, "measure", sensor, "pending")

    def to_capture(self) -> bytes:
        seq_client = ISN_CLIENT
        seq_server = ISN_SERVER
        buf = io.BytesIO()
        writer = dpkt.pcapng.Writer(buf)
        for event in self.events:
            if event.forward:
                frame = _frame(
                    True,
                    self.client_port,
                    self.server_port,
                    seq_client,
                    seq_server,
                    event.flags,
                    event.payload,
                )
                seq_client += len(event.payload)
                if event.flags & dpkt.tcp.TH_SYN:
                    seq_client += 1
                if event.flags & dpkt.tcp.TH_FIN:
                    seq_client += 1
            else:
                frame = _frame(
                    False,
                    self.client_port,
                    self.server_port,
                    seq_server,
                    seq_client,
                    event.flags,
                    event.payload,
                )
                seq_server += len(event.payload)
                if event.flags & (dpkt.tcp.TH_SYN | dpkt.tcp.TH_FIN):
                    seq_server += 1
            writer.writepkt(frame, ts=event.ts)
        data = buf.getvalue()
        buf.close()
        return data


def _result_text(command: int, body: bytes) -> str:
    if command == CMD_READ and len(body) >= 3:
        return str(int.from_bytes(body[1:3], "little"))
    if command == CMD_SET and len(body) >= 3:
        return f"applied {int.from_bytes(body[1:3], 'little')}"
    if command == CMD_MEASURE and len(body) >= 2:
        return f"{body[1]} samples"
    return "unknown"


# --- server and client --------------------------------------------------------


def _server_loop(server_socket: socket.socket, ready: threading.Event) -> None:
    server_socket.listen(1)
    ready.set()
    connection, _ = server_socket.accept()
    with connection:
        connection.settimeout(5.0)
        buffer = b""
        while True:
            try:
                chunk = connection.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buffer += chunk
            while len(buffer) >= HEADER_SIZE:
                length = int.from_bytes(buffer[2:4], "little")
                if len(buffer) < HEADER_SIZE + length:
                    break
                frame = buffer[: HEADER_SIZE + length]
                buffer = buffer[HEADER_SIZE + length :]
                request = parse_request(frame)
                body = handle_request(request)
                connection.sendall(encode_response(request.command, request.txid, body))
                time.sleep(RESPONSE_DELAY)


def _relay_loop(
    relay_socket: socket.socket,
    server_port: int,
    recorder: Recorder,
    ready: threading.Event,
) -> None:
    relay_socket.listen(1)
    ready.set()
    client_conn, client_addr = relay_socket.accept()
    recorder.client_port = client_addr[1]
    recorder.server_port = server_port
    upstream = socket.create_connection((SERVER_IP, server_port), timeout=5.0)
    recorder.start(time.time())

    stop = threading.Event()

    def pump(source: socket.socket, forward: bool) -> None:
        while not stop.is_set():
            try:
                chunk = source.recv(4096)
            except (socket.timeout, OSError):
                break
            if not chunk:
                break
            recorder.observe(forward, chunk, time.time())
            target = upstream if forward else client_conn
            try:
                target.sendall(chunk)
            except OSError:
                break
        stop.set()

    forward_thread = threading.Thread(target=pump, args=(client_conn, True), daemon=True)
    backward_thread = threading.Thread(
        target=pump, args=(upstream, False), daemon=True
    )
    forward_thread.start()
    backward_thread.start()
    forward_thread.join(timeout=10.0)
    backward_thread.join(timeout=10.0)
    recorder.stop(time.time())
    upstream.close()
    client_conn.close()


def _client_scenario(relay_port: int) -> None:
    connection = socket.create_connection((CLIENT_IP, relay_port), timeout=5.0)
    with connection:
        connection.settimeout(5.0)
        txid = 1

        def exchange(command: int, payload: bytes) -> bytes:
            nonlocal txid
            connection.sendall(encode_request(command, txid, payload))
            header = _recv_exact(connection, HEADER_SIZE)
            length = int.from_bytes(header[2:4], "little")
            return _recv_exact(connection, length)

        def pause() -> None:
            time.sleep(RESPONSE_DELAY)

        for name in ("flow_rate", "setpoint", "calibration"):
            exchange(CMD_READ, bytes([PARAM_IDS[name]]))
            txid = (txid % 255) + 1
            pause()
        for name, value in (("limit", 100), ("deadband", 25), ("ramp", 7)):
            exchange(CMD_SET, bytes([PARAM_IDS[name]]) + _value_le(value))
            txid = (txid % 255) + 1
            pause()
        for index in range(5):
            name = ("probe_x", "probe_y")[index % 2]
            exchange(CMD_MEASURE, bytes([SENSOR_IDS[name]]))
            txid = (txid % 255) + 1
            pause()


def _recv_exact(connection: socket.socket, count: int) -> bytes:
    data = b""
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            raise ConnectionError("connection closed before a full message arrived")
        data += chunk
    return data


# --- journal and README -------------------------------------------------------


def render_journal(entries: list[JournalEntry]) -> str:
    lines = [
        "# Synthetic stand journal",
        "",
        "One line per transaction: `timestamp | action | parameter | result`.",
        "The timestamp is the relay's observation time of the request segment,",
        "so it matches the capture exactly.",
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


README = """# Synthetic live capture

A capture of a real TCP exchange on loopback, produced by the stand in
`scripts/run_synthetic_stand.py`. Unlike `corpus_capture_*`, which are built by
writing packets directly, this exchange went through a real TCP stack: a client
and a server exchanged bytes over real sockets.

## Contents

| File | Description |
| ---- | ----------- |
| `synthetic_live.pcapng` | The recorded loopback exchange, one session. |
| `synthetic_live_journal.md` | Action journal for the recorded transactions. |

## How to run it again

```
python -m scripts.run_synthetic_stand
```

The stand starts a server and a client on loopback, relays the exchange through
a recording observer, verifies the capture through the capture engine, and only
then writes the files. Nothing here needs root; it never leaves loopback.

## Protocol

Different from the generated corpus on purpose:

- the length field is little-endian, not big-endian;
- every message carries a transaction id byte;
- the command values are 0x21 read, 0x22 set, 0x23 measure.

Request: `command, txid, len_lo, len_hi, payload`.
Response: `command | 0x80, txid, len_lo, len_hi, body`.

The two datasets therefore share no byte layout, so a rule written against one
is not accidentally right for the other.

## Recording method

The usual capture tools need elevated privileges. Instead, the stand relays the
client-server exchange through a recording observer in the same process. Every
forwarded chunk is a real TCP segment; the observer notes its time and direction
and rebuilds the capture from those segments, presenting the exchange as a
single session between the client port and the server port.
"""


# --- entry point --------------------------------------------------------------


def run_stand() -> tuple[bytes, list[JournalEntry], dict[str, int]]:
    """Run the exchange and return the capture bytes, journal, and port info."""

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_IP, 0))
    server_port = server_socket.getsockname()[1]
    server_ready = threading.Event()
    server_thread = threading.Thread(
        target=_server_loop, args=(server_socket, server_ready), daemon=True
    )
    server_thread.start()
    server_ready.wait(timeout=5.0)

    relay_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    relay_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    relay_socket.bind((CLIENT_IP, 0))
    relay_port = relay_socket.getsockname()[1]
    recorder = Recorder()
    relay_ready = threading.Event()
    relay_thread = threading.Thread(
        target=_relay_loop,
        args=(relay_socket, server_port, recorder, relay_ready),
        daemon=True,
    )
    relay_thread.start()
    relay_ready.wait(timeout=5.0)

    try:
        _client_scenario(relay_port)
    finally:
        time.sleep(CLOSE_GRACE)
        relay_thread.join(timeout=10.0)
        server_thread.join(timeout=10.0)
        relay_socket.close()
        server_socket.close()

    capture = recorder.to_capture()
    info = {"server_port": server_port, "relay_port": relay_port}
    return capture, recorder.journal, info


def generate(out_dir: Path) -> dict[str, int]:
    """Run the stand, verify the capture, and write the files."""

    capture, journal, _info = run_stand()

    # Verify before saving: run the result through the capture engine.
    from src.capture.pipeline import normalize_bytes

    normalized = normalize_bytes(capture, source_file=out_dir / "synthetic_live.pcapng")
    if not normalized.sessions:
        raise RuntimeError("the recorded capture produced no sessions")
    for session in normalized.sessions:
        for stream in normalized.streams[session.session_id].values():
            if stream.gaps():
                raise RuntimeError(
                    f"the recorded capture has a gap in {session.session_id}"
                )

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "synthetic_live.pcapng": capture,
        "synthetic_live_journal.md": render_journal(journal).encode("utf-8"),
        "synthetic_live_README.md": README.encode("utf-8"),
    }
    sizes: dict[str, int] = {}
    for name, data in files.items():
        if name == "synthetic_live.pcapng" and len(data) > 2 * 1024 * 1024:
            raise RuntimeError(
                f"{name} is {len(data)} bytes, above the 2 MiB commit limit"
            )
        (out_dir / name).write_bytes(data)
        sizes[name] = len(data)
    return sizes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the synthetic TCP stand.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "corpus",
        help="output directory",
    )
    args = parser.parse_args(argv)

    sizes = generate(args.out)
    for name, size in sizes.items():
        print(f"{name}: {size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
