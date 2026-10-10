"""Theme manager.

Owns the active token set, turns it into the application style sheet and
palette, and applies it live. The choice is persisted per user in ``QSettings``
(organisation ``Madrigal``, application ``Protocol Lab``); when nothing is
stored the dark theme is used.

``System`` mode follows the platform colour scheme when the running Qt exposes
one (Qt 6.5+); otherwise it falls back to dark and says so in the log.
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

from . import contrast, fonts
from .dark import DARK
from .light import LIGHT
from .tokens import Theme

logger = logging.getLogger(__name__)

ORGANISATION = "Madrigal"
APPLICATION = "Protocol Lab"
SETTINGS_KEY = "appearance/theme"

MODES = ("dark", "light", "system")
DEFAULT_MODE = "dark"

THEMES: dict[str, Theme] = {"dark": DARK, "light": LIGHT}

# The theme applied on import, before a manager exists. Widgets that build
# themselves outside a running manager read this.
_active: Theme = DARK


def current() -> Theme:
    """Return the active token set."""
    return _active


def set_current(theme: Theme) -> None:
    """Set the active token set without touching an application."""
    global _active
    _active = theme


def build_palette(theme: Theme | None = None) -> QtGui.QPalette:
    """Return a ``QPalette`` derived from *theme* (the active one by default)."""
    theme = theme or _active
    role = QtGui.QPalette.ColorRole
    group = QtGui.QPalette.ColorGroup
    palette = QtGui.QPalette()
    mapping = {
        role.Window: theme.background,
        role.WindowText: theme.text_primary,
        role.Base: theme.surface,
        role.AlternateBase: theme.surface_alt,
        role.Text: theme.text_primary,
        role.Button: theme.surface,
        role.ButtonText: theme.text_primary,
        role.Highlight: theme.selection,
        role.HighlightedText: theme.selection_text,
        role.ToolTipBase: theme.surface,
        role.ToolTipText: theme.text_primary,
        role.PlaceholderText: theme.text_muted,
    }
    for color_role, value in mapping.items():
        palette.setColor(color_role, QtGui.QColor(value))
        palette.setColor(group.Disabled, color_role, QtGui.QColor(theme.text_muted))
    return palette


def build_stylesheet(theme: Theme | None = None) -> str:
    """Return the Qt style sheet for *theme* (the active one by default)."""
    theme = theme or _active
    return f"""
    QWidget {{
        background-color: {theme.background};
        color: {theme.text_primary};
        font-family: "{theme.font_body}";
    }}
    QMainWindow, QDialog {{ background-color: {theme.background}; }}
    QLabel {{ background: transparent; }}
    QLabel[role="heading"] {{
        font-family: "{theme.font_heading}";
        color: {theme.text_primary};
    }}
    QLabel[role="secondary"] {{ color: {theme.text_secondary}; }}
    QGroupBox {{
        background-color: {theme.surface};
        border: 1px solid {theme.border};
        border-radius: {theme.radius}px;
        margin-top: 14px;
        padding: 8px;
        font-family: "{theme.font_heading}";
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {theme.text_secondary};
    }}
    QTreeWidget, QTableWidget, QPlainTextEdit, QTextEdit, QListWidget {{
        background-color: {theme.surface};
        border: 1px solid {theme.border};
        border-radius: {theme.radius}px;
        selection-background-color: {theme.selection};
        selection-color: {theme.selection_text};
        outline: none;
    }}
    QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {{
        background-color: {theme.surface_alt};
    }}
    QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
        background-color: {theme.selection};
        color: {theme.selection_text};
    }}
    QHeaderView::section {{
        background-color: {theme.surface_alt};
        color: {theme.text_secondary};
        border: none;
        border-right: 1px solid {theme.border};
        border-bottom: 1px solid {theme.border};
        padding: 4px 6px;
        font-family: "{theme.font_heading}";
    }}
    QPushButton {{
        background-color: {theme.surface};
        border: 1px solid {theme.border};
        border-radius: {theme.radius}px;
        padding: 6px 12px;
        color: {theme.text_primary};
    }}
    QPushButton:hover {{ border-color: {theme.accent}; }}
    QPushButton:pressed {{ background-color: {theme.button_pressed}; border-color: {theme.accent}; }}
    QPushButton:disabled {{
        color: {theme.text_muted};
        border-color: {theme.border};
        background-color: {theme.surface_alt};
    }}
    QPushButton[accent="true"] {{
        background-color: {theme.accent};
        border-color: {theme.accent};
        color: {theme.text_on_accent};
    }}
    QPushButton[accent="true"]:hover {{ background-color: {theme.accent_hover}; border-color: {theme.accent_hover}; }}
    QPushButton[accent="true"]:pressed {{ background-color: {theme.accent_hover}; }}
    QPushButton[accent="true"]:disabled {{
        background-color: {theme.surface_alt};
        border-color: {theme.border};
        color: {theme.text_muted};
    }}
    QLineEdit, QComboBox, QSpinBox {{
        background-color: {theme.surface};
        border: 1px solid {theme.border};
        border-radius: {theme.radius}px;
        padding: 4px 6px;
    }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: {theme.text_muted}; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {theme.accent}; }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
        background-color: {theme.surface_alt};
        color: {theme.text_muted};
    }}
    QTabWidget::pane {{ border: 1px solid {theme.border}; top: -1px; }}
    QTabBar::tab {{
        background-color: {theme.surface_alt};
        color: {theme.text_secondary};
        border: 1px solid {theme.border};
        border-bottom: none;
        padding: 5px 12px;
    }}
    QTabBar::tab:hover {{ color: {theme.text_primary}; }}
    QTabBar::tab:selected {{
        background-color: {theme.surface};
        color: {theme.text_primary};
        border-top: 2px solid {theme.accent};
    }}
    QMenuBar {{ background-color: {theme.surface_alt}; }}
    QMenuBar::item:selected {{ background-color: {theme.menu_selection}; color: {theme.menu_selection_text}; }}
    QMenu {{ background-color: {theme.surface_elevated}; border: 1px solid {theme.border}; }}
    QMenu::item:selected {{ background-color: {theme.menu_selection}; color: {theme.menu_selection_text}; }}
    QStatusBar {{ background-color: {theme.surface_alt}; color: {theme.text_secondary}; }}
    QScrollBar:vertical {{
        background: {theme.surface_alt}; width: 10px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {theme.border}; border-radius: 5px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {theme.text_muted}; }}
    QScrollBar:horizontal {{
        background: {theme.surface_alt}; height: 10px; margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {theme.border}; border-radius: 5px; min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {theme.text_muted}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QToolTip {{
        background-color: {theme.surface_elevated};
        color: {theme.text_primary};
        border: 1px solid {theme.border};
    }}
    QProgressBar {{
        background-color: {theme.surface_alt};
        border: 1px solid {theme.border};
        border-radius: {theme.radius}px;
        text-align: center;
        color: {theme.text_secondary};
    }}
    QProgressBar::chunk {{ background-color: {theme.accent}; }}
    QSplitter::handle {{ background-color: {theme.border}; }}
    """


def system_scheme() -> str | None:
    """Return ``"dark"`` or ``"light"`` from the platform, or ``None``.

    ``None`` means the running Qt does not expose a colour scheme, so the
    caller should fall back to the default.
    """
    app = QtWidgets.QApplication.instance()
    if app is None or not hasattr(app, "styleHints"):
        return None
    hints = app.styleHints()
    if hints is None or not hasattr(hints, "colorScheme"):
        return None
    scheme = hints.colorScheme()
    name = getattr(scheme, "name", "") or ""
    lowered = name.lower()
    if lowered == "dark":
        return "dark"
    if lowered == "light":
        return "light"
    return None


class ThemeManager(QtCore.QObject):
    """Apply a theme to an application and remember the choice."""

    themeChanged = QtCore.Signal(str)

    def __init__(
        self,
        app: QtWidgets.QApplication,
        settings: QtCore.QSettings | None = None,
        mode: str | None = None,
    ) -> None:
        super().__init__()
        self._app = app
        self._settings = settings if settings is not None else self._default_settings()
        self._mode = mode if mode in MODES else self._stored_mode()
        self.apply()

    @staticmethod
    def _default_settings() -> QtCore.QSettings:
        return QtCore.QSettings(ORGANISATION, APPLICATION)

    def _stored_mode(self) -> str:
        stored = self._settings.value(SETTINGS_KEY, DEFAULT_MODE)
        return stored if stored in MODES else DEFAULT_MODE

    @property
    def mode(self) -> str:
        """The selected mode: ``dark``, ``light`` or ``system``."""
        return self._mode

    @property
    def theme(self) -> Theme:
        """The active token set."""
        return _active

    def resolve(self, mode: str | None = None) -> str:
        """Resolve a mode to the concrete theme name to apply."""
        chosen = mode if mode is not None else self._mode
        if chosen == "system":
            scheme = system_scheme()
            if scheme is None:
                logger.info("no platform colour scheme; using dark")
                return "dark"
            return scheme
        return chosen if chosen in THEMES else DEFAULT_MODE

    def apply(self, mode: str | None = None) -> None:
        """Apply the resolved theme for *mode* (or the current mode)."""
        name = self.resolve(mode)
        theme = THEMES[name]
        set_current(theme)
        self._app.setPalette(build_palette(theme))
        self._app.setStyleSheet(build_stylesheet(theme))
        self.themeChanged.emit(name)

    def set_mode(self, mode: str) -> None:
        """Select *mode*, persist it and apply the resulting theme."""
        if mode not in MODES:
            mode = DEFAULT_MODE
        self._mode = mode
        self._settings.setValue(SETTINGS_KEY, mode)
        self.apply()

    def toggle(self) -> None:
        """Switch between dark and light, resolving from the active theme."""
        self.set_mode("light" if self.theme.name == "dark" else "dark")

    def set_theme(self, name: str) -> None:
        """Select the concrete theme *name* and persist it."""
        if name in THEMES:
            self.set_mode(name)

    def contrast_report(self) -> list[contrast.ContrastCheck]:
        """Return the WCAG checks for the active theme."""
        return contrast.check(self.theme)


def apply_to_app(app: QtWidgets.QApplication) -> ThemeManager:
    """Load fonts, then apply and return a manager for *app*."""
    fonts.load_fonts(app)
    return ThemeManager(app)
