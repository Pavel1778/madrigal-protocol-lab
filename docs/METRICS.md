# Metrics

Numbers to quote on defense. Every figure is from a run recorded under
`docs/`, not an estimate, except the one row marked as an estimate. The source
of each table is named so the number can be reproduced.

## Corpus

Counts from reading each capture with the capture engine
(`read_capture` / `build_sessions`). The corpus is produced by
`scripts/generate_corpus.py` and is reproducible from the committed scripts.

| Capture | File | Packets | Sessions | Role |
| --- | --- | --- | --- | --- |
| corpus_capture_01.pcapng | 28.4 KiB | 295 | 3 | primary; 280 framed messages, 140 requests |
| corpus_capture_02.pcapng | 8.3 KiB | 90 | 2 | held out from framing; used for applicability |
| corpus_capture_defects.pcapng | 1.7 KiB | 18 | 1 | retransmission, out-of-order, gap, conflicting overlap |
| synthetic_live.pcapng | 2.5 KiB | 27 | 1 | real TCP stack, different layout; applicability boundary |

## Command surface

| Stage | Command | Values |
| --- | --- | --- |
| Capture | `python -m src.capture.cli --pcap <f> --out <json>` | read |
| Project | `python -m src.project.cli pipeline --pcap <f> --project <d> --report <f>` | read, measure |
| Project | `python -m src.project.cli create \| open \| add-capture \| export \| import` | read, write |
| Protocol | `python -m src.protocol.cli apply --rule <f> --capture <f> --out <f>` | read, write |
| Report | `pipeline --report <f> --html` (no standalone CLI) | write |

## Processing

Source: `docs/BENCHMARK.md`, produced by `scripts/run_benchmark.py` over a
250000-packet, 1000-session, 95.66 MiB capture on 4 vCPU / 16 GiB RAM.

| Phase | Seconds |
| --- | --- |
| Parse | 7.29 |
| Sessions | 0.70 |
| Reassembly | 1.84 |
| Export | 2.27 |
| Total | 12.10 |

| Input | Packets | Sessions | Regular s | Regular peak MiB | Streaming s | Streaming peak MiB |
| --- | --- | --- | --- | --- | --- | --- |
| 9.57 MiB | 25000 | 100 | 1.10 | 58 | 1.06 | 54 |
| 47.84 MiB | 125000 | 500 | 6.10 | 186 | 5.71 | 167 |
| 90.88 MiB | 237500 | 950 | 11.46 | 336 | 10.86 | 293 |

Peak memory at the reference profile is 350 MiB against a 4 GiB budget; total
time is 12.10 s against a 5 minute budget.

## Rules

Source: `docs/REFERENCE_INVESTIGATION.md` (protocol engine). Rule v1 and rule
v2 describe the same bytes; only the description changed.

| Metric | v1 | v2 | Delta |
| --- | --- | --- | --- |
| matched | 60 | 140 | +80 |
| mismatched | 80 | 0 | -80 |
| counterexamples | 80 | 0 | -80 |
| coverage | 0.500000 | 0.500000 | 0.0 |
| precision | 0.428571 | 1.000000 | +0.571429 |
| counterexample density | 57.142857 | 0.0 | -57.142857 |

Framing candidates, all 10 streams: `payload` frames every stream with no
leftover bytes; `payload_and_length_field` and `entire_message` do not.

| Candidate | Streams framed cleanly |
| --- | --- |
| payload | 10 / 10 |
| payload and length field | 0 / 10 |
| entire message | 0 / 10 |

## Counterexamples

| Rule | Counterexamples in the corpus |
| --- | --- |
| v1 | 80 (60 command bytes of value `2`, 20 of value `3`, none in the expected set `[1]`) |
| v2 | 0 |

Resolved by the v1 -> v2 change: 80. Introduced: 0.

## Journal correlation

Source: `docs/REFERENCE_INVESTIGATION.md`.

| Capture | Requests | Correlated | Window |
| --- | --- | --- | --- |
| corpus_capture_01.pcapng | 140 | 140 | 500 ms |
| corpus_capture_02.pcapng | 40 | 40 | 500 ms |

## Robustness

Damaged and unusual captures are processed without an uncaught error; each
becomes a diagnostic or a clearly marked unknown.

| Fixture | Condition |
| --- | --- |
| defects/fragmented_ip.pcap | IP fragment |
| defects/mixed_ip_versions.pcapng | IPv4 and IPv6 in one file |
| defects/mixed_link_types.pcapng | two link types in one file |
| defects/truncated_header.pcapng | header cut short |
| defects/truncated_packet.pcapng | payload cut short |
| defects/unsupported_link_type.pcapng | link type the parser does not know |
| ipv6_mixed.pcapng | IPv6 present |
| no_syn.pcapng | no SYN, roles unknown |
| overlap_conflict.pcapng | conflicting overlap |

The defect capture (18 packets) normalizes in 0.021 s regular and 0.022 s
streaming, so diagnostics do not degrade throughput at this size.

## Manual comparison

| Approach | Time for 100 messages |
| --- | --- |
| Manual reading in a hex editor | 4-6 hours (estimate) |
| Rule applied to the corpus | seconds |

The manual figure is an estimate for the defense narrative and is not a
measurement; the automated figure is a run.
