"""Drive the GUI through the demo scenario for the screen recording.

Runs on the real (xvfb) X display so ``ffmpeg -f x11grab`` can record the
window while this script moves it through the walkthrough. Each step waits a
few seconds so the recording shows the state change and the viewer can read it.

    xvfb-run -a -s "-screen 0 1920x1080x24" \
        python -m presentation.screencast

The window is the normal ``MainWindow``; nothing here is a mock-up.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6 import QtCore, QtWidgets  # noqa: E402

from src.ui import theme  # noqa: E402
from src.ui.main_window import MainWindow, open_default_window  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_01 = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
RULE_V1 = REPO_ROOT / "examples" / "corpus_rule_v1.json"
RULE_V2 = REPO_ROOT / "examples" / "corpus_rule_v2.json"
FRAME = (1920, 1080)


class Director:
    """Walks the window through the demo, one step per timer tick."""

    def __init__(self, app: QtWidgets.QApplication, window: MainWindow) -> None:
        self.app = app
        self.window = window
        self.steps = [
            (14, self.step_open_capture),
            (14, self.step_select_session),
            (14, self.step_apply_v1),
            (14, self.step_click_byte),
            (14, self.step_provenance),
            (14, self.step_counterexample),
            (14, self.step_rule_editor),
            (14, self.step_apply_v2_diff),
            (14, self.step_hypotheses),
            (14, self.step_report),
            (20, self.step_finish),
        ]
        self.index = 0

    def start(self) -> None:
        QtCore.QTimer.singleShot(1500, self.tick)

    def tick(self) -> None:
        if self.index >= len(self.steps):
            return
        delay, action = self.steps[self.index]
        self.app.processEvents()
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - keep the recording going
            print(f"step {self.index} failed: {exc}", file=sys.stderr)
        self.index += 1
        QtCore.QTimer.singleShot(delay * 1000, self.tick)

    # Each step is a small, visible change.

    def step_open_capture(self) -> None:
        self.window.open_capture(CAPTURE_01)

    def step_select_session(self) -> None:
        tree = self.window.session_tree
        if tree.topLevelItemCount():
            tree.topLevelItem(0).setExpanded(True)
        tree.select_direction("s1", "A_to_B")

    def step_apply_v1(self) -> None:
        self.window.load_rule(RULE_V1)
        self.window.apply_rule()

    def step_click_byte(self) -> None:
        # Move the hex cursor to a byte so the status line updates.
        self.window.reveal_offset(1)

    def step_provenance(self) -> None:
        self.window.reveal_offset(2)

    def step_counterexample(self) -> None:
        self.window.right_tabs.setCurrentWidget(self.window.validation_view)
        self.window.validation_view._tabs.setCurrentIndex(2)

    def step_rule_editor(self) -> None:
        self.window.load_rule(RULE_V2)
        self.window.validation_view._tabs.setCurrentIndex(0)

    def step_apply_v2_diff(self) -> None:
        self.window.load_rule(RULE_V1)
        self.window.apply_to_capture()
        self.window.load_rule(RULE_V2)
        self.window.apply_to_capture()
        self.window.show_version_diff()

    def step_hypotheses(self) -> None:
        self.window.right_tabs.setCurrentWidget(self.window.hypotheses_view)

    def step_report(self) -> None:
        self.window.right_tabs.setCurrentWidget(self.window.report_view)
        self.window.show_report()

    def step_finish(self) -> None:
        print("scenario complete", file=sys.stderr)
        self.app.quit()


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    theme.load_fonts(app)
    app.setStyleSheet(theme.build_stylesheet())
    window = open_default_window(app)
    window.resize(*FRAME)
    window.show()
    window.move(0, 0)
    director = Director(app, window)
    QtCore.QTimer.singleShot(0, director.start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
