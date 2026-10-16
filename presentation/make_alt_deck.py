"""Derive the 13-slide cut of the defence deck from the 15-slide master.

The master deck is the canonical artefact and is not modified. This script
reads it, keeps thirteen slides and renumbers the visible counters so the two
files stay in sync as the master evolves. Two slides are folded to reach the
count: the problem statement and the "what is given / what is required" slide
become one "постановка и метод" slide, and the "hypothesis vs rule" and
"return to the bytes" slides become one core slide.

Run from the repository root:

    python -m presentation.make_alt_deck

Then print each variant to PDF with Chromium, exactly as for the master deck
(see presentation/README.md), and package the PDFs with
``presentation.make_deck_pptx``.
"""

from __future__ import annotations

import re
from pathlib import Path

PRES = Path(__file__).resolve().parent

THEMES = {
    "dark": {
        "src": PRES / "Презентация Madrigal Protocol Lab.html",
        "out": PRES / "Презентация Madrigal Protocol Lab (13 слайдов).html",
        "box_bg": "#27272a",
        "box_border": "#ef4444",
        "box_text": "#f8fafc",
        "green": "#10b981",
        "red": "#ef4444",
        "amber": "#f59e0b",
        "text": "#e2e8f0",
        "muted": "#94a3b8",
        "bright": "#f8fafc",
        "callout_bg": "rgba(239, 68, 68, 0.1)",
        "callout_border": "rgba(239, 68, 68, 0.3)",
        "callout_text": "#f8fafc",
        "core_bg": "#111318",
        "core_border": "#3b82f6",
        "core_text": "#f8fafc",
        "hint": "#38bdf8",
    },
    "light": {
        "src": PRES / "Презентация Madrigal Protocol Lab (светлая).html",
        "out": PRES / "Презентация Madrigal Protocol Lab (13 слайдов, светлая).html",
        "box_bg": "#F1EEE9",
        "box_border": "#D6362F",
        "box_text": "#14171C",
        "green": "#0E9F6E",
        "red": "#D6362F",
        "amber": "#B45309",
        "text": "#232936",
        "muted": "#5A6270",
        "bright": "#14171C",
        "callout_bg": "rgba(214, 54, 47, 0.08)",
        "callout_border": "rgba(214, 54, 47, 0.3)",
        "callout_text": "#14171C",
        "core_bg": "#F3F1ED",
        "core_border": "#2563EB",
        "core_text": "#14171C",
        "hint": "#1D4ED8",
    },
}

# Slides kept from the master, in order; ``None`` marks a folded slide that is
# rebuilt below. The list length is the slide count of the derived deck.
KEEP = [1, 2, None, 5, 6, None, 9, 10, 11, 12, 13, 14, 15]

FOLD_PROBLEM = '''<div class="slide-container" id="slide{number}">
    <div class="slide-header">
      <div>
        <div class="slide-tag">ПОСТАНОВКА И МЕТОД</div>
        <h2 class="slide-title">Пакет, сообщение и задача</h2>
      </div>
      <div class="slide-number">{number:02d} / {total}</div>
    </div>

    <div style="flex-grow: 1; display: flex; flex-direction: column; justify-content: center; gap: 22px;">
      <div class="bg-card" style="padding: 28px; display: flex; flex-direction: column; gap: 22px;">
        <div style="display: flex; gap: 16px; align-items: stretch; height: 66px;">
          <div style="flex: 1; background: {box_bg}; border: 2px dashed {box_border}; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: {box_text};">Пакет 1</div>
          <div style="flex: 1; background: {box_bg}; border: 2px dashed {box_border}; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: {box_text};">Пакет 2</div>
          <div style="flex: 3; background: {box_bg}; border: 2px dashed {box_border}; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: {box_text};">Пакет 3</div>
        </div>
        <div style="display: flex; gap: 16px; align-items: center;">
          <div style="flex: 2; height: 10px; background: {green}; border-radius: 5px; position: relative;">
            <span style="position: absolute; top: -24px; left: 0; font-family: 'JetBrains Mono'; font-size: 12px; color: {green}; font-weight: 700;">Сообщение A</span>
          </div>
          <div style="flex: 3; height: 10px; background: {amber}; border-radius: 5px; position: relative;">
            <span style="position: absolute; top: -24px; left: 0; font-family: 'JetBrains Mono'; font-size: 12px; color: {amber}; font-weight: 700;">Сообщение B</span>
          </div>
        </div>
      </div>

      <div style="display: flex; gap: 24px;">
        <div class="bg-card" style="flex: 1; padding: 22px;">
          <h3 style="font-size: 13px; font-family: 'JetBrains Mono'; color: {red}; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">ДАНО</h3>
          <ul style="list-style: none; font-size: 16px; color: {text}; display: flex; flex-direction: column; gap: 6px;">
            <li>Захваты pcap / pcapng и журнал устройства</li>
            <li>Спецификации протокола нет</li>
          </ul>
        </div>
        <div class="bg-card" style="flex: 1; padding: 22px;">
          <h3 style="font-size: 13px; font-family: 'JetBrains Mono'; color: {green}; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">ТРЕБУЕТСЯ</h3>
          <ul style="list-style: none; font-size: 16px; color: {text}; display: flex; flex-direction: column; gap: 6px;">
            <li>Проверяемая интерпретация структуры сообщений</li>
            <li>Видно, где чтение верно, а где перестаёт работать</li>
          </ul>
        </div>
      </div>

      <div style="text-align: center; background: {callout_bg}; border: 1px solid {callout_border}; padding: 14px; border-radius: 10px;">
        <p style="font-size: 18px; font-weight: 700; color: {callout_text}; margin: 0;">
          Границы пакета и границы сообщения — <span class="accent-red">разные вещи</span>
        </p>
      </div>
    </div>

    <div class="footer-bar">
      <span>Команда HTTP 418 · кейс #02 · Мадригал</span>
      <span>Постановка и метод</span>
    </div>
  </div>'''

