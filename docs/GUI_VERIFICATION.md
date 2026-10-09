# GUI verification

A record of driving the window on the reference export produced by the capture
module, of what it shows, and of the defects found while doing so. The window
was run in offscreen mode on the same files the demonstration uses:

```
QT_QPA_PLATFORM=offscreen python -m src.ui.main_window \
  --capture tests/corpus/reference_export/corpus_capture_01.normalized.json \
  --rule examples/corpus_rule_v1.json
```

Every statement below was observed on this run; the automated form of the same
scenario is `tests/ui/test_e2e.py`.

## What opens

- Title: `Madrigal protocol laboratory - corpus_capture_01.normalized.json`.
- Menu bar: File (Open capture, Open rule, Save result, Quit), Rule (Apply to
  current direction, Apply to whole capture, Compare versions), Report (Show
  REPORT.md, Export Markdown, Export HTML), Help (About).
- Central splitter, three columns:
  - left: the session tree, group box "Sessions";
  - centre: a direction selector, the annotation legend, and the hex view,
    group box "Bytes";
  - right: a tab widget with Interpretation, Compare, Report and Version diff.
- Status bar: the byte provenance label on the left, a progress bar on the
  right, and a transient message area.
- Interpretation tab, three sub-tabs: Rule (editable text plus an Apply button),
  Messages (a table of offset, length, status, fields) and Counterexamples.

## Session tree (step 1-2)

Opening `corpus_capture_01` lists three sessions, `s1`, `s2`, `s3`, each with
its two directions and the byte count per direction. `capture_capture_defects`
lists one session whose parent node is marked `[gap, ambiguity]` and whose two
direction children are tinted, so a defective stream is visible before it is
opened. The status bar reads
`3 sessions  capture_id sha256:1a2f3637124a  diagnostics none` for the clean
capture.

## Click on a byte and its provenance (step 2)

Selecting session `s1`, direction `A_to_B` and clicking the byte at offset 4
moves the edit cursor onto that byte and writes to the status bar:

```
s1 A_to_B  offset 4   packet 3  seq 1001  ts 1700000000.004
```

The packet index, sequence number and timestamp come from the provenance entry
that covers the offset, so a reader can find the byte in the pcap. This is the
check the integration checklist asks for, and it passes.

## Applying a rule (step 3-4)

With `corpus_rule_v1.json` loaded, applying to `s1 A_to_B` reports
`rule v1  matched=60`. Applying to `s2 A_to_B` reports `mismatched=60` and the
Messages tab titles become `Messages (60)` and `Counterexamples (60)`. Selecting
the first counterexample scrolls the hex view to its offset and the status bar
shows that offset again. Every counterexample is tied to real bytes, not to a
description of them.

Applying to the whole capture reports
`matched=60, mismatched=80, incomplete=0, ambiguous=0, uncovered=0, not_applicable=140, outdated=0, unknown=0`,
which is the count the research report states.

## Version diff (step 5)

After v1 is applied to the whole capture and `corpus_rule_v2.json` is loaded and
applied to the whole capture, the Version diff tab shows:

```
report v1 -> v2
  resolved counterexamples: 80
  introduced counterexamples: 0
  unchanged mismatches: 0
  matched delta: +80
  coverage delta: +0.000
```

This is `src.hypothesis.diff.diff_reports` rendered in the window, so the
refinement is visible as resolved and introduced counterexamples rather than as
a bare change of numbers.

## Defects found during verification

Three defects were found and fixed on this branch; a fourth limit is recorded
but not changed.

1. Session diagnostics were never populated. `CaptureModel._read_sessions` built
   each `SessionInfo` without passing `diagnostics`, so the session tree never
   showed the `[gap, ambiguity]` marker. Fixed in `src/ui/model.py`.
2. The Version diff panel did not exist: "Compare versions" only posted a status
   message. Added the tab and wired it to `diff_reports` in `src/ui/main_window.py`
   and `src/ui/model.py`.
3. Re-applying the same rule marked its own previous run outdated, because
   `RuleModel.reload` bumped the version on every call. `reload` is now a no-op
   when the text is unchanged.
4. Limit, not changed: the window has no project menu. A portable project
   (`src.project`) can be created and moved, but only from the command line; the
   window opens a capture file, not a project directory. Scenario step 10 is
   therefore verified at the project level (`Project.export` / `Project.import_`
   round trip with matching capture digests) plus a window reopen on the same
   capture reproducing the same counts, which is what `tests/ui/test_e2e.py`
   checks. A project menu remains open work.

## What works

- Opens the reference capture and lists its sessions and directions.
- Renders the stream bytes and highlights diagnostics on the defects file.
- Click on a byte shows its packet index, sequence number and timestamp.
- Applying a rule shows matched and mismatched per direction and over the whole
  capture, with counterexamples bound to bytes.
- Selecting a counterexample jumps the hex view to its bytes.
- The version diff reports resolved and introduced counterexamples.
- Reopening on the same capture reproduces the same verdicts.

## What requires further work

- A project menu in the window (open/save a portable project, not just a file).
- Response (`B_to_A`) interpretation field by field; today the window frames the
  response stream but the rule scopes only `A_to_B`.
- Editing a rule in the Rule tab creates a new version but the window does not
  yet offer to name or save the edited rule to disk.
