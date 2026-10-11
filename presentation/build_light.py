"""Derive ``slides-light.md`` from ``slides.md`` for a washed-out projector.

The dark deck stays the single source of content. This script copies it and
changes only what has to differ for the light theme:

* the headmatter ``colorSchema`` becomes ``light``, which puts the ``light``
  class on ``<html>`` and activates the light tokens in ``style.css``;
* every chart under ``/assets/`` is swapped for its ``-light`` twin, because a
  chart is an ``<img>`` and cannot inherit the page palette.

Run from the repository root (after ``presentation.build_visualizations``):

    python -m presentation.build_light
"""

from __future__ import annotations

import re
from pathlib import Path

PRES = Path(__file__).resolve().parent
SRC = PRES / "slides.md"
DST = PRES / "slides-light.md"

_ASSET = re.compile(r"/assets/([A-Za-z0-9_]+)\.svg")


def build() -> str:
    text = SRC.read_text(encoding="utf-8")
    text = text.replace("colorSchema: dark", "colorSchema: light", 1)
    text = _ASSET.sub(r"/assets/\1-light.svg", text)
    return text


def main() -> int:
    DST.write_text(build(), encoding="utf-8")
    print(f"wrote {DST.name} ({len(build().splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
