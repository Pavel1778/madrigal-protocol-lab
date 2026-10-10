"""The dark token set.

The Madrigal identity: a near-black background (not pure black, so an OLED
panel has no smearing and the surfaces still cast a shadow), one bordeaux
accent, and status colours that mark a verdict rather than decorate.

Elevation follows the light-from-above rule the dark-theme principles ask for:
the further a surface sits from the reader, the darker it is. The background is
the darkest layer, a panel sits above it, a raised row above that. Pure black
(`#000000`) and pure white (`#FFFFFF`) are avoided; the accent is brightened and
saturated so it stays legible on the dark ground.
"""

from __future__ import annotations

from .tokens import Theme

DARK = Theme(
    name="dark",
    background="#0E0F10",
    surface="#171819",
    surface_alt="#1C1E20",
    surface_elevated="#212325",
    border="#2E3134",
    text_primary="#E6E6E6",
    text_secondary="#A6A6A6",
    text_muted="#8A8A8A",
    accent="#8E1B33",
    accent_hover="#B52A44",
    accent_gradient=("#5A0F20", "#7D1830", "#B52A44"),
    text_on_accent="#F2F2F2",
    status_matched="#2F5D45",
    status_matched_text="#7FBF9B",
    status_mismatched="#7A2A2A",
    status_mismatched_text="#EC9A9A",
    status_ambiguous="#7A6818",
    status_ambiguous_text="#EED77E",
    status_incomplete="#7A5F24",
    status_incomplete_text="#E0C066",
    status_uncovered="#3A3C3E",
    status_not_applicable="#222527",
    status_outdated="#2E3134",
    gap="#5A1414",
    hypothesis="#B52A44",
    font_heading="Tektur",
    font_body="Montserrat",
    font_mono="DejaVu Sans Mono",
    radius=4,
    spacing_unit=4,
)
