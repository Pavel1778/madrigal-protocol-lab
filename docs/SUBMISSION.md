# Submission

## Solution

madrigal-protocol-lab is a local desktop laboratory for investigating an
undocumented binary protocol over TCP: it reads a PCAP or PCAPNG capture,
rebuilds each directional stream with per-byte provenance, applies declarative
interpretation rules, verifies them on a corpus to surface counterexamples, and
writes a portable project with a report.

## Participant

| Field | Value |
| --- | --- |
| Participant | Sabadash Pavel |
| Team size | one |
| Group | ИС-24 |

## Hackathon

| Field | Value |
| --- | --- |
| Hackathon | UMIRHack, 09-17 October 2026 |
| Case | Protocol Laboratory, Madrigal |

## Setup

Python 3.12 or newer on Linux x86-64. Every command runs offline.

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

| Task | Command |
| --- | --- |
| Tests | `pytest tests/ -v` |
| Window | `python -m src.ui.main_window --capture tests/corpus/reference_export/corpus_capture_01.normalized.json --rule examples/corpus_rule_v1.json` |
| Pipeline | `python -m src.project.cli pipeline --pcap tests/corpus/corpus_capture_01.pcapng --project project.madrigal --report REPORT.md` |

## Demo

The step-by-step window walkthrough is in `docs/demo.md`. The same
investigation from the command line, used as the fallback, is in
`docs/demo_cli.md`.

## What is implemented

| Area | Contents |
| --- | --- |
| `src/capture/` | PCAP and PCAPNG reading, session identification, directional reassembly with gap and ambiguity diagnostics, per-byte provenance, normalized export, CLI. |
| `src/hypothesis/` and `src/protocol/` | Framing strategies, declarative rules, the rule engine, corpus verification and counterexamples, the alternatives engine, rule versioning, CLI. |
| `src/ui/` | The PySide6 window: session tree, hex view with provenance, message comparison, rule and validation panels, the hypotheses panel, version diff. |
| `src/project/` | The portable on-disk investigation, relative paths and sha256, zip export and import. |
| `src/report/` | The investigation rendered to Markdown and to a self-contained HTML page. |

## Where things are

| Path | Contents |
| --- | --- |
| `src/` | sources |
| `docs/` | reference, contracts, schemas, the audit and this file |
| `presentation/` | the defense deck and its screenshots |
| `tests/corpus/` | the research corpus and its reference export |
| `tests/fixtures/` | synthetic captures and deliberately damaged ones |
| `REPORT.md` | the investigation report |

## Limits

| Area | State |
| --- | --- |
| IPv6 | Not supported; reported as a diagnostic, the record is skipped. |
| IP fragmentation | Not reassembled; a fragmented payload is reported as incomplete. |
| Encrypted payloads | Out of scope; the bytes are reported as they appear. |
| Checksum offloading | Off by default; reordering is treated as a diagnostic. |
| Window project menu | Not present; the pipeline CLI drives project export and import. |
| Organizer captures | Not available during the development window; the corpus is synthetic and reproducible from `scripts/generate_corpus`. |

## Contact

Pavel1778, sabadaspaha@gmail.com.
