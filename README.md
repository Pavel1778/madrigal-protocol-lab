# madrigal-protocol-lab

A local desktop laboratory for investigating an undocumented binary protocol
over TCP: open a PCAP or PCAPNG capture, identify TCP sessions, rebuild each
directional stream, inspect the bytes, state hypotheses about the message
structure, apply declarative interpretation rules, verify them on a corpus, find
counterexamples, and save the whole investigation as a portable project with a
report.

The guiding rule is that a fact and a guess are never mixed. Every byte range in
a rebuilt stream is tied to the packet it came from, a gap or an ambiguous
overlap is shown as such rather than filled in, and a rule that matches examples
is reported as confirmed in the tested scope, not as proven.

## Requirements

- Linux x86-64
- Python 3.12 or newer
- For the reference workload (up to 100 MiB PCAP, 250k packets, 1000 TCP
  sessions, 100k messages, responses up to 64 KiB): 4 vCPU and 8 GB RAM. The
  measured figures are in `docs/BENCHMARK.md`.

## Installation

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Quick start

Three commands: build the test data, normalize a capture, validate the result.

```
python -m scripts.generate_corpus
python -m src.capture.cli --pcap tests/corpus/corpus_capture_01.pcapng --out out/cap01.json --source-name captures/corpus_capture_01.pcapng
python -m pytest tests/ -q
```

The first command writes the deterministic corpus into `tests/corpus/` and the
synthetic fixtures into `tests/fixtures/`. The second produces a normalized
capture that follows `docs/CONTRACT.md`. The third confirms the whole suite.

## What is implemented

| Area | State |
| ---- | ----- |
| `src/capture/` | Done. PCAP and PCAPNG reading, TCP session identification, directional reassembly with gap and ambiguity diagnostics, per-byte provenance, normalized JSON export, streaming mode for large captures, Wireshark export of rebuild streams, CLI. |
| `src/project/` | Done. Portable on-disk investigation, manifest with relative paths and sha256, zip export and import with a digest check. |
| `src/report/` | Done. Investigation rendered to Markdown and to a self-contained HTML page. |
| `src/protocol/`, `src/hypothesis/` | In progress by the protocol/GUI branch. Framing and the rule engine. |
| `src/ui/` | In progress by the protocol/GUI branch. PySide6 interface. |

## Layout

- `src/capture/` — PCAP/PCAPNG reading, TCP sessions, stream reassembly, provenance
- `src/protocol/` — framing and the rule engine
- `src/hypothesis/` — result classification, corpus verification, versioning
- `src/ui/` — PySide6 interface
- `src/project/` — portable on-disk project
- `src/report/` — investigation reports
- `scripts/` — deterministic generators and benchmarks
- `docs/` — contracts, schemas, API notes, style, benchmark
- `tests/fixtures/` — small synthetic captures, one behaviour each
- `tests/fixtures/defects/` — deliberately damaged captures
- `tests/corpus/` — the research corpus and its reference export
- `tests/integration/` — the corpus run end to end

## Tests

```
pytest tests/ -q
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — the approach, the modules, the formats,
  the dependencies, and what is not implemented.
- [docs/CAPTURE_API.md](docs/CAPTURE_API.md) — the capture engine API, with
  quick start, scenarios, the full reference, diagnostics, and limits.
- [docs/PROTOCOL_API.md](docs/PROTOCOL_API.md) — the protocol and hypothesis
  engine API (added with that module).
- [docs/CONTRACT.md](docs/CONTRACT.md) — the JSON contracts between the stages.
- [docs/INTEGRATION.md](docs/INTEGRATION.md) — how the stages hand work to each
  other, and the seam check to run after a change.
- [docs/INTEGRATION_CHECKLIST.md](docs/INTEGRATION_CHECKLIST.md) — the checklist
  for the integration day.
- [docs/BENCHMARK.md](docs/BENCHMARK.md) — measured time and memory at the
  reference workload.
- [docs/demo.md](docs/demo.md) — the window walkthrough on the reference corpus.
- [docs/demo_cli.md](docs/demo_cli.md) — the same investigation from the command
  line, as the fallback for the demonstration.
- [docs/GUI_VERIFICATION.md](docs/GUI_VERIFICATION.md) — what the window was
  driven to show, and the defects found while checking it.
- [REPORT.md](REPORT.md) — the investigation report.
- [presentation/slides.pdf](presentation/slides.pdf) — the deck, with the eight
  window screenshots.

## License

MIT, see [LICENSE](LICENSE).

