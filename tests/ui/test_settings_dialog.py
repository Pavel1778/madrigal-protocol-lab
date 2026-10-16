"""Tests for the preferences dialog and its persistence.

The dialog and the application wiring are exercised against a real Qt
application and a throwaway ``QSettings`` scope, so no widget is mocked. The
theme and language managers are the production ones; only the stored keys are
redirected so the developer's own preferences are untouched.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtWidgets

from src.ui import i18n, theme
from src.ui import settings as settings_mod
from src.ui.main_window import MainWindow
from src.ui.settings import SettingsDialog

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = REPO_ROOT / "src" / "ui" / "locale" / "madrigal_ru.qm"
catalogue_required = pytest.mark.skipif(
    not CATALOGUE.is_file(), reason="Russian catalogue is not compiled"
)


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    return application


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Point both the dialog keys and the language key at throwaway stores.

    The store is cleared first: the settings file name derives from the stable
    test name, so without a clear a value written by an earlier run would leak
    into this one.
    """
    scope = f"protocol-lab-{tmp_path.name}"
    monkeypatch.setattr(settings_mod, "ORGANISATION", "madrigal-test")
    monkeypatch.setattr(settings_mod, "APPLICATION", scope)
    monkeypatch.setattr(i18n, "_SETTINGS_ORG", "madrigal-test")
    monkeypatch.setattr(i18n, "_SETTINGS_APP", scope)
    store = QtCore.QSettings("madrigal-test", scope)
    store.clear()
    store.sync()
    yield


@pytest.fixture
def window(app, isolated_settings):
    win = MainWindow()
    yield win
    win._language_manager.set_language("system")
    win.close()


def test_dialog_has_four_tabs(app, isolated_settings):
    dialog = SettingsDialog()
    tabs = dialog.findChild(QtWidgets.QTabWidget)
    labels = [tabs.tabText(i) for i in range(tabs.count())]
    assert labels == ["General", "Editor", "Paths", "Advanced"]


@catalogue_required
def test_dialog_has_four_tabs_in_russian(app, isolated_settings):
    window = MainWindow()
    try:
        window.set_language("ru")
        dialog = SettingsDialog()
        tabs = dialog.findChild(QtWidgets.QTabWidget)
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        assert labels == ["Общие", "Редактор", "Пути", "Дополнительно"]
    finally:
        window._language_manager.set_language("system")
        window.close()


@catalogue_required
def test_theme_names_are_translated(app, isolated_settings):
    window = MainWindow()
    try:
        window.set_language("ru")
        dialog = SettingsDialog()
        combo = dialog._widgets["general"]["theme"]
        labels = [combo.itemText(i) for i in range(combo.count())]
        # The literals must be extracted into the catalogue; a tr() call whose
        # argument is a variable is invisible to lupdate and would leave these
        # in English.
        assert labels == ["Тёмная", "Светлая", "Системный"]
    finally:
        window._language_manager.set_language("system")
        window.close()


def test_defaults_on_first_run(app, isolated_settings):
    values = settings_mod.read_settings()
    assert values["general"]["theme"] == "system"
    assert values["general"]["language"] == "system"
    assert values["editor"]["hex_font_size"] == 13
    assert values["editor"]["tree_font_size"] == 11
    assert values["editor"]["show_offset"] is True
    assert values["paths"]["relative_paths"] is True
    assert values["advanced"]["log_level"] == "INFO"
    assert values["advanced"]["show_diagnostics"] is True


def test_dialog_values_reflect_defaults(app, isolated_settings):
    dialog = SettingsDialog()
    values = dialog.values()
    assert values["editor"]["hex_font_size"] == 13
    assert values["advanced"]["log_level"] == "INFO"


def test_apply_persists_to_settings(window):
    values = window._settings
    values["editor"]["hex_font_size"] = 20
    window.apply_settings(values)
    stored = settings_mod.read_settings()
    assert stored["editor"]["hex_font_size"] == 20


