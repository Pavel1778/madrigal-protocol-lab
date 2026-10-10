# Settings

The application stores user preferences in `QSettings` under organisation
`madrigal`, application `protocol-lab`, grouped in four sections: `general`,
`editor`, `paths` and `advanced`. The window reads them on start and applies
them live; nothing is written until the user accepts the dialog.

Open the dialog with **View → Settings...** or the **Ctrl+,** shortcut.

## General

| Setting | Values | Default |
| --- | --- | --- |
| Theme | Dark, Light, System | System |
| Language | Русский, English, System | System |

The theme and the interface language apply as soon as they are changed, through
the same `ThemeManager` and `LanguageManager` the menus use. `System` follows the
desktop colour scheme and locale; see `docs/STYLE.md` for the palettes and the
catalogue in `src/ui/locale/`.

## Editor

| Setting | Range | Default |
| --- | --- | --- |
| Hex font size | 6–48 px | 13 |
| Tree font size | 6–48 px | 11 |
| Show offset column | on / off | on |

The hex font size scales the byte grid and its column header together. Hiding the
offset column removes the address gutter; the hex and ASCII columns keep their
alignment and the byte-to-packet lookup keeps working.

## Paths

| Setting | Meaning | Default |
| --- | --- | --- |
| Projects directory | where save dialogs start | empty |
| Captures directory | where open dialogs start | empty |
| Relative paths in manifest | store portable paths | on |

A configured directory is used the first time a file dialog opens. Once a file
has been opened or saved, its directory is remembered for the rest of the run
and takes precedence.

## Advanced

| Setting | Values | Default |
| --- | --- | --- |
| Logging level | DEBUG, INFO, WARNING, ERROR | INFO |
| Show diagnostics in UI | on / off | on |

The logging level reconfigures the root logger. Turning diagnostics off hides the
gap and ambiguity shading in the hex view so the raw bytes read without it; the
diagnostics themselves remain attached to the stream and stay reachable through
the provenance line.

## Buttons

- **OK** applies the values and closes.
- **Apply** applies without closing, so several sections can be tuned in a row.
- **Cancel** restores whatever was active when the dialog opened and closes
  without applying.

## Storage keys

| Group | Key | Type |
| --- | --- | --- |
| general | `theme` | string |
| general | `language` | string |
| editor | `hex_font_size` | int |
| editor | `tree_font_size` | int |
| editor | `show_offset` | bool |
| paths | `project_dir` | string |
| paths | `capture_dir` | string |
| paths | `relative_paths` | bool |
| advanced | `log_level` | string |
| advanced | `show_diagnostics` | bool |

The defaults are declared once in `src/ui/settings.py`; a reset simply clears the
`madrigal/protocol-lab` settings scope.
