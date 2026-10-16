"""Package a rendered deck PDF into a PPTX, one full-bleed page per slide.

The deck source is the HTML; Chromium prints it to a PDF. This turns that PDF
into a PPTX so the deck also opens in PowerPoint and LibreOffice. Each slide is
one rendered page at 13.333x7.5 in (16:9), so the PPTX reproduces the HTML
exactly. Zip entry timestamps are pinned to 1980-01-01 so a rebuild is
byte-identical.

    python -m presentation.make_deck_pptx slides.pdf slide.pptx
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pypdfium2 as pdfium
from pptx import Presentation
from pptx.util import Inches

HERE = Path(__file__).resolve().parent
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
EPOCH = (1980, 1, 1, 0, 0, 0)


def freeze_timestamps(path: Path) -> None:
    buffer = io.BytesIO(path.read_bytes())
    with zipfile.ZipFile(buffer) as src, zipfile.ZipFile(
        path, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for item in src.infolist():
            info = zipfile.ZipInfo(item.filename, date_time=EPOCH)
            info.compress_type = item.compress_type
            info.external_attr = item.external_attr
            dst.writestr(info, src.read(item.filename))


def build(pdf_path: Path, out_path: Path) -> int:
    doc = pdfium.PdfDocument(pdf_path)
    deck = Presentation()
    deck.slide_width = SLIDE_W
    deck.slide_height = SLIDE_H
    blank = deck.slide_layouts[6]
    for page in doc:
        slide = deck.slides.add_slide(blank)
        image = page.render(scale=1.0, rev_byteorder=True).to_pil().convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        buffer.seek(0)
        slide.shapes.add_picture(buffer, 0, 0, width=SLIDE_W, height=SLIDE_H)
    deck.save(str(out_path))
    freeze_timestamps(out_path)
    return len(doc)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    pages = build(Path(argv[1]), Path(argv[2]))
    print(f"wrote {argv[2]}: {pages} slides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
