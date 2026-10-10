"""The dark token set.

The default theme. Surfaces are warm neutrals rather than pure black: the
lightest layer sits closest to the reader (dialogs, popups), the darkest sits
furthest back (the window), so the depth reads the way it does under a light
from above. No surface is ``#000000`` and no text is ``#FFFFFF``, which avoids
the smear and the glare of a hard black/white pair. The single bordeaux accent
is used sparingly: as the row selection and the pressed-button fill only, so no
large block of saturated colour sits on the screen.
"""

from __future__ import annotations

from .tokens import Theme

DARK = Theme(
    name="dark",
    background="#141210",
    surface="#1C1917",
    surface_alt="#171412",
    surface_elevated="#242019",
    border="#322D28",
    text_primary="#E6E1DB",
    text_secondary="#A8A099",
    text_muted="#8C857E",
    accent="#7A1224",
    accent_hover="#A8391F",
    accent_gradient=("#4A0A16", "#6C1020", "#A8391F"),
    text_on_accent="#F2EDE7",
    selection="#7A1224",
    selection_text="#E6E1DB",
    menu_selection="#7A1224",
    menu_selection_text="#E6E1DB",
    button_pressed="#7A1224",
    status_matched="#2E5B44",
    status_matched_text="#8FCBA8",
    status_mismatched="#6E2A2A",
    status_mismatched_text="#E79A9A",
    status_ambiguous="#6E5C16",
    status_ambiguous_text="#E8D67A",
    status_incomplete="#6E5520",
    status_incomplete_text="#DCBB6A",
    status_uncovered="#3C3835",
    status_not_applicable="#211E1C",
    status_outdated="#2C2825",
    gap="#521616",
    hypothesis="#A8391F",
    font_heading="Tektur",
    font_body="Montserrat",
    font_mono="DejaVu Sans Mono",
    radius=4,
    spacing_unit=4,
)
