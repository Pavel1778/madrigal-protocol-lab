"""Portable investigation project: manifest, layout, and transfer.

Public API:

- :class:`Project` - :meth:`Project.create`, :meth:`Project.open`,
  :meth:`Project.add_capture`, :meth:`Project.export`, :meth:`Project.import_`
- :class:`Manifest` - the parsed ``manifest.json``
"""

from __future__ import annotations

from src.project.manifest import (
    ANNOTATIONS_FILE,
    CAPTURE_CONTRACT_VERSION,
    PROJECT_FORMAT_VERSION,
    Manifest,
    ManifestError,
    read_manifest,
    write_manifest,
)
from src.project.project import MANIFEST_FILE, Project, ProjectError

__all__ = [
    "ANNOTATIONS_FILE",
    "CAPTURE_CONTRACT_VERSION",
    "MANIFEST_FILE",
    "PROJECT_FORMAT_VERSION",
    "Manifest",
    "ManifestError",
    "Project",
    "ProjectError",
    "read_manifest",
    "write_manifest",
]
