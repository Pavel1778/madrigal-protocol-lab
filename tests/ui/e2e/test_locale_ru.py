"""End-to-end language switching: Russian interface.

The same surface as the English module, asserted against the strings in the
Russian catalogue. Reading the catalogue rather than hard-coding would make the
test agree with any translation, including a broken one, so the expected values
are written out here on purpose.
"""

from __future__ import annotations

import pytest

MODE = "ru"


@pytest.fixture()
def ru(window, app):
    window.set_language(MODE)
    window.set_theme_mode("dark")
    app.processEvents()
    return window


def test_window_title_is_russian(ru):
    assert ru.windowTitle().startswith("Лаборатория протоколов Мадригал")


def test_menu_titles_are_russian(ru):
    titles = {key: menu.title() for key, menu in ru._menus.items()}
    assert titles["file"] == "&Файл"
    assert titles["rule"] == "&Правило"
    assert titles["report"] == "&Отчёт"
    assert titles["view"] == "&Вид"
    assert titles["help"] == "&Справка"


def test_tab_captions_are_russian(ru):
    tabs = [ru.right_tabs.tabText(i) for i in range(ru.right_tabs.count())]
    assert tabs == ["Интерпретация", "Сравнение", "Гипотезы", "Отчёт", "Различие версий"]


def test_group_boxes_are_russian(ru):
    assert ru._bytes_box.title() == "Байты"
    assert ru._sessions_box.title() == "Сессии"


def test_direction_label_is_russian(ru):
    assert ru._direction_label.text() == "направление"


def test_direction_combo_values_are_protocol_names(ru):
    # The direction names are protocol identifiers, never translated.
    assert ru.direction_combo.currentText() in ("A_to_B", "B_to_A")


def test_open_capture_action_is_russian(ru):
    assert ru._actions["open_capture"].text() == "Открыть &нормализованный захват..."


def test_theme_action_is_russian(ru):
    assert ru._actions["theme_dark"].text() == "&Тёмная тема"


def test_settings_action_is_russian(ru):
    assert ru._actions["settings"].text() == "&Настройки..."


def test_help_action_is_russian(ru):
    assert ru._actions["quick_help"].text() == "&Краткая справка"


def test_legend_chips_are_russian(ru):
    captions = [chip.text() for chip in ru._legend_chips]
    assert "разрыв" in captions
    assert "совпадение" in captions
    assert "несовпадение" in captions


def test_session_tree_header_is_russian(ru):
    assert ru.session_tree.headerItem().text(0) == "сессия"


def test_validation_tab_labels_are_russian(ru):
    view = ru.validation_view
    texts = [view._tabs.tabText(i) for i in range(view._tabs.count())]
    assert "Правило" in texts


def test_status_line_is_russian_after_rule_apply(ru):
    ru.apply_rule()
    ru.apply_to_capture()
    text = ru.validation_view.rule_status.text()
    assert "контрпример" in text or "правило" in text


def test_language_preference_is_ru(ru):
    assert ru._language_manager.language == "ru"


def test_no_english_leaks_into_the_menu(ru):
    for menu in ru._menus.values():
        assert "File" not in menu.title()
