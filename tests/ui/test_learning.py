"""Tests for the interactive course and the reference catalogue.

The course is driven through the real window and the real engine: the tutor
advances only when the window's own state reaches the condition a step asks for,
so these tests perform the actions (opening the example, selecting a byte,
applying the rule) and assert that the tutor followed. Nothing is mocked except
the modal rule-builder dialog, which cannot be driven headlessly.

The reference tests check that the catalogue is complete against the real rule
model and that every entry can be looked up and rendered in both languages.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6 import QtWidgets

    from src.protocol.rule import ALL_FIELD_TYPES
    from src.ui import help as reference
    from src.ui import learning, theme
    from src.ui.help_dialog import HelpCard, LearningCentre
    from src.ui.main_window import SAMPLE_RULE, MainWindow
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


@pytest.fixture
def window(app):
    window = MainWindow()
    # The rule builder is a modal dialog; the course offers it but the test
    # cannot click through it headlessly. Adopting the sample rule performs the
    # same real work the dialog would, without the dialog.
    window.build_rule = lambda: window.load_rule(SAMPLE_RULE)
    yield window
    window.close()


def _walk(window: MainWindow, limit: int = 120) -> None:
    """Advance the tutor until it stops, performing the actions it asks for."""
    for _ in range(limit):
        if window.tutor_panel.isHidden():
            return
        step = window.tutor_panel.current_step
        if step is not None and step.requires == "byte_selected":
            window._on_byte_clicked(0)
        window._learning_next()


# -- the course ----------------------------------------------------------


def test_tutor_is_hidden_until_the_course_is_started(window):
    assert window.tutor_panel.isHidden()
    assert window._learning_active is False


def test_first_run_offer_loads_the_example_and_starts_the_course(window):
    assert window._capture is None
    window._start_course_from_welcome()
    assert window._capture is not None, "the course teaches on the real example"
    assert not window.tutor_panel.isHidden()
    assert window.tutor_panel.lesson_key == learning.LESSONS[0].key


def test_course_walks_to_the_end_and_records_progress(window):
    window._start_course_from_welcome()
    _walk(window)
    assert window.tutor_panel.isHidden(), "the course ends and the tutor leaves"
    assert window._learning_active is False
    assert set(learning.LESSON_BY_KEY) <= window._completed_lessons


def test_tutor_advances_only_when_the_action_is_done(window):
    """A step that asks for a byte is not passed by Next alone."""
    window._start_course_from_welcome()
    window.start_learning("bytes")
    assert window.tutor_panel.current_step.requires == "byte_selected"
    assert window._last_offset is None

    window._learning_next()  # asks for the action, does not advance
    assert window.tutor_panel.step_index == 0

    window._on_byte_clicked(0)  # the real action
    assert window._last_offset == 0


def test_back_returns_to_the_previous_step(window):
    window._start_course_from_welcome()
    window.start_learning("welcome")
    window._learning_next()
    assert window.tutor_panel.step_index == 1
    window._learning_back()
    assert window.tutor_panel.step_index == 0


def test_skip_moves_to_the_next_lesson(window):
    window._start_course_from_welcome()
    window.start_learning("welcome")
    window._learning_skip()
    assert window.tutor_panel.lesson_key == learning.LESSONS[1].key
    assert "welcome" in window._completed_lessons


def test_hide_keeps_the_position(window):
    window._start_course_from_welcome()
    window.start_learning("bytes")
    window._learning_hide()
    assert window.tutor_panel.isHidden()
    window.start_learning()
    assert not window.tutor_panel.isHidden()
    assert window.tutor_panel.lesson_key == "bytes"


def test_expert_mode_hides_the_tutor(window):
    window._start_course_from_welcome()
    assert not window.tutor_panel.isHidden()
    window.set_guided_mode(False)
    assert window.tutor_panel.isHidden()
    window.set_guided_mode(True)
    assert not window.tutor_panel.isHidden()


def test_progress_survives_a_new_window(app):
    first = MainWindow()
    first._start_course_from_welcome()
    first.start_learning("welcome")
    first._learning_skip()
    first.close()

    second = MainWindow()
    assert "welcome" in second._completed_lessons
    second.close()


def test_reset_clears_progress_without_touching_the_work(window):
    window._start_course_from_welcome()
    window.start_learning("welcome")
    window._learning_skip()
    assert window._completed_lessons
    capture_before = window._capture
    window.reset_learning()
    assert not window._completed_lessons
    assert window._capture is capture_before, "the open work is untouched"


def test_learning_centre_lists_every_lesson_and_starts_one(window):
    centre = LearningCentre(completed={"welcome"}, current_lesson="load")
    try:
        assert centre.lesson_list.count() == len(learning.LESSONS)
        chosen: list[str] = []
        centre.lessonChosen.connect(chosen.append)
        centre.lesson_list.setCurrentRow(2)
        centre._on_lesson_activated(centre.lesson_list.currentItem())
        assert chosen and chosen[0] == learning.LESSONS[2].key
    finally:
        centre.close()


def test_learning_centre_searches_the_reference(window):
    centre = LearningCentre()
    try:
        centre.search.setText("byte order")
        assert centre.entry_list.count() >= 1
        centre.search.setText("no such term anywhere")
        assert centre.entry_list.count() == 0
    finally:
        centre.close()


# -- the reference catalogue ---------------------------------------------


def test_every_entry_is_well_formed():
    for entry in reference.HELP_ENTRIES:
        assert entry.key, entry
        assert entry.title and entry.summary, entry.key
        assert entry.section in reference.SECTIONS, entry.key


def test_entry_keys_are_unique():
    keys = [entry.key for entry in reference.HELP_ENTRIES]
    assert len(keys) == len(set(keys))


def test_every_field_type_has_a_reference_entry():
    """A new field type in the rule model must not arrive without an explanation."""
    documented = " ".join(
        reference.translate(entry.title) + reference.translate(entry.summary)
        for entry in reference.HELP_ENTRIES
    )
    for field_type in ALL_FIELD_TYPES:
        assert field_type in documented, f"no reference entry mentions {field_type}"


def test_related_entries_resolve():
    for entry in reference.HELP_ENTRIES:
        for key in entry.related:
            assert reference.lookup(key) is not None, f"{entry.key} -> {key}"


def test_search_finds_by_title_and_term():
    assert reference.lookup("offset") is not None
    assert any(e.key == "offset" for e in reference.search("offset"))
    assert any(e.key == "precision" for e in reference.search("precision"))
    assert reference.search("") == list(reference.HELP_ENTRIES)


def test_help_card_renders_an_entry(window):
    card = HelpCard(reference.ENTRY_BY_KEY["offset"])
    try:
        assert card.title.text()
        assert card.summary.text()
    finally:
        card.close()


def test_window_opens_help_for_a_key(window):
    window.show_help_for("byte_order")
    assert window._help_card is not None
    window.show_help_for("precision")
    assert window._help_card is not None


def test_tutor_help_button_opens_the_step_target(window):
    """The '?' on the tutor opens the reference for the element a step names."""
    window._start_course_from_welcome()
    window.start_learning("interface")
    window._learning_help("hex_view")
    assert window._help_card is not None


# -- the spotlight -------------------------------------------------------


def test_spotlight_lights_the_target_and_clears(window):
    """A step that names an element dims the rest and lights that element."""
    window.setFixedSize(1280, 800)
    window.show()
    window.open_demo()
    window.start_learning("interface")
    app = QtWidgets.QApplication.instance()
    app.processEvents()
    spotlight = window._spotlight
    assert spotlight.isVisible(), "a targeted step shows the spotlight"
    assert spotlight._target is not None
    opening = spotlight._opening()
    assert opening is not None, "the target has a lit opening"
    # The opening is around the target, not the whole workspace.
    assert opening.width() < spotlight.width()
    window._clear_pointer()
    assert not spotlight.isVisible(), "clearing the pointer removes the spotlight"


def test_spotlight_never_covers_the_tutor_strip(window):
    """The dim is bounded by the workspace so the course buttons stay readable."""
    window.setFixedSize(1280, 800)
    window.show()
    window.open_demo()
    window.start_learning("interface")
    app = QtWidgets.QApplication.instance()
    app.processEvents()
    spotlight = window._spotlight
    tutor_rect = window.tutor_panel.geometry()
    assert not spotlight.geometry().intersects(tutor_rect), (
        "the spotlight must not dim the tutor strip"
    )


def test_spotlight_follows_a_resize(window):
    """The overlay and its opening track the workspace after a resize."""
    window.setFixedSize(1280, 800)
    window.show()
    window.open_demo()
    window.start_learning("interface")
    app = QtWidgets.QApplication.instance()
    app.processEvents()
    spotlight = window._spotlight
    before = spotlight.geometry()
    window.setFixedSize(1000, 700)
    app.processEvents()
    after = spotlight.geometry()
    assert after.width() < before.width(), "the overlay shrank with the window"
    assert spotlight._opening() is not None, "the opening is still aligned"
