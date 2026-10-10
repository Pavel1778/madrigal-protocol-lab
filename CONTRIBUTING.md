# Contributing

How changes are made in this repository. It is a small team on a fixed
hackathon schedule, so the rules are short and enforced by CI.

## Setup

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Branches

- `main` holds the integrated project. Do not push to it directly; open a pull
  request.
- Work on a short-lived branch named for its scope, for example
  `agent1/capture` or `agent2/protocol`. Delete it after the merge.

## Commits

Conventional Commits, English, subject at most 72 characters, imperative mood.

```
feat(capture): implement TCP stream reassembly
test(protocol): cover incomplete message framing
fix(ui): keep hex selection after a theme switch
docs(readme): note the portable project layout
```

The scope names the area (`capture`, `protocol`, `hypothesis`, `ui`, `project`,
`report`, `docs`, `ci`). One logical change per commit.

## Before pushing

Run the gates locally; CI runs the same ones.

```
QT_QPA_PLATFORM=offscreen pytest tests/ -q
ruff check .
```

CI also audits dependencies (`pip-audit` under `.[dev]`). `ruff format --check`
and `mypy .` are deferred for the modules outside this change, as recorded in
`docs/AUDIT.md`; run them on the files you touch.

- All tests pass. A new behaviour comes with a test over the real bytes and the
  real engine, not over a mock.
- No `TODO`, `FIXME`, commented-out code, or debug output.
- No secrets, no personal data, no large binaries outside `presentation/`.
- Do not commit `.venv/`, `__pycache__/`, `*.pcap` outside `tests/fixtures/`, a
  local `project.madrigal/`, or `.env`. The `.gitignore` covers all of these.

## Pull requests

- Keep the title in the commit style above.
- State what changed, why, and how it was checked (the command you ran).
- Do not merge your own pull request; it is reviewed first.

## Ownership by area

| Area | Directory | Owner |
| --- | --- | --- |
| Capture engine | `src/capture/` | branch `agent1/*` |
| Protocol and hypothesis engines | `src/protocol/`, `src/hypothesis/` | branch `agent2/*` |
| Window, project, report, presentation | `src/ui/`, `src/project/`, `src/report/`, `presentation/` | branch `agent3/*` |
| Shared contracts and schemas | `docs/CONTRACT.md`, `docs/schemas/` | change by agreement, never silently |