def test_apply_does_not_close_dialog(app, isolated_settings):
    dialog = SettingsDialog()
    dialog.show()
    hex_size = dialog._widgets["editor"]["hex_font_size"]
    hex_size.setValue(18)
    dialog._on_apply()
    assert dialog.isVisible()
    assert dialog.result() == 0


def test_ok_saves_and_closes(window):
    values = window._settings
    values["editor"]["hex_font_size"] = 22
    dialog = SettingsDialog(values, window)
    dialog.settingsChanged.connect(window.apply_settings)
    dialog._on_ok()
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert settings_mod.read_settings()["editor"]["hex_font_size"] == 22


def test_cancel_restores_previous(window):
    before = settings_mod.read_settings()
    values = dict(window._settings)
    values["editor"] = dict(values["editor"])
    values["editor"]["hex_font_size"] = 40
    dialog = SettingsDialog(window._settings, window)
    dialog.settingsChanged.connect(window.apply_settings)
    dialog._on_cancel()
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Rejected
    # The stored value is unchanged and the window keeps the old font size.
    assert (
        settings_mod.read_settings()["editor"]["hex_font_size"]
        == before["editor"]["hex_font_size"]
    )
    assert window.hex_view._font_size == window._settings["editor"]["hex_font_size"]


def test_theme_applied_live(window):
    values = window._settings
    values["general"]["theme"] = "light"
    window.apply_settings(values)
    assert window._theme_manager.mode == "light"
    values["general"]["theme"] = "dark"
    window.apply_settings(values)
    assert window._theme_manager.mode == "dark"


def test_language_applied_live(window):
    values = window._settings
    values["general"]["language"] = "ru"
    window.apply_settings(values)
    assert window._language_manager.preference == "ru"
    values["general"]["language"] = "en"
    window.apply_settings(values)
    assert window._language_manager.preference == "en"


def test_font_size_applied_to_hex_view(window):
    values = window._settings
    values["editor"]["hex_font_size"] = 17
    window.apply_settings(values)
    assert window.hex_view._font_size == 17
    assert window.hex_view.font().pixelSize() == 20


def test_tree_font_size_applied(window):
    values = window._settings
    values["editor"]["tree_font_size"] = 14
    window.apply_settings(values)
    assert window.session_tree._font_size == 14


def test_show_offset_toggle(window):
    window.hex_view.set_stream(bytes(range(32)))
    assert window.hex_view.textCursor().block().text().startswith("00000000")
    values = window._settings
    values["editor"]["show_offset"] = False
    window.apply_settings(values)
    first = window.hex_view.document().firstBlock().text()
    assert not first.startswith("00000000")


def test_annotations_follow_bytes_when_offset_hidden(window):
    """Byte highlighting must not shift when the offset column is hidden.

    The rendered line stride changes with the offset column, so an annotation
    computed from the shown-offset geometry lands inside the previous line. Every
    annotated byte must still resolve to the selection that covers it.
    """
    from src.ui.model import MATCHED, ByteAnnotation

    data = bytes(range(64))
    window.hex_view.set_stream(data, [ByteAnnotation(kind=MATCHED) for _ in data])
    window.hex_view.set_show_offset(False)
    window.hex_view.set_show_offset(True)
    window.hex_view.set_show_offset(False)
    selections = window.hex_view.extraSelections()
    assert selections, "the stream carries annotations"
    stride = len(window.hex_view.document().firstBlock().text()) + 1
    for selection in selections:
        start = selection.cursor.selectionStart()
        assert start % stride == 0, "a selection must start on the first byte column"
    last = selections[-1].cursor
    assert last.selectionEnd() > last.selectionStart(), "the last line keeps its bytes"


def test_settings_signal_emits_mapping(app, isolated_settings):
    dialog = SettingsDialog()
    captured: list[dict] = []
    dialog.settingsChanged.connect(captured.append)
    dialog._on_apply()
    assert captured and captured[0]["advanced"]["log_level"] == "INFO"


