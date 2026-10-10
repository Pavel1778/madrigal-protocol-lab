"""The dark token set.

The Madrigal identity: near-black background, one bordeaux accent, muted status
colours that mark a verdict rather than decorate. This is the default theme.
"""

from __future__ import annotations

from .tokens import Theme

DARK = Theme(
    name="dark",
    background="#131516",
    surface="#1D1D1D",
    surface_alt="#171819",
    surface_elevated="#1D1D1D",
    border="#2A2C2E",
    text_primary="#E0E0E0",
    text_secondary="#9F9F9F",
    text_muted="#9F9F9F",
    accent="#6D071F",
    accent_hover="#A2391D",
    accent_gradient=("#410913", "#610D1C", "#A2391D"),
    text_on_accent="#E0E0E0",
    selection="#6D071F",
    selection_text="#E0E0E0",
    menu_selection="#6D071F",
    menu_selection_text="#E0E0E0",
    button_pressed="#6D071F",
    status_matched="#2F5D45",
    status_matched_text="#7FBF9B",
    status_mismatched="#6E2626",
    status_mismatched_text="#E08A8A",
    status_ambiguous="#6B5B14",
    status_ambiguous_text="#E6D071",
    status_incomplete="#6B5320",
    status_incomplete_text="#D8B65C",
    status_uncovered="#3A3C3E",
    status_not_applicable="#202224",
    status_outdated="#2A2C2E",
    gap="#4A1414",
    hypothesis="#A2391D",
    font_heading="Tektur",
    font_body="Montserrat",
    font_mono="DejaVu Sans Mono",
    radius=4,
    spacing_unit=4,
)
