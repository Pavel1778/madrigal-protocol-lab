"""Visual theme for the application window.

The palette, typography and geometry follow the client style sheet
(``docs/STYLE.md``): dark background, one bordeaux accent, Tektur for headings
and Montserrat for body text, 4 px corners, no soft shadows. Status colours are
used only for statuses.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtGui

BACKGROUND = "#131516"
PANEL = "#1D1D1D"
PANEL_ALT = "#171819"
LIGHT_CARD = "#E8E8E8"
ACCENT = "#6D071F"
ACCENT_GRADIENT = ("#410913", "#610D1C", "#A2391D")
TEXT = "#E0E0E0"
TEXT_SECONDARY = "#9F9F9F"
BORDER = "#2A2C2E"

# Status colours. Green and red are muted on purpose; they mark a verdict, not
# decoration. ``gap`` uses its own red so a missing range reads as missing.
MATCHED = "#2F5D45"
MATCHED_TEXT = "#7FBF9B"
MISMATCHED = "#6E2626"
MISMATCHED_TEXT = "#E08A8A"
INCOMPLETE = "#6B5320"
INCOMPLETE_TEXT = "#D8B65C"
AMBIGUOUS = "#6B5B14"
AMBIGUOUS_TEXT = "#E6D071"
GAP = "#4A1414"
UNCOVERED = "#3A3C3E"
NOT_APPLICABLE = "#202224"
OUTDATED = "#2A2C2E"
HYPOTHESIS = "#A2391D"

HEADING_FAMILY = "Tektur"
BODY_FAMILY = "Montserrat"

_FONT_FILES = (
    "Montserrat-Regular.ttf",
    "Montserrat-SemiBold.ttf",
    "Tektur-Medium.ttf",
    "Tektur-SemiBold.ttf",
)


def fonts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "fonts"


def body_font(size: int = 10, semibold: bool = False) -> QtGui.QFont:
    font = QtGui.QFont(BODY_FAMILY, size)
    font.setPixelSize(max(9, size + 3))
    font.setWeight(QtGui.QFont.Weight.DemiBold if semibold else QtGui.QFont.Weight.Normal)
    return font


def heading_font(size: int = 12, semibold: bool = True) -> QtGui.QFont:
    font = QtGui.QFont(HEADING_FAMILY, size)
    font.setPixelSize(max(11, size + 3))
    font.setWeight(QtGui.QFont.Weight.DemiBold if semibold else QtGui.QFont.Weight.Medium)
    return font


def mono_font(size: int = 10) -> QtGui.QFont:
    font = QtGui.QFont("DejaVu Sans Mono", size)
    font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
    font.setPixelSize(max(10, size + 3))
    font.setFixedPitch(True)
    return font


def load_fonts(app: QtGui.QGuiApplication | None = None) -> list[str]:
    """Register the bundled fonts and return the families that loaded.

    A missing file is skipped rather than fatal: the application still runs on
    the platform defaults, and ``application_font_families`` tells the caller
    what was actually installed.
    """
    families: list[str] = []
    for name in _FONT_FILES:
        path = fonts_dir() / name
        if not path.is_file():
            continue
        font_id = QtGui.QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families.extend(QtGui.QFontDatabase.applicationFontFamilies(font_id))
    return families


def build_stylesheet() -> str:
    return f"""
    QWidget {{
        background-color: {BACKGROUND};
        color: {TEXT};
        font-family: "{BODY_FAMILY}";
    }}
    QMainWindow, QDialog {{ background-color: {BACKGROUND}; }}
    QLabel {{ background: transparent; }}
    QLabel[role="heading"] {{
        font-family: "{HEADING_FAMILY}";
        color: {TEXT};
    }}
    QLabel[role="secondary"] {{ color: {TEXT_SECONDARY}; }}
    QGroupBox {{
        background-color: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 4px;
        margin-top: 14px;
        padding: 8px;
        font-family: "{HEADING_FAMILY}";
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {TEXT_SECONDARY};
    }}
    QTreeWidget, QTableWidget, QPlainTextEdit, QTextEdit, QListWidget {{
        background-color: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 4px;
        selection-background-color: {ACCENT};
        selection-color: {TEXT};
        outline: none;
    }}
    QTreeWidget::item:selected, QTableWidget::item:selected {{
        background-color: {ACCENT};
    }}
    QHeaderView::section {{
        background-color: {PANEL_ALT};
        color: {TEXT_SECONDARY};
        border: none;
        border-right: 1px solid {BORDER};
        padding: 4px 6px;
        font-family: "{HEADING_FAMILY}";
    }}
    QPushButton {{
        background-color: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 6px 12px;
        color: {TEXT};
    }}
    QPushButton:hover {{ border-color: {ACCENT}; }}
    QPushButton:pressed {{ background-color: {ACCENT}; }}
    QPushButton[accent="true"] {{
        background-color: {ACCENT};
        border-color: {ACCENT};
    }}
    QLineEdit, QComboBox, QSpinBox {{
        background-color: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 4px 6px;
    }}
    QMenuBar {{ background-color: {PANEL_ALT}; }}
    QMenuBar::item:selected {{ background-color: {ACCENT}; }}
    QMenu {{ background-color: {PANEL}; border: 1px solid {BORDER}; }}
    QMenu::item:selected {{ background-color: {ACCENT}; }}
    QStatusBar {{ background-color: {PANEL_ALT}; color: {TEXT_SECONDARY}; }}
    QScrollBar:vertical {{
        background: {PANEL_ALT}; width: 12px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER}; border-radius: 4px; min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QProgressBar {{
        background-color: {PANEL_ALT};
        border: 1px solid {BORDER};
        border-radius: 4px;
        text-align: center;
        color: {TEXT_SECONDARY};
    }}
    QProgressBar::chunk {{ background-color: {ACCENT}; }}
    QSplitter::handle {{ background-color: {BORDER}; }}
    """


def is_offscreen() -> bool:
    return bool(sys.platform) and "offscreen" in (
        QtGui.QGuiApplication.platformName() if QtGui.QGuiApplication.instance() else ""
    )
