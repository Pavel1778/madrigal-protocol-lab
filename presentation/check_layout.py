"""Layout checks over an exported deck PDF.

These are the checks a human would do by eye, made measurable: the page is not
blank, nothing runs off the left/right/top edge, and nothing reaches the footer
band. The footer band is the same fraction of the page the CSS reserves, so the
check stays correct if the export scale changes.

    python -m presentation.check_layout slides.pdf slides-light.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium

RENDER_W = 1600
# The brand rule is a full-height bar on the left edge; ignore its columns.
RULE_COLS = 14
# The CSS slide is 552px tall and reserves 68px at the bottom for the footer
# plus its 22px of padding, i.e. the last 68/552 of the page is not for body
# content. The footer text itself sits higher, so this keeps a safety gap.
BAND_FRACTION = 68.0 / 552.0
EDGE_TOL = 4
# The organizer asks for at least 60 render px of clear margin at every edge.
MIN_MARGIN = 60


def _bg_color(page: pdfium.PdfPage, scale: float) -> np.ndarray:
    """Sample the page background from the top-left area below the accent bar."""
    bitmap = page.render(scale=scale, rev_byteorder=True)
    arr = np.asarray(bitmap.to_pil().convert("RGB"))
    corner = arr[8:40, 40:120].reshape(-1, 3)
    return np.median(corner, axis=0)


def check(path: Path) -> list[str]:
    doc = pdfium.PdfDocument(str(path))
    problems: list[str] = []
    for index in range(len(doc)):
        page = doc[index]
        width_pt, height_pt = page.get_size()
        scale = RENDER_W / width_pt
        # The band sits at the BOTTOM of the page. PDF object bounds are measured
        # from the bottom-left corner, so the band is a *small* y range.
        band_pt = height_pt * BAND_FRACTION

        # Text geometry, in points, so the footer can be excluded exactly.
        boxes = [
            tuple(float(v) for v in el.get_bounds())
            for el in page.get_objects()
            if el.type == 1  # FPDF_PAGEOBJ_TEXT
        ]
        body = [b for b in boxes if b[1] > band_pt]

        bitmap = page.render(scale=scale, rev_byteorder=True)
        arr = np.asarray(bitmap.to_pil().convert("RGB")).astype(int)
        height, width = arr.shape[:2]
        bg = _bg_color(page, scale)
        diff = np.abs(arr - bg).sum(axis=2)
        content = diff > 24
        content[:, :RULE_COLS] = False  # ignore the full-height brand rule

        if not content.any():
            problems.append(f"{path.name} p{index + 1}: blank page")
            continue

        rows = np.where(content.any(axis=1))[0]
        cols = np.where(content.any(axis=0))[0]
        top, bottom = int(rows[0]), int(rows[-1])
        left, right = int(cols[0]), int(cols[-1])
        band_px = int(band_pt * scale)

        # Fill ratio: how much of the usable frame the content block spans, and
        # how dense the ink is. A "lot of air" slide has a low fill ratio.
        usable_h = height - band_px
        fill = ((right - left) * (bottom - top)) / (width * usable_h)
        density = content[:usable_h].mean()

        if left <= EDGE_TOL:
            problems.append(f"{path.name} p{index + 1}: content at left edge")
        if right >= width - EDGE_TOL:
            problems.append(f"{path.name} p{index + 1}: content at right edge")
        if top <= EDGE_TOL:
            problems.append(f"{path.name} p{index + 1}: content at top edge")
        if bottom >= height - EDGE_TOL:
            problems.append(f"{path.name} p{index + 1}: content at bottom edge")
        if left < MIN_MARGIN:
            problems.append(
                f"{path.name} p{index + 1}: left margin {left}px < {MIN_MARGIN}px"
            )
        if width - right < MIN_MARGIN:
            problems.append(
                f"{path.name} p{index + 1}: right margin {width - right}px "
                f"< {MIN_MARGIN}px"
            )
        if top < MIN_MARGIN:
            problems.append(
                f"{path.name} p{index + 1}: top margin {top}px < {MIN_MARGIN}px"
            )
        if bottom > height - band_px:
            problems.append(
                f"{path.name} p{index + 1}: pixels reach footer band "
                f"(bottom={bottom}, band starts {height - band_px}/{height})"
            )
        # A body text box sits in the band when its lower edge is inside it.
        for _bx0, by0, _bx1, _by1 in body:
            if by0 < band_pt - 1:
                problems.append(
                    f"{path.name} p{index + 1}: body text in footer band "
                    f"(y0={by0:.1f} < {band_pt:.1f})"
                )
        print(
            f"{path.name} p{index + 1:>2}: box x[{left},{right}] y[{top},{bottom}] "
            f"of {width}x{height}; fill {fill:.0%} ink {density:.1%}; "
            f"text {len(boxes)} (body {len(body)})"
        )
    return problems


def main(argv: list[str]) -> int:
    files = [Path(a) for a in (argv or ["slides.pdf"])]
    problems: list[str] = []
    for path in files:
        problems.extend(check(path))
    print()
    if problems:
        print("LAYOUT PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("layout ok: no edge or footer-band overflow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
