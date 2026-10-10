"""Visual themes for the application window.

Two token sets live here: :data:`DARK` (the Madrigal identity, the default) and
:data:`LIGHT` (an alternative for bright rooms and printed screenshots).

Widgets take colours, fonts and geometry from the active token set, never from
a literal, so :class:`ThemeManager` can switch themes at run time without a
restart. The module-level constants are the legacy names: they read from the
active set at import time and are kept so colour choices that predate the
manager keep working. New code should read a token off :func:`current` or a
manager, not a module constant.
"""

from __future__ import annotations

from .dark import DARK
from .fonts import (
    BODY_FAMILY,
    HEADING_FAMILY,
    MONO_FAMILY,
    body_font,
    fonts_dir,
    heading_font,
    load_fonts,
    mono_font,
)
from .light import LIGHT
from .manager import (
    APPLICATION,
    DEFAULT_MODE,
    MODES,
    ORGANISATION,
    SETTINGS_KEY,
    THEMES,
    ThemeManager,
    apply_to_app,
    build_palette,
    build_stylesheet,
    current,
    set_current,
    system_scheme,
)
from .tokens import Theme

# Legacy module-level names, resolved from the active token set.
BACKGROUND = current().background
PANEL = current().surface
PANEL_ALT = current().surface_alt
LIGHT_CARD = "#E8E8E8"
ACCENT = current().accent
ACCENT_GRADIENT = current().accent_gradient
TEXT = current().text_primary
TEXT_SECONDARY = current().text_secondary
BORDER = current().border
MATCHED = current().status_matched
MATCHED_TEXT = current().status_matched_text
MISMATCHED = current().status_mismatched
MISMATCHED_TEXT = current().status_mismatched_text
INCOMPLETE = current().status_incomplete
INCOMPLETE_TEXT = current().status_incomplete_text
AMBIGUOUS = current().status_ambiguous
AMBIGUOUS_TEXT = current().status_ambiguous_text
GAP = current().gap
UNCOVERED = current().status_uncovered
NOT_APPLICABLE = current().status_not_applicable
OUTDATED = current().status_outdated
HYPOTHESIS = current().hypothesis

__all__ = [
    "APPLICATION",
    "ACCENT",
    "ACCENT_GRADIENT",
    "AMBIGUOUS",
    "AMBIGUOUS_TEXT",
    "BACKGROUND",
    "BODY_FAMILY",
    "BORDER",
    "DARK",
    "DEFAULT_MODE",
    "GAP",
    "HEADING_FAMILY",
    "HYPOTHESIS",
    "INCOMPLETE",
    "INCOMPLETE_TEXT",
    "LIGHT",
    "LIGHT_CARD",
    "MATCHED",
    "MATCHED_TEXT",
    "MISMATCHED",
    "MISMATCHED_TEXT",
    "MODES",
    "MONO_FAMILY",
    "NOT_APPLICABLE",
    "ORGANISATION",
    "OUTDATED",
    "PANEL",
    "PANEL_ALT",
    "SETTINGS_KEY",
    "TEXT",
    "TEXT_SECONDARY",
    "THEMES",
    "Theme",
    "ThemeManager",
    "UNCOVERED",
    "apply_to_app",
    "body_font",
    "build_palette",
    "build_stylesheet",
    "current",
    "fonts_dir",
    "heading_font",
    "load_fonts",
    "mono_font",
    "set_current",
    "system_scheme",
]
