"""Tests for the submission builder.

The archive build and the manifest rendering are pure file operations, so they
are checked directly. The verification step shells out to pytest over the
extracted archive; it is driven on a tiny synthetic project so the test does not
re-run the whole suite, and it is skipped when a separate run exceeds a few
seconds.
"""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.build_submission import (
    MANIFEST_NAME,
    SubmissionError,
    build_archive,
    collect_files,
    missing_required,
    render_manifest,
    verify_archive,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def _seed(root: Path) -> None:
    """Write a minimal valid solution tree into ``root``."""
    for name in ("README.md", "ARCHITECTURE.md", "CHANGELOG.md", "LICENSE"):
        (root / name).write_text(f"# {name}\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'sample'\nversion = '0.1.0'\n", encoding="utf-8"
    )
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "CONTRACT.md").write_text("# Contract\n", encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    # An excluded cache directory that must not reach the archive.
    (root / "src" / "__pycache__").mkdir(exist_ok=True)
    (root / "src" / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"\x00\x01")


def test_archive_is_created_when_requirements_are_met(tmp_path: Path) -> None:
    _seed(tmp_path)
    stamp = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)

    result = build_archive(tmp_path, tmp_path / "dist", stamp=stamp)

    assert result.archive.is_file()
    assert result.archive.name == "submission_20261012_0930.zip"


def test_archive_holds_the_required_files_and_no_caches(tmp_path: Path) -> None:
    _seed(tmp_path)

    result = build_archive(
        tmp_path, tmp_path / "dist", stamp=datetime(2026, 10, 12, tzinfo=UTC)
    )
    with zipfile.ZipFile(result.archive) as bundle:
        names = bundle.namelist()
        manifest = bundle.read(MANIFEST_NAME).decode("utf-8")

    for required in (
        "README.md",
        "ARCHITECTURE.md",
        "CHANGELOG.md",
        "LICENSE",
        "pyproject.toml",
        "docs/CONTRACT.md",
        "src/app.py",
        MANIFEST_NAME,
    ):
        assert required in names

    assert not any("__pycache__" in name for name in names)
    assert not any(name.endswith(".pyc") for name in names)

    # The manifest carries every mandatory section.
    for heading in (
        "# Submission",
        "## Solution",
        "## Participant",
        "## Hackathon",
        "## What is implemented",
        "## Setup",
        "## Demo",
        "## Where things are",
    ):
        assert heading in manifest


def test_archive_reproduces_passing_tests_after_extraction(tmp_path: Path) -> None:
    _seed(tmp_path)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "test_value.py").write_text(
        "from src.app import VALUE\n\n\ndef test_value() -> None:\n    assert VALUE == 1\n",
        encoding="utf-8",
    )

    result = build_archive(
        tmp_path, tmp_path / "dist", stamp=datetime(2026, 10, 12, tzinfo=UTC)
    )
    workdir = tmp_path / "work"
    workdir.mkdir()

    check = verify_archive(result.archive, workdir)

    assert check.returncode == 0, check.stdout + check.stderr


def test_build_refuses_when_a_required_file_is_missing(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "docs" / "CONTRACT.md").unlink()

    files = collect_files(tmp_path)
    assert "docs/CONTRACT.md" in missing_required(files)

    with pytest.raises(SubmissionError):
        build_archive(
            tmp_path, tmp_path / "dist", stamp=datetime(2026, 10, 12, tzinfo=UTC)
        )


def test_collect_files_prunes_excluded_directories(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "marker.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    names = {f.as_posix() for f in collect_files(tmp_path)}

    assert "src/app.py" in names
    assert not any(name.startswith(".venv/") for name in names)
    assert not any(name.startswith(".git/") for name in names)


def test_manifest_records_the_author_and_hackathon(tmp_path: Path) -> None:
    text = render_manifest(ROOT, datetime(2026, 10, 12, tzinfo=UTC))

    assert "UMIRHack, 09-17 October 2026" in text
    assert "Protocol Laboratory, Madrigal" in text
    assert "madrigal-protocol-lab" in text
