# Portability

The submission must run on a Linux x86-64 machine other than the one it was
built on, so the suite is checked in clean containers rather than only on the
development host. This page records what was checked, how, and the result. It
covers requirement R5 (reproducible transfer) at the level of the environment.

## Target

- Linux x86-64.
- Python 3.12 or newer.
- No system services and no network at run time; every command runs offline.

## Checks

| Environment | Python | Command | Result |
| --- | --- | --- | --- |
| Ubuntu 22.04 (glibc 2.35) | 3.12 | `scripts/test_in_docker.sh ubuntu:22.04 3.12` | 183 passed, 1 skipped |
| Ubuntu 24.04 (glibc 2.39) | 3.13 | `scripts/test_in_docker.sh ubuntu:24.04 3.13` | 183 passed, 1 skipped |
| Debian 13 development host | 3.13 | `pytest tests/ -q` | 183 passed, 1 skipped |
| Fresh clone, new venv | 3.13 | `pip install -e ".[dev]"` + README/USAGE commands | all run |

The one skipped test is the rule path, which needs the `src.protocol` engine
from the protocol/GUI branch; it runs once that branch is merged.

## What each check does

`scripts/test_in_docker.sh` copies the working tree into an image, installs the
pinned dependencies into a virtual environment, and runs the suite. It takes an
image and a Python version, so the same script covers both ends of the supported
range:

```
scripts/test_in_docker.sh                 # ubuntu:22.04, python 3.12
scripts/test_in_docker.sh ubuntu:24.04 3.13
```

The distribution Python on Ubuntu 22.04 is 3.10, so the script adds the
deadsnakes PPA when the requested interpreter is not the distribution one. The
build steps are chained into one `RUN` line so the Dockerfile stays a single
instruction. The script uses the Docker daemon directly when the current user can
reach the socket and falls back to `sudo -n` when it cannot.

## Dependencies in a clean environment

- `PySide6==6.8.1` installs from the `manylinux_2_28` wheel, which needs glibc
  2.28 or newer. Ubuntu 22.04 and 24.04 both satisfy this. No build tools, no
  compiler, and no system Qt are required; the wheel carries the Qt libraries.
- `dpkt==1.9.8`, `PyYAML==6.0.2`, and the pinned development tools install
  without errors.
- No install warns or fails on either Python version.

## Findings

No portability defect was found. Two notes are worth keeping:

- `git` is not present in a minimal container. The submission builder reads the
  author from `git config` when rendering its manifest and treats a missing
  `git` as an empty identity rather than failing, so the builder also runs in a
  stripped environment.
- The suite must not depend on a working tree. It does not: the corpus and the
  reference exports are committed, and `scripts/generate_corpus` rebuilds them
  deterministically when needed.

## Reproducing without Docker

Where Docker is unavailable, a clean virtual environment on any Linux x86-64
host reproduces the check:

```
git clone https://github.com/Pavel1778/madrigal-protocol-lab.git
cd madrigal-protocol-lab
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
pytest tests/ -q
```

Expected: the suite passes. Then run the walkthrough in `docs/USAGE.md`.
