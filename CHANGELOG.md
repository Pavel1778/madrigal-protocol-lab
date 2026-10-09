# Changelog

Short record of the work on the capture, project, and report stages, by
iteration. Commits are Conventional Commits; the short hashes are from the
`agent1/capture` branch.

## Iteration 1 - capture engine

PCAP/PCAPNG reading, TCP session identification, directional reassembly, byte
provenance, and the normalized-capture export.

- `465e93c` feat(capture): add pcap/pcapng parsing, sessions, reassembly
- `b845787` test(capture): cover parser, sessions, reassembly and export

## Iteration 2 - corpus and benchmarks

A research corpus with its action journal, and the first resource benchmark.

- `274e16e` feat(capture): add research corpus and its journal
- `6674117` perf(capture): benchmark the engine on the reference profile
- `1d002ce` docs(capture): document the API and the integration seam

## Iteration 3 - streaming and defect handling

Streaming normalization for large captures, defect fixtures, and a pcap export
of the reassembled streams.

- `ddab671` perf(capture): add streaming mode for large captures
- `057194d` test(capture): cover deformed pcap and pcapng fixtures
- `f204b2d` feat(capture): export reassembled streams as pcap
- `78e5b48` docs(capture): record the diagnostic set and the pcap export
- `0134798` feat(capture): add a synthetic stand with a real TCP exchange

## Iteration 4 - integration, project, report

Corpus integration tests, committed reference exports, the portable project
container, and the report renderers.

- `9e2cd07` test(capture): add corpus integration tests
- `6dd72a5` chore(corpus): add reference export
- `ea25583` feat(project): add portable project container
- `1970ae6` feat(report): add markdown and html rendering
- `442835c` docs: finalize readme, architecture, and capture api

## Iteration 5 - pipeline CLI, benchmarks, usage

An end-to-end pipeline command, a size sweep and phase breakdown in the
benchmark, and this documentation.

- `55313bf` fix(gitignore): un-ignore tests/corpus
- `069eda8` feat(project): add end-to-end pipeline CLI
- `40a7253` perf(capture): expand benchmarks by phase and size
- docs: add usage walkthrough and changelog

## Iteration 6 - audit, CI, submission

A repository audit with boundary tests, a wider CI, a submission builder, and
the portability report.

- `87c71a2` docs: add repository audit
- `a296b0d` test: cover capture, project, and report boundaries
- `245bece` ci: add python matrix and code-quality jobs
- `029ae96` chore: hygiene pass on repository
- `3cf0b33` feat(scripts): add submission builder
- `92d2762` docs: add portability report
- `43694ad` docs: extend the integration checklist

## Iteration 7 - protocol integration and CI rescope

The protocol and window branch merged into `main`, and the lint gate scoped to
the starter ruleset so the shared branch is green.

- `a5535e0` merge(protocol): verify branch, screenshots, lint fixes
- `779238c` merge: verify branch, lint fixes, CI rescope
- `1c86f10` chore(ci): rescope code-quality to starter ruleset
- `308b62c` docs(audit): record CI rescope and integration merge

## Iteration 8 - submission, container, defense material

The submission archive, the container image, and the numbers and decisions for
the defense.

- `e70bfd8` docs: add submission metadata and delivery formats
- `cbb4b48` fix(submission): include examples directory in the archive
- `87e722f` docs: add submission metadata and portability check
- `29451c7` feat(docker): add container image and update portability notes
- `c5b9cd2` docs: add metrics, roadmap and architecture decisions
