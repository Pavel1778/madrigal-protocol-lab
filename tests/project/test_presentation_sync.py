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
import zipfile
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


def test_team_slide_uses_the_requested_sizes() -> None:
    """The organizers asked for a 180 px avatar, a 28 px name and an 80 px QR."""
    css = (PRES / "style.css").read_text(encoding="utf-8")

    def rule(selector: str) -> str:
        block = re.search(rf"{re.escape(selector)}\s*\{{(.*?)\}}", css, re.S)
        assert block, f"{selector} is missing from style.css"
        return block.group(1)

    assert re.search(r"width:\s*180px", rule(".member__photo"))
    assert re.search(r"height:\s*180px", rule(".member__photo"))
    assert re.search(r"font-size:\s*28px", rule(".member__name"))
    assert re.search(r"width:\s*80px", rule(".member__qr"))
    assert re.search(r"height:\s*80px", rule(".member__qr"))

    # The PPTX mirrors the CSS: a 1.8 in avatar and a 0.83 in QR, at 100 px/in.
    deck = (PRES / "scripts" / "build_pptx.py").read_text(encoding="utf-8")
    assert "Inches(1.8), Inches(1.8)" in deck
    assert "Inches(0.83), Inches(0.83)" in deck


def test_chart_assets_carry_no_build_timestamp() -> None:
    """A rebuild must be a no-op: no wall-clock stamp in the sixteen charts.

    ``build_visualizations`` writes the SVGs with ``metadata={"Date": None}`` and
    renumbers the hashed ids, so a chart that did not change is byte-identical.
    A stray date would rewrite every file and churn the bundle and the PDFs.
    """
    charts = sorted((PRES / "assets").glob("*.svg"))
    assert len(charts) == 16, f"expected sixteen charts, found {len(charts)}"
    stamped = [p.name for p in charts if b"<dc:date>" in p.read_bytes()]
    assert not stamped, f"charts carry a build date: {stamped}"


def test_pptx_parts_have_fixed_timestamps() -> None:
    """The PPTX packages must not churn in git on every rebuild.

    python-pptx stamps every part with the wall clock; ``freeze_zip`` pins them
    to 1980-01-01 so two builds of the same deck are byte-identical.
    """
    for name in ("slides.pptx", "team-slide.pptx"):
        pptx = PRES / name
        assert pptx.is_file(), f"presentation/{name} is not built"
        stamps = {item.date_time for item in zipfile.ZipFile(pptx).infolist()}
        assert stamps == {(1980, 1, 1, 0, 0, 0)}, f"{name} parts carry build times: {stamps}"


def test_pptx_embeds_the_brand_fonts() -> None:
    """The deck names Tektur/Montserrat/JetBrains Mono; without an embedded
    copy a viewer substitutes Calibri and the title stops looking like the deck.
    Every face the runs reference must ship as a de-obfuscatable ``.fntdata``."""
    import io

    from fontTools.ttLib import TTFont

    pptx = PRES / "slides.pptx"
    with zipfile.ZipFile(pptx) as z:
        pres = z.read("ppt/presentation.xml").decode("utf-8")
        types = z.read("[Content_Types].xml").decode("utf-8")
        assert 'Extension="fntdata"' in types
        assert "<p:embeddedFontLst>" in pres and 'embedTrueTypeFonts="1"' in pres
        rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8")

        families = dict(
            re.findall(r'<p:font typeface="([^"]+)"/>(.*?)</p:embeddedFont>', pres, re.S)
        )
        assert set(families) == {"Tektur", "Montserrat", "JetBrains Mono"}
        for family, body in families.items():
            for variant in ("regular", "bold"):
                m = re.search(
                    rf'<p:{variant} r:id="(rId\d+)" fontKey="\{{([^}}]+)\}}"/>', body
                )
                if not m:
                    continue
                rid, guid = m.groups()
                target = re.search(
                    rf'Id="{rid}"[^>]*Target="([^"]+)"', rels
                ).group(1)
                data = z.read("ppt/" + target)
                key = bytes(reversed(bytes.fromhex(guid.replace("-", ""))))
                head = bytearray(data[:32])
                for i in range(len(head)):
                    head[i] ^= key[i % 16]
                raw = bytes(head) + data[32:]
                assert raw[:4] == b"\x00\x01\x00\x00", f"{family} {variant} not a TTF"
                face = TTFont(io.BytesIO(raw), lazy=True)
                names = {r.nameID: r.toUnicode() for r in face["name"].names}
                assert names.get(1) == family, f"{family} {variant}: {names.get(1)!r}"
                assert face.getBestCmap(), f"{family} {variant} lost its cmap"

