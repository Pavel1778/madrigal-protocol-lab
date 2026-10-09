"""A portable investigation project on disk.

An investigation is not just a capture: it is the capture, the rules written
against it, the results of applying those rules, annotations, and reports. A
project binds all of that into one directory that can be copied to another
machine and opened there without editing a single path.

The layout is::

    project.madrigal/
        manifest.json
        captures/
        logs/
        rules/
        results/
        annotations.sqlite
        reports/

Everything the manifest points at is relative to the project root. The class
here owns creation, opening, adding captures, and moving the whole project in
and out of a zip archive.
"""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path

from src.project.manifest import (
    ANNOTATIONS_FILE,
    Manifest,
    ManifestError,
    read_manifest,
    utc_now,
    write_manifest,
)

DIRECTORIES = ("captures", "logs", "rules", "results", "reports")
MANIFEST_FILE = "manifest.json"

# A single capture is copied whole; the read is chunked so a large file does
# not have to fit in memory at once.
_CHUNK = 1 << 20


class ProjectError(ValueError):
    """Raised when a project cannot be created, opened, or imported."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


class Project:
    """An open investigation project rooted at ``root``."""

    def __init__(self, root: Path, manifest: Manifest) -> None:
        self._root = root.resolve()
        self._manifest = manifest

    # -- construction -----------------------------------------------------

    @classmethod
    def create(cls, path: Path, name: str) -> "Project":
        """Create a new project directory at ``path``.

        The directory must not exist yet, so a mistyped path cannot overwrite a
        finished investigation.
        """

        root = Path(path)
        if root.exists():
            raise ProjectError(f"{root} already exists")
        root.mkdir(parents=True)
        for directory in DIRECTORIES:
            (root / directory).mkdir()
        (root / ANNOTATIONS_FILE).touch()
        manifest = Manifest.new(name)
        write_manifest(root / MANIFEST_FILE, manifest)
        return cls(root, manifest)

    @classmethod
    def open(cls, path: Path) -> "Project":
        """Open the project at ``path``, validating its manifest."""

        root = Path(path).resolve()
        if not root.is_dir():
            raise ProjectError(f"{root} is not a directory")
        manifest = read_manifest(root / MANIFEST_FILE)
        missing = [d for d in DIRECTORIES if not (root / d).is_dir()]
        if missing:
            raise ProjectError(f"project is missing directories: {', '.join(missing)}")
        return cls(root, manifest)

    # -- accessors --------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    @property
    def manifest(self) -> Manifest:
        """The in-memory manifest. Call :meth:`save` after mutating it."""

        return self._manifest

    @property
    def name(self) -> str:
        return self._manifest.name

    def path(self, *parts: str) -> Path:
        """Resolve ``parts`` relative to the project root."""

        return self._root.joinpath(*parts)

    # -- mutations --------------------------------------------------------

    def save(self) -> None:
        """Write the manifest back to disk, refreshing ``updated_at``."""

        self._manifest.touch()
        write_manifest(self._root / MANIFEST_FILE, self._manifest)

    def add_capture(self, pcap_path: Path) -> str:
        """Copy a capture into the project and register it.

        Returns the relative path of the copy inside ``captures/``. The file is
        copied under its own name; if a different capture with that name is
        already registered, the new copy gets a numeric suffix so nothing is
        overwritten.
        """

        source = Path(pcap_path)
        if not source.is_file():
            raise ProjectError(f"no capture at {source}")

        digest = _sha256(source)
        existing = self._manifest.has_capture(f"captures/{source.name}")
        if existing == digest:
            return f"captures/{source.name}"

        target_name = source.name
        counter = 1
        while self._manifest.has_capture(f"captures/{target_name}") is not None:
            stem, dot, suffix = source.name.partition(".")
            target_name = f"{stem}-{counter}{dot}{suffix}"
            counter += 1

        relative = f"captures/{target_name}"
        shutil.copy2(source, self._root / relative)
        self._manifest.captures.append(
            {"path": relative, "sha256": digest, "added_at": utc_now()}
        )
        return relative

    def verify_captures(self) -> list[str]:
        """Return the relative paths of captures whose bytes have changed."""

        broken: list[str] = []
        for entry in self._manifest.captures:
            relative = entry["path"]
            target = self._root / relative
            if not target.is_file():
                broken.append(relative)
                continue
            if _sha256(target) != entry.get("sha256"):
                broken.append(relative)
        return broken

    # -- transfer ---------------------------------------------------------

    def export(self, out_zip: Path) -> None:
        """Write the whole project to ``out_zip``.

        Paths inside the archive are relative to the project root, so importing
        it elsewhere recreates the same tree.
        """

        out = Path(out_zip)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.save()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            # Record the directory tree explicitly so empty directories survive
            # the zip round trip; a plain file walk drops them.
            for directory in DIRECTORIES:
                archive.writestr(f"{directory}/", b"")
            for path in sorted(self._root.rglob("*")):
                if not path.is_file():
                    continue
                archive.write(path, path.relative_to(self._root).as_posix())

    @classmethod
    def import_(cls, in_zip: Path, target_dir: Path) -> "Project":
        """Unpack ``in_zip`` into ``target_dir`` and open it.

        Every registered capture is checked against its recorded digest. A
        mismatch aborts the import and removes the partial directory, so a
        corrupt archive never leaves a half-open project behind.
        """

        archive_path = Path(in_zip)
        target = Path(target_dir)
        if not archive_path.is_file():
            raise ProjectError(f"no archive at {archive_path}")
        if target.exists():
            raise ProjectError(f"{target} already exists")
        target.mkdir(parents=True)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                cls._safe_extract(archive, target)
            project = cls.open(target)
            broken = project.verify_captures()
            if broken:
                raise ProjectError(
                    "capture digests do not match after import: "
                    + ", ".join(broken)
                )
            return project
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

    @staticmethod
    def _safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
        """Extract an archive, refusing members that escape ``target``."""

        base = target.resolve()
        for member in archive.namelist():
            destination = (target / member).resolve()
            if destination != base and base not in destination.parents:
                raise ProjectError(f"archive member escapes target: {member}")
        archive.extractall(target)


__all__ = [
    "ANNOTATIONS_FILE",
    "MANIFEST_FILE",
    "Manifest",
    "ManifestError",
    "Project",
    "ProjectError",
    "read_manifest",
    "write_manifest",
]
