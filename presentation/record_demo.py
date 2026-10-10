"""Drive the laboratory window for a short screen recording.

The script performs the reference investigation with the real window code and
pauses on each step so the recording reads as a demonstration. It is a recording
aid, not part of the product: the window code is unchanged and every action is
the one the menus perform.

Run under a display, for example::

    DISPLAY=:0 QT_QPA_PLATFORM=xcb python presentation/record_demo.py

The recording itself is taken with a screen grabber (see presentation/VIDEO.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from src.ui import theme  # noqa: E402
from src.ui.main_window import open_default_window  # noqa: E402

CAPTURE_01 = REPO_ROOT / "tests/corpus/reference_export/corpus_capture_01.normalized.json"
CAPTURE_02 = REPO_ROOT / "tests/corpus/reference_export/corpus_capture_02.normalized.json"
RULE_V1 = REPO_ROOT / "examples/corpus_rule_v1.json"
RULE_V2 = REPO_ROOT / "examples/corpus_rule_v2.json"

# The narration in presentation/VIDEO.md runs about four minutes; the scene
# times below are its beats at reading pace, scaled here so the silent take
# lasts as long as the spoken one.
PACE = 3.6


class Overlay(QtWidgets.QWidget):
    """A translucent caption band drawn over the window bottom."""

    def __init__(self, window: QtWidgets.QWidget) -> None:
        super().__init__(window)
        self._text = ""
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self._label = QtWidgets.QLabel(self)
        self._label.setFont(theme.body_font(5))
        self._label.setStyleSheet(
            "background: rgba(14,16,17,225); color: #F0F0F0;"
            "border-left: 6px solid #A2391D; padding: 14px 22px;"
        )
        self._label.setWordWrap(False)

    def set_caption(self, text: str) -> None:
        self._text = text
        self._label.setText(text)
        self._layout()

    def _layout(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = parent.width()
        self._label.adjustSize()
        height = self._label.height()
        # Sit under the menu bar so the status line stays readable.
        self.setGeometry(0, 44, width, height)
        self._label.setGeometry(0, 0, width, height)
        self.show()
        self.raise_()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout()


def _settle(app: QtWidgets.QApplication, ms: int) -> None:
    """Let the event loop paint (and the grabber see) for *ms* milliseconds."""
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([sys.argv[0]])
    app.setApplicationName("Madrigal protocol laboratory")
    theme.load_fonts(app)

    window = open_default_window(app, capture=CAPTURE_01, rule=RULE_V1)
    window.show()
    overlay = Overlay(window)
    _settle(app, 800)

    def scene(caption: str, ms: int) -> None:
        overlay.set_caption(caption)
        _settle(app, int(ms * PACE))

    # Scene 1 - the window and the sessions.
    scene("Захват открыт: три сессии, направления, байты.", 3000)
    scene("Задача: восстановить протокол по байтам и журналу.", 4000)
    window.session_tree.select_direction("s1", "A_to_B")
    scene("Сессия s1, направление A_to_B.", 2500)
    window.session_tree.select_direction("s2", "A_to_B")
    scene("Сессия s2, направление A_to_B.", 2500)

    # Scene 2 - provenance of a byte.
    window.reveal_offset(0)
    scene("Байт 0: происхождение — пакет, номер последовательности, время.", 4000)
    window.reveal_offset(19)
    scene("Байт 19: тот же захват, то же происхождение.", 4000)

    # Scene 3 - the rule describes the whole stream.
    window.load_rule(RULE_V1)
    window.right_tabs.setCurrentWidget(window.validation_view)
    window.apply_rule()
    scene("Правило v1 применено к направлению: сообщения не перечислялись вручную.", 5000)

    # Scene 4 - open a counterexample and show its bytes.
    counter = window.validation_view.counter_list
    if counter.count() and counter.item(0).data(QtCore.Qt.ItemDataRole.UserRole) is not None:
        counter.setCurrentRow(0)
    scene("Контрпример: команда 2 вне допустимого набора [1].", 5000)

    # Scene 5 - the alternatives behind the refinement.
    window.apply_to_capture()
    window.right_tabs.setCurrentWidget(window.hypotheses_view)
    scene("Альтернативные чтения: constant 0.43 против entropy_enum 1.00.", 5000)

    # Scene 6 - verify over the whole capture with rule v1.
    window.right_tabs.setCurrentWidget(window.validation_view)
    scene("Проверка по всему корпусу: v1 даёт 80 контрпримеров.", 5000)

    # Scene 7 - refine the rule and recheck.
    window.load_rule(RULE_V2)
    window.apply_to_capture()
    scene("Правило v2: набор команд 1, 2, 3 — контрпримеров нет.", 4500)

    # Scene 8 - transfer to a second capture.
    window.open_capture(CAPTURE_02)
    window.apply_to_capture()
    scene("Перенос на второй захват: 40 matched, 0 контрпримеров.", 4500)

    # Scene 9 - the version diff.
    window.show_version_diff()
    window.right_tabs.setCurrentWidget(window.diff_view)
    scene("Сравнение версий: изменён только список команд, структура та же.", 4500)

    # Scene 10 - the report and the repository.
    window.show_report()
    window.right_tabs.setCurrentWidget(window.report_view)
    scene("Отчёт и переносимая интерпретация.", 4000)
    scene("github.com/Pavel1778/madrigal-protocol-lab", 4000)

    overlay.set_caption("")
    _settle(app, 500)
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
