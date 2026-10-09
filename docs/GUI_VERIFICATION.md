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
- Menu bar: File (Open normalized capture, Open rule, Save result, Quit), Rule
  (Apply to current direction, Apply to whole capture, Compare versions), Report
  (Show REPORT.md, Export Markdown, Export HTML), Help (Quick help, About).
  Every menu and item carries a keyboard mnemonic; Quick help is F1.
- Central splitter, three columns:
  - left: the session tree, group box "Sessions";
  - centre: a direction selector, a colour-chip annotation legend, and the hex
    view, group box "Bytes";
  - right: a tab widget with Interpretation, Compare, Report and Version diff.
- Status bar: the byte provenance label on the left, a progress bar on the
  right (hidden while idle), and a transient message area.
- Interpretation tab, three sub-tabs: Rule (editable text, live parse feedback,
  field-type completion, and Apply to current direction / Apply to whole capture
  / Load example buttons), Messages (a table of offset, length, status, fields)
  and Counterexamples.

The legend is not a text label. Each byte kind is a swatch painted with the same
brush the hex view uses, so `gap` and `ambiguity` show their hatch and the names
sit next to their colour; the legend cannot drift from the bytes it explains.

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
description of them. A direction with no mismatch is not left blank: the
Counterexamples tab reads `no counterexamples in this direction`, so an empty
list is never mistaken for a clean result.

Applying to the whole capture reports
`matched=60, mismatched=80, incomplete=0, ambiguous=0, uncovered=0, not_applicable=140, outdated=0, unknown=0`,
which is the count the research report states. The same run fills the
Counterexamples tab from the corpus report, so the tab and the status line agree
and each corpus counterexample carries its session and direction; clicking one
switches to that session and direction and jumps to its bytes.

`File - Save result` writes the contract result: the file validates against
`docs/schemas/result.schema.json` and carries `contract_version`, `rule_id`,
`rule_version`, `capture_id`, `messages` and `summary`, so a saved result is the
same shape the command line produces.

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

## Hypotheses panel (step 4b)

The Hypotheses tab is filled every time a rule is applied, and reads the rule
against the messages it applies to. Applying to a single direction scores the
candidates over that one stream; applying to the whole capture (Rule, Apply to
whole capture) scores them over every scoped stream, which is the comparison the
refinement is decided on. With `corpus_rule_v1.json` applied to the whole capture,
the tab lists one row per candidate reading of each `hypothesis` field
(`command`, `target`, `value`), with the field, the candidate name, support,
contradiction count and score. The score is colour-coded: green at or above 0.9,
amber between 0.5 and 0.9, grey below. For `command` the top rows are
`entropy_enum` and `low_cardinality` at 1.00 (140 support, 0 contradiction), and
the row for `constant` (the reading v1 declares) sits at 0.43 (60 support, 80
contradict). Selecting a row emits the first evidence offset and jumps the hex
view to that message, the same jump a counterexample click makes. The panel is
driven from `src.hypothesis.alternatives.suggest_alternatives`, so it shows the
engine's own output, not a second computation. `tests/ui/test_hypotheses_view.py`
covers the colour bands, the row-per-candidate layout and the emitted offset, and
`tests/ui/test_main_window.py::test_hypotheses_tab_fills_on_apply` checks the tab
is populated after an apply.

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

A later interaction pass over the same window raised further items; the ones
closed on this branch are: the corpus run now refreshes the Messages and
Counterexamples tabs (they had shown the previous single-direction run); a
counterexample can be browsed from the corpus report; `Save result` writes the
contract shape above; the legend is painted swatches; the progress bar resets;
the empty panels explain themselves; and the file dialogs remember the last
directory.

## What works

- Opens the reference capture and lists its sessions and directions.
- Renders the stream bytes and highlights diagnostics on the defects file.
- Click on a byte shows its packet index, sequence number and timestamp.
- Applying a rule shows matched and mismatched per direction and over the whole
  capture, with counterexamples bound to bytes.
- Selecting a counterexample jumps the hex view to its bytes.
- The version diff reports resolved and introduced counterexamples.
- Reopening on the same capture reproduces the same verdicts.
- An empty panel states why it is empty: the Messages tab reads `no messages
  yet - apply a rule...` before any run, and a clean direction reads `no
  counterexamples in this direction` rather than showing nothing.
- The file dialogs remember the last directory used, so a second open does not
  start at the repository root again.
- The progress bar resets to zero and hides when a run finishes, so it never
  shows a stale fraction of a previous run.
- The rule editor gives live parse feedback (a red status on invalid text, a
  plain one when the rule parses) and completes field types as they are typed.

## What requires further work

- A project menu in the window (open/save a portable project, not just a file).
- Response (`B_to_A`) interpretation field by field; today the window frames the
  response stream but the rule scopes only `A_to_B`.
- Editing a rule in the Rule tab creates a new version but the window does not
  yet offer to name or save the edited rule to disk.
