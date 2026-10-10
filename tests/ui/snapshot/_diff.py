"""Baseline comparison for the snapshot tests.

A snapshot baseline lives in ``tests/ui/snapshot/baselines`` and is a PNG saved
by Qt itself. The state under the image (language, theme, zoom, window size) is
pinned by ``tests.ui.support`` so the picture is the same on every machine; the
glyphs inside it are not, because font rasterization differs between platforms
and between Qt builds. A byte comparison therefore passes on the machine that
recorded a baseline and fails on a runner that renders the same window a shade
differently, which says nothing about the interface.

The comparison is instead perceptual and coarse. Both images are reduced to
greyscale and pooled into blocks; the mean difference over the whole frame and
the fraction of blocks that differ strongly are both checked. Antialiasing and a
focus ring move a few pixels a little and stay inside the tolerance; a swapped
theme, a changed layout or a missing widget moves whole regions a lot and fails.
The tolerance is deliberately generous on glyph shape and tight on structure.

When a baseline is missing (first run, or an intentional new state) it is
written and the test is skipped rather than failed. When a baseline differs
beyond tolerance, the actual image, a highlighted difference image and a text
file with the measured metrics are written under ``.snapshot-actual`` for the CI
artefact upload, and the test fails with the paths.

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

# Pooling and tolerances. A block is BLOCK x BLOCK pixels; the frame passes when
# the mean per-pixel difference is under MEAN_LIMIT and no more than
# HOT_FRACTION of the blocks differ by HOT_LEVEL or more. The mean limit absorbs
# the small, everywhere antialiasing difference between platforms; the block
# limit catches a region that changed content or colour.
BLOCK = 8
MEAN_LIMIT = 6.0
HOT_LEVEL = 48
HOT_FRACTION = 0.02


def _rgba_bytes(image: QtGui.QImage) -> bytes:
    if image.format() != QtGui.QImage.Format.Format_RGBA8888:
        image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    return bytes(image.constBits())


def _measure(actual_path: Path, baseline_path: Path) -> dict[str, float]:
    """Return the perceptual metrics between the two PNG files."""
    from PIL import Image, ImageChops, ImageStat  # type: ignore

    actual = Image.open(actual_path).convert("L")
    baseline = Image.open(baseline_path).convert("L")
    if actual.size != baseline.size:
        return {"mean": float("inf"), "hot_fraction": 1.0}

    diff = ImageChops.difference(actual, baseline)
    mean = ImageStat.Stat(diff).mean[0] / 255.0

    width, height = diff.size
    pooled = diff.resize(
        (max(1, width // BLOCK), max(1, height // BLOCK)), Image.Resampling.BOX
    )
    values = pooled.tobytes()
    hot = sum(1 for value in values if value >= HOT_LEVEL)
    hot_fraction = hot / len(values) if values else 0.0
    return {"mean": mean, "hot_fraction": hot_fraction}


def _within_tolerance(metrics: dict[str, float]) -> bool:
    return metrics["mean"] <= MEAN_LIMIT and metrics["hot_fraction"] <= HOT_FRACTION


def _write_artifact(name: str, actual: QtGui.QImage, metrics: dict[str, float]) -> Path:
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
    metrics_path = ARTIFACT_DIR / f"metrics_{name}.txt"
    metrics_path.write_text(
        f"mean={metrics['mean']:.4f} hot_fraction={metrics['hot_fraction']:.4f}\n",
        encoding="utf-8",
    )
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
        _write_artifact(name, image, {"mean": float("inf"), "hot_fraction": 1.0})
        pytest.fail(
            f"snapshot {name} size changed: baseline {baseline.width()}x{baseline.height()}, "
            f"actual {image.width()}x{image.height()}"
        )
    if _rgba_bytes(baseline) == _rgba_bytes(image):
        return

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    probe_path = ARTIFACT_DIR / f"actual_{name}"
    image.save(str(probe_path), "PNG")
    metrics = _measure(probe_path, baseline_path)
    if _within_tolerance(metrics):
        probe_path.unlink(missing_ok=True)
        return

    artifact = _write_artifact(name, image, metrics)
    pytest.fail(
        f"snapshot {name} differs from its baseline beyond tolerance "
        f"(mean {metrics['mean']:.2f} > {MEAN_LIMIT} or hot blocks "
        f"{metrics['hot_fraction']:.3f} > {HOT_FRACTION}); "
        f"actual written to {artifact.relative_to(REPO_ROOT)}"
    )

