"""Embed the brand fonts into the built PPTX so the deck renders anywhere.

PowerPoint only substitutes a font when the file carries it. The deck asks for
``Tektur``, ``Montserrat`` and ``JetBrains Mono``, and the TTFs we ship declare
themselves as ``Tektur SemiBold`` and friends, so a viewer without those fonts
installed falls back to Calibri -- the title stops looking like the deck.

This module makes the PPTX self-contained: for each face it subsets the TTF to
the glyphs the deck actually uses (Cyrillic included), renames the subset to the
plain family name the runs reference, obfuscates the first 32 bytes the way
OOXML requires, and registers the result as an ``.fntdata`` part with an
``<p:embeddedFontLst>`` entry. Everything is derived from the font bytes, so the
output stays byte-reproducible.

    from presentation.fonts import embed_brand_fonts
    embed_brand_fonts(OUT, deck_text())
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path

from fontTools import subset

PRES = Path(__file__).resolve().parents[0]
FONT_DIR = PRES / "public" / "fonts"

# (typeface used by the runs, regular TTF, bold TTF or None)
FACES = (
    ("Tektur", "Tektur-Medium.ttf", "Tektur-SemiBold.ttf"),
    ("Montserrat", "Montserrat-Regular.ttf", "Montserrat-SemiBold.ttf"),
    ("JetBrains Mono", "JetBrainsMono-Regular.ttf", None),
)

# Extra glyphs the deck may show but does not put in a text run verbatim.
EXTRA_CHARS = "→·—«»№°×≥≤…•"

_FONT_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
)


def collect_text(prs) -> str:
    """Every character the deck renders, so the subsets keep the right glyphs."""
    out: list[str] = [EXTRA_CHARS]
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                out.append(shape.text_frame.text)
    return "".join(out)


def _subset(src: Path, text: str, family: str, bold: bool) -> bytes:
    """Subset ``src`` to ``text`` and rename it to ``family``/Regular|Bold."""
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.notdef_outline = True
    options.recalc_bounds = True
    options.drop_tables += ["DSIG"]
    font = subset.load_font(str(src), options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=text)
    subsetter.subset(font)

    sub = "Bold" if bold else "Regular"
    full = f"{family} {sub}" if bold else family
    ps = f"{family.replace(' ', '')}-{sub}"
    for record in font["name"].names:
        if record.nameID == 1:
            record.string = family
        elif record.nameID == 2:
            record.string = sub
        elif record.nameID == 4:
            record.string = full
        elif record.nameID == 6:
            record.string = ps
        elif record.nameID == 16:
            record.string = family
        elif record.nameID == 17:
            record.string = sub
    # Mark the bold face so a viewer that keys off OS/2 picks the right one.
    os2, head = font["OS/2"], font["head"]
    if bold:
        os2.fsSelection = (os2.fsSelection | 0x20) & ~0x40
        head.macStyle = head.macStyle | 0x01
    else:
        os2.fsSelection = (os2.fsSelection | 0x40) & ~0x20
        head.macStyle = head.macStyle & ~0x01
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()


def _guid(seed: str) -> str:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest().upper()
    return f"{digest[0:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def _obfuscate(font_bytes: bytes, guid: str) -> bytes:
    """XOR the first 32 bytes with the reversed GUID, per the OOXML spec."""
    key = bytes(reversed(bytes.fromhex(guid.replace("-", ""))))
    head = bytearray(font_bytes[:32])
    for i in range(len(head)):
        head[i] ^= key[i % 16]
    return bytes(head) + font_bytes[32:]


def _next_rid(rels_xml: str) -> int:
    used = [int(m) for m in re.findall(r'Id="rId(\d+)"', rels_xml)]
    return (max(used) + 1) if used else 1


def embed_brand_fonts(path: Path, text: str) -> list[str]:
    """Embed every face of ``FACES`` into ``path``; return the part names."""
    with zipfile.ZipFile(path) as src:
        parts = {name: src.read(name) for name in src.namelist()}

    pres = parts["ppt/presentation.xml"].decode("utf-8")
    rels = parts["ppt/_rels/presentation.xml.rels"].decode("utf-8")
    types = parts["[Content_Types].xml"].decode("utf-8")

    embedded: list[str] = []
    entries: list[str] = []
    rid = _next_rid(rels)

    for family, regular, bold in FACES:
        entry = [f'<p:embeddedFont><p:font typeface="{family}"/>']
        for variant, filename in (("regular", regular), ("bold", bold)):
            if not filename:
                continue
            part = f"ppt/fonts/font{len(embedded) + 1}.fntdata"
            guid = _guid(f"{family}-{variant}")
            data = _subset(FONT_DIR / filename, text, family, variant == "bold")
            parts[part] = _obfuscate(data, guid)
            embedded.append(part)
            rels = rels.replace(
                "</Relationships>",
                f'<Relationship Id="rId{rid}" Type="{_FONT_REL}" '
                f'Target="fonts/{Path(part).name}"/></Relationships>',
            )
            entry.append(
                f'<p:{variant} r:id="rId{rid}" fontKey="{{{guid}}}"/>'
            )
            rid += 1
        entry.append("</p:embeddedFont>")
        entries.append("".join(entry))

    if 'Extension="fntdata"' not in types:
        types = types.replace(
            "<Default",
            '<Default Extension="fntdata" ContentType="application/x-fontdata"/><Default',
            1,
        )
    if "<p:embeddedFontLst>" not in pres:
        pres = pres.replace("<p:embeddedFontLst/>", "")
        pres = pres.replace(
            "</p:presentation>",
            f'<p:embeddedFontLst>{"".join(entries)}</p:embeddedFontLst></p:presentation>',
        )
    if "embedTrueTypeFonts=" not in pres:
        pres = re.sub(
            r"(<p:presentation\b[^>]*?)(\s*>)",
            r'\1 embedTrueTypeFonts="1"\2',
            pres,
            count=1,
        )

    # The default theme still names Calibri; point it at the bundled family so
    # any run without an explicit font does not fall back to a system face.
    theme_name = next(
        (n for n in parts if re.fullmatch(r"ppt/theme/theme\d+\.xml", n)), None
    )
    if theme_name:
        theme = parts[theme_name].decode("utf-8")
        theme = theme.replace('typeface="Calibri Light"', 'typeface="Montserrat"')
        theme = theme.replace('typeface="Calibri"', 'typeface="Montserrat"')
        parts[theme_name] = theme.encode("utf-8")

    parts["ppt/presentation.xml"] = pres.encode("utf-8")
    parts["ppt/_rels/presentation.xml.rels"] = rels.encode("utf-8")
    parts["[Content_Types].xml"] = types.encode("utf-8")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for name, blob in parts.items():
            dst.writestr(name, blob)
    return embedded
