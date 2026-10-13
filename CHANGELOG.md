# Changelog

Short record of the work on the capture, project, and report stages, by
iteration. Commits are Conventional Commits; the short hashes are from the
the capture stage.

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

## Iteration 9 - installers, presentation, test isolation

The packaging branch, the defense presentation, and locale-independent UI
tests. This is the work after the `v1.0.0` tag.

- `b192531` fix(packaging): ship Qt runtime libs in the image and the whole package tree in the wheel
- `116e64b` docs: install guide for every format, delivery table, Docker in BINARY
- `bc7d315` test(project): cover packaging scripts and record video measurement
- `540e5fd` feat(presentation): team, killer features, web and roadmap slides, reserve video
- `84362b8` test(ui): isolate window tests from the developer QSettings and locale

## Iteration 10 - interface test coverage and verification

The interface test suites, the CI matrix that runs them, and the consolidated
verification of the deck, the screencast and the demo driver.

- `4c3b1a3` chore(repo): add git attributes, hook, message template and hygiene doc
- `1c8621f` test(ui): add locale, snapshot and state-isolation suites

## Unreleased

Everything merged into `main` after the `v1.0.0` tag, by pull request. `v1.0.0`
is the merge of PR #14 (`f637644`); the entries below are the work that followed.

### Added

- Interface test coverage and a CI matrix for it: locale, snapshot,
  state-isolation and layout suites, and the `ui` job (PR #18).
- A perceptual snapshot comparison for the interface, replacing the exact-pixel
  baseline that broke on every font hinting change (PR #18).
- The organizer capture set, committed under `tests/corpus/real/`, with the
  thermal-stand rules in `examples/` and the CSV action journal (PR #20).
- `scripts/investigate_dataset.py`, which regenerates
  `docs/DATASET_INVESTIGATION.md` from the supplied captures (PR #20).
- A fixed-header bias in length framing (`length_bias`), and a condition on any
  field, which the thermal-stand protocol needed (PR #20).
- A light theme for the deck and the site, and the reserve video
  `presentation/screencast.mp4` (PR #21, PR #23).
- `docs/DEFENSE_CHECKLIST.md` and `docs/FAQ_FOR_JUDGES.md` for the defense
  (PR #26).
- `docs/DEMO_CHEATSHEET.md` (a print-and-keep one-pager for the demo) and
  `presentation/Q_and_A.md` (fifteen defense questions in short form), linked
  from the README document list.
- `presentation/fonts.py`, which embeds Tektur, Montserrat and JetBrains Mono
  into `slides.pptx` as obfuscated `.fntdata` parts, so the deck renders its own
  typefaces on a machine that has none of them installed.
- Field types `float`, `varint`, `tlv` and bit fields, decoded by the rule engine
  and covered by the rule schema.
- CSV and JSONL result export: `write_result` picks the format from the output
  suffix, alongside the contract JSON.
- Request/response pairing (`src/hypothesis/pairing.py`): turns carry a
  confidence and the observations it rests on, and the protocol CLI gained a
  `pair` subcommand.
- Researcher annotations stored in the project (`src/project/annotations.py`),
  with `annotate` and `annotations` subcommands, and an Annotations section in
  both report renderers.

### Changed

- The deck was rebuilt as editable native PPTX text with click build-ins, then
  reduced to nineteen slides with varied layouts and no overflow (PR #16,
  PR #21, PR #25).
- The final pass trimmed the animations to at most three click build-ins per
  slide and a plain fade transition everywhere; the cover, the section
  dividers, the recording slide and the closing slide are now static. The
  recording slide's play badge moved to a 40 px marker in the bottom-right
  corner, the metric note states that the 4 GiB budget is on a 16 GiB machine,
  and the PPTX captions and labels were raised to 14 pt.
- The defense script was split into a 5-minute and a 10-minute route with
  timings derived from the spoken text (PR #24).
- The test counts across the documentation were refreshed to the merged
  revision, and the deck and verification documents resynced to the 14-slide
  deck (PR #16, PR #18, PR #25, PR #26).
- The README, the audit, the portability report and the presentation
  verification now quote 781 tests and the published `v1.0.0` archive
  (PR #26).

### Fixed

- The interface now fits small windows, and the Russian labels are complete,
  including the Settings theme names (PR #17).
- The deck overflow and the reserve-clip length were corrected (PR #16, PR #23).
- The stale "organizer captures not available" limit was replaced with the
  received-and-analysed state (PR #20, PR #26).

### Removed

- The merged feature branches were cleaned up after the dataset work landed
  (PR #20).
- The browser-downloaded `sample_protocol.tar*` archives left in the repository
  root; the dataset itself is committed under `tests/corpus/real/`, and the
  duplicates are ignored.

