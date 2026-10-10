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


def test_light_theme_uses_the_refined_surfaces():
    light = theme.LIGHT
    assert light.surface == "#FFFFFF"
    assert light.surface_elevated == "#F5F5F5"
    assert light.background == "#FAFAFA"
    assert light.border == "#E0E0E0"
    assert light.selection == "#E3F2FD"
    assert light.menu_selection == "#EEEEEE"


def test_light_selection_is_not_the_accent():
    # The accent is a dark bordeaux; a selected row on a light surface must use
    # the soft tint, not the accent fill.
    assert theme.LIGHT.selection != theme.LIGHT.accent
    assert theme.LIGHT.selection_text == theme.LIGHT.text_primary


def test_light_stylesheet_covers_interactive_states():
    sheet = theme.build_stylesheet(theme.LIGHT)
    for selector in (
        "QPushButton:hover",
        "QPushButton:pressed",
        "QPushButton:disabled",
        "QLineEdit:focus",
        "QTabBar::tab:selected",
        "QMenu::item:selected",
        "QScrollBar::handle:vertical",
    ):
        assert selector in sheet, selector


def test_refined_theme_tokens_reach_wcag():
    from src.ui.theme import contrast

    for name in ("dark", "light"):
        failures = [c for c in contrast.check(theme.THEMES[name]) if not c.passes]
        assert not failures, f"{name}: {failures}"


def test_dark_palette_highlight_is_the_accent():
    # The dark selection fill stays the accent, so the dark look is unchanged.
    palette = theme.build_palette(theme.DARK)
    assert palette.color(QtGui.QPalette.ColorRole.Highlight).name().lower() == theme.DARK.accent.lower()
    assert theme.DARK.button_pressed == theme.DARK.accent
