---
name: madrigal-ci
description: Reproduce the madrigal-protocol-lab CI pipeline locally (Python 3.12/3.13). Use when running tests, linting, type-checking, or investigating a CI failure on this repository.
---

# madrigal-protocol-lab CI

Reproduce CI locally before pushing. The commands below mirror
`.github/workflows/ci.yml`; when that file and this skill disagree, the workflow
wins.

## Environment

- CI matrix: Python **3.12** and **3.13**, on `ubuntu-latest` and `ubuntu-22.04`.
- `requires-python = ">=3.12"`; ruff `target-version = "py312"`; mypy
  `python_version = "3.12"`.
- Install: `pip install -e ".[dev,web]"`. The `web` extra is needed by
  `tests/ui` (FastAPI `TestClient`) and the `test` job installs it; the
  `ui-tests` and `audit` jobs install `.[dev]` only.

## Commands

Lint — the only gate enforced by the `code-quality` job:

    ruff check .

Format check — **commented out** in CI, not a gate:

    ruff format --check .

Type check — **commented out** in CI, not a gate (mypy is not run with
`--strict`; see `docs/AUDIT.md` for the deferred findings):

    mypy .

Tests, with the same offscreen platform CI uses:

    QT_QPA_PLATFORM=offscreen pytest tests/ -q

UI tests with the coverage CI collects (matches the `ui-tests` job):

    QT_QPA_PLATFORM=offscreen pytest tests/ui -q \
      --cov=src.ui --cov-report=term-missing --cov-report=xml:coverage-ui.xml

Dependency audit (the `audit` job fails on any new advisory):

    pip-audit

## Pre-commit hook

`.githooks/pre-commit` (enable once per clone:
`git config core.hooksPath .githooks`) runs a fast subset on staged files:

    ruff check --select "E4,E7,E9,F" --ignore E501 <staged .py files>
    pytest tests/protocol tests/hypothesis -q -p no:cacheprovider

## Known pitfalls

- **UI tests need `libegl1` first of all.** PySide6 links `libEGL` at import
  time; without it `tests/ui` does not collect at all (`ImportError:
  libEGL.so.1`). `QT_QPA_PLATFORM=offscreen` alone is not enough. On
  Debian/Ubuntu: `apt-get install -y libegl1 libgl1 libglib2.0-0 libxkbcommon0
  libdbus-1-3 libfontconfig1` (this is exactly what the CI "Install Qt runtime
  libraries" step installs). In a headless dev container the missing piece is
  usually just `libegl1`; `fontconfig`, `dbus`, `GL` and `xkbcommon` are
  commonly present already — check with
  `python -c "import ctypes.util; print(ctypes.util.find_library('EGL'))"`.
- `ruff format --check` and `mypy .` are commented out in
  `.github/workflows/ci.yml`. Do not treat them as gates, and mypy is not
  `--strict` here.
- No coverage threshold is enforced. Coverage is collected for `src.ui` only,
  in the `ui-tests` job.
- The full suite takes roughly **8 minutes** on 4 cores (UI tests dominate). Run
  it in the background and poll the log; do not block a foreground shell on it.
- Reassembly is **single-threaded** — there is no `threading`, `asyncio` or
  lock in `src/`. 32-bit sequence wrap is handled with `SEQ_MASK = 0xFFFFFFFF`
  and modular arithmetic against a per-direction reference
  (`src/capture/reassembly.py`).

## CI failure triage

1. Reproduce with the exact command from the failing job
   (`pytest tests/ -v`, or the `tests/ui` command with coverage).
2. If it is version-specific (3.12 vs 3.13), check the stdlib `asyncio` and
   `typing` changes for 3.13.
3. If it is UI-related, confirm `libegl1` and the other Qt libs are installed
   before assuming a test bug.
4. Push the fix on the same branch; do not open a second PR for the same change.
