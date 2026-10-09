"""Render the presentation screenshots from the running window.

The window is built offscreen and grabbed with ``QPixmap``, so the images are
real captures of the application, not mock-ups. Each screenshot drives the
window into the state it should show, then grabs the relevant widget.

Run with the repository root as the working directory:

    python -m presentation.generate_screenshots
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from src.ui import theme  # noqa: E402
from src.ui.main_window import (  # noqa: E402
    DEFAULT_CAPTURE,
    DEFAULT_RULE,
    MainWindow,
    open_default_window,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "presentation" / "screenshots"
RULE_V2 = REPO_ROOT / "examples" / "corpus_rule_v2.json"
CAPTURE_02 = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_02.normalized.json"
SYNTHETIC = REPO_ROOT / "tests" / "corpus" / "reference_export" / "synthetic_live.normalized.json"


def _grab(widget, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    pixmap = widget.grab()
    if not pixmap.save(str(path)):
        raise RuntimeError(f"could not write {path}")
    return path


def _app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    theme.load_fonts(app)
    app.setStyleSheet(theme.build_stylesheet())
    return app


def _show(app: QtWidgets.QApplication, window: MainWindow) -> None:
    window.resize(1440, 880)
    window.show()
    app.processEvents()


def main() -> int:
    app = _app()
    written: list[Path] = []

    window = open_default_window(app)
    _show(app, window)
    written.append(_grab(window, "main_window.png"))

    # Hex view with a matched rule applied to the first session.
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    app.processEvents()
    written.append(_grab(window.hex_view, "hex_matched.png"))

    # Counterexample: the too-narrow rule against a session that carries other
    # commands, with the offending bytes revealed.
    window.session_tree.select_direction("s2", "A_to_B")
    window.apply_rule()
    window.right_tabs.setCurrentWidget(window.validation_view)
    window.validation_view._tabs.setCurrentIndex(2)
    if window._rule.root.counterexamples:
        window.reveal_offset(window._rule.root.counterexamples[0].offset)
    app.processEvents()
    written.append(_grab(window, "counterexample.png"))

    # Rule editor with the refined rule.
    if RULE_V2.is_file():
        window.load_rule(RULE_V2)
        window.validation_view._tabs.setCurrentIndex(0)
        app.processEvents()
        written.append(_grab(window, "rule_editor.png"))

    # Whole-capture verification with the refined rule: no counterexamples.
    window.apply_to_capture()
    window.validation_view._tabs.setCurrentIndex(1)
    app.processEvents()
    written.append(_grab(window.validation_view, "capture_verification.png"))

    # Applicability boundary: the refined rule against the different capture.
    if SYNTHETIC.is_file():
        window.open_capture(SYNTHETIC)
        window.load_rule(RULE_V2)
        window.apply_to_capture()
        app.processEvents()
        written.append(_grab(window, "applicability_boundary.png"))

    # Compare two messages.
    if CAPTURE_02.is_file():
        window.open_capture(DEFAULT_CAPTURE)
        window.load_rule(DEFAULT_RULE)
        window.session_tree.select_direction("s1", "A_to_B")
        window.apply_rule()
        window.right_tabs.setCurrentWidget(window.compare_view)
        app.processEvents()
        written.append(_grab(window.compare_view, "compare_view.png"))

    # Report preview.
    window.show_report()
    app.processEvents()
    written.append(_grab(window.report_view, "report_preview.png"))

    window.close()
    for path in written:
        print(path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
