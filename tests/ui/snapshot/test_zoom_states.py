"""Zoom levels apply to the bytes and the tree together.

The snapshot modules pin the zoom at 100 percent. Here the three documented
levels are exercised directly, and the rendered image is asserted to differ
between them, which is what proves the zoom reached the widget rather than only
the stored number.
"""

from __future__ import annotations

from tests.ui.support import ZOOM_FONTS, grab, image_bytes, set_state


def test_zoom_applies_the_documented_font_sizes(window, app, zoom):
    set_state(window, app, language="en", theme_mode="dark", resolution=(1280, 800), zoom=zoom)
    hex_font, tree_font = ZOOM_FONTS[zoom]
    assert window.hex_view.font_size == hex_font
    assert window.session_tree.font_size == tree_font


def test_zoom_levels_render_differently(window, app):
    set_state(window, app, language="en", theme_mode="dark", resolution=(1280, 800), zoom=100)
    at_100 = image_bytes(grab(window))
    set_state(window, app, language="en", theme_mode="dark", resolution=(1280, 800), zoom=200)
    at_200 = image_bytes(grab(window))
    assert at_100 != at_200


def test_zoom_is_bounded(window, app):
    set_state(window, app, language="en", theme_mode="dark", resolution=(1280, 800), zoom=100)
    window._set_zoom(999, 999)
    assert window.hex_view.font_size <= 28
    window._set_zoom(0, 0)
    assert window.hex_view.font_size >= 8


def test_language_and_theme_combinations_render(window, app, language, theme_mode):
    set_state(window, app, language=language, theme_mode=theme_mode, resolution=(1280, 800), zoom=100)
    image = grab(window)
    assert image.width() >= 1280
    assert image.height() >= 800
