"""WCAG contrast helpers.

Used to check that every text/background pair in a token set reaches the
contrast the accessibility guidelines ask for: 4.5:1 for body text, 3:1 for
large text and for interface marks such as status colours.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tokens import Theme


def _channel(value: float) -> float:
    value = value / 255.0
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(colour: str) -> float:
    """WCAG relative luminance of a ``#RRGGBB`` colour."""
    text = colour.lstrip("#")
    red, green, blue = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    return (
        0.2126 * _channel(red)
        + 0.7152 * _channel(green)
        + 0.0722 * _channel(blue)
    )


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio between two ``#RRGGBB`` colours."""
    a = relative_luminance(first)
    b = relative_luminance(second)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


@dataclass(frozen=True)
class ContrastCheck:
    """One text/background pair and the ratio it reaches."""

    label: str
    foreground: str
    background: str
    ratio: float
    minimum: float

    @property
    def passes(self) -> bool:
        return self.ratio >= self.minimum


def _rounded(first: str, second: str) -> float:
    return round(contrast_ratio(first, second), 2)


def check(theme: Theme) -> list[ContrastCheck]:
    """Check every meaningful pair in *theme* against its WCAG minimum."""
    body = 4.5
    large = 3.0
    pairs = [
        ("body text on background", theme.text_primary, theme.background, body),
        ("body text on surface", theme.text_primary, theme.surface, body),
        ("secondary text on background", theme.text_secondary, theme.background, body),
        ("secondary text on surface", theme.text_secondary, theme.surface, body),
        ("secondary text on surface_alt", theme.text_secondary, theme.surface_alt, body),
        ("muted text on background", theme.text_muted, theme.background, body),
        ("muted text on surface", theme.text_muted, theme.surface, body),
        ("heading on background", theme.text_primary, theme.background, large),
        ("selected text on selection", theme.selection_text, theme.selection, body),
        (
            "menu text on menu highlight",
            theme.menu_selection_text,
            theme.menu_selection,
            body,
        ),
        ("matched text on surface", theme.status_matched_text, theme.surface, large),
        (
            "mismatched text on surface",
            theme.status_mismatched_text,
            theme.surface,
            large,
        ),
        (
            "ambiguous text on surface",
            theme.status_ambiguous_text,
            theme.surface,
            large,
        ),
        (
            "incomplete text on surface",
            theme.status_incomplete_text,
            theme.surface,
            large,
        ),
        ("text on accent", theme.text_on_accent, theme.accent, large),
    ]
    return [
        ContrastCheck(label, foreground, background, _rounded(foreground, background), minimum)
        for label, foreground, background, minimum in pairs
    ]
