"""Visual theme for the application window.

The palette, typography and geometry follow the client style sheet
(``docs/STYLE.md``): dark background, one bordeaux accent, Tektur for headings
and Montserrat for body text, 4 px corners, no soft shadows. Status colours are
used only for statuses.

The token sets live in :mod:`src.ui.theme.dark` and :mod:`src.ui.theme.light`;
this module keeps the font helpers and the font loader, which do not depend on
the active theme.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui

HEADING_FAMILY = "Tektur"
BODY_FAMILY = "Montserrat"
MONO_FAMILY = "DejaVu Sans Mono"

# Zoom bounds as a percentage of the base size, so 100 is the un-zoomed view.
MIN_ZOOM = 60
MAX_ZOOM = 300
DEFAULT_ZOOM = 100

# The active zoom, applied by every font factory below. Callers ask for a base
# size (the one stored in settings); the factory turns it into the pixel size on
# screen, so a view that re-reads its fonts picks up a new zoom for free.
_zoom_percent = DEFAULT_ZOOM

_FONT_FILES = (
    "Montserrat-Regular.ttf",
    "Montserrat-SemiBold.ttf",
    "Tektur-Medium.ttf",
    "Tektur-SemiBold.ttf",
)


def fonts_dir() -> Path:
    """Directory holding the bundled font files."""
    return Path(__file__).resolve().parents[3] / "assets" / "fonts"


def zoom() -> int:
    """The active zoom as a percentage (100 is un-zoomed)."""
    return _zoom_percent


def set_zoom(percent: int) -> int:
    """Clamp and store the zoom percentage; return the value kept."""
    global _zoom_percent
    _zoom_percent = max(MIN_ZOOM, min(MAX_ZOOM, int(percent)))
    return _zoom_percent


def step_zoom(delta: int) -> int:
    """Move the zoom by ``delta`` percentage points and return the new value."""
    return set_zoom(_zoom_percent + delta)


def _scaled(base_pixels: int) -> int:
    return max(1, round(base_pixels * _zoom_percent / 100))


def body_font(size: int = 10, semibold: bool = False) -> QtGui.QFont:
    """The body font at ``size``, optionally semibold, at the active zoom."""
    font = QtGui.QFont(BODY_FAMILY, size)
    font.setPixelSize(_scaled(max(9, size + 3)))
    font.setWeight(QtGui.QFont.Weight.DemiBold if semibold else QtGui.QFont.Weight.Normal)
    return font


def heading_font(size: int = 12, semibold: bool = True) -> QtGui.QFont:
    """The heading font at ``size``, semibold by default, at the active zoom."""
    font = QtGui.QFont(HEADING_FAMILY, size)
    font.setPixelSize(_scaled(max(11, size + 3)))
    font.setWeight(QtGui.QFont.Weight.DemiBold if semibold else QtGui.QFont.Weight.Medium)
    return font


def mono_font(size: int = 10) -> QtGui.QFont:
    """The fixed-pitch font used for hex and byte views, at the active zoom."""
    font = QtGui.QFont(MONO_FAMILY, size)
    font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
    font.setPixelSize(_scaled(max(10, size + 3)))
    font.setFixedPitch(True)
    return font


def load_fonts(app: QtGui.QGuiApplication | None = None) -> list[str]:
    """Register the bundled fonts and return the families that loaded.

    A missing file is skipped rather than fatal: the application still runs on
    the platform defaults, and ``application_font_families`` tells the caller
    what was actually installed.
    """
    families: list[str] = []
    for name in _FONT_FILES:
        path = fonts_dir() / name
        if not path.is_file():
            continue
        font_id = QtGui.QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families.extend(QtGui.QFontDatabase.applicationFontFamilies(font_id))
    return families
