"""Guards that the interface catalogues stay complete and in step.

``scripts/update_translations.sh`` extracts the translatable strings with
``lupdate`` and compiles them, but nothing fails when a developer adds a
``tr()`` call and forgets to run the script: the window then shows the English
source string in Russian, silently. These tests read the same sources and both
catalogues directly and fail on the drift.

They parse the sources with :mod:`ast` rather than with a regular expression, so
a string assembled from adjacent literals (which the compiler joins into one
constant) is compared as the single string ``lupdate`` would extract. No Qt
runtime is required: the ``.ts`` files are XML and the sources are text.
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCALE_DIR = REPO_ROOT / "src" / "ui" / "locale"

# The files ``scripts/update_translations.sh`` feeds to ``lupdate``. Kept here so
# the guard scans exactly what the script scans; a file that is added to the
# script but not here is caught by the module-level check below.
SOURCE_FILES = (
    "src/ui/main_window.py",
    "src/ui/session_tree.py",
    "src/ui/hex_view.py",
    "src/ui/compare_view.py",
    "src/ui/hypotheses_view.py",
    "src/ui/validation_view.py",
    "src/ui/corpus_dialog.py",
    "src/ui/welcome_view.py",
    "src/ui/settings.py",
    "src/ui/legend.py",
    "src/ui/rule_builder.py",
    "src/ui/timeline_view.py",
    "src/ui/tutor.py",
    "src/ui/help_dialog.py",
    "src/ui/learning.py",
    "src/ui/help.py",
)

# ``QCoreApplication.translate(context, source)`` carries its context as the
# first argument; ``tr(source)`` and ``QT_TRANSLATE_NOOP(context, source)`` carry
# the source in the position noted here.
_CONTEXT_FUNCS = {"QT_TRANSLATE_NOOP"}
_SOURCE_POSITION = {
    "tr": 0,
    "translate": 1,
    "QT_TRANSLATE_NOOP": 1,
}

PLACEHOLDER = re.compile(r"\{[0-9]+\}|%[0-9]+|%[A-Za-z]")


def _load_catalogue(path: Path) -> dict[tuple[str, str], str]:
    """Return ``{(context, source): translation}`` for a ``.ts`` file."""
    root = ET.parse(path).getroot()
    messages: dict[tuple[str, str], str] = {}
    for context in root.findall("context"):
        name = context.findtext("name") or ""
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            text = (translation.text or "") if translation is not None else ""
            messages[(name, source)] = text
    return messages


def _string_value(node: ast.AST) -> str | None:
    """The literal string a node evaluates to, if it is one.

    ``ast`` has already joined adjacent string literals into a single constant,
    so a caption split over several lines is seen as the one string the window
    shows and ``lupdate`` extracts.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_from_source(path: Path) -> set[str]:
    """Every translatable source string in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            continue
        position = _SOURCE_POSITION.get(name)
        if position is None:
            continue
        if name == "translate" and isinstance(func, ast.Attribute):
            # ``QCoreApplication.translate`` and the ``learning.translate`` /
            # ``help.translate`` wrappers share the name. The wrappers take the
            # source first, the Qt call takes the context first.
            owner = func.value
            owner_name = getattr(owner, "id", None) or getattr(owner, "attr", None)
            if owner_name != "QCoreApplication":
                position = 0
        if len(node.args) <= position:
            continue
        value = _string_value(node.args[position])
        if value is not None and value.strip():
            found.add(value)
    return found


CATALOGUES = {
    "ru": LOCALE_DIR / "madrigal_ru.ts",
    "en": LOCALE_DIR / "madrigal_en.ts",
}


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_catalogue_file_exists(language: str) -> None:
    assert CATALOGUES[language].is_file(), CATALOGUES[language]


def test_catalogues_cover_the_same_messages() -> None:
    """Russian and English hold the same (context, source) pairs."""
    ru = _load_catalogue(CATALOGUES["ru"])
    en = _load_catalogue(CATALOGUES["en"])
    only_ru = set(ru) - set(en)
    only_en = set(en) - set(ru)
    assert not only_ru, f"only in Russian: {sorted(only_ru)[:5]}"
    assert not only_en, f"only in English: {sorted(only_en)[:5]}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_no_message_is_unfinished_or_empty(language: str) -> None:
    root = ET.parse(CATALOGUES[language]).getroot()
    problems = []
    for context in root.findall("context"):
        name = context.findtext("name") or ""
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            kind = translation.get("type") if translation is not None else None
            text = (translation.text or "") if translation is not None else ""
            if kind == "unfinished" or not text.strip():
                problems.append((name, source))
    assert not problems, f"{language}: unfinished or empty: {problems[:5]}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_source_string_is_in_the_catalogue(language: str) -> None:
    """Every ``tr()``/``translate()`` source is present in the catalogue.

    This is the guard that fails when a caption is added without running
    ``scripts/update_translations.sh``.
    """
    catalogue_sources = {source for _, source in _load_catalogue(CATALOGUES[language])}
    missing: dict[str, list[str]] = {}
    for relative in SOURCE_FILES:
        path = REPO_ROOT / relative
        for source in _extract_from_source(path):
            if source not in catalogue_sources:
                missing.setdefault(relative, []).append(source)
    assert not missing, f"{language}: untranslated sources: {missing}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_placeholders_match_between_source_and_translation(language: str) -> None:
    """A translation keeps the same ``{0}``/``%1`` placeholders as its source."""
    root = ET.parse(CATALOGUES[language]).getroot()
    mismatched = []
    for context in root.findall("context"):
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            text = (translation.text or "") if translation is not None else ""
            if not text.strip():
                continue
            if sorted(PLACEHOLDER.findall(source)) != sorted(PLACEHOLDER.findall(text)):
                mismatched.append((source, text))
    assert not mismatched, f"{language}: placeholder mismatch: {mismatched[:5]}"


def test_source_list_matches_the_update_script() -> None:
    """The files scanned here are exactly the files the update script scans.

    A new source file added to the script (or removed from it) must be reflected
    above, otherwise this guard would silently stop covering it.
    """
    script = (REPO_ROOT / "scripts" / "update_translations.sh").read_text(encoding="utf-8")
    block = script.split("SOURCES=(", 1)[1].split(")", 1)[0]
    scripted = {line.strip() for line in block.splitlines() if line.strip().endswith(".py")}
    assert scripted == set(SOURCE_FILES)
