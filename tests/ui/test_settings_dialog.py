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

import pytest  # noqa: E402
from PySide6 import QtCore, QtWidgets  # noqa: E402

from src.ui import i18n, settings as settings_mod, theme  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from src.ui.settings import SettingsDialog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # noqa: BLE001 - a missing Qt runtime is a skip
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
    assert settings_mod.read_settings()["editor"]["hex_font_size"] == before["editor"]["hex_font_size"]
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


def test_settings_signal_emits_mapping(app, isolated_settings):
    dialog = SettingsDialog()
    captured: list[dict] = []
    dialog.settingsChanged.connect(captured.append)
    dialog._on_apply()
    assert captured and captured[0]["advanced"]["log_level"] == "INFO"


def test_logging_level_is_valid_choice(app, isolated_settings):
    dialog = SettingsDialog()
    level = dialog._widgets["advanced"]["log_level"]
    assert [level.itemData(i) for i in range(level.count())] == ["DEBUG", "INFO", "WARNING", "ERROR"]