def test_welcome_screen_marks_progress(window):
    """The empty state walks capture, session and rule, then yields the workspace."""
    welcome = window.welcome_view
    assert window._stack.currentWidget() is welcome, "the empty state is shown first"
    assert welcome.step_capture.property("state") == "next"

    window.open_capture(
        REPO_ROOT
        / "tests"
        / "corpus"
        / "reference_export"
        / "corpus_capture_01.normalized.json"
    )
    assert window._stack.currentWidget() is window.workspace
    assert welcome.step_capture.property("state") == "done"
    assert welcome.step_session.property("state") == "done"
    assert welcome.step_rule.property("state") == "next"

    window.load_rule(REPO_ROOT / "examples" / "corpus_rule_v1.json")
    assert welcome.step_rule.property("state") == "done"


def test_guided_mode_marks_progress(window):
    """The tutor follows the real state and can be walked through a lesson."""
    window.start_learning("load")
    panel = window.tutor_panel
    assert not panel.isHidden(), "the tutor is shown once the course is started"
    assert panel.lesson_key == "load"

    window.open_capture(
        REPO_ROOT
        / "tests"
        / "corpus"
        / "reference_export"
        / "corpus_capture_01.normalized.json"
    )
    # The capture selects its first direction, so the reader is past the load
    # lesson's opening steps.
    window._update_learning()
    assert panel.lesson_key == "load"


def test_welcome_screen_can_be_shown_again(window):
    window.open_demo()
    assert window._stack.currentWidget() is window.workspace
    window.show_guide()
    assert window._stack.currentWidget() is window.welcome_view


def test_welcome_screen_offers_one_obvious_first_action(window):
    """A first-time reader sees the recommended action before the others."""
    welcome = window.welcome_view
    assert welcome.learning_button.text()
    assert welcome.learning_button.objectName() == "welcomePrimary"
    assert welcome.demo_button.objectName() == "welcomeSecondary"
    assert welcome.capabilities_button.objectName() == "welcomeSecondary"


def test_apply_is_gated_until_a_capture_and_a_rule_are_open(window):
    """Applying needs both inputs, so the button is disabled until they exist."""
    view = window.validation_view
    assert not view.apply_button.isEnabled()
    window.open_demo()
    assert view.apply_button.isEnabled()
    assert view.apply_button.toolTip() == ""


def test_guided_mode_can_be_shown_again(window):
    window.start_learning("load")
    assert not window.tutor_panel.isHidden()
    window.set_guided_mode(False)
    assert window.tutor_panel.isHidden()
    window.set_guided_mode(True)
    assert not window.tutor_panel.isHidden()


def test_guided_mode_stays_a_thin_strip(window):
    """The tutor must not eat the workspace it introduces."""
    window.start_learning("load")
    panel = window.tutor_panel
    # The tutor sits in the workspace, which appears once a capture is open;
    # measuring it on the welcome screen would measure a hidden page.
    window.open_capture(
        REPO_ROOT
        / "tests"
        / "corpus"
        / "reference_export"
        / "corpus_capture_01.normalized.json"
    )
    panel.setVisible(True)
    window.resize(1024, 768)
    window.show()
    for _ in range(3):
        QtWidgets.QApplication.processEvents()
    assert panel.height() < window.height() // 4


def test_guided_mode_round_trips_through_the_dialog(app, isolated_settings):
    """Turning the hints off in the dialog persists and reaches a new window."""
    dialog = SettingsDialog()
    dialog._widgets["general"]["guided_mode"].setChecked(False)
    values = dialog.values()
    assert values["general"]["guided_mode"] is False

    first = MainWindow()
    first.apply_settings(values)
    first.close()

    second = MainWindow()
    assert second._guided_enabled is False
    # The tutor is only shown once the course is started, so it stays hidden.
    second.start_learning("load")
    assert second.tutor_panel.isHidden()
    second.close()


def test_capture_action_names_both_accepted_forms(window):
    """The menu must not claim that a raw pcap is rejected, because it is read."""
    tip = window._actions["open_capture"].toolTip()
    assert "pcap" in tip.lower()
    assert "not read" not in tip.lower()


def test_logging_level_is_valid_choice(app, isolated_settings):
    dialog = SettingsDialog()
    level = dialog._widgets["advanced"]["log_level"]
    assert [level.itemData(i) for i in range(level.count())] == [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
    ]
