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

## v1.2.0

The final-stabilization release: the documentation, the presentation and the
reserve screencast are brought in line with the current tree, and the version is
bumped from `v1.1.0`. No product code changed.

### Changed

- The reserve screencast `presentation/screencast.mp4` was re-recorded from the
  current GUI: 3:40 (219.8 s), 1920x1080, 15 fps, no sound. The previous clip
  was 125 s and showed the pre-overhaul interface. The poster frame and the
  inlined `data:video/mp4` in the deck were refreshed.
- The presentation screenshots were regenerated from the current theme, and the
  deck PDFs and PPTX were rebuilt (15 slides).
- The release QR and the deck's release text now point at `v1.2.0`.
- The test count across the documentation is the measured 898 on the current
  `main` (794 on the frozen `v1.0.0` archive).
- The raw pcap/pcapng open path is documented in `README.md`, `docs/demo.md` and
  `docs/GUI_VERIFICATION.md`; the verification environment is recorded there too.

## Unreleased

Everything merged into `main` after the `v1.0.0` tag, by pull request. `v1.0.0`
is the merge of PR #14 (`f637644`); the entries below are the work that followed.

### Added

- A `Project` menu that manages a portable project directory: create, open,
  write the manifest, add a capture, store a named rule version, and export or
  import the project as a zip. `rule_text`/`save_rule` let the window write the
  same JSON document the CLI reads, and the new strings are translated in both
  catalogues.
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
- The deck carries Tektur, Montserrat and JetBrains Mono, inlined into the
  HTML, so it renders its own typefaces on a machine that has none of them
  installed.
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
- The reserve screencast is embedded in the deck: the demo slide (13) plays
  `public/screencast.mp4` in a `<video>` element (poster frame, controls,
  autoplay, loop, muted, playsinline) inlined as a `data:video/mp4` URI, and the
  printed PDF/PPTX carry the poster frame.
- A byte-state legend strip above the hex view (`src/ui/legend.py`): a
  collapsible row of painted swatches whose captions and swatches carry an
  explanatory tooltip, with a Settings switch to hide the strip.

### Changed

- The deck was rebuilt as a single self-contained HTML file, printed to PDF and
  packaged to PPTX as one full-bleed page per slide, reduced to a static
  fifteen-slide deck with varied layouts and no overflow (PR #16, PR #21,
  PR #25, PR #64).
- The deck is now static: no click build-ins and no transition animations. The
  demo slide plays the reserve clip in place of a play badge, the metric note
  states that the 4 GiB budget is on a 16 GiB machine, and the PDF and PPTX carry
  the poster frame.
- The defense script was split into a 5-minute and a 10-minute route with
  timings derived from the spoken text (PR #24).
- The test counts across the documentation were refreshed to the merged
  revision, and the deck and verification documents resynced to the 15-slide
  deck (PR #16, PR #18, PR #25, PR #26, PR #70).
- The README, the audit, the portability report and the presentation
  verification now quote the v1.0.0 test counts and the published `v1.0.0` archive
  (PR #26).
- The ASCII column caption is drawn in the same fixed-pitch face and size as the
  bytes and shifted by the document margin, so it lines up with the column it
  names instead of drifting left; the byte-state legend is now a compact strip
  above the hex view that folds onto further lines and collapses, instead of a
  row beside the direction selector.
- The documented test counts are the measured 957 total on the current `main`
  (620 without the interface suite, 589 without the interface and web suites),
  across the living docs and the deck Q&A.

### Fixed

- The interface now fits small windows, and the Russian labels are complete,
  including the Settings theme names (PR #17).
- The deck overflow and the reserve-clip length were corrected (PR #16, PR #23).
- The printed deck filled only the top of each page: Chromium fell back to
  Letter, so the content sat in the top two-thirds with a blank lower half. An
  `@media print` block now pins the page to 2560×1440 pt (16:9) with no margins
  and one slide per page, and the slides fill 92% of the height instead of 69%.
- The stale "organizer captures not available" limit was replaced with the
  received-and-analysed state (PR #20, PR #26).
- Marker-based framing no longer drops the bytes that precede a start marker.
  A run that belongs to no framed message (leading synchronisation noise, or
  debris between two messages) is now returned as an incomplete range instead of
  being discarded, matching the module contract that an un-framed range is
  reported rather than silently lost. Regression tests cover both the leading
  and the between-message case, and the whole stream is accounted for.
- The hex bytes were painted in the proportional body face: the application
  style sheet sets a family on every `QWidget`, which outranks `setFont`, so the
  hex columns did not line up and the ASCII column was not on a fixed grid. The
  byte area and its column caption now pin the fixed-pitch family themselves.

### Removed

- The merged feature branches were cleaned up after the dataset work landed
  (PR #20).
- The browser-downloaded `sample_protocol.tar*` archives left in the repository
  root; the dataset itself is committed under `tests/corpus/real/`, and the
  duplicates are ignored.

