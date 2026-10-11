"""Build the defence deck as a real, editable PPTX from our own code.

Mirrors ``slides.md`` (19 slides, 16:9). Every slide is drawn with python-pptx
directly — no PowerPoint template — with native editable text, the deck palette,
click-triggered fade entrances and fade/push transitions.

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

ROOT = Path(__file__).resolve().parents[2]
PRES = ROOT / "presentation"
OUT = PRES / "slides.pptx"

# --- palette (mirrors presentation/style.css) --------------------------------
BG = RGBColor(0x0E, 0x10, 0x11)
SURFACE = RGBColor(0x17, 0x18, 0x1A)
TEXT = RGBColor(0xE8, 0xE6, 0xE3)
SECONDARY = RGBColor(0xA8, 0xA2, 0x9E)
ACCENT = RGBColor(0xD0, 0x60, 0x3A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

F_HEAD = "Inter"
F_BODY = "Inter"
F_MONO = "JetBrains Mono"

MARGIN = Inches(0.75)
FOOTER_H = Inches(0.45)
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
BODY_TOP = Inches(1.75)
GITHUB = "https://github.com/Pavel1778/madrigal-protocol-lab"
RELEASE = "https://github.com/Pavel1778/madrigal-protocol-lab/releases/tag/v1.0.0"
TELEGRAM = "https://t.me/Pasha1778"
TOTAL = 19

_TOKEN = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


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


def rect(slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    solid(s, color)
    return s


def bg(slide):
    rect(slide, 0, 0, SLIDE_W, SLIDE_H, BG)
    rect(slide, 0, 0, Inches(0.05), SLIDE_H, ACCENT)


def footer(slide, page):
    tb, tf = textbox(slide, MARGIN, SLIDE_H - FOOTER_H, SLIDE_W - 2 * MARGIN,
                     Inches(0.3))
    p = tf.paragraphs[0]
    add_runs(p, "Команда HTTP 418 · кейс #02 · Мадригал", 9, SECONDARY)
    tb2, tf2 = textbox(slide, MARGIN, SLIDE_H - FOOTER_H, SLIDE_W - 2 * MARGIN,
                       Inches(0.3))
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.RIGHT
    add_runs(p2, f"{page} / {TOTAL}", 9, SECONDARY)


def heading(slide, text, size=30):
    tb, tf = textbox(slide, MARGIN, Inches(0.5), SLIDE_W - 2 * MARGIN,
                     Inches(1.05))
    add_runs(tf.paragraphs[0], text, size, TEXT, bold=True, font=F_HEAD)
    return tb


def caption(slide, text, y=Inches(6.55)):
    tb, tf = textbox(slide, MARGIN, y, SLIDE_W - 2 * MARGIN, Inches(0.4))
    add_runs(tf.paragraphs[0], text, 11, SECONDARY)
    return tb


def bullets(slide, items, x, y, w, h, size=17):
    tb, tf = textbox(slide, x, y, w, h)
    first = True
    for it in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(10)
        add_runs(p, "•  " + it, size, TEXT)
    return tb


def bullets_each(slide, items, x, y, w, line_h=Inches(0.75), size=17):
    """One textbox per bullet, so each can build in on its own click."""
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
    <p:cTn id="{cid+2}" dur="500" fill="hold"/>
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
    <p:cTn id="{cid+2}" dur="700" fill="hold"/>
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

    if kind == "title":
        pic = picture(slide, "public/team-avatar.png", MARGIN, Inches(2.45),
                      Inches(2.4), Inches(2.4))
        tx, tf = textbox(slide, MARGIN + Inches(2.9), Inches(2.6),
                         SLIDE_W - MARGIN - Inches(2.9), Inches(1.3))
        add_runs(tf.paragraphs[0], spec["title"], 40, TEXT, font=F_HEAD)
        steps.append((tx.shape_id, "fade"))
        tx2, tf2 = textbox(slide, MARGIN + Inches(2.9), Inches(3.9),
                           SLIDE_W - MARGIN - Inches(2.9), Inches(0.6))
        add_runs(tf2.paragraphs[0], spec["line"], 16, SECONDARY)

    elif kind == "two_col":
        heading(slide, spec["title"])
        x2 = MARGIN + Inches(6.1)
        w2 = SLIDE_W - x2 - MARGIN
        if spec.get("left_image"):
            pic = fit_picture(slide, spec["left_image"], MARGIN, BODY_TOP,
                              Inches(5.6), Inches(4.3))
            steps.append((pic.shape_id, "fade"))
        elif spec.get("build_left"):
            for spid in bullets_each(slide, spec.get("left", []), MARGIN,
                                     BODY_TOP, Inches(5.6)):
                steps.append((spid, "fade"))
        else:
            tb = bullets(slide, spec.get("left", []), MARGIN, BODY_TOP,
                         Inches(5.6), Inches(4.3), size=17)
            if spec.get("animate"):
                steps.append((tb.shape_id, "fade"))
        if spec.get("right_image"):
            pic = fit_picture(slide, spec["right_image"], x2, BODY_TOP, w2,
                              Inches(4.3))
            if spec.get("animate"):
                steps.append((pic.shape_id, "fade"))
        elif spec.get("build_right"):
            for spid in bullets_each(slide, spec.get("right", []), x2,
                                     BODY_TOP, w2):
                steps.append((spid, "fade"))
        elif spec.get("right"):
            tb = bullets(slide, spec["right"], x2, BODY_TOP, w2, Inches(4.3),
                         size=17)
            if spec.get("animate"):
                steps.append((tb.shape_id, "fade"))
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "statement":
        tb, tf = textbox(slide, MARGIN, Inches(2.5),
                         SLIDE_W - 2 * MARGIN, Inches(1.8))
        add_runs(tf.paragraphs[0], spec["title"], 46, TEXT, font=F_HEAD)
        steps.append((tb.shape_id, "fade"))
        tb2, tf2 = textbox(slide, MARGIN, Inches(4.3),
                           SLIDE_W - 2 * MARGIN, Inches(0.8))
        add_runs(tf2.paragraphs[0], spec["sub"], 20, SECONDARY)

    elif kind == "moment":
        rect(slide, MARGIN, Inches(2.4), Inches(0.06), Inches(2.4), ACCENT)
        tb, tf = textbox(slide, MARGIN + Inches(0.4), Inches(2.5),
                         SLIDE_W - MARGIN - Inches(0.4), Inches(1.5))
        add_runs(tf.paragraphs[0], spec["title"], 34, TEXT, font=F_HEAD)
        steps.append((tb.shape_id, "fade"))
        tb2, tf2 = textbox(slide, MARGIN + Inches(0.4), Inches(3.9),
                           SLIDE_W - MARGIN - Inches(0.4), Inches(0.9))
        add_runs(tf2.paragraphs[0], spec["sub"], 18, SECONDARY)

    elif kind == "diagram":
        heading(slide, spec["title"])
        pic = fit_picture(slide, spec["image"], MARGIN, BODY_TOP,
                          SLIDE_W - 2 * MARGIN, Inches(4.5))
        steps.append((pic.shape_id, "wipe"))

    elif kind == "figure_full":
        heading(slide, spec["title"])
        fit_picture(slide, spec["image"], MARGIN, BODY_TOP,
                    SLIDE_W - 2 * MARGIN, Inches(4.3))
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "figure_pair":
        heading(slide, spec["title"])
        gap = Inches(0.4)
        cw = (SLIDE_W - 2 * MARGIN - gap) / 2
        for i, img in enumerate(spec["images"]):
            pic = fit_picture(slide, img, MARGIN + i * (cw + gap), BODY_TOP,
                              cw, Inches(4.2))
            steps.append((pic.shape_id, "fade"))
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "byte":
        heading(slide, spec["title"])
        x2 = MARGIN + Inches(6.6)
        w2 = SLIDE_W - x2 - MARGIN
        fit_picture(slide, spec["image"], MARGIN, BODY_TOP, Inches(5.8),
                    Inches(4.2))
        card = rect(slide, x2, BODY_TOP + Inches(0.4), w2, Inches(2.0), SURFACE)
        steps.append((card.shape_id, "fade"))
        tb, tf = textbox(slide, x2 + Inches(0.25), BODY_TOP + Inches(0.6),
                         w2 - Inches(0.5), Inches(1.6))
        add_runs(tf.paragraphs[0], spec["bytes"], 22, ACCENT, font=F_MONO)
        add_runs(tf.add_paragraph(), spec["note"], 14, SECONDARY)
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "divider":
        tb, tf = textbox(slide, MARGIN, Inches(2.5), SLIDE_W - 2 * MARGIN,
                         Inches(1.1))
        add_runs(tf.paragraphs[0], spec["index"], 60, ACCENT, font=F_MONO)
        steps.append((tb.shape_id, "fade"))
        tb2, tf2 = textbox(slide, MARGIN, Inches(3.6), SLIDE_W - 2 * MARGIN,
                           Inches(1.0))
        add_runs(tf2.paragraphs[0], spec["title"], 40, TEXT, font=F_HEAD)
        rect(slide, MARGIN, Inches(4.7), Inches(3.2), Inches(0.07), ACCENT)

    elif kind == "metric":
        tb, tf = textbox(slide, MARGIN, Inches(1.6), SLIDE_W - 2 * MARGIN,
                         Inches(0.8))
        add_runs(tf.paragraphs[0], spec["title"], 26, SECONDARY, bold=True,
                 font=F_HEAD)
        tb2, tf2 = textbox(slide, MARGIN, Inches(2.5), SLIDE_W - 2 * MARGIN,
                           Inches(2.2))
        add_runs(tf2.paragraphs[0], spec["big"], 96, ACCENT, bold=True,
                 font=F_HEAD)
        steps.append((tb2.shape_id, "fade"))
        tb3, tf3 = textbox(slide, MARGIN, Inches(4.9), Inches(10.5), Inches(1.0))
        add_runs(tf3.paragraphs[0], spec["note"], 18, TEXT)

    elif kind == "video":
        heading(slide, spec["title"])
        fit_picture(slide, spec["poster"], MARGIN, BODY_TOP,
                    SLIDE_W - 2 * MARGIN, Inches(4.3))
        if spec.get("caption"):
            caption(slide, spec["caption"])

    elif kind == "closing":
        tb, tf = textbox(slide, Inches(1.0), Inches(1.5),
                         SLIDE_W - Inches(2.0), Inches(1.6))
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        add_runs(p, spec["title"], 36, TEXT, bold=True, font=F_HEAD)
        steps.append((tb.shape_id, "fade"))
        gap = Inches(1.4)
        qw = Inches(1.6)
        total = 2 * qw + gap
        x0 = (SLIDE_W - total) / 2
        for i, (rel, label, url) in enumerate(spec["qrs"]):
            x = x0 + i * (qw + gap)
            pic = picture(slide, rel, x, Inches(3.5), qw, qw)
            steps.append((pic.shape_id, "fade"))
            tb2, tf2 = textbox(slide, x - Inches(0.4), Inches(5.2),
                               qw + Inches(0.8), Inches(0.35))
            p2 = tf2.paragraphs[0]
            p2.alignment = PP_ALIGN.CENTER
            add_runs(p2, label, 11, SECONDARY)
        tb3, tf3 = textbox(slide, Inches(1.0), Inches(5.9),
                           SLIDE_W - Inches(2.0), Inches(0.5))
        p3 = tf3.paragraphs[0]
        p3.alignment = PP_ALIGN.CENTER
        run = p3.add_run()
        run.text = "github.com/Pavel1778/madrigal-protocol-lab · @Pasha1778"
        run.font.size = Pt(13)
        run.font.name = F_MONO
        run.font.color.rgb = SECONDARY
        run.hyperlink.address = GITHUB

    footer(slide, spec["page"])
    if spec.get("notes"):
        slide.notes_slide.notes_text_frame.text = spec["notes"]
    return slide, steps


# --- content (mirrors slides.md, 19 slides) ---------------------------------
def deck() -> list[dict]:
    return [
        dict(kind="title", page=1, title="Лаборатория протоколов",
             line="Команда HTTP 418 · UMIRHack 2026 · кейс #02 · Мадригал",
             notes="Восстановление недокументированного протокола поверх TCP."),
        dict(kind="two_col", page=2, title="Нас двое",
             left=["**Сабадаш Павел** — архитектура, захват, интерфейс · @Pasha1778",
                   "**Предков Никита** — правила, тесты · @petruan"],
             right_image="public/team-avatar.png", animate=True,
             notes="Команда HTTP 418."),
        dict(kind="statement", page=3, title="TCP разрезает сообщения посередине",
             sub="Границы пакета и границы сообщения — разные вещи"),
        dict(kind="two_col", page=4, title="Дано и требуется",
             left=["Захваты pcap/pcapng и журнал действий устройства",
                   "Спецификации протокола нет"],
             right=["Проверяемая интерпретация структуры сообщений",
                    "Видно, где чтение верно, а где перестаёт работать"],
             build_left=True, build_right=True),
        dict(kind="moment", page=5,
             title="Первые дни мы не понимали, где у протокола длина",
             sub="Смещение поля длины оказалось на четыре байта позже, чем мы считали"),
        dict(kind="diagram", page=6,
             title="Три модуля связаны форматами, а не вызовами",
             image="assets/architecture.png",
             caption="capture → protocol → hypothesis → ui; контракты зафиксированы JSON Schema"),
        dict(kind="figure_full", page=7, title="Каждый байт знает свой пакет",
             image="screenshots/09_provenance.png",
             caption="Клик по байту: packet 3 · seq 1001 · ts 1700000000.004"),
        dict(kind="figure_pair", page=8,
             title="Правило проверяется на всём корпусе сразу",
             images=["screenshots/07_rule_editor.png",
                     "screenshots/05_validation.png"],
             caption="Одно правило описывает весь поток; сообщения не перечисляют вручную"),
        dict(kind="byte", page=9, title="Контрпример важнее метрики",
             image="screenshots/05_validation.png", bytes="02 00 00 03 13 00 55",
             note="Команда 2 не входила в ожидаемый набор [1]",
             caption="Один такой байт превратил 80 контрпримеров в ноль"),
        dict(kind="divider", page=10, index="01", title="Что получилось"),
        dict(kind="metric", page=11, title="Точность правила: 0.43 → 1.00",
             big="1.00",
             note="Было 60 matched и 80 mismatched. Стало 140 matched и ноль контрпримеров"),
        dict(kind="metric", page=12, title="Набор организаторов разобран целиком",
             big="90",
             note="45 запросов и 45 ответов, все matched, покрытие байтов 100 %"),
        dict(kind="metric", page=13, title="95 МиБ разбираются за 12 секунд",
             big="12 с",
             note="250 000 пакетов, 1000 сессий, 4 vCPU. Пик памяти 350 МиБ"),
        dict(kind="divider", page=14, index="02", title="Демонстрация"),
        dict(kind="figure_full", page=15, title="Живое окно",
             image="screenshots/01_main.png",
             caption="Сессии, байты, интерпретация, происхождение и диагностика в одном окне"),
        dict(kind="video", page=16,
             title="Запись прогона на случай, если экран не поднимется",
             poster="screenshots/02_sessions.png",
             caption="Четыре минуты: шесть сцен референсного исследования"),
        dict(kind="divider", page=17, index="03", title="Границы и итог"),
        dict(kind="two_col", page=18, title="Что мы не утверждаем",
             left=["Смысл байта флагов не установлен: в корпусе он постоянен",
                   "Поле значения остаётся гипотезой, а не фактом"],
             right=["Альтернативные чтения берутся из заданного набора",
                    "Интерпретация верна для проверенных захватов и молчит вне них"],
             build_left=True, build_right=True),
        dict(kind="closing", page=19,
             title="Инструмент превращает байты в проверяемое знание",
             qrs=[("public/qr_repo.png", "Репозиторий", GITHUB),
                  ("public/qr_release.png", "Релиз v1.0.0", RELEASE)],
             notes="QR ведут на репозиторий и на релиз v1.0.0."),
    ]


def main() -> None:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    for spec in deck():
        slide, steps = build_slide(prs, spec)
        if steps:
            add_entrance(slide, steps)
        add_transition(slide, "push" if spec["kind"] == "divider" else "fade")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
