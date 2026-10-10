"""Regression tests for the interface-test isolation.

These assert the invariants that :mod:`tests.ui.conftest` establishes, so the
suite cannot quietly start depending on the developer's locale or on a saved
``QSettings`` file again.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from PySide6 import QtCore
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

from src.ui.settings import DEFAULTS  # noqa: E402


def test_desktop_locale_is_english():
    """The running locale resolves to English even when launched in Russian.

    The window derives ``system`` from ``QLocale.system()``; pinning it in the
    fixture keeps assertions written against the English source strings valid.
    """
    assert QtCore.QLocale.system().name().split("_", 1)[0] == "en"


def test_settings_store_is_not_the_user_configuration():
    """The store the window reads lives outside the user's configuration."""
    store = QtCore.QSettings("madrigal", "protocol-lab")
    user_config = Path.home() / ".config" / "madrigal"
    assert user_config not in Path(store.fileName()).parents


def test_default_font_sizes_are_not_read_from_the_machine(app):
    """A fresh window starts from the documented font defaults.

    A saved ``tree_font_size`` at the lower bound used to pin the session tree
    on its clamp, which made the zoom step a no-op on that machine alone.
    """
    from src.ui.main_window import open_default_window

    window = open_default_window(app)
    assert window.hex_view.font_size == DEFAULTS["editor"]["hex_font_size"]
    assert window.session_tree.font_size == DEFAULTS["editor"]["tree_font_size"]
    window.close()


@pytest.fixture(scope="session")
def app():
    from PySide6 import QtWidgets

    from src.ui import theme

    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application
