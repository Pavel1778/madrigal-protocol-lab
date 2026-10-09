# Resource benchmark

Measured on the reference load profile. Numbers below are produced by
`scripts/run_benchmark.py`; regenerate them rather than editing by hand.

## Check environment

- OS: Linux-6.8.0-1055-gke-x86_64-with-glibc2.41
- Kernel: 6.8.0-1055-gke
- CPU: x86_64 (4 logical cores)
- RAM: 15990 MiB
- Python: 3.13.15
- dpkt: 1.9.8

The reference environment in the specification is Linux x86-64, 4 vCPU,
8 GB RAM. The numbers below are from the machine shown above.

## Input

- Input capture: 95.66 MiB
- Packets read: 250000
- TCP sessions: 1000
- Read diagnostics: 0
- Target profile: 250000 packets, 1000 sessions, up to 100 MiB, responses up to 65536 bytes

## Timings

| Phase | Seconds |
| ----- | ------- |
| Parse (read_capture) | 6.90 |
| Sessions (build_sessions) | 0.68 |
| Reassembly (reassemble) | 1.83 |
| Export (export_capture) | 2.15 |
| Total | 11.56 |

## Streaming mode

`process_streaming` reads the capture in blocks and writes each session as
soon as it can no longer receive packets, so closed sessions leave memory.
The output is identical to the regular mode; only the resource profile
differs. The streaming peak is measured in its own process so the two do
not share a high-water mark.

| Metric | Regular | Streaming |
| ------ | ------- | --------- |
| Total seconds | 11.56 | 11.22 |
| Peak RSS (MiB) | 354 | 224 |
| Output JSON (MiB) | 122.44 | 122.44 |

The streaming run flushed 1000 sessions.

Streaming used less memory.

## Memory and output

- Peak process RSS: 354 MiB
- Output JSON: 122.44 MiB

## Conclusions and limitations

- Peak memory is 354 MiB, well under the 4 GiB threshold.
- Total time is 11.56 s, well under the 5 minute threshold.

Observations:

- The parser dominates the time. It builds one Python object per packet, which is the cost of keeping the header fields available for provenance.
- The normalized JSON (122.44 MiB) is larger than the input (95.66 MiB) because stream bytes are stored base64 encoded and every observed range carries a provenance record.
- Memory scales with the capture size: all packets are held in memory at once. At this profile that is affordable; for a capture several times larger the same approach would need to stream or use memory mapping.

If a larger capture must be supported, the first step is to stop holding every packet object at once: parse and reassemble session by session, and write provenance ranges to disk as they are produced. That trades peak memory for a second pass over the file.
