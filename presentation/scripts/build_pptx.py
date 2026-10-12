"""Build the defence deck as a real, editable PPTX from our own code.

Mirrors ``slides.md`` (19 slides, 16:9). Every slide is drawn with python-pptx
directly — no PowerPoint template — with native editable text, the deck palette
and brand fonts, click-triggered fade/wipe entrances and native slide
transitions. The build fails loudly if the number of slides it emits is not the
number the deck promises.

    python -m presentation.scripts.build_pptx

Layout is fixed in inches; the deck grid is 13.333 x 7.5 in (16:9).
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from presentation.fonts import collect_text, embed_brand_fonts
from presentation.reproducible import freeze_zip

ROOT = Path(__file__).resolve().parents[2]
PRES = ROOT / "presentation"
OUT = PRES / "slides.pptx"

# --- palette (mirrors presentation/style.css, brand book) --------------------
BG = RGBColor(0x0E, 0x10, 0x11)
SURFACE = RGBColor(0x1F, 0x21, 0x24)
SURFACE_HI = RGBColor(0x26, 0x28, 0x2B)
TEXT = RGBColor(0xF4, 0xF1, 0xEC)
SECONDARY = RGBColor(0xA8, 0xA2, 0x9E)
ACCENT = RGBColor(0xD0, 0x60, 0x3A)
ACCENT_HOVER = RGBColor(0xE8, 0x7A, 0x52)
ACCENT_DEEP = RGBColor(0x61, 0x0D, 0x1C)
MATCHED = RGBColor(0x16, 0xA3, 0x4A)
MISMATCHED = RGBColor(0xDC, 0x26, 0x26)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

F_HEAD = "Tektur"
F_BODY = "Montserrat"
F_MONO = "JetBrains Mono"

MARGIN = Inches(0.9)
FOOTER_H = Inches(0.45)
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
BODY_TOP = Inches(1.85)
GITHUB = "https://github.com/Pavel1778/madrigal-protocol-lab"
RELEASE = "https://github.com/Pavel1778/madrigal-protocol-lab/releases/tag/v1.0.0"
TOTAL = 19

_TOKEN = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


# --- primitives --------------------------------------------------------------
def add_runs(paragraph, text, size, color, bold=False, font=F_BODY):
    """Write text into a paragraph, honouring **bold** and `code` spans."""
    for part in _TOKEN.split(text):
        if not part:
            continue
        run = paragraph.add_run()
        run.font.size = Pt(size)
        run.font.name = font
        if part.startswith("**") and part.endswith("**"):
            run.text = part[2:-2]
            run.font.bold = True
            run.font.color.rgb = WHITE
        elif part.startswith("`") and part.endswith("`"):
            run.text = part[1:-1]
            run.font.name = F_MONO
            run.font.size = Pt(size - 2)
            run.font.color.rgb = ACCENT
        else:
            run.text = part
            run.font.bold = bold
            run.font.color.rgb = color
    return paragraph


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    return tb, tf


def solid(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False


def rect(slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE, line=None):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    solid(s, color)
    if line is not None:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    return s


def gradient_bar(slide, x, y, w, h):
    """A left-to-right brand gradient rectangle, used for the accent rule."""
    shape = rect(slide, x, y, w, h, ACCENT_DEEP)
    fill = shape.fill._xPr.find(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill"
    )
    gs = etree.SubElement(
        shape.fill._xPr,
        "{http://schemas.openxmlformats.org/drawingml/2006/main}gradFill",
    )
    gs.set("rotWithShape", "1")
    gsl = etree.SubElement(
        gs, "{http://schemas.openxmlformats.org/drawingml/2006/main}gsLst"
    )
    for pos, color in ((0, "410913"), (50000, "610D1C"), (100000, "A2391D")):
        gsx = etree.SubElement(
            gsl, "{http://schemas.openxmlformats.org/drawingml/2006/main}gs"
        )
        gsx.set("pos", str(pos))
        etree.SubElement(
            gsx, "{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr"
        ).set("val", color)
    lin = etree.SubElement(
        gs, "{http://schemas.openxmlformats.org/drawingml/2006/main}lin"
    )
    lin.set("ang", "2700000")
    if fill is not None:
        shape.fill._xPr.remove(fill)
    return shape


def bg(slide):
    rect(slide, 0, 0, SLIDE_W, SLIDE_H, BG)
    gradient_bar(slide, 0, 0, Inches(0.08), SLIDE_H)


SECTIONS = ((1, "Постановка и метод"), (10, "Результаты"),
            (14, "Демонстрация"), (17, "Границы и итог"))


def footer(slide, page):
    _tb, tf = textbox(slide, MARGIN, SLIDE_H - FOOTER_H, Inches(4.2),
                     Inches(0.3))
    add_runs(tf.paragraphs[0], "Команда HTTP 418 · кейс #02 · Мадригал", 10,
             SECONDARY)
    section = SECTIONS[0][1]
    for start, label in SECTIONS:
        if page >= start:
            section = label
    _tb1, tf1 = textbox(slide, Inches(4.8), SLIDE_H - FOOTER_H, Inches(3.7),
                       Inches(0.3))
    p1 = tf1.paragraphs[0]
    p1.alignment = PP_ALIGN.CENTER
    add_runs(p1, section, 10, SECONDARY)
    _tb2, tf2 = textbox(slide, Inches(8.9), SLIDE_H - FOOTER_H, Inches(3.5),
                       Inches(0.3))
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.RIGHT
    add_runs(p2, f"{page} / {TOTAL}", 10, SECONDARY)


def heading(slide, text, size=40, height=None):
    if height is None:
        height = Inches(1.15)
    tb, tf = textbox(slide, MARGIN, Inches(0.5), SLIDE_W - 2 * MARGIN,
                     height)
    add_runs(tf.paragraphs[0], text, size, TEXT, bold=True, font=F_HEAD)
    return tb


def caption(slide, text, y=None):
    if y is None:
        y = Inches(6.6)
    tb, tf = textbox(slide, MARGIN, y, SLIDE_W - 2 * MARGIN, Inches(0.4))
    add_runs(tf.paragraphs[0], text, 14, SECONDARY)
    return tb


def bullets(slide, items, x, y, w, h, size=17, gap=None):
    if gap is None:
        gap = Pt(10)
    tb, tf = textbox(slide, x, y, w, h)
    first = True
    for it in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = gap
        add_runs(p, "•  " + it, size, TEXT)
    return tb


def bullets_each(slide, items, x, y, w, line_h=None, size=17):
    """One textbox per bullet, so each can build in on its own click."""
    if line_h is None:
        line_h = Inches(0.8)
    ids = []
    for i, it in enumerate(items):
        tb, tf = textbox(slide, x, y + i * line_h, w, line_h)
        add_runs(tf.paragraphs[0], "•  " + it, size, TEXT)
        ids.append(tb.shape_id)
    return ids


def fit_picture(slide, rel, x, y, max_w, max_h):
    """Place a picture scaled to fit inside max_w x max_h, keeping aspect."""
    from PIL import Image

    path = PRES / rel.lstrip("/")
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    return slide.shapes.add_picture(str(path), x, y,
                                    width=int(iw * scale), height=int(ih * scale))


def picture(slide, rel, x, y, w, h=None):
    path = PRES / rel.lstrip("/")
    pic = slide.shapes.add_picture(str(path), x, y, width=w)
    if h is not None:
        pic.height = h
    return pic


def panel(slide, x, y, w, h, accent=False):
    box = rect(slide, x, y, w, h, SURFACE, line=None)
    if accent:
        rect(slide, x, y, Inches(0.05), h, ACCENT)
    return box


def lead(slide, x, y, w, text):
    tb, tf = textbox(slide, x, y, w, Inches(0.35))
    add_runs(tf.paragraphs[0], text.upper(), 14, ACCENT, bold=True)
    return tb


# --- animations / transitions ------------------------------------------------
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def _fade(spid: int, cid: int) -> str:
    return f"""