FOLD_CORE = '''<div class="slide-container" id="slide{number}">
    <div class="slide-header">
      <div>
        <div class="slide-tag">ЯДРО ПРОЕКТА</div>
        <h2 class="slide-title">Гипотеза → Правило → Возврат к байтам</h2>
      </div>
      <div class="slide-number">{number:02d} / {total}</div>
    </div>

    <div style="flex-grow: 1; display: flex; flex-direction: column; justify-content: center; gap: 22px;">
      <div style="display: flex; gap: 24px;">
        <div class="bg-card" style="flex: 1; padding: 24px; border-color: {amber};">
          <div class="mono accent-amber" style="font-size: 15px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 12px;">Гипотеза</div>
          <div class="mono" style="font-size: 17px; color: {bright}; margin-bottom: 12px;">«Кажется, value = байты 5–6»</div>
          <ul style="list-style: none; font-size: 14px; color: {muted}; display: flex; flex-direction: column; gap: 6px;">
            <li>Словами, с основанием</li>
            <li>Статус: черновик / проверяется</li>
          </ul>
        </div>
        <div class="bg-card" style="flex: 1; padding: 24px; border-color: {green};">
          <div class="mono accent-green" style="font-size: 15px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 12px;">Правило</div>
          <div class="mono" style="font-size: 17px; color: {bright}; margin-bottom: 12px;">offset: 2, size: 2, type: uint16</div>
          <ul style="list-style: none; font-size: 14px; color: {muted}; display: flex; flex-direction: column; gap: 6px;">
            <li>Формально, применимо</li>
            <li>Статус: актуально / устарело</li>
          </ul>
        </div>
      </div>

      <div class="bg-card" style="padding: 18px 24px; font-family: 'JetBrains Mono', monospace; font-size: 15px; display: flex; gap: 28px; align-items: center;">
        <div style="color: {bright}; font-weight: 700;">value = 21</div>
        <div style="color: {muted};">← сообщение #12</div>
        <div style="color: {muted};">← байты 5..6</div>
        <div style="color: {muted};">← пакет #103</div>
        <div style="color: {hint}; font-size: 13px;">клик по значению ведёт к байту</div>
      </div>

      <div style="text-align: center; background: {core_bg}; border: 1px solid {core_border}; padding: 14px; border-radius: 10px;">
        <p style="font-size: 17px; color: {core_text}; margin: 0;">
          Гипотеза без правила — заметка. Правило без гипотезы — парсер. Ценность — когда связаны.
        </p>
      </div>
    </div>

    <div class="footer-bar">
      <span>Команда HTTP 418 · кейс #02 · Мадригал</span>
      <span>Ядро проекта</span>
    </div>
  </div>'''


def split_slides(document: str) -> tuple[str, dict[int, str], str]:
    """Return the head, the per-number slide blocks and the tail."""
    marks = [
        (m.start(), int(m.group(1)))
        for m in re.finditer(r'<div class="slide-container" id="slide(\d+)"', document)
    ]
    head = document[: marks[0][0]]
    end_of_body = document.rfind("</body>")
    slides: dict[int, str] = {}
    for i, (pos, number) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else end_of_body
        slides[number] = document[pos:end]
    return head, slides, document[end_of_body:]


def build(theme: str) -> None:
    cfg = THEMES[theme]
    head, slides, tail = split_slides(cfg["src"].read_text(encoding="utf-8"))
    total = len(KEEP)

    def renumber(block: str, number: int) -> str:
        block = re.sub(
            r'<div class="slide-container" id="slide\d+"',
            f'<div class="slide-container" id="slide{number}"',
            block,
            count=1,
        )
        return re.sub(
            r'(<div class="slide-number">)\d+ / \d+(</div>)',
            rf"\g<1>{number:02d} / {total}\g<2>",
            block,
            count=1,
        )

    parts = [head]
    for position, keep in enumerate(KEEP, start=1):
        if keep is None:
            template = FOLD_PROBLEM if position == 3 else FOLD_CORE
            parts.append(template.format(number=position, total=total, **cfg))
        else:
            parts.append(renumber(slides[keep], position))
    parts.append(tail)

    output = "".join(parts)
    cfg["out"].write_text(output, encoding="utf-8")
    produced = len(re.findall(r'<div class="slide-container" id="slide', output))
    print(f"{theme}: {cfg['out'].name} -> {produced} slides")


def main() -> int:
    for theme in THEMES:
        build(theme)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
