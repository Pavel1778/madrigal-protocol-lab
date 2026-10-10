"""Theme tokens.

A theme is a named set of tokens, not a bag of constants read at import time.
Every widget takes its colours, fonts and geometry from the active token set, so
switching themes is a matter of swapping the set and re-applying it, with no
restart and no hard-coded colour in the widget code.

The dark set keeps the Madrigal identity and is the default; the light set is an
alternative for bright rooms, projectors and printed screenshots.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """One complete set of visual tokens."""

    name: str

    # Surfaces.
    background: str
    surface: str
    surface_alt: str
    surface_elevated: str
    border: str

    # Text.
    text_primary: str
    text_secondary: str
    text_muted: str

    # Accent.
    accent: str
    accent_hover: str
    accent_gradient: tuple[str, str, str]
    text_on_accent: str

    # Selection: the fill behind a selected row and its text. The dark set keeps
    # the accent as the selection fill; the light set uses a soft tint so a
    # selected row does not glare.
    selection: str
    selection_text: str

    # Menu highlight: the fill and text behind a hovered/selected menu entry.
    # Kept apart from ``selection`` because the dark set highlights a menu with
    # the accent fill, while the light set uses a soft grey with accent text.
    menu_selection: str
    menu_selection_text: str

    # The fill behind a pressed (non-accent) button. The dark set keeps the
    # accent, matching the flat dark look; the light set uses a soft grey so a
    # press does not flash a saturated fill.
    button_pressed: str

    # Status verdicts. ``status_*`` is a fill behind bytes; ``status_*_text`` is
    # the text colour for the same verdict.
    status_matched: str
    status_matched_text: str
    status_mismatched: str
    status_mismatched_text: str
    status_ambiguous: str
    status_ambiguous_text: str
    status_incomplete: str
    status_incomplete_text: str
    status_uncovered: str
    status_not_applicable: str
    status_outdated: str
    gap: str
    hypothesis: str

    # Typography.
    font_heading: str
    font_body: str
    font_mono: str

    # Geometry.
    radius: int
    spacing_unit: int

    def as_dict(self) -> dict[str, object]:
        """Return the tokens as a plain mapping, for export and tests."""
        return {field: getattr(self, field) for field in self.__dataclass_fields__}

    def colour_tokens(self) -> dict[str, str]:
        """Return only the colour tokens, for contrast checking."""
        return {
            name: value
            for name, value in self.as_dict().items()
            if isinstance(value, str) and value.startswith("#")
        }
