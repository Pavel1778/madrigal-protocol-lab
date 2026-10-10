"""Build the branded SVG visualisations used by ``presentation/slides.md``.

Every number is taken from ``docs/METRICS.md`` (the single source of truth for
the defense); nothing is invented. The Madrigal palette and the bundled Tektur
and Montserrat fonts are used, and text is converted to paths so the SVGs render
identically in the browser and in the printed PDF.

Run from the repository root:

    python -m presentation.build_visualizations
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "presentation" / "assets"
FONTS = REPO_ROOT / "assets" / "fonts"

BACKGROUND = "#131516"
PANEL = "#1D1D1D"
TEXT = "#E0E0E0"
SECONDARY = "#9F9F9F"
ACCENT = "#6D071F"
HIGHLIGHT = "#A2391D"
GRID = "#2A2C2E"

MATCHED = "#2E7D5B"
MISMATCHED = "#8E2A2A"
INCOMPLETE = "#6B6B6B"
AMBIGUOUS = "#B8860B"
UNCOVERED = "#3A3A3A"

matplotlib.rcParams.update(
    {
        "svg.fonttype": "path",  # text -> paths: no font dependency in <img>
        "figure.facecolor": BACKGROUND,
        "axes.facecolor": BACKGROUND,
        "savefig.facecolor": BACKGROUND,
        "text.color": TEXT,
        "axes.labelcolor": TEXT,
        "xtick.color": SECONDARY,
        "ytick.color": SECONDARY,
        "axes.edgecolor": GRID,
    }
)


def _register_fonts() -> None:
    for name in ("Tektur-Medium.ttf", "Tektur-SemiBold.ttf",
                 "Montserrat-Regular.ttf", "Montserrat-SemiBold.ttf"):
        path = FONTS / name
        if path.is_file():
            font_manager.fontManager.addfont(str(path))


def _style_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0)


def precision_v1_v2() -> None:
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=150)
    labels = ["v1", "v2"]
    values = [0.428571, 1.0]
    colors = [ACCENT, HIGHLIGHT]
    bars = ax.bar(labels, values, width=0.5, color=colors, zorder=3)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.03, f"{value:.2f}",
                ha="center", va="bottom", fontsize=20, fontfamily="Tektur", color=TEXT)
    ax.plot(labels, values, "o", color=TEXT, markersize=7, zorder=4)
    ax.set_ylim(0, 1.18)
    ax.set_ylabel("Precision", fontfamily="Montserrat", fontsize=13)
    ax.set_title("Precision: 0.43 → 1.00", fontfamily="Tektur", fontsize=17,
                 color=TEXT, pad=14)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(OUT / "precision_v1_v2.svg")
    plt.close(fig)


def framing_payload() -> None:
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=150)
    labels = ["payload", "payload + length", "entire message"]
    values = [10, 0, 0]
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, height=0.5, color=[HIGHLIGHT, ACCENT, ACCENT], zorder=3)
    for yi, value in zip(y, values):
        ax.text(value + 0.15, yi, f"{value} / 10", va="center", fontsize=16,
                fontfamily="Tektur", color=TEXT)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontfamily="Montserrat", fontsize=12)
    ax.set_xlim(0, 12)
    ax.set_xlabel("Streams framed cleanly", fontfamily="Montserrat", fontsize=12)
    ax.set_title("Framing: only payload frames every stream",
                 fontfamily="Tektur", fontsize=15, color=TEXT, pad=14)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(OUT / "framing_payload.svg")
    plt.close(fig)


def coverage_donut() -> None:
    fig, ax = plt.subplots(figsize=(6.0, 4.6), dpi=150)
    # Rule v2 over corpus_capture_01: 140 matched, 140 not applicable, 0 others.
    values = [140, 140, 0, 0, 0]
    labels = ["matched", "not applicable", "mismatched", "incomplete", "uncovered"]
    colors = [MATCHED, UNCOVERED, MISMATCHED, INCOMPLETE, AMBIGUOUS]
    present = [
        (value, label, color)
        for value, label, color in zip(values, labels, colors)
        if value > 0
    ]
    sizes = [p[0] for p in present]
    wedges, _ = ax.pie(
        sizes, colors=[p[2] for p in present], startangle=90,
        counterclock=False, wedgeprops=dict(width=0.34, edgecolor=BACKGROUND, linewidth=2),
    )
    ax.text(0, 0.12, "280", ha="center", va="center", fontsize=30,
            fontfamily="Tektur", color=TEXT)
    ax.text(0, -0.18, "messages", ha="center", va="center", fontsize=12,
            fontfamily="Montserrat", color=SECONDARY)
    ax.legend(wedges, [f"{p[1]}  {p[0]}" for p in present], loc="center left",
              bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=12,
              prop={"family": "Montserrat", "size": 12}, labelcolor=TEXT)
    ax.set_title("Coverage of corpus_capture_01 (rule v2)", fontfamily="Tektur",
                 fontsize=15, color=TEXT, pad=10)
    fig.tight_layout()
    fig.savefig(OUT / "coverage_donut.svg")
    plt.close(fig)


def research_timeline() -> None:
    fig, ax = plt.subplots(figsize=(9.2, 3.4), dpi=150)
    steps = ["наблюдение", "гипотеза", "проверка", "контрпример",
             "уточнение", "повторная\nпроверка"]
    x = np.arange(len(steps))
    ax.plot(x, np.zeros_like(x), color=GRID, linewidth=3, zorder=1)
    ax.scatter(x, np.zeros_like(x), s=520, color=PANEL, edgecolor=HIGHLIGHT,
               linewidth=2.5, zorder=2)
    for i, label in enumerate(steps):
        ax.text(i, 0, str(i + 1), ha="center", va="center", fontsize=13,
                fontfamily="Tektur", color=TEXT, zorder=3)
        ax.text(i, -0.28 if i % 2 else 0.24, label, ha="center",
                va="top" if i % 2 else "bottom", fontsize=12,
                fontfamily="Montserrat", color=SECONDARY)
    ax.set_xlim(-0.6, len(steps) - 0.4)
    ax.set_ylim(-0.7, 0.7)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "research_timeline.svg")
    plt.close(fig)


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(9.6, 4.4), dpi=150)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    modules = [
        (0.4, "capture", "pcap/pcapng → сессии\nreassembly, provenance"),
        (3.7, "protocol + hypothesis", "правила, фрейминг\nконтрпримеры, версии"),
        (7.0, "ui", "окно PySide6\nисследование и просмотр"),
    ]
    for x, title, subtitle in modules:
        box = FancyBboxPatch((x, 1.6), 2.6, 1.9, boxstyle="round,pad=0.02,rounding_size=0.06",
                             linewidth=1.6, edgecolor=HIGHLIGHT, facecolor=PANEL)
        ax.add_patch(box)
        ax.text(x + 1.3, 3.05, title, ha="center", va="center", fontsize=13,
                fontfamily="Tektur", color=TEXT)
        ax.text(x + 1.3, 2.35, subtitle, ha="center", va="center", fontsize=10,
                fontfamily="Montserrat", color=SECONDARY)
    for x in (3.0, 6.3):
        ax.add_patch(FancyArrowPatch((x, 2.55), (x + 0.7, 2.55), arrowstyle="-|>",
                                     mutation_scale=16, color=HIGHLIGHT, linewidth=1.8))
    ax.text(3.35, 2.8, "JSON", ha="center", fontsize=9, fontfamily="Montserrat",
            color=SECONDARY)
    ax.text(6.65, 2.8, "JSON", ha="center", fontsize=9, fontfamily="Montserrat",
            color=SECONDARY)
    ax.text(5.0, 0.7, "Контракты зафиксированы JSON Schema (draft 2020-12)",
            ha="center", fontsize=11, fontfamily="Montserrat", color=SECONDARY)
    fig.tight_layout()
    fig.savefig(OUT / "architecture.svg")
    plt.close(fig)


def memory_sweep() -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.2), dpi=150)
    sizes = [9.57, 47.84, 90.88]
    regular = [58, 186, 336]
    streaming = [54, 167, 293]
    ax.plot(sizes, regular, "-o", color=ACCENT, markersize=7, linewidth=2,
            label="regular")
    ax.plot(sizes, streaming, "-s", color=HIGHLIGHT, markersize=7, linewidth=2,
            label="streaming")
    ax.set_xlabel("Вход, МиБ", fontfamily="Montserrat", fontsize=12)
    ax.set_ylabel("Пиковая память, МиБ", fontfamily="Montserrat", fontsize=12)
    ax.set_title("Свип памяти: streaming ниже regular", fontfamily="Tektur",
                 fontsize=15, color=TEXT, pad=14)
    ax.grid(color=GRID, linewidth=0.8, zorder=0)
    legend = ax.legend(frameon=False, fontsize=12, labelcolor=TEXT)
    for text in legend.get_texts():
        text.set_fontfamily("Montserrat")
    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(OUT / "memory_sweep.svg")
    plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    _register_fonts()
    precision_v1_v2()
    framing_payload()
    coverage_donut()
    research_timeline()
    architecture()
    memory_sweep()
    for name in sorted(p.name for p in OUT.glob("*.svg")):
        print("presentation/assets/" + name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
