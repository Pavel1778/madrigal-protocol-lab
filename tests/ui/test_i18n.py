"""Tests for the interface-language switching.

The tests exercise the real Qt translator: a ``.qm`` catalogue is loaded for
Russian, the window relabels itself, and switching back to English restores the
source strings. No widget is mocked; only the stored preference is redirected to
a throwaway ``QSettings`` scope so the developer's own choice is untouched.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

try:
    from PySide6 import QtWidgets  # noqa: E402

    from src.ui import i18n, theme  # noqa: E402
    from src.ui.main_window import MainWindow  # noqa: E402
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = REPO_ROOT / "src" / "ui" / "locale" / "madrigal_ru.qm"

catalogue_required = pytest.mark.skipif(
    not CATALOGUE.is_file(), reason="Russian catalogue is not compiled"
)


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # noqa: BLE001 - a missing Qt runtime is a skip
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Point the language preference at a throwaway settings file."""
    monkeypatch.setattr(i18n, "_SETTINGS_ORG", "madrigal-test")
    monkeypatch.setattr(i18n, "_SETTINGS_APP", f"protocol-lab-{tmp_path.name}")
    yield


@pytest.fixture
def english_window(app, isolated_settings):
    """A window that is restored to English afterwards."""
    window = MainWindow()
    yield window
    window._language_manager.set_language("en")
    window.close()


def test_resolve_language_maps_system_locale():
    assert i18n.resolve_language("system", "ru_RU") == "ru"
    assert i18n.resolve_language("system", "ru") == "ru"
    assert i18n.resolve_language("system", "en_US") == "en"
    assert i18n.resolve_language("system", "fr_FR") == "en"


def test_resolve_language_keeps_explicit_choice():
    assert i18n.resolve_language("ru", "en_US") == "ru"
    assert i18n.resolve_language("en", "ru_RU") == "en"


def test_language_manager_emits_and_loads_catalogue(app, isolated_settings):
    manager = i18n.LanguageManager(app)
    seen: list[str] = []
    manager.languageChanged.connect(seen.append)

    manager.set_language("ru")
    assert manager.language == "ru"
    assert seen == ["ru"]

    manager.set_language("en")
    assert manager.language == "en"
    assert seen == ["ru", "en"]


def test_language_manager_rejects_unknown_code(app, isolated_settings):
    manager = i18n.LanguageManager(app)
    manager.set_language("de")
    assert manager.preference == "system"


@catalogue_required
def test_window_retranslates_to_russian(english_window):
    window = english_window
    assert window.windowTitle() == "Madrigal protocol laboratory"

    window.set_language("ru")
    assert window.windowTitle() == "Лаборатория протоколов Мадригал"
    assert window._menus["file"].title() == "&Файл"
    assert window._actions["quit"].text() == "Вы&ход"
    assert window.right_tabs.tabText(0) == "Интерпретация"
    assert window._bytes_box.title() == "Байты"
    assert window.validation_view.apply_button.text() == "Применить к текущему направлению"


@catalogue_required
def test_window_language_switch_is_reversible(english_window):
    window = english_window
    window.set_language("ru")
    window.set_language("en")
    assert window.windowTitle() == "Madrigal protocol laboratory"
    assert window._menus["file"].title() == "&File"
    assert window.right_tabs.tabText(0) == "Interpretation"


@catalogue_required
def test_language_choice_is_stored(english_window, app):
    window = english_window
    window.set_language("ru")
    reopened = MainWindow()
    try:
        assert reopened._language_manager.preference == "ru"
        assert reopened.windowTitle() == "Лаборатория протоколов Мадригал"
    finally:
        reopened._language_manager.set_language("en")
        reopened.close()


@catalogue_required
def test_language_menu_checks_current_choice(english_window):
    window = english_window
    window.set_language("ru")
    assert window._language_actions["ru"].isChecked()
    window.set_language("en")
    assert window._language_actions["en"].isChecked()


@catalogue_required
def test_switching_language_keeps_open_capture(english_window):
    window = english_window
    capture = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
    if not capture.is_file():
        pytest.skip("reference corpus not present")
    window.open_capture(capture)
    session_before = window._session_id
    window.set_language("ru")
    assert window._capture is not None
    assert window._session_id == session_before
    assert window._capture_name in window.windowTitle()
