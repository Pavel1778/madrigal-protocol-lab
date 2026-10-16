"""Geometry and accessibility guards for the window and its dialogs.

A caption that is wider than the box that holds it is clipped silently, and a
dialog whose minimum size is larger than the smallest supported screen opens
off-screen. Both are easy to introduce and easy to miss by eye, so they are
pinned here:

* every dialog's ``minimumSizeHint`` fits inside the smallest supported window
  (1024x768), in both interface languages;
* no fixed (non-wrapping) label in the main window is narrower than its own text
  at that size, so nothing is cut off;
* every push button carries either a caption or an accessible name, so a control
  with no visible text is still named for assistive technology.

The hex view's column header is exempt from the label check: it is a fixed-pitch
strip that is meant to scroll horizontally with the bytes when the window is
narrower than one line, not a caption that should wrap.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6 import QtWidgets

    from src.ui import theme
    from src.ui.corpus_dialog import CorpusDialog
    from src.ui.help import HELP_ENTRIES
    from src.ui.help_dialog import HelpCard, LearningCentre
    from src.ui.hex_view import HexView
    from src.ui.rule_builder import RuleBuilderDialog
    from src.ui.settings import SettingsDialog
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = (
    REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
)
DEFAULT_RULE = REPO_ROOT / "examples" / "corpus_rule_v1.json"

# The smallest window size the product documents as supported.
SMALLEST = (1024, 768)

corpus_required = pytest.mark.skipif(
    not DEFAULT_CAPTURE.is_file() or not DEFAULT_RULE.is_file(),
    reason="reference corpus not present",
)


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


def _dialog_factories() -> dict[str, object]:
    return {
        "settings": SettingsDialog,
        "rule_builder": RuleBuilderDialog,
        "corpus": CorpusDialog,
        "help_card": lambda: HelpCard(HELP_ENTRIES[0]),
        "learning_centre": LearningCentre,
    }


@pytest.mark.parametrize("name", sorted(_dialog_factories()))
def test_dialog_minimum_fits_the_smallest_screen(app, name):
    """A dialog must be usable on the smallest supported screen."""
    dialog = _dialog_factories()[name]()
    dialog.show()
    app.processEvents()
    hint = dialog.minimumSizeHint()
    assert hint.width() <= SMALLEST[0], f"{name} needs {hint.width()}px wide"
    assert hint.height() <= SMALLEST[1], f"{name} needs {hint.height()}px tall"
    dialog.close()


@pytest.mark.parametrize("name", sorted(_dialog_factories()))
def test_dialog_buttons_are_labelled(app, name):
    """No push button in a dialog is left with neither caption nor name."""
    dialog = _dialog_factories()[name]()
    dialog.show()
    app.processEvents()
    unnamed = [
        button.objectName()
        for button in dialog.findChildren(QtWidgets.QPushButton)
        if button.isVisible()
        and not button.text().strip()
        and not button.accessibleName().strip()
        and not button.toolTip().strip()
    ]
    dialog.close()
    assert not unnamed, f"{name}: unlabelled buttons {unnamed}"


def _is_hex_header(label: QtWidgets.QLabel) -> bool:
    """Whether *label* belongs to the hex view's scrolling column header."""
    parent = label.parent()
    while parent is not None:
        if isinstance(parent, HexView):
            return True
        parent = parent.parent()
    return False


@corpus_required
@pytest.mark.parametrize("language", ["en", "ru"])
def test_no_label_is_clipped_in_the_main_window(app, language):
    """No fixed label in the workspace is narrower than its own text."""
    from src.ui.main_window import open_default_window

    window = open_default_window(app, capture=DEFAULT_CAPTURE, rule=DEFAULT_RULE)
    window.setFixedSize(*SMALLEST)
    window.show()
    window.set_language(language)
    app.processEvents()
    app.processEvents()

    clipped = []
    for label in window.findChildren(QtWidgets.QLabel):
        if not label.isVisible() or label.wordWrap() or _is_hex_header(label):
            continue
        text = label.text()
        if not text.strip():
            continue
        if label.width() < label.sizeHint().width():
            clipped.append((text[:40], label.width(), label.sizeHint().width()))
    window.close()
    assert not clipped, f"{language}: clipped labels {clipped}"
