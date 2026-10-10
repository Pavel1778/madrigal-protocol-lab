"""Shared isolation for the interface tests.

The window reads two kinds of state from the desktop: the interface language
and the editor font sizes. Both live in ``QSettings`` (organisation
``madrigal``, application ``protocol-lab``), and both fall back to the running
machine when unset — ``language`` defaults to ``system`` and the font sizes to
the table in :mod:`src.ui.settings`. That makes the suite depend on the
developer's own configuration: a saved ``language=ru`` starts the window in
Russian and a saved ``tree_font_size`` can pin the session tree to its lower
bound, so assertions written against the English source strings and the default
sizes fail on that machine and pass on a clean one.

This module removes that dependency for every test under ``tests/ui``:

* the desktop locale is forced to English so ``system`` resolves to ``en``;
* every ``QSettings`` read and write is redirected to a throwaway directory so
  the real ``~/.config/madrigal/protocol-lab.conf`` is neither read nor touched;
* the redirected store is emptied before each test, so each one starts from the
  documented defaults.

Nothing here reaches into the application: the isolation is expressed entirely
through the environment and ``QSettings`` path selection, which the application
already honours.
"""

from __future__ import annotations

import os

# The window is opened without a display. Set at import time so any module that
# builds a QApplication afterwards inherits it.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# A deterministic desktop locale. ``LANGUAGE`` takes precedence over ``LANG`` in
# gettext lookup, and both are set so ``QLocale.system()`` reports English
# whichever variable the running Qt build consults first. Set here as well as
# per session so a later import cannot observe the developer's locale.
os.environ["LANG"] = "en_US.UTF-8"
os.environ["LANGUAGE"] = "en"
os.environ["LC_ALL"] = "en_US.UTF-8"

import pytest  # noqa: E402

try:
    from PySide6 import QtCore  # noqa: E402
except ImportError:  # pragma: no cover - depends on the runner
    QtCore = None  # type: ignore[assignment]

# The organisation and application the window reads from. Kept as literals here
# because the isolation must apply before any application module is imported.
_SETTINGS_ORG = "madrigal"
_SETTINGS_APP = "protocol-lab"


@pytest.fixture(scope="session", autouse=True)
def _isolated_ui_settings(tmp_path_factory: pytest.TempPathFactory):
    """Redirect every QSettings store to a throwaway directory.

    Both user and system paths are pointed at a temporary directory for the
    native and the ini format, so a store created with any organisation or
    application name lands there instead of in ``~/.config``. The native format
    is what a bare ``QSettings(org, app)`` uses on this platform; the ini format
    is covered so the redirect does not depend on that.
    """
    if QtCore is None:
        yield
        return
    store = tmp_path_factory.mktemp("ui-settings")
    scope = QtCore.QSettings.Scope
    for format_ in (QtCore.QSettings.Format.NativeFormat, QtCore.QSettings.Format.IniFormat):
        QtCore.QSettings.setPath(format_, scope.UserScope, str(store))
        QtCore.QSettings.setPath(format_, scope.SystemScope, str(store))
    yield


@pytest.fixture(autouse=True)
def _clean_ui_settings(_isolated_ui_settings):
    """Start each test from the documented defaults.

    The language and editor preferences are cleared for the store the window
    uses, so no test inherits a size or a language written by another test or by
    the developer.
    """
    if QtCore is not None:
        store = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        store.clear()
        store.sync()
    yield
