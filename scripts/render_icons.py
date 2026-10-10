"""Render the application icon to the raster sizes the desktop needs.

The source of truth is ``assets/icons/app/madrigal-protocol-lab.svg``. This
script writes the per-application PNGs next to it and the freedesktop icon-theme
copies under ``packaging/icons/hicolor/<size>x<size>/apps``.

It prefers ``inkscape`` or ``rsvg-convert`` when either is installed, and falls
back to the SVG renderer that ships with PySide6, so a developer without the
external tools can still regenerate the icons.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SVG = REPO_ROOT / "assets" / "icons" / "app" / "madrigal-protocol-lab.svg"
APP_DIR = SVG.parent
HICOLOR_DIR = REPO_ROOT / "packaging" / "icons" / "hicolor"

# Sizes the application bundles, and the extra size freedesktop expects (48).
APP_SIZES = (16, 32, 64, 128, 256, 512)
HICOLOR_SIZES = (16, 32, 48, 64, 128, 256, 512)


def _render_with_tool(tool: str, svg: Path, out: Path, size: int) -> bool:
    command = {
        "inkscape": [
            "inkscape",
            str(svg),
            "--export-type=png",
            f"--export-filename={out}",
            f"--export-width={size}",
            f"--export-height={size}",
        ],
        "rsvg-convert": ["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(out), str(svg)],
    }[tool]
    try:
        subprocess.run(command, check=True, capture_output=True)
        return out.is_file()
    except (OSError, subprocess.CalledProcessError):
        return False


def _render_with_qt(svg: Path, out: Path, size: int) -> bool:
    try:
        from PySide6 import QtCore, QtGui, QtSvg
    except ImportError:
        return False
    # Offscreen platform so the render works on a headless build host.
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    renderer = QtSvg.QSvgRenderer(str(svg))
    if not renderer.isValid():
        return False
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    renderer.render(painter)
    painter.end()
    ok = image.save(str(out), "PNG")
    del app
    return bool(ok)


def _render(svg: Path, out: Path, size: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    for tool in ("inkscape", "rsvg-convert"):
        if shutil.which(tool) and _render_with_tool(tool, svg, out, size):
            return
    if _render_with_qt(svg, out, size):
        return
    raise RuntimeError(
        f"no SVG renderer available for {out}; install inkscape or rsvg-convert"
    )


def main() -> int:
    if not SVG.is_file():
        print(f"missing source icon: {SVG}", file=sys.stderr)
        return 1

    for size in APP_SIZES:
        _render(SVG, APP_DIR / f"madrigal-protocol-lab-{size}.png", size)

    for size in HICOLOR_SIZES:
        if size not in APP_SIZES:
            _render(SVG, APP_DIR / f"madrigal-protocol-lab-{size}.png", size)
        _render(
            SVG,
            HICOLOR_DIR / f"{size}x{size}" / "apps" / "madrigal-protocol-lab.png",
            size,
        )

    print(f"rendered icons from {SVG.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
