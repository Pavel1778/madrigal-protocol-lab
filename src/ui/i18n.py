"""Interface language selection for the protocol laboratory.

The window is translated with the Qt toolchain: source strings are written in
English and wrapped in :meth:`QObject.tr`, ``pyside6-lrelease`` compiles the
``.ts`` catalogues under ``src/ui/locale`` into ``.qm`` files, and a
:class:`QTranslator` supplies them at run time. No third-party translation
library is involved.

The choice is stored with ``QSettings`` so it survives a restart. ``system``
follows the desktop locale; ``en`` needs no catalogue because English is the
source language, so selecting it simply unloads the translator.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore

LOCALE_DIR = Path(__file__).resolve().parent / "locale"

# Preference codes. "system" is resolved from the desktop locale at install
# time; the catalogue base name is the resolved code.
LANGUAGES = ("system", "ru", "en")

_CATALOGUE = "madrigal"
_DEFAULT_LANGUAGE = "system"

_SETTINGS_ORG = "madrigal"
_SETTINGS_APP = "protocol-lab"
_SETTINGS_KEY = "interface/language"


def resolve_language(preference: str, system_name: str) -> str:
    """Return the catalogue code for *preference*.

    ``system`` maps to the leading language subtag of *system_name* (for
    example ``ru_RU`` becomes ``ru``). An explicit code is returned unchanged,
    and a preference that names no catalogue falls back to English.
    """
    if preference == "system":
        language = system_name.split("_", 1)[0].split("-", 1)[0]
    else:
        language = preference
    if language in ("ru", "en"):
        return language
    return "en"


class LanguageManager(QtCore.QObject):
    """Install and remove the Qt translator for the chosen interface language."""

    languageChanged = QtCore.Signal(str)

    def __init__(self, app: QtCore.QCoreApplication, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._translator: QtCore.QTranslator | None = None
        self._settings = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._preference = self._settings.value(_SETTINGS_KEY, _DEFAULT_LANGUAGE)
        if self._preference not in LANGUAGES:
            self._preference = _DEFAULT_LANGUAGE
        self._install()

    @property
    def preference(self) -> str:
        """The stored choice: ``system``, ``ru`` or ``en``."""
        return str(self._preference)

    @property
    def language(self) -> str:
        """The catalogue code currently in effect: ``ru`` or ``en``."""
        return resolve_language(str(self._preference), QtCore.QLocale.system().name())

    def set_language(self, preference: str) -> None:
        """Store *preference* and install the matching catalogue."""
        if preference not in LANGUAGES:
            preference = _DEFAULT_LANGUAGE
        self._preference = preference
        self._settings.setValue(_SETTINGS_KEY, preference)
        self._install()
        self.languageChanged.emit(self.language)

    def _install(self) -> None:
        """Load the catalogue for the current preference, if one exists.

        The previous translator is always removed first so switching back to
        English (or to a language with no catalogue) restores the source
        strings rather than leaving the old translation installed.
        """
        if self._translator is not None:
            self._app.removeTranslator(self._translator)
            self._translator = None
        language = self.language
        if language == "en":
            return
        path = LOCALE_DIR / f"{_CATALOGUE}_{language}.qm"
        if not path.is_file():
            return
        translator = QtCore.QTranslator(self)
        if translator.load(str(path)):
            self._app.installTranslator(translator)
            self._translator = translator
