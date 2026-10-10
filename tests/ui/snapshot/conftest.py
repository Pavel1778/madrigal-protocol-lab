"""Fixtures shared by the snapshot modules.

One application and one window are built per module and reused, so the reference
capture is loaded once per colour/language pair instead of once per image.
"""

from __future__ import annotations

import pytest
from PySide6 import QtWidgets

from tests.ui.support import (
    LANGUAGES,
    RESOLUTIONS,
    THEMES,
    ZOOM_LEVELS,
    configure_app,
    load_window,
)


@pytest.fixture(scope="module")
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    configure_app(application)
    return application


@pytest.fixture(scope="module")
def window(app):
    w = load_window(app)
    yield w
    # Leave the shared application on the default language and theme so a later
    # module is not rendered Russian or light.
    w.set_language("en")
    w.set_theme_mode("dark")
    app.processEvents()
    w.close()


@pytest.fixture(params=RESOLUTIONS, ids=lambda r: f"{r[0]}x{r[1]}")
def resolution(request):
    """Every window size the product supports, one test each."""
    return request.param


@pytest.fixture(params=ZOOM_LEVELS, ids=lambda z: f"zoom{z}")
def zoom(request):
    """The documented zoom levels: 100, 150 and 200 percent."""
    return request.param


@pytest.fixture(params=LANGUAGES, ids=lambda code: f"lang-{code}")
def language(request):
    return request.param


@pytest.fixture(params=THEMES, ids=lambda name: f"theme-{name}")
def theme_mode(request):
    return request.param

