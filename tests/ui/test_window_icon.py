"""The window carries the application icon in its title bar.

The icon comes from the packaged SVG, so the tests check that the asset exists,
parses as XML and renders through the Qt SVG backend, and that both the window
and the application object report a non-null icon.
"""

from __future__ import annotations

import os
import xml.dom.minidom

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

try:
    from PySide6 import QtSvg, QtWidgets  # noqa: E402

    from src.ui.main_window import APP_ICON, MainWindow, app_icon  # noqa: E402
except ImportError:  # pragma: no cover - headless runner without Qt libraries
    pytest.skip("PySide6 is not importable", allow_module_level=True)


def test_icon_file_exists() -> None:
    assert APP_ICON.is_file(), f"missing icon asset: {APP_ICON}"
    assert APP_ICON.suffix == ".svg"


def test_icon_svg_parses() -> None:
    document = xml.dom.minidom.parse(str(APP_ICON))
    assert document.documentElement.tagName == "svg"


def test_icon_svg_renders() -> None:
    renderer = QtSvg.QSvgRenderer(str(APP_ICON))
    assert renderer.isValid()
    assert renderer.defaultSize().width() > 0


def test_window_icon_is_set(qapp: QtWidgets.QApplication) -> None:
    window = MainWindow()
    try:
        assert not window.windowIcon().isNull()
    finally:
        window.close()


def test_application_icon_is_set(qapp: QtWidgets.QApplication) -> None:
    assert not app_icon().isNull()
    assert not qapp.windowIcon().isNull()


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setWindowIcon(app_icon())
    return app
