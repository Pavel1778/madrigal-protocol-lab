"""Named constants for the interface widgets.

Colours, fonts and radii come from the theme tokens in :mod:`src.ui.theme`;
this module only holds the small, layout-level numbers that are not part of the
theme. They are named here so a widget does not scatter the same literal through
the code and so a later change happens in one place.
"""

from __future__ import annotations

# Interface font sizes, in points. The theme builds the fonts; these are the
# sizes the window asks for, large enough to stay legible and small enough to
# keep the dense grid.
FONT_SIZE_CAPTION = 8
FONT_SIZE_BODY = 9
FONT_SIZE_DEFAULT_BYTES = 13
FONT_SIZE_DEFAULT_TREE = 11

# The font a byte or tree view starts with before the window applies the stored
# preference; the window always overwrites it on construction.
FONT_SIZE_WIDGET_DEFAULT = 10

# The legend swatch is a fixed square by design: it stands in for a byte brush
# and must not scale with the text.
LEGEND_SWATCH_PX = 12

# Minimum width of the progress bar in the status line.
PROGRESS_BAR_WIDTH = 140

# Corner radius for the small painted swatches, in pixels.
SWATCH_RADIUS_PX = 2