<p:par><p:cTn id="{cid}" presetID="10" presetClass="entr" presetSubtype="0"
 fill="hold" grpId="0" nodeType="clickEffect">
 <p:stCondLst><p:cond delay="0"/></p:stCondLst>
 <p:childTnLst>
  <p:set>
   <p:cBhvr><p:cTn id="{cid+1}" dur="1" fill="hold">
    <p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
    <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
    <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
   </p:cBhvr>
   <p:to><p:strVal val="visible"/></p:to>
  </p:set>
  <p:anim calcmode="lin" valueType="num">
   <p:cBhvr additive="base">
    <p:cTn id="{cid+2}" dur="300" fill="hold"/>
    <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
    <p:attrNameLst><p:attrName>style.opacity</p:attrName></p:attrNameLst>
   </p:cBhvr>
   <p:tavLst>
    <p:tav tm="0"><p:val><p:fltVal val="0"/></p:val></p:tav>
    <p:tav tm="100000"><p:val><p:fltVal val="1"/></p:val></p:tav>
   </p:tavLst>
  </p:anim>
 </p:childTnLst>
</p:cTn></p:par>"""


def _wipe(spid: int, cid: int) -> str:
    """A left-to-right wipe, used to build a chart in on click."""
    return f"""
<p:par><p:cTn id="{cid}" presetID="22" presetClass="entr" presetSubtype="8"
 fill="hold" grpId="0" nodeType="clickEffect">
 <p:stCondLst><p:cond delay="0"/></p:stCondLst>
 <p:childTnLst>
  <p:set>
   <p:cBhvr><p:cTn id="{cid+1}" dur="1" fill="hold">
    <p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
    <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
    <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
   </p:cBhvr>
   <p:to><p:strVal val="visible"/></p:to>
  </p:set>
  <p:anim calcmode="lin" valueType="num">
   <p:cBhvr additive="base">
    <p:cTn id="{cid+2}" dur="400" fill="hold"/>
    <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
    <p:attrNameLst><p:attrName>ppt_w</p:attrName></p:attrNameLst>
   </p:cBhvr>
   <p:tavLst>
    <p:tav tm="0"><p:val><p:fltVal val="0"/></p:val></p:tav>
    <p:tav tm="100000"><p:val><p:fltVal val="1"/></p:val></p:tav>
   </p:tavLst>
  </p:anim>
 </p:childTnLst>
