# Merge plan

Preparation for merging the capture/infrastructure branch and the
protocol/GUI branch into `main`. Produced before the merge; the merge itself is
recorded at the end once it is done.

## Heads at preparation

| Ref | Commit | Note |
| --- | --- | --- |
| `main` | `5ac4f0b` | untouched, last common point |
| `agent1/capture` | `255dadc` | iteration six, CI green on the matrix |
| `agent2/protocol` | `0948fb0` | fast-forward of `5ac4f0b`, four audit fixes, CI green |
| merge base (`agent1/capture`, `agent2/protocol`) | `5dd907d` | the capture merge into `main` |

`5ac4f0b` is a child of `5dd907d`, so the true merge base between the two
branches is `5dd907d`, not `5ac4f0b`. Comparing both branches against `5ac4f0b`
instead would list every protocol file as changed on `agent1/capture` merely
because that branch predates them, which is an artifact of the base, not a
conflict. The comparison below uses the merge base.

## Files changed on each side

Relative to the merge base `5dd907d`:

- `agent1/capture` changes 50 files: `.dockerignore`, `.github/workflows/ci.yml`,
  `.gitignore`, `CHANGELOG.md`, `README.md`, `pyproject.toml`, `docs/AUDIT.md`,
  `docs/CAPTURE_API.md`, `docs/INTEGRATION.md`, `docs/INTEGRATION_CHECKLIST.md`,
  `docs/PORTABILITY.md`, `docs/USAGE.md`, the `scripts/` generators and the
  submission builder, the `src/capture/`, `src/project/`, `src/report/` modules,
  and the matching tests.
- `agent2/protocol` changes 70 files: `REPORT.md`, `assets/fonts/`,
  `docs/PROTOCOL_API.md`, `docs/REFERENCE_INVESTIGATION.md`, `docs/demo.md`,
  `docs/schemas/rule.schema.json`, `examples/`, `presentation/`, `scripts/run_reference_investigation.py`,
  the `src/protocol/`, `src/hypothesis/`, `src/ui/` modules, and the matching
  tests.

The two sets are **disjoint**. No file is changed on both sides.

```
git diff --name-only 5dd907d..origin/agent1/capture | sort > /tmp/a1.txt
git diff --name-only 5dd907d..origin/agent2/protocol | sort > /tmp/a2.txt
comm -12 /tmp/a1.txt /tmp/a2.txt      # empty
```

## Conflict assessment

| File | Changed on both? | Conflict type | Resolution |
| --- | --- | --- | --- |
| `.gitignore`, `.dockerignore` | no | none | keep both sides as merged |
| `README.md`, `ARCHITECTURE.md` | no | none | keep both sides as merged |
| `CHANGELOG.md` | no | none | keep both sides as merged |
| `.github/workflows/ci.yml` | no | none | keep the capture matrix and code-quality jobs |
| `pyproject.toml` | no | none | keep both sides as merged |
| `docs/**` | no | none | keep both sides as merged |

A dry run confirms this:

```
git merge-tree --write-tree origin/agent1/capture origin/agent2/protocol   # exit 0, no conflict
git merge-tree --write-tree origin/main origin/agent1/capture              # exit 0, no conflict
```

`merge-tree` exits non-zero and prints conflict markers only when there is a
textual conflict. Both runs exit zero, so neither merge needs conflict
resolution.

One semantic point to check after the merge, not a textual conflict: both sides
add tests and modules, and `main` gains the union. The capture tests must still
pass with `src.protocol` present (the one skipped rule test turns green), and
the protocol tests must pass alongside the capture modules. The full suite is
run after the merge to confirm this.

## Rehearsal

The merge was rehearsed in a throwaway worktree (`git worktree add`), not on
`main`, so the outcome is known before Phase B:

- `git merge --no-ff origin/agent2/protocol` completed with no conflict.
- `pip install -e ".[dev]"` then `pytest tests/ -q`: **371 passed**, no failure,
  no skip. The rule test that is skipped on `agent1/capture` alone runs here,
  because `src.protocol` is present.
- The end-to-end pipeline on `corpus_capture_01.pcapng` succeeds and the report
  renders. With `examples/corpus_rule_v1.json`, the run produces 60 matched
  messages and 80 counterexamples, the same figure recorded in the reference
  investigation, which confirms the capture and protocol stages are wired
  together correctly.

The worktree was removed afterwards; `main` and the working tree are unchanged.

## Merge order and rollback

1. `git checkout agent1/capture`
2. `git pull origin agent1/capture`
3. `git merge --no-ff origin/agent2/protocol -m "merge(protocol): ui audit, contract validation, is_confirmed fix"`
4. `pip install -e ".[dev]"` then `pytest tests/ -v` on the merged branch.
5. `git checkout main`, `git pull origin main`, `pytest tests/ -v`.
6. `git merge --no-ff agent1/capture -m "merge(capture): iteration six, CI matrix, submission builder, audit fixes"`
7. `pytest tests/ -v` on `main`.
8. `git push origin main`.
9. `git checkout agent1/capture` and `git merge main` so the branch is not left
   behind `main`.

Rollback: at any step before the push, `git merge --abort` returns the working
tree to the pre-merge state. Nothing reaches `main` until step 8, so a failure
in steps 4 or 7 is fully recoverable by aborting and reporting.

## Cleanliness checks

- `git ls-files | grep -i openhands` is empty: the agent memory directory is not
  tracked.
- `git log --all -p | grep -i "ghp_"` matches only `docs/AUDIT.md`, which quotes
  the search string as part of the audit text. No token is in history.
- `git log --all --format='%h %s' | grep -iE '\b(ai|llm|openhands|assistant)\b'`
  is empty: no commit subject or body mentions an assistant.
- `git grep -nE "TODO|FIXME"` outside the audit and checklist documents is
  empty.

### One item to raise with the participant

The only occurrences of the string `OpenHands` in the repository are the path
rules `.openhands/` in `.gitignore`, `.dockerignore`, and the exclusion list in
`scripts/build_submission.py`. These are ignore rules, not attribution, but a
reviewer searching the tree for the word will find them. If the submission rule
is read strictly, the three lines can be renamed to a neutral cache path, or
left as they are. Decision with the participant; not changed here.
