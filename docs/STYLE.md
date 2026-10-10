# Style

The window takes every colour, font and radius from a token set, not from
constants scattered in the widget code. The tokens live in `src/ui/theme/`:
`tokens.py` defines the field names, `dark.py` and `light.py` fill them,
`manager.py` swaps the active set and re-applies it. Switching a theme is a swap
with no restart.

## Palette — dark (default)

The Madrigal identity: a warm near-black background, one bordeaux accent. The
surfaces are layered by depth: the layer closest to the reader (menus, tooltips)
is the lightest, the window is the darkest. No surface is pure black and no text
is pure white.

| Token | Field | Value |
| --- | --- | --- |
| Background | `background` | `#141210` |
| Panel | `surface` | `#1C1917` |
| Panel, alternate | `surface_alt` | `#171412` |
| Panel, elevated | `surface_elevated` | `#242019` |
| Border | `border` | `#322D28` |
| Accent | `accent` | `#7A1224` |
| Accent hover | `accent_hover` | `#A8391F` |
| Accent gradient | `accent_gradient` | `#4A0A16` → `#6C1020` → `#A8391F` |
| Text | `text_primary` | `#E6E1DB` |
| Secondary text | `text_secondary` | `#A8A099` |
| Muted text | `text_muted` | `#8C857E` |

## Palette — light

An alternative for bright rooms and printed screenshots. Same field names, only
the values change, so a widget reads the same token in either theme.

| Token | Field | Value |
| --- | --- | --- |
| Background | `background` | `#FAFAFA` |
| Panel | `surface` | `#FFFFFF` |
| Panel, alternate | `surface_alt` | `#F5F5F5` |
| Border | `border` | `#E0E0E0` |
| Accent | `accent` | `#8B0A28` |
| Accent hover | `accent_hover` | `#6D071F` |
| Accent gradient | `accent_gradient` | `#6D071F` → `#8B0A28` → `#A2391D` |
| Text | `text_primary` | `#1A1A1A` |
| Secondary text | `text_secondary` | `#4A4A4A` |

## Status colours

Status colours mark a verdict, never decorate. Each set has a fill (behind
bytes) and a text variant for the same verdict; the light set uses light fills
with dark text, the dark set uses muted fills with light text. The names are
`status_matched`, `status_mismatched`, `status_ambiguous`, `status_incomplete`,
`status_uncovered`, `status_not_applicable`, `status_outdated`, plus `gap` and
`hypothesis`. Green, yellow and red appear only through these tokens.

## Typography

- Headings: Tektur, weights Medium (500) and SemiBold (600).
- Body: Montserrat, weights Regular (400) and SemiBold (600).
- Monospace: `DejaVu Sans Mono` (`font_mono`), used by the hex view.
- Line height: 1.3.
- Both display fonts are from Google Fonts, OFL licensed; the `.ttf` files and
  their licence texts live in `assets/fonts/`.

## Geometry

- Corner radius: 4 px (`radius` token), at most 5 px.
- Spacing unit: 4 px (`spacing_unit` token).
- No pill buttons.
- No soft shadows.
- No gradients except the accent gradient.
- Dense modular grid.

## Zoom

- **Ctrl +** and **Ctrl −** step the byte size within 8–28 px and move the tree
  two points behind it, so the two never drift apart; **Ctrl 0** restores the
  defaults (13 px bytes, 11 px tree). The steps are clamped at the limits and
  the menu entries disable when a limit is reached.

## Rules

- No emoji.
- No exclamation marks.
- No friendly tone.
- Status colours are used for statuses only, never as decoration.
- No jargon humor.