</p:cTn></p:par>"""


def add_entrance(slide, steps: list[tuple[int, str]]) -> None:
    """Append click-triggered entrances. steps = [(shape_id, 'fade'|'wipe')]."""
    if not steps:
        return
    cid = 3
    pars = []
    for spid, kind in steps:
        pars.append(_wipe(spid, cid) if kind == "wipe" else _fade(spid, cid))
        cid += 3
    xml = f"""<p:timing xmlns:p="{NS['p']}" xmlns:a="{NS['a']}">
 <p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
  <p:childTnLst><p:seq concurrent="1" nextAc="seek">
   <p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>
    {''.join(pars)}
   </p:childTnLst></p:cTn>
  </p:seq></p:childTnLst>
 </p:cTn></p:par></p:tnLst>
</p:timing>"""
    slide._element.append(etree.fromstring(xml))


def add_transition(slide, kind="fade") -> None:
    xml = f"""<p:transition xmlns:p="{NS['p']}" spd="med" {kind}="1"/>"""
    slide._element.append(etree.fromstring(xml))


# --- slide builders ----------------------------------------------------------
def build_slide(prs, spec):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg(slide)
    kind = spec["kind"]
    steps: list[tuple[int, str]] = []

    if kind == "cover":
        logo = picture(slide, "public/logo.png", MARGIN, Inches(1.15),
                       Inches(0.9), Inches(0.9))
        tb, tf = textbox(slide, MARGIN + Inches(1.1), Inches(1.32),
                         Inches(8.0), Inches(0.5))
        add_runs(tf.paragraphs[0], "MADRIGAL-PROTOCOL-LAB", 14, SECONDARY,
                 font=F_MONO)
        tb, tf = textbox(slide, MARGIN, Inches(2.35), SLIDE_W - 2 * MARGIN,
                         Inches(1.5))
        add_runs(tf.paragraphs[0], spec["title"], 56, TEXT, bold=True,
                 font=F_HEAD)
        tb, tf = textbox(slide, MARGIN, Inches(3.7), Inches(9.5), Inches(1.0))
        add_runs(tf.paragraphs[0], spec["sub"], 22, TEXT)
        rect(slide, MARGIN, Inches(4.75), Inches(2.4), Inches(0.07), ACCENT)
        tb, tf = textbox(slide, MARGIN, Inches(5.05), SLIDE_W - 2 * MARGIN,
                         Inches(0.5))
        add_runs(tf.paragraphs[0], spec["meta"], 15, SECONDARY, font=F_MONO)
        _ = logo

    elif kind == "team":
        heading(slide, spec["title"])
        col_w = (SLIDE_W - 2 * MARGIN - Inches(0.5)) / 2
        for i, (name, role, handle, qr, avatar) in enumerate(spec["members"]):
            x = MARGIN + i * (col_w + Inches(0.5))
            # 2.7in clears the 180px avatar (bottom at 2.25) with a margin.
            panel(slide, x, BODY_TOP, col_w, Inches(2.7))
            av = picture(slide, f"public/{avatar}", x + Inches(0.3),
                         BODY_TOP + Inches(0.4), Inches(1.8), Inches(1.8))
            steps.append((av.shape_id, "fade"))
            tx = x + Inches(2.35)
            _, tf = textbox(slide, tx, BODY_TOP + Inches(0.5),
                            col_w - Inches(3.6), Inches(0.6))
            add_runs(tf.paragraphs[0], name, 21, TEXT, bold=True, font=F_HEAD)
            _, tf = textbox(slide, tx, BODY_TOP + Inches(1.1),
                            col_w - Inches(3.6), Inches(0.5))
            add_runs(tf.paragraphs[0], role, 14, SECONDARY)
            _, tf = textbox(slide, tx, BODY_TOP + Inches(1.6),
                            col_w - Inches(3.6), Inches(0.4))
            add_runs(tf.paragraphs[0], handle, 14, ACCENT, font=F_MONO)
            # 80px QR, aligned with the top of the avatar.
            picture(slide, f"public/{qr}", x + col_w - Inches(1.15),
                    BODY_TOP + Inches(0.5), Inches(0.83), Inches(0.83))

    elif kind == "arch":
        heading(slide, spec["title"])
        box_w = Inches(3.5)
        arrow_w = Inches(0.7)
        total = 3 * box_w + 2 * arrow_w
        x = MARGIN + (SLIDE_W - 2 * MARGIN - total) / 2
        y = BODY_TOP + Inches(0.3)
        for i, (name, desc) in enumerate(spec["modules"]):
            panel(slide, x, y, box_w, Inches(2.2), accent=True)
            steps.append((slide.shapes[-1].shape_id, "fade"))
            _, tf = textbox(slide, x + Inches(0.25), y + Inches(0.35),
                            box_w - Inches(0.5), Inches(0.6))
            add_runs(tf.paragraphs[0], name, 20, TEXT, bold=True, font=F_HEAD)
            _, tf = textbox(slide, x + Inches(0.25), y + Inches(1.05),
                            box_w - Inches(0.5), Inches(0.9))
            for j, line in enumerate(desc.split("\n")):
                add_runs(tf.paragraphs[0] if j == 0 else tf.add_paragraph(),
                         line, 14, SECONDARY)
            x += box_w
            if i < len(spec["modules"]) - 1:
                tb, tf = textbox(slide, x, y + Inches(0.85), arrow_w,
                                 Inches(0.6), anchor=MSO_ANCHOR.MIDDLE)
                tf.paragraphs[0].alignment = PP_ALIGN.CENTER
                add_runs(tf.paragraphs[0], "JSON →", 14, ACCENT, font=F_MONO)
                x += arrow_w
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "statement":
        tb, tf = textbox(slide, MARGIN, Inches(0.85), SLIDE_W - 2 * MARGIN,
                         Inches(0.4))
        add_runs(tf.paragraphs[0], "ПОСТАНОВКА ЗАДАЧИ", 14, ACCENT, bold=True)
        tb, tf = textbox(slide, MARGIN, Inches(1.35), SLIDE_W - 2 * MARGIN,
                         Inches(1.3))
        add_runs(tf.paragraphs[0], spec["title"], 44, TEXT, bold=True,
                 font=F_HEAD)
        steps.append((tb.shape_id, "fade"))
        tb, tf = textbox(slide, MARGIN, Inches(2.65), Inches(10.5), Inches(0.7))
        add_runs(tf.paragraphs[0], spec["sub"], 20, SECONDARY)
        pic = fit_picture(slide, spec["image"], MARGIN, Inches(3.5),
                          SLIDE_W - 2 * MARGIN, Inches(2.6))
        steps.append((pic.shape_id, "fade"))

    elif kind == "given":
        heading(slide, spec["title"])
        col_w = (SLIDE_W - 2 * MARGIN - Inches(0.5)) / 2
        for i, (title, items) in enumerate(spec["columns"]):
            x = MARGIN + i * (col_w + Inches(0.5))
            panel(slide, x, BODY_TOP, col_w, Inches(3.6), accent=True)
            steps.append((slide.shapes[-1].shape_id, "fade"))
            lead(slide, x + Inches(0.35), BODY_TOP + Inches(0.3),
                 col_w - Inches(0.7), title)
            bullets_each(slide, items, x + Inches(0.35),
                         BODY_TOP + Inches(0.85), col_w - Inches(0.7),
                         line_h=Inches(0.9), size=17)

    elif kind == "moment":
        tb, tf = textbox(slide, MARGIN, Inches(0.85), SLIDE_W - 2 * MARGIN,
                         Inches(0.4))
        add_runs(tf.paragraphs[0], "ХОД РАБОТЫ", 14, ACCENT, bold=True)
        tb, tf = textbox(slide, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN,
                         Inches(1.1))
        add_runs(tf.paragraphs[0], spec["title"], 34, TEXT, bold=True,
                 font=F_HEAD)
        steps.append((tb.shape_id, "fade"))
        tb, tf = textbox(slide, MARGIN, Inches(2.35), Inches(10.5), Inches(0.5))
        add_runs(tf.paragraphs[0], spec["sub"], 17, SECONDARY)
        pic = fit_picture(slide, spec["image"], MARGIN, Inches(3.0),
                          SLIDE_W - 2 * MARGIN, Inches(2.2))
        steps.append((pic.shape_id, "fade"))
        chips = spec.get("chips", [])
        gap = Inches(0.15)
        cw = (SLIDE_W - 2 * MARGIN - gap * (len(chips) - 1)) / max(len(chips), 1)
        for i, chip in enumerate(chips):
            x = MARGIN + i * (cw + gap)
            box = rect(slide, x, Inches(5.5), cw, Inches(0.42), ACCENT,
                       shape=MSO_SHAPE.ROUNDED_RECTANGLE)
            _, tf = textbox(slide, x, Inches(5.55), cw, Inches(0.35))
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            add_runs(p, chip, 14, WHITE, font=F_MONO)
            _ = box

    elif kind == "diagram":
        heading(slide, spec["title"])
        pic = fit_picture(slide, spec["image"], MARGIN, BODY_TOP,
                          SLIDE_W - 2 * MARGIN, Inches(3.9))
        steps.append((pic.shape_id, "wipe"))
        caption(slide, spec["caption"])

    elif kind == "shot_side":
        heading(slide, spec["title"], height=Inches(0.8))
        if spec.get("kicker"):
            tb, tf = textbox(slide, MARGIN, BODY_TOP - Inches(0.55),
                             SLIDE_W - 2 * MARGIN, Inches(0.35))
            add_runs(tf.paragraphs[0], spec["kicker"].upper(), 14, ACCENT,
                     bold=True)
        left_w = Inches(7.4)
        right_x = MARGIN + left_w + Inches(0.5)
        right_w = SLIDE_W - right_x - MARGIN
        pic = fit_picture(slide, spec["image"], MARGIN, BODY_TOP, left_w,
                          Inches(3.9))
        steps.append((pic.shape_id, "fade"))
        for i, block in enumerate(spec["blocks"]):
            y = BODY_TOP + i * Inches(1.5)
            panel(slide, right_x, y, right_w, Inches(1.35),
                  accent=block.get("accent", False))
            if spec.get("build_blocks"):
                steps.append((slide.shapes[-1].shape_id, "fade"))
            if block.get("lead"):
                lead(slide, right_x + Inches(0.25), y + Inches(0.18),
                     right_w - Inches(0.5), block["lead"])
            _, tf = textbox(slide, right_x + Inches(0.25),
                            y + (Inches(0.55) if block.get("lead") else Inches(0.25)),
                            right_w - Inches(0.5), Inches(0.9))
            add_runs(tf.paragraphs[0], block["text"], 14, TEXT)
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "pair":
        heading(slide, spec["title"])
        gap = Inches(0.5)
        cw = (SLIDE_W - 2 * MARGIN - gap) / 2
        for i, img in enumerate(spec["images"]):
            fit_picture(slide, img, MARGIN + i * (cw + gap), BODY_TOP,
                        cw, Inches(3.9))
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "divider":
        tb, tf = textbox(slide, MARGIN, Inches(2.2), SLIDE_W - 2 * MARGIN,
                         Inches(1.4))
        add_runs(tf.paragraphs[0], spec["index"], 72, ACCENT, bold=True,
                 font=F_HEAD)
        tb, tf = textbox(slide, MARGIN, Inches(3.5), SLIDE_W - 2 * MARGIN,
                         Inches(1.0))
        add_runs(tf.paragraphs[0], spec["title"], 40, TEXT, bold=True,
                 font=F_HEAD)
        gradient_bar(slide, MARGIN, Inches(4.6), Inches(3.4), Inches(0.09))
        tb, tf = textbox(slide, MARGIN, Inches(4.9), SLIDE_W - 2 * MARGIN,
                         Inches(0.5))
        add_runs(tf.paragraphs[0], spec["note"], 16, SECONDARY)

    elif kind == "metric":
        tb, tf = textbox(slide, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN,
                         Inches(0.9))
        add_runs(tf.paragraphs[0], spec["title"], 30, TEXT, bold=True,
                 font=F_HEAD)
        if spec.get("sub"):
            tb, tf = textbox(slide, MARGIN, Inches(2.15),
                             SLIDE_W - 2 * MARGIN, Inches(0.5))
            add_runs(tf.paragraphs[0], spec["sub"], 14, SECONDARY)
        tb, tf = textbox(slide, MARGIN, Inches(2.5), Inches(5.6), Inches(2.0))
        add_runs(tf.paragraphs[0], spec["big"], spec.get("bigsize", 88), ACCENT,
                 bold=True, font=F_HEAD)
        tb, tf = textbox(slide, MARGIN, Inches(4.6), Inches(5.6), Inches(1.2))
        add_runs(tf.paragraphs[0], spec["note"], 16, TEXT)
        if spec.get("animated"):
            steps.append((tb.shape_id, "fade"))
        if spec.get("image"):
            pic = fit_picture(slide, spec["image"], Inches(6.6), Inches(2.2),
                              SLIDE_W - Inches(6.6) - MARGIN, Inches(4.0))
            if spec.get("animated"):
                steps.append((pic.shape_id, "wipe"))
        if spec.get("chips"):
            cx = MARGIN
            for ci, chip in enumerate(spec["chips"]):
                cw = Inches(0.22) + Inches(0.085) * len(chip)
                box = rect(slide, cx, Inches(5.85), cw, Inches(0.4),
                           SURFACE_HI, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
                           line=SURFACE_HI)
                _, tf = textbox(slide, cx, Inches(5.9), cw, Inches(0.32))
                p = tf.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER
                add_runs(p, chip, 14, TEXT)
                if spec.get("animated") and ci == 0:
                    steps.append((box.shape_id, "fade"))
                cx += cw + Inches(0.25)
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "bars":
        tb, tf = textbox(slide, MARGIN, Inches(1.3), SLIDE_W - 2 * MARGIN,
                         Inches(0.9))
        add_runs(tf.paragraphs[0], spec["title"], 30, TEXT, bold=True,
                 font=F_HEAD)
        if spec.get("sub"):
            tb, tf = textbox(slide, MARGIN, Inches(2.15),
                             SLIDE_W - 2 * MARGIN, Inches(0.5))
            add_runs(tf.paragraphs[0], spec["sub"], 14, SECONDARY)
        if spec.get("big"):
            tb, tf = textbox(slide, MARGIN, Inches(2.5), Inches(4.4), Inches(1.6))
            add_runs(tf.paragraphs[0], spec["big"], 88, ACCENT, bold=True,
                     font=F_HEAD)
            steps.append((tb.shape_id, "fade"))
        if spec.get("note"):
            tb, tf = textbox(slide, MARGIN, Inches(5.9), SLIDE_W - 2 * MARGIN,
                             Inches(0.6))
            add_runs(tf.paragraphs[0], spec["note"], 16, TEXT)

        bx = MARGIN
        bw = SLIDE_W - 2 * MARGIN
        for i, (label, value, ratio, color) in enumerate(spec["bars"]):
            y = Inches(3.05) + i * Inches(1.3)
            tb, tf = textbox(slide, bx, y, Inches(1.0), Inches(0.7),
                             anchor=MSO_ANCHOR.MIDDLE)
            add_runs(tf.paragraphs[0], label, 22, SECONDARY, font=F_MONO)
            rect(slide, bx + Inches(1.1), y + Inches(0.05),
                 bw - Inches(3.4), Inches(0.6), SURFACE_HI)
            fill = rect(slide, bx + Inches(1.1), y + Inches(0.05),
                        (bw - Inches(3.4)) * ratio, Inches(0.6), color)
            tb, tf = textbox(slide, bx + bw - Inches(2.2), y, Inches(2.2),
                             Inches(0.7), anchor=MSO_ANCHOR.MIDDLE)
            tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
            add_runs(tf.paragraphs[0], value, 40, TEXT, bold=True, font=F_HEAD)
            steps.append((fill.shape_id, "fade"))
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "live":
        heading(slide, spec["title"])
        fit_picture(slide, spec["image"], MARGIN, BODY_TOP,
                    SLIDE_W - 2 * MARGIN, Inches(4.0))
        caption(slide, spec["caption"])

    elif kind == "video":
        heading(slide, spec["title"])
        pic = fit_picture(slide, spec["poster"], MARGIN, BODY_TOP,
                          SLIDE_W - 2 * MARGIN, Inches(3.6))
        # A small 40 px play badge in the bottom-right corner: a poster with a
        # centred badge reads as a real video embed and competes with the frame.
        size = Inches(0.4)
        px = pic.left + pic.width - size - Inches(0.25)
        py = pic.top + pic.height - size - Inches(0.25)
        rect(slide, px, py, size, size, BG, shape=MSO_SHAPE.OVAL, line=ACCENT)
        tri = rect(slide, px + Inches(0.13), py + Inches(0.08), Inches(0.14),
                   Inches(0.24), ACCENT, shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
        tri.rotation = 90
        if spec.get("meta"):
            tb, tf = textbox(slide, MARGIN, Inches(5.9), SLIDE_W - 2 * MARGIN,
                             Inches(0.4))
            add_runs(tf.paragraphs[0], spec["meta"], 14, SECONDARY, font=F_MONO)
        caption(slide, spec["caption"])

    elif kind == "limits":
        heading(slide, spec["title"])
        col_w = (SLIDE_W - 2 * MARGIN - Inches(0.5)) / 2
        for i, items in enumerate(spec["columns"]):
            x = MARGIN + i * (col_w + Inches(0.5))
            bullets_each(slide, items, x, BODY_TOP + Inches(0.2), col_w,
                         line_h=Inches(1.0), size=17)

    elif kind == "closing":
        tb, tf = textbox(slide, Inches(1.0), Inches(1.4), SLIDE_W - Inches(2.0),
                         Inches(1.4))
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        add_runs(p, spec["title"], 34, TEXT, bold=True, font=F_HEAD)
        qw = Inches(1.5)
        gap = Inches(0.9)
        n = len(spec["qrs"])
        total = n * qw + (n - 1) * gap
        x0 = (SLIDE_W - total) / 2
        for i, (rel, label, _url) in enumerate(spec["qrs"]):
            x = x0 + i * (qw + gap)
            picture(slide, rel, x, Inches(3.1), qw, qw)
            _, tf = textbox(slide, x - Inches(0.3), Inches(4.75),
                            qw + Inches(0.6), Inches(0.35))
            p2 = tf.paragraphs[0]
            p2.alignment = PP_ALIGN.CENTER
            add_runs(p2, label, 14, SECONDARY)
        tb, tf = textbox(slide, Inches(1.0), Inches(5.5), SLIDE_W - Inches(2.0),
                         Inches(0.5))
        p3 = tf.paragraphs[0]
        p3.alignment = PP_ALIGN.CENTER
        run = p3.add_run()
        run.text = "github.com/Pavel1778/madrigal-protocol-lab"
        run.font.size = Pt(14)
        run.font.name = F_MONO
        run.font.color.rgb = SECONDARY
        run.hyperlink.address = GITHUB

    if spec["kind"] not in ("cover", "closing"):
        footer(slide, spec["page"])
    if spec.get("notes"):
        slide.notes_slide.notes_text_frame.text = spec["notes"]
    return slide, steps


# --- content (mirrors slides.md, 19 slides) ---------------------------------
def deck() -> list[dict]:
    return [
        {"kind": "cover", "page": 1, "title": "Лаборатория протоколов",
             "sub": "Восстановление недокументированного бинарного протокола поверх TCP",
             "meta": "UMIRHack 2026 · кейс #02 · Мадригал · команда HTTP 418",
             "notes": "Приветствие, 20 секунд."},
        {"kind": "team", "page": 2, "title": "Нас двое",
             "members": [("Сабадаш Павел", "Архитектура · захват · интерфейс",
                       "@Pasha1778", "qr_telegram_pasha.png",
                       "avatar_pavel_round.png"),
                      ("Предков Никита", "Правила · тесты · ревью", "@petruan",
                       "qr_telegram_nikita.png", "avatar_nikita_round.png")],
             "notes": "Два человека, разделение ролей, QR на контакт у каждого."},
        {"kind": "statement", "page": 3,
             "title": "TCP разрезает сообщения посередине",
             "sub": "Границы пакета и границы сообщения — разные вещи",
             "image": "assets/tcp_framing.png"},
        {"kind": "given", "page": 4, "title": "Дано и требуется",
             "columns": [("Дано", ["Захваты `pcap`/`pcapng` и журнал действий устройства",
                                "Спецификации протокола нет"]),
                      ("Требуется", ["Проверяемая интерпретация структуры сообщений",
                                     "Видно, где чтение верно, а где перестаёт работать"])]},
        {"kind": "moment", "page": 5,
             "title": "Смещение поля длины оказалось на четыре байта позже, чем мы считали",
             "sub": "Одно правило, два чтения: поле длины остаётся на offset 2",
             "image": "assets/length_offset.png",
             "chips": ["наблюдение", "гипотеза", "проверка", "контрпример", "уточнение",
                    "повторная проверка"]},
        {"kind": "arch", "page": 6,
             "title": "Три модуля связаны форматами, а не вызовами",
             "modules": [("capture", "pcap/pcapng → сессии\nreassembly, provenance"),
                      ("protocol + hypothesis", "правила, фрейминг\nконтрпримеры, версии"),
                      ("ui", "окно PySide6\nисследование и просмотр")],
             "caption": "Контракты между модулями зафиксированы схемами JSON; порядок вызовов не важен"},
        {"kind": "shot_side", "page": 7, "title": "От интерпретации можно вернуться к исходным данным",
             "image": "public/screenshot-provenance.png",
             "blocks": [{"accent": True, "lead": "",
                          "text": "packet 3 · seq 1001 · ts 1700000000.004 · сессия s1"}]},
        {"kind": "pair", "page": 8, "title": "Правило проверяется на всём корпусе сразу",
             "images": ["public/screenshot-rule.png",
                     "public/screenshot-validation.png"]},
        {"kind": "shot_side", "page": 9, "title": "Контрпример важнее метрики",
             "kicker": "4 независимые сессии в корпусе + журнал действий устройства",
             "build_blocks": True,
             "image": "public/screenshot-counterexamples.png",
             "blocks": [{"accent": True, "lead": "",
                          "text": "02 00 00 03 13 00 55  —  команда 2 вне ожидаемого набора [1]"},
                     {"lead": "Один байт — 80 контрпримеров",
                          "text": "80 несоответствий v1 — на offset 0 в сессиях s2 и s3."}],
             "caption": "Значение 2 повторяется в независимых сессиях корпуса и связано с действием «изменить настройку» в журнале"},
        {"kind": "divider", "page": 10, "index": "01", "title": "Что получилось",
             "note": "Точность, покрытие корпуса организаторов, ресурсы"},
        {"kind": "bars", "page": 11, "title": "Уточнили правило: 60 из 140 → 140 из 140",
             "sub": "На корпусе уточнения. Отдельно проверено на реальном датасете: 45 + 45, precision 1.00",
             "note": "Было 60 matched из 140 и 80 контрпримеров. Стало 140 matched из 140 и ноль контрпримеров",
             "bars": [("v1", "0.43", 0.43, MISMATCHED),
                   ("v2", "1.00", 1.0, MATCHED)]},
        {"kind": "metric", "page": 12, "title": "Набор организаторов разобран целиком",
             "big": "90", "bigsize": 120, "image": "assets/coverage_donut.png",
             "note": "45 запросов + 45 ответов. Все matched.",
             "caption": "Данные не использовались при уточнении правила"},
        {"kind": "metric", "page": 13, "title": "95 МиБ разбираются за 12 секунд",
             "big": "12 с", "animated": True, "image": "assets/memory_sweep.png",
             "note": "Пик памяти 350 МиБ — 9% бюджета 4 ГиБ на машине 16 ГиБ",
             "chips": ["12 с общее время", "350 МиБ пик памяти", "250k пакетов"],
             "caption": "Условия замера: 95.66 МиБ, 250 000 пакетов, 1000 сессий, 4 vCPU / 16 ГиБ"},
        {"kind": "divider", "page": 14, "index": "02", "title": "Демонстрация",
             "note": "Живое окно и запись прогона"},
        {"kind": "live", "page": 15, "title": "Живое окно",
             "image": "public/screenshot-main.png",
             "caption": "Сессии, байты, интерпретация, происхождение и диагностика в одном окне"},
        {"kind": "video", "page": 16,
             "title": "Резерв: запись прогона",
             "poster": "public/screencast-poster.png",
             "meta": "Полный прогон референсного исследования · 2:22 · без звука",
             "caption": "Играется, если живое окно не поднимется на защите"},
        {"kind": "divider", "page": 17, "index": "03", "title": "Границы и итог",
             "note": "Что мы не утверждаем и что осталось за рамками"},
        {"kind": "limits", "page": 18, "title": "Что мы не утверждаем",
             "columns": [["Смысл байта флагов не установлен: в корпусе он постоянен",
                       "Поле значения остаётся гипотезой, а не фактом"],
                      ["Альтернативные чтения берутся из заданного набора",
                       "Интерпретация верна для проверенных захватов и молчит вне них"]]},
        {"kind": "closing", "page": 19,
             "title": "Инструмент превращает байты в проверяемое знание",
             "qrs": [("public/qr_repo.png", "Репозиторий", GITHUB),
                  ("public/qr_release.png", "Релиз v1.0.0", RELEASE),
                  ("public/qr_telegram_pasha.png", "@Pasha1778", "https://t.me/Pasha1778"),
                  ("public/qr_telegram_nikita.png", "@petruan", "https://t.me/petruan")],
             "notes": "QR ведут на репозиторий, релиз и контакты."},
    ]


def main() -> None:
    specs = deck()
    if len(specs) != TOTAL:
        raise SystemExit(f"deck() has {len(specs)} slides, expected {TOTAL}")
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    for spec in deck():
        slide, steps = build_slide(prs, spec)
        if steps:
            add_entrance(slide, steps)
        add_transition(slide, "fade")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    # The deck names Tektur/Montserrat/JetBrains Mono, which a viewer may not
    # have; embed the faces so the deck renders the same everywhere, then pin
    # the zip timestamps so the result stays byte-reproducible.
    embed_brand_fonts(OUT, collect_text(prs))
    freeze_zip(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
