# madrigal-protocol-lab

Local desktop laboratory for investigating undocumented binary protocols over TCP.

The application opens a PCAP or PCAPNG capture, identifies TCP sessions, rebuilds
each directional stream, lets the researcher inspect the bytes, state hypotheses
about the message structure, apply declarative interpretation rules, verify them
against a corpus, find counterexamples, and save a portable project plus a report.

## Requirements

- Linux x86-64
- Python 3.12 or newer
- 4 vCPU, 8 GB RAM for the reference workload (up to 100 MiB PCAP, 250k packets,
  1000 TCP sessions, 100k messages)

## Installation

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Usage

Capture engine (normalize a capture into the contract format):

```
python -m src.capture.cli --pcap path/to/cap.pcapng --out normalized.json
```

## Tests

```
pytest tests/ -v
```

## Layout

- `src/capture/` — PCAP/PCAPNG reading, TCP sessions, stream reassembly, provenance
- `src/protocol/` — framing and rule engine
- `src/hypothesis/` — result classification, corpus verification, versioning
- `src/ui/` — PySide6 interface
- `src/project/` — portable on-disk project
- `src/report/` — report generation
- `docs/` — contracts, schemas, style
- `tests/fixtures/` — synthetic captures used by the test suite

## License

MIT, see `LICENSE`.
