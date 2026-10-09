"""Render the presentation screenshots from the running window.

The window is built offscreen and grabbed with ``QPixmap``, so the images are
real captures of the application, not mock-ups. Each screenshot drives the
window into the state it should show, then grabs the whole window at the
presentation frame size (1920x1080). Before each grab any tooltip is hidden and
the hover flags are cleared, so no tooltip or hover-only affordance appears and
only widget content is captured.

The images feed the slides in ``presentation/slides.md``. Run with the
repository root as the working directory:

    QT_QPA_PLATFORM=offscreen python -m presentation.generate_screenshots
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets  # noqa: E402

from src.ui import theme  # noqa: E402
from src.ui.main_window import MainWindow, open_default_window  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "presentation" / "screenshots"
CAPTURE_01 = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
CAPTURE_02 = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_02.normalized.json"
CAPTURE_DEFECTS = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_defects.normalized.json"
RULE_V1 = REPO_ROOT / "examples" / "corpus_rule_v1.json"
RULE_V2 = REPO_ROOT / "examples" / "corpus_rule_v2.json"

FRAME = (1920, 1080)


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
    window.resize(*FRAME)
    window.show()
    window.move(0, 0)
    _park(app, window)


def _park(app: QtWidgets.QApplication, window: MainWindow) -> None:
    """Drop any pending tooltip and clear hover flags before a grab."""

    QtWidgets.QToolTip.hideText()
    QtCore.QCoreApplication.processEvents()
    # The offscreen platform leaves a phantom cursor over (0,0); clearing the
    # under-mouse flag keeps hover-only affordances out of the grab.
    for widget in window.findChildren(QtWidgets.QWidget):
        widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_UnderMouse, False)
    app.processEvents()


def main() -> int:
    app = _app()
    written: list[Path] = []

    # 01 main window: the reference capture and rule v1 loaded.
    window = open_default_window(app, capture=CAPTURE_01, rule=RULE_V1)
    _show(app, window)
    window.session_tree.select_direction("s1", "A_to_B")
    _park(app, window)
    written.append(_grab(window, "01_main.png"))

    # 02 session tree with diagnostics: the defective capture, expanded.
    if CAPTURE_DEFECTS.is_file():
        window.open_capture(CAPTURE_DEFECTS)
        window.session_tree.topLevelItem(0).setExpanded(True)
        window.session_tree.select_direction("s1", "A_to_B")
        _park(app, window)
        written.append(_grab(window, "02_sessions.png"))

    # 03 hex with matched highlighting: rule v1 on a session it frames cleanly.
    window.open_capture(CAPTURE_01)
    window.load_rule(RULE_V1)
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    _park(app, window)
    written.append(_grab(window, "03_hex_matched.png"))

    # 04 hex over a gap: the defective capture's A_to_B carries the gap.
    if CAPTURE_DEFECTS.is_file():
        window.open_capture(CAPTURE_DEFECTS)
        window.session_tree.select_direction("s1", "A_to_B")
        _park(app, window)
        written.append(_grab(window, "04_hex_gap.png"))

    # 05 validation panel with a counterexample revealed.
    window.open_capture(CAPTURE_01)
    window.load_rule(RULE_V1)
    window.session_tree.select_direction("s2", "A_to_B")
    window.apply_rule()
    window.right_tabs.setCurrentWidget(window.validation_view)
    window.validation_view._tabs.setCurrentIndex(2)
    if window._rule.root.counterexamples:
        window.reveal_offset(window._rule.root.counterexamples[0].offset)
    _park(app, window)
    written.append(_grab(window, "05_validation.png"))

    # 06 compare two messages byte by byte.
    window.session_tree.select_direction("s1", "A_to_B")
    window.apply_rule()
    window.right_tabs.setCurrentWidget(window.compare_view)
    window.compare_view.left_combo.setCurrentIndex(0)
    window.compare_view.right_combo.setCurrentIndex(
        min(1, window.compare_view.right_combo.count() - 1)
    )
    _park(app, window)
    written.append(_grab(window, "06_compare.png"))

    # 07 rule editor with rule v2 loaded.
    window.load_rule(RULE_V2)
    window.right_tabs.setCurrentWidget(window.validation_view)
    window.validation_view._tabs.setCurrentIndex(0)
    _park(app, window)
    written.append(_grab(window, "07_rule_editor.png"))

    # 08 version diff between v1 and v2 over the whole capture.
    window.load_rule(RULE_V1)
    window.apply_to_capture()
    window.load_rule(RULE_V2)
    window.apply_to_capture()
    _park(app, window)
    written.append(_grab(window, "08_diff.png"))

    window.close()
    for path in written:
        print(path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
