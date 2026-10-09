"""Tests for the portable project container: create, open, transfer, verify."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from src.project import MANIFEST_FILE, Manifest, ManifestError, Project, ProjectError
from src.project.project import _sha256

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
CAPTURE = CORPUS / "corpus_capture_02.pcapng"


def _project(tmp_path: Path) -> Project:
    return Project.create(tmp_path / "project.madrigal", "investigation")


def test_create_writes_layout_and_manifest(tmp_path: Path) -> None:
    project = _project(tmp_path)
    root = project.root
    assert (root / MANIFEST_FILE).is_file()
    for directory in ("captures", "logs", "rules", "results", "reports"):
        assert (root / directory).is_dir()
    assert (root / "annotations.sqlite").is_file()

    manifest = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert manifest["contract_version"] == 1
    assert manifest["project_version"] == 1
    assert manifest["name"] == "investigation"
    assert manifest["captures"] == []
    assert manifest["annotations"] == "annotations.sqlite"


def test_create_refuses_existing_directory(tmp_path: Path) -> None:
    _project(tmp_path)
    with pytest.raises(ProjectError):
        Project.create(tmp_path / "project.madrigal", "second")


def test_open_round_trips_manifest(tmp_path: Path) -> None:
    project = _project(tmp_path)
    reopened = Project.open(project.root)
    assert reopened.name == "investigation"
    assert reopened.manifest.contract_version == 1


def test_add_capture_copies_and_records_digest(tmp_path: Path) -> None:
    project = _project(tmp_path)
    relative = project.add_capture(CAPTURE)
    assert relative == "captures/corpus_capture_02.pcapng"
    copied = project.root / relative
    assert copied.read_bytes() == CAPTURE.read_bytes()
    assert project.manifest.captures[0]["sha256"] == _sha256(CAPTURE)
    assert project.verify_captures() == []


def test_add_same_capture_twice_is_idempotent(tmp_path: Path) -> None:
    project = _project(tmp_path)
    first = project.add_capture(CAPTURE)
    second = project.add_capture(CAPTURE)
    assert first == second
    assert len(project.manifest.captures) == 1


def test_relocation_to_tmp_keeps_project_openable(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.add_capture(CAPTURE)
    moved = tmp_path / "elsewhere" / "project.madrigal"
    moved.parent.mkdir()
    shutil.copytree(project.root, moved)

    reopened = Project.open(moved)
    assert reopened.name == "investigation"
    assert reopened.path("captures", "corpus_capture_02.pcapng").is_file()
    # Relative paths mean the digest check still passes in the new location.
    assert reopened.verify_captures() == []


def test_export_and_import_round_trip(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.add_capture(CAPTURE)

    archive = tmp_path / "bundle.zip"
    project.export(archive)
    assert zipfile.is_zipfile(archive)

    restored = Project.import_(archive, tmp_path / "restored")
    assert restored.name == "investigation"
    assert restored.manifest.captures == project.manifest.captures
    assert restored.verify_captures() == []
    with zipfile.ZipFile(archive) as handle:
        assert MANIFEST_FILE in handle.namelist()
        # Directory entries are present so the layout survives the round trip.
        assert "captures/" in handle.namelist()


def test_import_detects_capture_digest_mismatch(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.add_capture(CAPTURE)
    archive = tmp_path / "bundle.zip"
    project.export(archive)

    # Corrupt the capture inside the archive.
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(
        tampered, "w"
    ) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.endswith(".pcapng"):
                data = b"not the same bytes"
            target.writestr(item, data)

    target_dir = tmp_path / "broken"
    with pytest.raises(ProjectError):
        Project.import_(tampered, target_dir)
    # The failed import leaves nothing behind.
    assert not target_dir.exists()


def test_import_rejects_missing_capture_file(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.add_capture(CAPTURE)
    archive = tmp_path / "bundle.zip"
    project.export(archive)

    stripped = tmp_path / "stripped.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(
        stripped, "w"
    ) as target:
        for item in source.infolist():
            if item.filename.endswith(".pcapng"):
                continue
            target.writestr(item, source.read(item.filename))

    with pytest.raises(ProjectError):
        Project.import_(stripped, tmp_path / "gaps")


def test_manifest_rejects_unknown_future_version(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest = json.loads((project.root / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest["project_version"] = 99
    (project.root / MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError):
        Project.open(project.root)


def test_manifest_round_trip_is_stable() -> None:
    manifest = Manifest.new("x")
    again = Manifest.from_dict(manifest.to_dict())
    assert again.to_dict() == manifest.to_dict()
