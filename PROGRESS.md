# Progress

Daily checkpoint of the work. One entry per day: done, broken, next.

## 2026-10-09

- Done: repository foundation created (structure, contracts, schemas, style,
  CI, license, packaging).
- Broken: none.
- Next: capture engine modules and fixtures.

## 2026-10-09 (later)

- Done: rule field types (float, varint, tlv, bits), CSV/JSONL result export,
  request/response pairing with a confidence, and researcher annotations stored
  in the project and rendered in both reports.
- Broken: none. `ruff check .` clean, the offline suite passes (no UI/web extras).
- Next: full-suite and CI check, then hold for review.

## 2026-10-14

- Done: `rework/ui-usable` merged into `main` (start guide, rule builder, web
  capture upload). Documentation resynced to the merged tree: the suite is now
  846 tests (613 without the Qt UI tests), `ruff check .` clean.
- Broken: none. The test count had drifted in the docs (840 -> 830 -> 846); the
  figure now matches `main`.
- Next: hold for the final release; the deck and screenshots were refreshed on
  `main` separately.

## 2026-10-14 (interface test isolation)

- Done: the interface-language tests are order independent. `tests/ui/conftest.py`
  now removes the `QTranslator` a test installs, so a window closed with Russian
  selected no longer leaks its catalogue into the next module. Added
  `docs/DEVELOPMENT.md`: the translation workflow and the mandatory `lupdate`
  strip step.
- Broken: none. Full suite 846 passed, `ruff check .` clean.
- Next: usability pass for a first-time user (hypothesis wizard, bundled sample
  project); the start guide, rule builder and provenance card are already in.

## 2026-10-14 (ux-select merged)

- Done: `feat/ux-select` merged into `main` (PR #59) — the bundled demo
  (`src/ui/samples/`, `File -> Open demo`, web `GET /demo`), the timeline view
  and the web status guidance. Documentation resynced: the suite is now
  **849 tests** (615 without the Qt UI tests), `ruff check .` clean.
- Broken: none. The test count had drifted in the docs (846 -> 849); the figure
  now matches `main`.
- Next: full GUI usability overhaul (`ux/full-overhaul`) — empty-state screen,
  Russian-only strings, rule wizard, provenance inspector.

## 2026-10-14 (bilingual catalogue)

- Done: both interface languages now load a compiled catalogue; the English one
  (`madrigal_en.ts`/`.qm`) is filled one for one from the source strings and is
  built by `scripts/update_translations.sh` alongside Russian. Captions the
  window assembled from variables were replaced with literals so `lupdate`
  extracts them, and the rule-status line and provenance card are rebuilt on a
  language switch instead of keeping the language they were first rendered in.
- Broken: none. The suite is now 852 tests (615 without the Qt UI tests), full
  run 852 passed, `ruff check .` clean; the counters in the docs moved from
  846/613 to 852/615.
- Next: hold for review; the branch `ux/full-overhaul` (PR #65) is green.

## 2026-10-15 (independent audit — framing residue)

- Done: independent audit of the current `main` (v1.2.0 tree with the learning
  mode). One real defect fixed in `src/protocol/framing.py`: `marker_based`
  framing returned nothing for the bytes before a start marker, so a stream that
  did not begin on a start marker (leading synchronisation noise, or debris
  between two messages) silently lost those bytes from the message list while
  the module docstring promises an un-framed range is reported as `incomplete`.
  The residue is now returned as an incomplete `Message` with reason
  `bytes_before_start_marker`, and the end marker is consumed even when
  `include_markers` is false, so the whole stream is accounted for. Two
  regression tests added (`test_marker_based_reports_bytes_before_the_first_start_marker`,
  `test_marker_based_reports_debris_between_messages`).
- Broken: none. Non-UI suite 617 passed, `ruff check .` clean; framing, protocol,
  hypothesis, report and project suites green. A 5000-case engine fuzz and a
  2000-case framing fuzz over random bytes raised no unexpected exception.
- Docs: the documented test counts moved 896/615/584 -> 898/617/586 across the
  docs and the deck Q&A, matching the measured `main`.
- Next: hold for review.

## 2026-10-15 (project management and rule versions)

- Done: the GUI project workflow. A `Project` menu creates and opens a portable
  project directory, writes its manifest, copies a capture in and registers it,
  stores a named rule version, and exports or imports the project as a zip.
  `src/protocol/rule.py` gained `rule_text`/`save_rule` so a rule written from the
  window is the same JSON the CLI reads. The window title tracks the open project
  and capture, closing with unsaved project changes asks first, and the new
  strings are translated in both catalogues.
- Broken: none. Non-UI suite 620 passed, `ruff check .` clean; every `tests/ui`
  module passes on its own. New tests: `tests/ui/test_project_management.py` and
  three serialization cases in `tests/protocol/test_rule.py`.
- Docs: the documented test counts moved 898/617/586 -> 914/620/589 across the
  living docs and the deck Q&A, matching the measured `main`.
- Next: hold for review.

## 2026-10-16 (legend strip and final count sync)

- Done: PR #72 integrated. The ASCII column caption is drawn in the same
  fixed-pitch face and size as the bytes, and the byte-state legend is a compact,
  collapsible strip above the hex view (`src/ui/legend.py`) with a Settings switch
  to hide it. The HexView font fallback — the application style sheet outranked
  `setFont`, so the hex columns did not line up — is fixed. Both catalogues were
  rebuilt on top of the project-management strings and the legend strings are
  translated in Russian. The deck path is consistent: the dark deck PDF is
  `presentation/slides.pdf` (the upload renamed it from `slide.pdf`), so the
  docs, the README build steps, the hygiene notes and the verification commands
  now all name `slides.pdf`, keeping `slide-light.pdf` for the light twin.
- Broken: none. Suite 932 tests (620 without the interface suite). `ruff check .`
  clean, `git diff --check` clean; every `tests/ui` module passes on its own and
  the snapshot baselines match.
- Docs: the living docs and the deck Q&A now quote 932/620/589 and the 15-slide
  deck; the Russian mirror's test and page counts are synced to the same figures
  (the mirror prose still tracks an earlier revision; the English is the source
  of truth).
- Next: hold for review.

## 2026-10-16 (final integration)

- Done: the last two feature PRs are integrated into `main`. The course
  spotlight and its guard tests arrive from `ux/learning-spotlight-and-guards`,
  and the defence material arrives from `presentation/defense-fixes` (the
  author's guide, the 13-slide cut, the short demo clip and the screenshot
  index). The screenshot-refresh branch is superseded: it re-lands the capture
  set an earlier commit reverted and conflicts on the renamed deck assets, so
  its unique text is already covered by the two merged branches.
- Broken: none. The suite on the integrated `main` is 957 tests (620 without
  the interface suite, 589 without the interface and web suites), all passing;
  `ruff check .` clean and `git diff --check` clean.
- Docs: the living docs and the deck Q&A quote the measured 957 total.
- Next: hold for review.
