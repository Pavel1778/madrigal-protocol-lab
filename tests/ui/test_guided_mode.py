"""Tests for guided mode: the plain-language coach above the workspace.

The coach is on by default and follows the state of the window: it advances as a
capture, a session, a rule and an applied rule appear, and it can be switched off
from the strip or from the settings dialog. These tests drive the real window and
the real engine; nothing is mocked.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6 import QtWidgets

    from src.ui import theme
    from src.ui.guided import STEP_COUNT
    from src.ui.main_window import MainWindow
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = (
    REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
)
DEFAULT_RULE = REPO_ROOT / "examples" / "corpus_rule_v1.json"


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


def test_guided_is_on_by_default(app):
    window = MainWindow()
    try:
        assert not window.guided_panel.isHidden()
        assert window.guided_panel.step_index == 0
    finally:
        window.close()


def test_guided_advances_with_the_workflow(app):
    window = MainWindow()
    try:
        assert window.guided_panel.step_index == 0

        window.open_capture(DEFAULT_CAPTURE)
        # A capture selects its first direction, so the coach is already past
        # the "pick a conversation" stage.
        assert window.guided_panel.step_index == 2

        window.load_rule(DEFAULT_RULE)
        assert window.guided_panel.step_index == 3

        window.apply_rule()
        assert window.guided_panel.step_index == 4
        assert window.guided_panel.step_index < STEP_COUNT
    finally:
        window.close()


def test_guided_stage_names_are_plain_words(app):
    window = MainWindow()
    try:
        for index in range(STEP_COUNT):
            window.guided_panel.set_step(index)
            label = window.guided_panel.step_label.text()
            assert label.startswith("Step ")
            assert window.guided_panel.body.text()
            assert window.guided_panel.next_button.text()
    finally:
        window.close()


def test_hide_hints_switches_guided_mode_off(app):
    window = MainWindow()
    try:
        window.set_guided_mode(False)
        assert window.guided_panel.isHidden()
        assert window._settings["general"]["guided_mode"] is False

        # The choice survives a fresh window.
        reopened = MainWindow()
        try:
            assert reopened.guided_panel.isHidden()
        finally:
            reopened.close()
    finally:
        window.close()


def test_guided_can_be_turned_back_on(app):
    window = MainWindow()
    try:
        window.set_guided_mode(False)
        assert window.guided_panel.isHidden()
        window.set_guided_mode(True)
        assert not window.guided_panel.isHidden()
    finally:
        window.close()


def test_guided_next_opens_the_example(app):
    window = MainWindow()
    try:
        assert window.guided_panel.step_index == 0
        window._guided_next()
        # The built-in demo loads a capture and applies a rule, so the coach
        # reaches its last stage.
        assert window.guided_panel.step_index == 4
    finally:
        window.close()


def test_guided_setting_is_visible_in_the_dialog(app):
    from src.ui.settings import SettingsDialog

    dialog = SettingsDialog()
    try:
        checkbox = dialog._widgets["general"]["guided_mode"]
        assert checkbox.isChecked(), "guided mode is on by default"
        assert dialog.values()["general"]["guided_mode"] is True
    finally:
        dialog.close()
