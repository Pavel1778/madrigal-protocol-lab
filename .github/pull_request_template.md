## What

<!-- One paragraph: what this change does. -->

## Why

<!-- The problem it solves, or the requirement it serves. -->

## How it was checked

<!-- The command you ran and what it printed. Example:
     QT_QPA_PLATFORM=offscreen pytest tests/ -q -> 664 passed
-->

## Checklist

- [ ] Tests pass locally (`pytest tests/ -q`); new behaviour has a test over the real code path.
- [ ] `ruff check .` is clean.
- [ ] No `TODO`, `FIXME`, commented-out code, or debug output.
- [ ] No contract change (or `docs/CONTRACT.md` and the schemas are updated).
- [ ] No secrets or personal data committed.
