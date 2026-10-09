"""The manifest that describes a portable investigation project.

The manifest is the single index of a project directory. Every path in it is
relative to the project root, so the whole directory can be moved or copied to
another machine without rewriting anything. Timestamps are recorded in UTC.

See the project format section of ``docs/INTEGRATION.md`` for the layout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Version of the on-disk project container format.
PROJECT_FORMAT_VERSION = 1
# Version of the normalized capture contract the container is built around.
CAPTURE_CONTRACT_VERSION = 1

ANNOTATIONS_FILE = "annotations.sqlite"

_MANIFEST_KEYS = (
    "contract_version",
    "project_version",
    "name",
    "created_at",
    "updated_at",
    "captures",
    "rules",
    "results",
    "annotations",
)


class ManifestError(ValueError):
    """Raised when a manifest is missing, malformed, or unsupported."""


def utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string with a ``Z`` suffix."""

    stamp = datetime.now(timezone.utc).replace(microsecond=0)
    return stamp.isoformat().replace("+00:00", "Z")


@dataclass
class Manifest:
    """The parsed contents of ``manifest.json``."""

    name: str
    created_at: str
    updated_at: str
    captures: list[dict[str, Any]] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    annotations: str = ANNOTATIONS_FILE
    contract_version: int = CAPTURE_CONTRACT_VERSION
    project_version: int = PROJECT_FORMAT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in _MANIFEST_KEYS}

    def touch(self) -> None:
        """Mark the manifest as modified now."""

        self.updated_at = utc_now()

    def has_capture(self, relative_path: str) -> str | None:
        """Return the recorded digest for ``relative_path``, or ``None``."""

        for entry in self.captures:
            if entry.get("path") == relative_path:
                return entry.get("sha256")
        return None

    @classmethod
    def new(cls, name: str) -> "Manifest":
        stamp = utc_now()
        return cls(name=name, created_at=stamp, updated_at=stamp)

    @classmethod
    def from_dict(cls, data: Any) -> "Manifest":
        if not isinstance(data, dict):
            raise ManifestError("manifest must be a JSON object")
        missing = [key for key in _MANIFEST_KEYS if key not in data]
        if missing:
            raise ManifestError(f"manifest is missing keys: {', '.join(missing)}")

        version = data["project_version"]
        if not isinstance(version, int):
            raise ManifestError("project_version must be an integer")
        if version > PROJECT_FORMAT_VERSION:
            raise ManifestError(
                f"project format {version} is newer than supported "
                f"{PROJECT_FORMAT_VERSION}"
            )

        for key in ("captures", "rules", "results"):
            if not isinstance(data[key], list):
                raise ManifestError(f"{key} must be a list")

        return cls(
            name=str(data["name"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            captures=list(data["captures"]),
            rules=list(data["rules"]),
            results=list(data["results"]),
            annotations=str(data["annotations"]),
            contract_version=int(data["contract_version"]),
            project_version=version,
        )


def read_manifest(path: Path) -> Manifest:
    """Read and validate the manifest at ``path``."""

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManifestError(f"no manifest at {path}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest at {path} is not valid JSON") from exc
    return Manifest.from_dict(data)


def write_manifest(path: Path, manifest: Manifest) -> None:
    """Write ``manifest`` to ``path`` with a stable, readable layout."""

    path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
