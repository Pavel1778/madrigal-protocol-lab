"""Build the submission archive for the hackathon.

The archive is a self-contained copy of the solution: the source, the tests,
the committed corpus and reference exports, the documentation, and a
``SUBMISSION.md`` that describes the entry. It is meant to be handed over as a
single file and to run after unpacking, so the builder refuses to produce one
while the working tree is dirty or while the test suite is red. A branch can be
pinned with ``--branch``; by default the builder runs on any branch.

    python -m scripts.build_submission

The build checks the entry, then verifies the result: the archive is extracted
into a temporary directory and the suite is run from there, so a broken archive
is never reported as ready.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent

# Empty means the builder runs on any branch; pass --branch to pin one.
EXPECTED_BRANCH = ""

# Directories copied into the archive when present.
INCLUDE_DIRS = (
    ".github",
    "assets",
    "docs",
    "examples",
    "packaging",
    "presentation",
    "scripts",
    "src",
    "tests",
)

# Top-level files copied into the archive when present.
INCLUDE_ROOT_FILES = (
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "Dockerfile",
    "LICENSE",
    "PROGRESS.md",
    "README.md",
    "REPORT.md",
    "pyproject.toml",
)

# Files that must be present for a valid submission.
REQUIRED_FILES = (
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "docs/CONTRACT.md",
    "docs/SUBMISSION.md",
    "examples/corpus_rule_v1.json",
)

# Directory names pruned wherever they appear in the tree.
EXCLUDED_DIRS = frozenset(
    {
        ".benchmark",
        ".eggs",
        ".git",
        ".mypy_cache",
        ".agent-cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vite-cache",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "out",
        "venv",
    }
)

# File suffixes and names pruned wherever they appear.
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})
EXCLUDED_NAMES = frozenset({".coverage"})

MANIFEST_NAME = "SUBMISSION.md"
DEFAULT_OUT_DIR = ROOT / "dist"

HACKATHON = "UMIRHack, 09-17 October 2026"
CASE = "Protocol Laboratory, Madrigal"


class SubmissionError(RuntimeError):
    """A precondition or the verification step failed."""


@dataclass
class SubmissionResult:
    """The built archive and the entries it holds."""

    archive: Path
    entries: list[str] = field(default_factory=list)


def _is_excluded(relative: PurePosixPath) -> bool:
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return True
    if relative.suffix in EXCLUDED_SUFFIXES:
        return True
    return relative.name in EXCLUDED_NAMES


def collect_files(root: Path) -> list[Path]:
    """Return the files to archive, relative to ``root``, sorted."""
    selected: list[Path] = []

    for name in INCLUDE_ROOT_FILES:
        candidate = root / name
        if candidate.is_file():
            selected.append(Path(name))

    for directory in INCLUDE_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            if _is_excluded(relative):
                continue
            selected.append(Path(relative.as_posix()))

    return sorted(set(selected))


def missing_required(files: list[Path]) -> list[str]:
    """Return the required entries absent from ``files``."""
    present = {f.as_posix() for f in files}
    return [name for name in REQUIRED_FILES if name not in present]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        # ``git`` may be absent in a minimal environment; report it as a failed
        # command rather than letting the caller crash.
        return subprocess.CompletedProcess(
            ["git", *args], 127, "", f"git is not available: {error}"
        )


def working_tree_clean(root: Path) -> bool:
    """True when there is nothing staged or unstaged and no untracked file."""
    result = _git(root, "status", "--porcelain")
    if result.returncode != 0:
        raise SubmissionError(f"git status failed in {root}: {result.stderr.strip()}")
    return result.stdout.strip() == ""


def current_branch(root: Path) -> str:
    result = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if result.returncode != 0:
        raise SubmissionError(
            f"git rev-parse failed in {root}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def committed_identity(root: Path) -> tuple[str, str]:
    """Return the author name and email recorded in the git configuration."""
    name = _git(root, "config", "user.name").stdout.strip()
    email = _git(root, "config", "user.email").stdout.strip()
    return name, email


def run_tests(
    root: Path,
    target: str = "tests/",
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    child_env = None
    if env is not None:
        child_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=child_env,
    )


def run_quality(root: Path) -> dict[str, subprocess.CompletedProcess[str] | None]:
    """Run the static checks that do not gate the build."""
    results: dict[str, subprocess.CompletedProcess[str] | None] = {}
    for name, command in (
        ("ruff", ["ruff", "check", "."]),
        ("mypy", [sys.executable, "-m", "mypy", "."]),
    ):
        if name == "ruff" and shutil.which("ruff") is None:
            results[name] = None
            continue
        results[name] = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False
        )
    return results


def render_manifest(root: Path, stamp: datetime) -> str:
    """Render the SUBMISSION.md text for the archive."""
    name, email = committed_identity(root)
    author = f"{name} <{email}>" if email else name or "not recorded"
    lines = [
        "# Submission",
            "",
            "## Solution",
            "",
            "madrigal-protocol-lab: a local desktop laboratory for investigating",
            "an undocumented binary protocol over TCP. It opens a PCAP or PCAPNG",
            "capture, rebuilds each directional TCP stream with per-byte",
            "provenance, applies declarative interpretation rules, verifies them",
            "on a corpus to surface counterexamples, and writes a portable",
            "project with a report.",
            "",
            "## Participant",
            "",
            f"- Author: {author}",
            "- Team size: one",
            "",
            "## Hackathon",
            "",
            f"- {HACKATHON}",
            f"- Case: {CASE}",
            "",
            "## What is implemented",
            "",
            "- `src/capture/` - PCAP and PCAPNG reading, TCP session",
            "  identification, directional reassembly with gap and ambiguity",
            "  diagnostics, per-byte provenance, normalized JSON export,",
            "  streaming mode, Wireshark export, CLI.",
            "- `src/project/` - portable on-disk investigation, manifest with",
            "  relative paths and sha256, zip export and import, end-to-end",
            "  pipeline CLI.",
            "- `src/report/` - the investigation rendered to Markdown and to a",
            "  self-contained HTML page.",
            "- `src/protocol/`, `src/hypothesis/` and `src/ui/` - the rule engine",
            "  and the PySide6 interface, delivered by the protocol/GUI branch.",
            "  When that module is absent the capture, project and report stages",
            "  still run.",
            "",
            "## Setup",
            "",
            "```",
            "python3.12 -m venv .venv",
            "source .venv/bin/activate",
            'pip install -e ".[dev]"',
            "```",
            "",
            "Python 3.12 or newer on Linux x86-64.",
            "",
            "## Demo",
            "",
            "The step-by-step walkthrough is in `docs/demo.md` when the",
            "protocol/GUI branch is merged; the capture and project walkthrough",
            "is in `docs/USAGE.md`. The shortest end-to-end run:",
            "",
            "```",
            "python -m scripts.generate_corpus",
            "python -m src.project.cli pipeline \\",
            "  --pcap tests/corpus/corpus_capture_01.pcapng \\",
            "  --project project.madrigal \\",
            "  --report REPORT.md",
            "pytest tests/ -q",
            "```",
            "",
            "## Where things are",
            "",
            "- Sources: `src/`",
            "- Tests and corpus: `tests/`, with reference exports under",
            "  `tests/corpus/reference_export/`",
            "- Reports: `REPORT.md`, `docs/`",
            "- Presentation: `presentation/`",
            "- Contracts and schemas: `docs/CONTRACT.md`, `docs/schemas/`",
            "",
            "## Archive",
            "",
            f"- Built: {stamp.strftime('%Y-%m-%d %H:%M UTC')}",
            "- Wipe the extracted directory and reinstall to run from scratch;",
            "  all paths inside the archive are relative.",
            "",
        ]

    detail = root / "docs" / "SUBMISSION.md"
    if detail.is_file():
        lines.extend(["", "---", "", detail.read_text(encoding="utf-8").rstrip()])
    return "\n".join(lines) + "\n"


def build_archive(
    root: Path,
    out_dir: Path,
    *,
    stamp: datetime | None = None,
    archive_name: str | None = None,
) -> SubmissionResult:
    """Write the submission archive and return its path and entries."""
    stamp = stamp or datetime.now(UTC)
    files = collect_files(root)
    absent = missing_required(files)
    if absent:
        raise SubmissionError("required files are missing: " + ", ".join(absent))

    out_dir.mkdir(parents=True, exist_ok=True)
    name = archive_name or f"submission_{stamp.strftime('%Y%m%d_%H%M')}.zip"
    archive = out_dir / name

    entries: list[str] = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for relative in files:
            bundle.write(root / relative, arcname=relative.as_posix())
            entries.append(relative.as_posix())
        bundle.writestr(MANIFEST_NAME, render_manifest(root, stamp))
        entries.append(MANIFEST_NAME)

    return SubmissionResult(archive=archive, entries=sorted(entries))


def verify_archive(
    archive: Path,
    workdir: Path,
    *,
    pytest_target: str = "tests/",
) -> subprocess.CompletedProcess[str]:
    """Extract the archive into ``workdir`` and run the suite from there."""
    extract = workdir / "extracted"
    if extract.exists():
        shutil.rmtree(extract)
    extract.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extract)
    if not (extract / MANIFEST_NAME).is_file():
        raise SubmissionError(f"{MANIFEST_NAME} is missing from the archive")
    return run_tests(extract, pytest_target)


def _report_quality(
    results: dict[str, subprocess.CompletedProcess[str] | None],
) -> None:
    for name, result in results.items():
        if result is None:
            print(f"{name}: not installed, skipped")
        elif result.returncode == 0:
            print(f"{name}: clean")
        else:
            print(f"{name}: findings (not fatal)")
            print(result.stdout.strip() or result.stderr.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument(
        "--out-dir", type=Path, default=None, help="directory for the archive"
    )
    parser.add_argument(
        "--branch",
        default=EXPECTED_BRANCH,
        help="required git branch (empty to skip the check)",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="build even when the working tree has changes",
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="skip the pre-build test run (the archive is still verified)",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="do not extract and re-run the suite",
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    out_dir = args.out_dir or (root / "dist")

    try:
        if not args.allow_dirty and not working_tree_clean(root):
            print("working tree is not clean; commit or stash first", file=sys.stderr)
            return 1

        if args.branch:
            branch = current_branch(root)
            if branch != args.branch:
                print(
                    f"on branch {branch!r}, expected {args.branch!r}",
                    file=sys.stderr,
                )
                return 1

        if not args.no_test:
            tests = run_tests(root)
            if tests.returncode != 0:
                print("the test suite is red; not building", file=sys.stderr)
                print(tests.stdout.strip(), file=sys.stderr)
                return 1
            print("tests: green")

        _report_quality(run_quality(root))

        result = build_archive(root, out_dir)
        print(f"archive: {result.archive}")
        print(f"entries: {len(result.entries)}")

        if not args.skip_verify:
            with tempfile.TemporaryDirectory() as workdir:
                check = verify_archive(result.archive, Path(workdir))
            if check.returncode != 0:
                print("the archive does not reproduce the suite", file=sys.stderr)
                print(check.stdout.strip(), file=sys.stderr)
                return 1
            print("archive verified: the suite passes after extraction")
    except SubmissionError as error:
        print(str(error), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
