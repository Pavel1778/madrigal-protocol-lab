"""Tests for the packaging scripts.

The build scripts are shell, so their content is checked rather than executed.
The executable bit is asserted through git, which records it; a plain zip
extract does not restore Unix modes, so the mode is not asserted on an extracted
copy of the tree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

EXECUTABLE_SCRIPTS = [
    "scripts/build_linux_binary.sh",
    "scripts/build_deb.sh",
    "scripts/build_appimage.sh",
    "scripts/build_run.sh",
    "packaging/install.sh",
]
BINARY_DEPENDENT = [
    "scripts/build_deb.sh",
    "scripts/build_appimage.sh",
    "scripts/build_run.sh",
]


def _git_root() -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def test_build_scripts_exist_with_shebang() -> None:
    for name in EXECUTABLE_SCRIPTS:
        script = ROOT / name
        assert script.is_file(), name
        first = script.read_text(encoding="utf-8").splitlines()[0]
        assert first.startswith("#!"), name
        assert "bash" in first, name


def test_installer_payload_contract() -> None:
    body = (ROOT / "packaging" / "install.sh").read_text(encoding="utf-8")
    # It installs under a prefix the caller controls, never into a fixed path.
    assert "PREFIX=" in body
    assert "madrigal-lab" in body


def test_build_scripts_are_executable_in_git() -> None:
    if _git_root() is None:
        pytest.skip("not a git checkout; mode is recorded by git, not by zip")
    for name in EXECUTABLE_SCRIPTS:
        result = subprocess.run(
            ["git", "ls-files", "-s", name],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.stdout.startswith("100755"), f"{name} is not executable"


@pytest.mark.parametrize("name", BINARY_DEPENDENT)
def test_release_scripts_require_the_binary(tmp_path: Path, name: str) -> None:
    # Each script derives the project root from its own location and checks for
    # dist/madrigal-lab. Copy just the script into an empty tree so the guard
    # runs before any packaging tool is touched.
    (tmp_path / "scripts").mkdir()
    (tmp_path / name).write_text(
        (ROOT / name).read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = subprocess.run(
        ["bash", str(tmp_path / name)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "build_linux_binary.sh" in result.stderr
