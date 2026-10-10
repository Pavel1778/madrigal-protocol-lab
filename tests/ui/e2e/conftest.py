"""Fixtures for the interface end-to-end tests.

One application and one window are built per module. The window offers a public
``set_language``; the tests never reach into translation internals.
"""

from __future__ import annotations

import pytest
from PySide6 import QtWidgets

from tests.ui.support import configure_app, load_window


@pytest.fixture(scope="module")
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    configure_app(application)
    return application


@pytest.fixture(scope="module")
def window(app):
    w = load_window(app)
    yield w
    # The translator and the style sheet live on the shared QApplication, so a
    # module that left the interface Russian or light would break the next one.
    w.set_language("en")
    w.set_theme_mode("dark")
    app.processEvents()
    w.close()
