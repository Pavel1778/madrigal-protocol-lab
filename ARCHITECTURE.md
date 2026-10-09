# Architecture

## Approach

The project is a local desktop application with four cooperating parts:

1. **Capture engine** — reads a PCAP/PCAPNG file and produces a normalized
   capture: TCP sessions, reassembled directional streams, and per-byte
   provenance.
2. **Protocol engine** — frames a directional stream into messages and applies
   declarative interpretation rules.
3. **Hypothesis engine** — classifies rule results, verifies rules on a corpus,
   finds counterexamples, and versions rules and results.
4. **UI / project / report** — PySide6 interface, portable on-disk project,
   export and import, reports, and the defense presentation.

The interface between the parts is fixed by the JSON contracts in
`docs/CONTRACT.md` and the schemas in `docs/schemas/`.

## Capture engine

### Library choice

PCAP and PCAPNG reading uses **dpkt 1.9.8**.

- dpkt reads both classic pcap (`dpkt.pcap.Reader`) and pcapng
  (`dpkt.pcapng.Reader`) without external processes.
- PyShark was rejected because it shells out to `tshark`, which would have to be
  present on the target machine; the reference environment does not guarantee it.
- scapy is kept as a mental fallback but is not a dependency: it is heavier and
  slower for the reference workload of up to 250k packets.

Link-layer types other than Ethernet (raw IP, Linux cooked capture, ...) and
IPv6 packets are reported as diagnostics instead of raising, so a mixed capture
still yields the TCP sessions that can be read.

### Modules

- `parser.py` — `read_capture(path) -> Iterator[Packet]`. Yields TCP packets
  with a monotonic `index`, timestamp, endpoints, sequence numbers, flags, and
  payload. Non-TCP and non-IPv4 packets are skipped with a diagnostic where
  relevant.
- `session.py` — `build_sessions(packets) -> list[Session]`. Groups packets into
  TCP connection instances. A new session is started on SYN without ACK, on a
  new tuple after a FIN/RST, and on any reuse of an endpoint pair after the
  previous instance ended.
- `reassembly.py` — `reassemble(session, direction, packets) -> DirectionalStream`.
  Orders payload by sequence number, deduplicates identical retransmissions,
  buffers out-of-order segments, marks gaps explicitly, records contradictory
  overlaps as ambiguity, and handles the 32-bit sequence wrap.
- `provenance.py` — `Range` and helpers mapping stream offsets to source packets.
- `export.py` — `export_capture(...)` writes the contract JSON, streaming so the
  whole file is not held in memory.
- `cli.py` — `python -m src.capture.cli --pcap ... --out ...`.

## Formats

See `docs/CONTRACT.md`.

## Limitations

- Only IPv4 and Ethernet (and raw IP) link types are interpreted; other link
  types and IPv6 are reported as diagnostics.
- Checksum validation is off by default because of checksum offloading.
- Reassembly assumes a single direction is driven by one side's sequence space;
  conflicting overlaps are surfaced as ambiguity rather than resolved.
