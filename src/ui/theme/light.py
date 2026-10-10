"""The light token set.

An alternative for bright rooms, projectors and printed screenshots. The
structure matches the dark set token for token; only the values change, so a
widget reads the same name in either theme. The accent is darkened so it keeps
contrast on a light background.
"""

from __future__ import annotations

from .tokens import Theme

LIGHT = Theme(
    name="light",
    background="#FAFAFA",
    surface="#FFFFFF",
    surface_alt="#F5F5F5",
    surface_elevated="#F5F5F5",
    border="#E0E0E0",
    text_primary="#1A1A1A",
    text_secondary="#4A4A4A",
    text_muted="#737373",
    accent="#8B0A28",
    accent_hover="#6D071F",
    accent_gradient=("#6D071F", "#8B0A28", "#A2391D"),
    text_on_accent="#FFFFFF",
    status_matched="#C8E6C9",
    status_matched_text="#1B5E20",
    status_mismatched="#FFCDD2",
    status_mismatched_text="#B71C1C",
    status_ambiguous="#FFE0B2",
    status_ambiguous_text="#E65100",
    status_incomplete="#E0E0E0",
    status_incomplete_text="#424242",
    status_uncovered="#EEEEEE",
    status_not_applicable="#F5F5F5",
    status_outdated="#E0E0E0",
    gap="#FFCDD2",
    hypothesis="#8B0A28",
    font_heading="Tektur",
    font_body="Montserrat",
    font_mono="DejaVu Sans Mono",
    radius=4,
    spacing_unit=4,
)
