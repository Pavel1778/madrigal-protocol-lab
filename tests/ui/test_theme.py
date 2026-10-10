"""Tests for the theme token sets and the theme manager.

The theme is real behaviour, not a constant: a manager applies a palette and a
style sheet to a live application, and switching must change what the widgets
draw. The tests check the token contract, that both sets reach the contrast the
accessibility guidelines ask for, and that a switch recolours a live view.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

try:
    from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

    from src.ui import theme  # noqa: E402
    from src.ui.model import UNCOVERED, ByteAnnotation  # noqa: E402
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)


@pytest.fixture()
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    theme.load_fonts(application)
    return application


@pytest.fixture()
def manager(app, tmp_path):
    settings = QtCore.QSettings(str(tmp_path / "theme.ini"), QtCore.QSettings.Format.IniFormat)
    return theme.ThemeManager(app, settings=settings, mode="dark")


def test_themes_share_the_same_tokens():
    assert set(theme.DARK.as_dict()) == set(theme.LIGHT.as_dict())


def test_both_themes_pass_wcag_contrast():
    from src.ui.theme import contrast

    for name in ("dark", "light"):
        failures = [c for c in contrast.check(theme.THEMES[name]) if not c.passes]
        assert not failures, f"{name}: {failures}"


def test_colour_tokens_are_hex():
    for token in theme.THEMES.values():
        for value in token.colour_tokens().values():
            assert len(value) == 7 and value.startswith("#")


def test_relative_luminance_extremes():
    from src.ui.theme import contrast

    assert contrast.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert contrast.contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=0.01)


def test_stylesheet_reflects_the_active_theme():
    dark = theme.build_stylesheet(theme.DARK)
    light = theme.build_stylesheet(theme.LIGHT)
    assert theme.DARK.background in dark
    assert theme.LIGHT.background in light
    assert theme.LIGHT.background not in dark


def test_manager_persists_and_restores_mode(app, tmp_path):
    settings = QtCore.QSettings(str(tmp_path / "theme.ini"), QtCore.QSettings.Format.IniFormat)
    manager = theme.ThemeManager(app, settings=settings, mode="dark")
    manager.set_mode("light")
    assert manager.theme.name == "light"

    restored = theme.ThemeManager(app, settings=settings)
    assert restored.mode == "light"
    assert restored.theme.name == "light"


def test_toggle_switches_between_dark_and_light(manager):
    assert manager.theme.name == "dark"
    manager.toggle()
    assert manager.theme.name == "light"
    manager.toggle()
    assert manager.theme.name == "dark"


def test_unknown_mode_falls_back_to_default(app, tmp_path):
    settings = QtCore.QSettings(str(tmp_path / "theme.ini"), QtCore.QSettings.Format.IniFormat)
    manager = theme.ThemeManager(app, settings=settings, mode="chartreuse")
    assert manager.mode == theme.DEFAULT_MODE


def test_system_mode_resolves_to_a_known_theme(manager):
    assert manager.resolve("system") in theme.THEMES


def test_palette_carries_the_theme_colours(manager):
    palette = theme.build_palette(manager.theme)
    assert palette.color(QtGui.QPalette.ColorRole.Window).name().lower() == manager.theme.background.lower()


def test_theme_changed_signal_fires_on_switch(manager):
    seen: list[str] = []
    manager.themeChanged.connect(seen.append)
    manager.apply("light")
    assert seen[-1] == "light"


def test_hex_view_recolours_on_theme_switch(manager):
    from src.ui.hex_view import HexView

    view = HexView()
    annotations = [ByteAnnotation(kind=UNCOVERED) for _ in range(8)]
    view.set_stream(b"\x00" * 8, annotations)

    manager.apply("dark")
    view.apply_theme()
    selections = view.extraSelections()
    dark_selection = selections[0].format.background().color().name().lower()
    manager.apply("light")
    view.apply_theme()
    selections = view.extraSelections()
    light_selection = selections[0].format.background().color().name().lower()

    assert dark_selection == theme.DARK.status_uncovered.lower()
    assert light_selection == theme.LIGHT.status_uncovered.lower()
    assert dark_selection != light_selection


def test_main_window_switches_theme_live(app):
    from src.ui.main_window import MainWindow

    window = MainWindow()
    try:
        window.set_theme_mode("light")
        assert theme.current().name == "light"
        assert theme.LIGHT.background in app.styleSheet()
        window.set_theme_mode("dark")
        assert theme.current().name == "dark"
    finally:
        window.set_theme_mode("dark")
        window.close()


def _luminance(token: str) -> float:
    from src.ui.theme import contrast

    return contrast.relative_luminance(token)


def test_dark_theme_avoids_pure_black_and_white():
    """The dark ground must not be #000000 (OLED smear) nor snow-white text."""
    dark = theme.DARK
    assert dark.background.lower() != "#000000"
    for token in (dark.background, dark.surface, dark.surface_alt, dark.border):
        assert _luminance(token) > 0.0, token
    assert dark.text_primary.lower() != "#ffffff"
    assert _luminance(dark.text_primary) < 1.0


def test_dark_theme_has_elevation_order():
    """Nearer surfaces are lighter: background < surface < surface_elevated."""
    dark = theme.DARK
    assert _luminance(dark.background) < _luminance(dark.surface)
    assert _luminance(dark.surface) < _luminance(dark.surface_elevated)
    assert _luminance(dark.surface_alt) <= _luminance(dark.surface_elevated)
    # A raised surface must actually differ from the panel, or the elevation is
    # invisible.
    assert dark.surface_elevated.lower() != dark.surface.lower()


def test_zoom_clamps_and_scales_fonts(app):
    base = theme.body_font(10).pixelSize()
    try:
        assert theme.set_zoom(10_000) == theme.MAX_ZOOM
        assert theme.body_font(10).pixelSize() > base
        assert theme.set_zoom(1) == theme.MIN_ZOOM
        assert theme.body_font(10).pixelSize() < base
    finally:
        theme.set_zoom(theme.DEFAULT_ZOOM)
    assert theme.body_font(10).pixelSize() == base
    assert theme.zoom() == theme.DEFAULT_ZOOM


def test_stylesheet_scales_with_zoom(app):
    theme.set_zoom(theme.DEFAULT_ZOOM)
    base = theme.build_stylesheet(theme.DARK)
    try:
        theme.set_zoom(200)
        scaled = theme.build_stylesheet(theme.DARK)
        assert scaled != base
        assert "font-size: 26px;" in scaled
    finally:
        theme.set_zoom(theme.DEFAULT_ZOOM)
