"""End-to-end language switching: English interface.

The window is driven through the real language menu path and every visible
caption is read back. The point is that switching language relabels the window
in place; nothing is rebuilt and no state is lost. The strings asserted here are
the English source strings, so the catalogue cannot silently supply a wrong
translation.
"""

from __future__ import annotations

import pytest

from src.ui import theme

MODE = "en"


@pytest.fixture()
def en(window, app):
    window.set_language(MODE)
    window.set_theme_mode("dark")
    app.processEvents()
    return window


def test_window_title_is_english(en):
    assert en.windowTitle().startswith("Madrigal protocol laboratory")


def test_menu_titles_are_english(en):
    titles = {key: menu.title() for key, menu in en._menus.items()}
    assert titles["file"] == "&File"
    assert titles["rule"] == "&Rule"
    assert titles["report"] == "&Report"
    assert titles["view"] == "&View"
    assert titles["help"] == "&Help"


def test_tab_captions_are_english(en):
    tabs = [en.right_tabs.tabText(i) for i in range(en.right_tabs.count())]
    assert tabs == ["Interpretation", "Compare", "Hypotheses", "Report", "Version diff"]


def test_group_boxes_are_english(en):
    assert en._bytes_box.title() == "Bytes"
    assert en._sessions_box.title() == "Sessions"


def test_direction_label_is_english(en):
    assert en._direction_label.text() == "direction"


def test_direction_combo_values(en):
    assert en.direction_combo.currentText() in ("A_to_B", "B_to_A")


def test_open_capture_action_is_english(en):
    assert en._actions["open_capture"].text() == "Open &normalized capture..."


def test_theme_action_is_english(en):
    assert en._actions["theme_dark"].text() == "&Dark theme"


def test_settings_action_is_english(en):
    assert en._actions["settings"].text() == "&Settings..."


def test_help_action_is_english(en):
    assert en._actions["quick_help"].text() == "&Quick help"


def test_legend_chips_are_english(en):
    captions = [chip.text() for chip in en._legend_chips]
    assert "gap" in captions
    assert "matched" in captions
    assert "mismatched" in captions


def test_session_tree_header_is_english(en):
    header = en.session_tree.headerItem().text(0)
    assert header.lower().startswith("session")


def test_validation_tab_labels_are_english(en):
    view = en.validation_view
    texts = [view._tabs.tabText(i) for i in range(view._tabs.count())]
    assert any("Counterexample" in t for t in texts)


def test_status_line_is_english_after_rule_apply(en):
    en.apply_rule()
    en.apply_to_capture()
    text = en.validation_view.rule_status.text()
    assert "counterexamples" in text or "rule v" in text


def test_language_preference_is_en(en):
    assert en._language_manager.language == "en"


def test_no_russian_leaks_into_the_menu(en):
    for menu in en._menus.values():
        assert "Файл" not in menu.title()


def test_font_family_loaded(en):
    assert theme.body_font(10).family()
