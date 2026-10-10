"""Shared helpers for the interface end-to-end and snapshot tests.

Every render is pinned in four independent ways so a screenshot is reproducible
byte for byte:

* the language (``en`` or ``ru``) is set explicitly, never left to the desktop
  locale;
* the theme (``dark`` or ``light``) is set explicitly;
* the zoom is set explicitly, and the zoom steps are names of the three levels
  the product documents (100, 150, 200 percent), not font sizes guessed at the
  call site;
* the window size is fixed, so a smaller or larger desktop cannot move the
  layout under the comparison.

The window is offscreen. No display, no window manager and no user settings are
involved: the settings root is redirected by ``tests/ui/conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui, QtWidgets

from src.ui import theme
from src.ui.main_window import MainWindow

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT = REPO_ROOT / "tests" / "corpus" / "reference_export"
CAPTURE_01 = EXPORT / "corpus_capture_01.normalized.json"
RULE_V1 = REPO_ROOT / "examples" / "corpus_rule_v1.json"

BASELINE_DIR = Path(__file__).resolve().parent / "snapshot" / "baselines"

# Window sizes a laptop or a desktop actually uses, smallest first.
RESOLUTIONS: tuple[tuple[int, int], ...] = (
    (1024, 768),
    (1280, 800),
    (1366, 768),
    (1440, 900),
    (1600, 900),
)

LANGUAGES: tuple[str, ...] = ("en", "ru")
THEMES: tuple[str, ...] = ("dark", "light")

# Zoom level -> (byte font, tree font). The tree tracks the bytes two steps
# smaller, matching the window's own zoom step.
ZOOM_FONTS: dict[int, tuple[int, int]] = {
    100: (13, 11),
    150: (19, 17),
    200: (26, 24),
}
ZOOM_LEVELS: tuple[int, ...] = (100, 150, 200)


def configure_app(app: QtWidgets.QApplication) -> None:
    """Load the bundled fonts and apply the base style sheet once."""
    theme.load_fonts(app)
    app.setStyleSheet(theme.build_stylesheet())


def load_window(app: QtWidgets.QApplication) -> MainWindow:
    """Open the reference capture and rule in a fresh window."""
    from src.ui.main_window import open_default_window

    return open_default_window(app, capture=CAPTURE_01, rule=RULE_V1)


def set_state(
    window: MainWindow,
    app: QtWidgets.QApplication,
    *,
    language: str,
    theme_mode: str,
    resolution: tuple[int, int] | None = None,
    zoom: int | None = None,
) -> None:
    """Apply language, theme, zoom and size, then settle the event loop."""
    window.set_language(language)
    window.set_theme_mode(theme_mode)
    if zoom is not None:
        hex_font, tree_font = ZOOM_FONTS[zoom]
        window._set_zoom(hex_font, tree_font)
    if resolution is not None:
        window.setFixedSize(*resolution)
    app.processEvents()
    app.processEvents()


def grab(window: MainWindow) -> QtGui.QImage:
    """Return the window rendered to an RGBA image."""
    image = window.grab().toImage()
    if image.format() != QtGui.QImage.Format.Format_RGBA8888:
        image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    return image


def image_bytes(image: QtGui.QImage) -> bytes:
    """Return the raw pixel bytes of *image*."""
    return bytes(image.constBits())


def snapshot_name(theme_mode: str, language: str, resolution: tuple[int, int]) -> str:
    width, height = resolution
    return f"{theme_mode}_{language}_{width}x{height}.png"
