"""Tests for portable-project management and rule-version saving from the window.

The window drives the existing :mod:`src.project` API; these tests use the same
API to inspect what the window wrote, so they exercise real directories and real
files rather than stubs. Every dialog is answered through the same public Qt
entry points the application calls, so the code path under test is the one a
researcher triggers.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6 import QtWidgets

    from src.project.project import Project
    from src.protocol.rule import load_rule, parse_rule
    from src.ui import theme
    from src.ui.main_window import MainWindow, open_default_window
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPTURE = (
    REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
)
RULE = REPO_ROOT / "examples" / "corpus_rule_v1.json"

corpus_required = pytest.mark.skipif(
    not CAPTURE.is_file() or not RULE.is_file(),
    reason="reference corpus not present",
)


@pytest.fixture(scope="session")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # pragma: no cover - depends on the runner
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


def _answer(monkeypatch, *, directory=None, text=None, save_path=None, question=None):
    """Answer the dialogs a project or rule action opens.

    Only the calls the action makes are replaced, so the rest of the window
    keeps its real behaviour. ``warning`` and ``information`` are always made
    non-blocking: an error path opens a modal box that would otherwise wait for
    a click no offscreen run can give.
    """
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", staticmethod(lambda *a, **k: None)
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information", staticmethod(lambda *a, **k: None)
    )
    # Default every yes/no prompt to Discard so a window closed on an unsaved
    # project does not wait for a click; a test that needs another answer passes
    # ``question`` explicitly.
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        staticmethod(
            lambda *a, **k: question
            if question is not None
            else QtWidgets.QMessageBox.StandardButton.Discard
        ),
    )
    if directory is not None:
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getExistingDirectory",
            staticmethod(lambda *a, **k: str(directory)),
        )
    if text is not None:
        monkeypatch.setattr(
            QtWidgets.QInputDialog,
            "getText",
            staticmethod(lambda *a, **k: (text[0], text[1])),
        )
    if save_path is not None:
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *a, **k: (str(save_path), "")),
        )


def test_new_project_creates_and_adopts(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("Field trial", True))
    window.new_project_dialog()

    project_dir = tmp_path / "Field-trial"
    assert project_dir.is_dir()
    assert window._project is not None
    assert window._project.name == "Field trial"
    assert project_dir.name in window.windowTitle()
    window.close()


def test_new_project_cancel_is_side_effect_free(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("Field trial", False))
    window.new_project_dialog()
    assert window._project is None
    assert not (tmp_path / "Field-trial").exists()
    window.close()


def test_empty_project_name_is_rejected(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("   ", True))
    window.new_project_dialog()
    assert window._project is None
    window.close()


def test_failed_open_keeps_the_current_project(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("Kept", True))
    window.new_project_dialog()
    original = window._project

    # A folder that is not a project: the open must fail without clearing the
    # project the window already holds.
    bogus = tmp_path / "not-a-project"
    bogus.mkdir()
    _answer(monkeypatch, directory=bogus, question=QtWidgets.QMessageBox.StandardButton.Discard)
    window.open_project_dialog()
    assert window._project is original
    window.close()


def test_open_then_save_round_trips_manifest(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("Round trip", True))
    window.new_project_dialog()
    window.save_project()

    reopened = Project.open(tmp_path / "Round-trip")
    assert reopened.name == "Round trip"
    assert window._project_is_dirty() is False
    window.close()


def test_add_capture_registers_it_in_the_manifest(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("With capture", True))
    window.new_project_dialog()
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(CAPTURE), "")),
    )
    window.add_capture_to_project_dialog()

    reopened = Project.open(tmp_path / "With-capture")
    assert reopened.manifest.captures
    assert reopened.verify_captures() == []
    window.close()


def test_dirty_project_is_detected_after_an_unsaved_change(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("Dirty", True))
    window.new_project_dialog()
    assert window._project_is_dirty() is False
    window._project.manifest.name = "renamed"
    assert window._project_is_dirty() is True
    window.close()


def test_close_can_be_cancelled_on_unsaved_changes(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("Guarded", True))
    window.new_project_dialog()
    window._project.manifest.name = "renamed"

    events = []

    class _Event:
        def accept(self):
            events.append("accept")

        def ignore(self):
            events.append("ignore")

    _answer(monkeypatch, question=QtWidgets.QMessageBox.StandardButton.Cancel)
    window.closeEvent(_Event())
    assert events == ["ignore"]
    window._project = None
    window.close()


@corpus_required
def test_save_rule_version_copies_into_the_project(app, monkeypatch, tmp_path):
    window = open_default_window(app, capture=CAPTURE, rule=RULE)
    _answer(monkeypatch, directory=tmp_path, text=("Baseline", True))
    window.new_project_dialog()
    _answer(monkeypatch, text=("Baseline request", True))
    window.save_rule_version_dialog()

    reopened = Project.open(tmp_path / "Baseline")
    assert reopened.manifest.rules
    entry = reopened.manifest.rules[0]
    assert entry["rule_id"] == window._rule.rule.rule_id
    stored = load_rule(reopened.path(entry["path"]))
    assert stored.name == "Baseline request"
    assert reopened.verify_rules() == []
    window.close()


@corpus_required
def test_save_rule_version_without_project_writes_the_chosen_file(app, monkeypatch, tmp_path):
    window = open_default_window(app, capture=CAPTURE, rule=RULE)
    target = tmp_path / "version.json"
    _answer(monkeypatch, text=("Standalone", True), save_path=target)
    window.save_rule_version_dialog()
    assert target.is_file()
    assert load_rule(target).name == "Standalone"
    window.close()


@corpus_required
def test_save_rule_version_cancelled_writes_nothing(app, monkeypatch, tmp_path):
    window = open_default_window(app, capture=CAPTURE, rule=RULE)
    _answer(monkeypatch, directory=tmp_path, text=("Cancel case", True))
    window.new_project_dialog()
    _answer(monkeypatch, text=("Ignored", False))
    window.save_rule_version_dialog()
    assert Project.open(tmp_path / "Cancel-case").manifest.rules == []
    window.close()


def test_export_and_import_round_trip(app, monkeypatch, tmp_path):
    window = MainWindow()
    _answer(monkeypatch, directory=tmp_path, text=("Portable", True))
    window.new_project_dialog()
    archive = tmp_path / "portable.zip"
    _answer(monkeypatch, save_path=archive)
    window.export_project_dialog()
    assert archive.is_file()

    target_parent = tmp_path / "restore"
    target_parent.mkdir()
    _answer(monkeypatch, directory=target_parent, question=QtWidgets.QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(archive), "")),
    )
    window.import_project_dialog()
    assert (target_parent / "portable").is_dir()
    window.close()


def test_rule_serialisation_keeps_the_direction_scope(tmp_path):
    """A rule saved from the window keeps its scope, so B_to_A survives."""
    from src.protocol.rule import rule_text, save_rule

    rule = parse_rule(
        {
            "rule_id": "r-response",
            "rule_version": 2,
            "name": "response",
            "scope": {"direction": "B_to_A"},
            "framing": {"type": "fixed_size", "size": 4},
            "fields": [{"name": "code", "offset": 0, "type": "uint8"}],
        }
    )
    path = tmp_path / "response.json"
    save_rule(rule, path)
    reloaded = load_rule(path)
    assert reloaded.direction == "B_to_A"
    assert reloaded.applies_to("B_to_A") is True
    assert reloaded.applies_to("A_to_B") is False
    assert "B_to_A" in rule_text(reloaded)
