"""Entry point for the packaged binary.

PyInstaller runs the target file as a top-level script, which breaks the
relative imports inside ``src.ui.main_window``. This module imports the package
normally and calls its entry point, so the frozen binary loads the same code the
installed package does.
"""

from __future__ import annotations

from src.ui.main_window import main

if __name__ == "__main__":
    raise SystemExit(main())
