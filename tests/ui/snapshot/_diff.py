"""Baseline comparison for the snapshot tests.

A snapshot baseline lives in ``tests/ui/snapshot/baselines`` and is a PNG saved
by Qt itself. The comparison is exact: the freshly rendered image is converted
to RGBA8888 and its pixel bytes are compared with the baseline loaded the same
way, so the round trip through the PNG encoder is symmetric and no tolerance is
needed.

When a baseline is missing (first run, or an intentional new state) it is
written and the test is skipped rather than failed. When a baseline differs, the
actual image and a highlighted difference image are written under
``.snapshot-actual`` for the CI artefact upload, and the test fails with the
paths.

Set ``MADRIGAL_UPDATE_SNAPSHOTS=1`` to rewrite every baseline in place.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6 import QtGui

from tests.ui.support import BASELINE_DIR, REPO_ROOT

ARTIFACT_DIR = REPO_ROOT / ".snapshot-actual"

_UPDATE = os.environ.get("MADRIGAL_UPDATE_SNAPSHOTS") == "1"


def _rgba_bytes(image: QtGui.QImage) -> bytes:
    if image.format() != QtGui.QImage.Format.Format_RGBA8888:
        image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    return bytes(image.constBits())


def _write_artifact(name: str, actual: QtGui.QImage) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    actual_path = ARTIFACT_DIR / f"actual_{name}"
    actual.save(str(actual_path), "PNG")
    diff_path = ARTIFACT_DIR / f"diff_{name}"
    try:
        from PIL import Image, ImageChops  # type: ignore

        a = Image.open(actual_path).convert("RGBA")
        b = Image.open(BASELINE_DIR / name).convert("RGBA")
        if a.size == b.size:
            ImageChops.difference(a, b).save(diff_path)
    except Exception:  # noqa: BLE001 - a missing Pillow only drops the diff image
        pass
    return actual_path


def assert_snapshot(name: str, image: QtGui.QImage) -> None:
    """Compare *image* with the baseline *name*, recording it when absent."""
    baseline_path = BASELINE_DIR / name
    if _UPDATE or not baseline_path.is_file():
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(baseline_path), "PNG")
        action = "updated" if _UPDATE else "recorded"
        pytest.skip(f"baseline {action}: {name}")

    baseline = QtGui.QImage(str(baseline_path))
    if baseline.isNull():
        pytest.fail(f"baseline {name} could not be read")
    if baseline.size() != image.size():
        _write_artifact(name, image)
        pytest.fail(
            f"snapshot {name} size changed: baseline {baseline.width()}x{baseline.height()}, "
            f"actual {image.width()}x{image.height()}"
        )
    if _rgba_bytes(baseline) == _rgba_bytes(image):
        return

    artifact = _write_artifact(name, image)
    pytest.fail(
        f"snapshot {name} differs from its baseline; "
        f"actual written to {artifact.relative_to(REPO_ROOT)}"
    )
