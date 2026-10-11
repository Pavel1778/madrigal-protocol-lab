"""Guard against drift between ``presentation/slides.md`` and the PPTX builder.

``presentation/scripts/build_pptx.py`` mirrors the Markdown deck by hand, so the
two can silently diverge: a slide edited in the Markdown but not carried over
leaves the PPTX showing different words than the PDF. This module reads both
files and fails when a slide's text disagrees, in either direction.

Only the slide specs in ``deck()`` are compared. Text the builders add on their
own -- the footer, the section label, the cover wordmark -- is chrome; the
section labels are checked against the Vue component that renders them in
``test_footer_sections_match_global_component``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PRES = Path(__file__).resolve().parents[2] / "presentation"
SLIDES = PRES / "slides.md"
SCRIPT = PRES / "scripts" / "build_pptx.py"
FOOTER = PRES / "global-bottom.vue"

# Tokens that are markup, asset paths or footer chrome rather than slide copy.
_DROP = {"public", "assets", "src", "http", "https"}
_ASSET = re.compile(r".*\.(png|mp4|svg|jpg)$")
_CHROME = {
    "постановка", "задачи", "ход", "работы", "метод", "результаты",
    "демонстрация", "границы", "итог", "команда", "418", "кейс", "#02",
    "мадригал", "tcp", "madrigal-protocol-lab",
}


def _tokens(text: str) -> set[str]:
    """Words that carry meaning, with URLs, tags and asset paths removed."""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"github\.com\S*", " ", text)
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("`", " ").replace("**", " ").lower().replace("/", " ")
    words = (w.strip(".").strip("-") for w in re.split(r"[^0-9a-zа-яё+._-]+", text))
    return {w for w in words if len(w) > 2 and w not in _DROP and not _ASSET.match(w)}


def _markdown_slides() -> list[str]:
    """The slide bodies of ``slides.md``, in order (cover included)."""
    blocks = re.split(r"(?m)^---\s*$", SLIDES.read_text(encoding="utf-8"))[1:]
    return [b for b in blocks if re.search(r"(?m)^#\s+\S", b)]


def _deck_slides() -> list[set[str]]:
    """Token sets of the ``deck()`` specs, in source order."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    calls: list[ast.Call] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "dict"
    ]
    calls.sort(key=lambda call: call.lineno)

    slides: list[set[str]] = []
    for call in calls:
        if not any(kw.arg == "kind" for kw in call.keywords):
            continue
        tokens: set[str] = set()
        for kw in call.keywords:
            if kw.arg in ("notes", "kind"):
                continue
            for node in ast.walk(kw.value):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    tokens |= _tokens(node.value)
        slides.append(tokens)
    return slides


def test_deck_and_markdown_have_the_same_slide_count() -> None:
    assert len(_deck_slides()) == len(_markdown_slides())


def test_deck_adds_no_text_absent_from_markdown() -> None:
    pairs = zip(_deck_slides(), _markdown_slides())
    for page, (deck, body) in enumerate(pairs, start=1):
        extra = sorted(deck - _tokens(body) - _CHROME)
        assert not extra, f"slide {page}: deck() has text not in slides.md: {extra}"


def test_markdown_visible_text_is_present_in_deck() -> None:
    pairs = zip(_deck_slides(), _markdown_slides())
    for page, (deck, body) in enumerate(pairs, start=1):
        missing = sorted(_tokens(body) - deck - _CHROME)
        assert not missing, f"slide {page}: slides.md text missing from deck(): {missing}"


def test_slide_titles_match_markdown_headings() -> None:
    pairs = zip(_deck_slides(), _markdown_slides())
    for page, (deck, body) in enumerate(pairs, start=1):
        heading = re.search(r"(?m)^#\s+(.+)$", body)
        assert heading is not None, f"slide {page} has no H1"
        missing = sorted(_tokens(heading.group(1)) - deck)
        assert not missing, f"slide {page}: title missing from deck(): {missing}"


def test_footer_sections_match_global_component() -> None:
    """The section label in the PPTX footer tracks the Vue component."""
    vue = [
        (int(page), label)
        for page, label in re.findall(
            r"\[\s*(\d+)\s*,\s*'([^']+)'\s*\]", FOOTER.read_text(encoding="utf-8")
        )
    ]
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    pptx: list[tuple[int, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "SECTIONS" for t in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Tuple):
            continue
        for item in node.value.elts:
            if not isinstance(item, ast.Tuple) or len(item.elts) != 2:
                continue
            page, label = item.elts
            assert isinstance(page, ast.Constant) and isinstance(page.value, int)
            assert isinstance(label, ast.Constant) and isinstance(label.value, str)
            pptx.append((page.value, label.value))
    assert vue, "no sections parsed from global-bottom.vue"
    assert pptx, "no SECTIONS found in build_pptx.py"
    assert vue == pptx


def _asset_problems() -> list[str]:
    """Every ``src="..."`` in slides.md must resolve, with no ``/public/`` prefix.

    Slidev serves the public directory at the root, so ``/public/x.png`` renders
    in the PDF but 404s in the built deck. ``/assets/*`` is imported and bundled;
    every other path is served straight from ``public/``.
    """
    problems: list[str] = []
    for ref in re.findall(r'src="([^"]+)"', SLIDES.read_text(encoding="utf-8")):
        if ref.startswith(("http", "data:")):
            continue
        if ref.startswith("/public/"):
            problems.append(f"{ref}: drop the '/public' prefix -> '/{ref[len('/public/'):]}'")
            continue
        base = PRES / ref.lstrip("/") if ref.startswith("/assets/") else PRES / "public" / ref.lstrip("/")
        if not base.is_file():
            problems.append(f"{ref}: missing at {base.relative_to(PRES)}")
    return problems


def test_every_asset_reference_resolves() -> None:
    problems = _asset_problems()
    assert not problems, "; ".join(problems)


def test_team_slide_uses_two_distinct_member_photos() -> None:
    refs = re.findall(r'src="(/avatar_[a-z]+_round\.png)"', SLIDES.read_text(encoding="utf-8"))
    assert len(refs) == 2, f"expected two member photos, found {refs}"
    assert len(set(refs)) == 2, f"the two members share one photo: {refs}"
    for ref in refs:
        assert (PRES / "public" / ref.lstrip("/")).is_file(), f"{ref} is not in public/"

    pavel, nikita = ((PRES / "public" / r.lstrip("/")).read_bytes() for r in refs)
    assert pavel != nikita, "the member photos are byte-identical"
