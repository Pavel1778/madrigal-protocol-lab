"""Render ``presentation/slides.md`` to a themed deck.

The Markdown is split on ``---`` into slides. Each slide becomes a fixed-size
page in a single HTML document, styled with the client palette and the bundled
Tektur and Montserrat fonts. Chromium prints the document to PDF.

Run from the repository root:

    python -m presentation.render_pdf

Set ``PRESENTATION_PDF`` to a Chromium or Chrome binary to override discovery.
"""

from __future__ import annotations

import html
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SLIDES_MD = REPO_ROOT / "presentation" / "slides.md"
OUT_HTML = REPO_ROOT / "presentation" / "slides.html"
OUT_PDF = REPO_ROOT / "presentation" / "slides.pdf"
FONTS = REPO_ROOT / "assets" / "fonts"

BACKGROUND = "#131516"
PANEL = "#1D1D1D"
TEXT = "#E0E0E0"
SECONDARY = "#9F9F9F"
ACCENT = "#6D071F"
HIGHLIGHT = "#A2391D"

_CHROMIUM_CANDIDATES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
)


def find_chromium() -> str | None:
    override = os.environ.get("PRESENTATION_PDF")
    if override and Path(override).exists():
        return override
    for name in _CHROMIUM_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def _inline(text: str) -> str:
    """Escape then restore the inline code spans the slides use."""
    escaped = html.escape(text)
    parts = escaped.split("`")
    out = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            out.append(f"<code>{part}</code>")
        else:
            out.append(part)
    return "".join(out)


def _render_slide(lines: list[str], first: bool) -> str:
    body: list[str] = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                body.append("</ul>")
                in_list = False
            continue
        if stripped == "***" or stripped == "___":
            body.append("<hr>")
            continue
        if stripped.startswith("!["):
            alt, _, rest = stripped[2:].partition("](")
            src = rest.rstrip(")")
            body.append(f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}"></figure>')
            continue
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = _inline(stripped[level:].strip())
            body.append(f"<h{level}>{text}</h{level}>")
            continue
        if stripped.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        if stripped.startswith("|"):
            body.append(_table_row(stripped))
            continue
        if stripped[0].isdigit() and stripped[1:3] == ". ":
            body.append(f"<p class='step'>{_inline(stripped)}</p>")
            continue
        body.append(f"<p>{_inline(stripped)}</p>")
    if in_list:
        body.append("</ul>")
    body = _group_figures(body)
    title_class = " class='title-slide'" if first else ""
    return f"<section{title_class}>\n" + "\n".join(body) + "\n</section>"


def _group_figures(body: list[str]) -> list[str]:
    """Wrap consecutive figures in a flex row so two images share one slide."""

    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if not run:
            return
        if len(run) == 1:
            out.append(run[0])
        else:
            out.append("<div class='figrow'>" + "".join(run) + "</div>")
        run.clear()

    for block in body:
        if block.startswith("<figure>"):
            run.append(block)
        else:
            flush()
            out.append(block)
    flush()
    return out


def _table_row(line: str) -> str:
    cells = [c.strip() for c in line.strip("|").split("|")]
    if all(set(c) <= set("-: ") for c in cells):
        return ""
    return "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>"


def build_html(markdown: str) -> str:
    blocks = _split_slides(markdown)
    slides = [_render_slide(block, index == 0) for index, block in enumerate(blocks)]
    fonts = "\n".join(
        f"@font-face{{font-family:'{family}';src:url('{(FONTS / file).as_uri()}');"
        f"{weight}}}"
        for family, file, weight in (
            ("Montserrat", "Montserrat-Regular.ttf", "font-weight:400;"),
            ("Montserrat", "Montserrat-SemiBold.ttf", "font-weight:600;"),
            ("Tektur", "Tektur-Medium.ttf", "font-weight:500;"),
            ("Tektur", "Tektur-SemiBold.ttf", "font-weight:600;"),
        )
    )
    css = f"""
    @page {{ size: 1280px 720px; margin: 0; }}
    * {{ box-sizing: border-box; }}
    {fonts}
    html, body {{ margin: 0; padding: 0; background: {BACKGROUND}; }}
    body {{ color: {TEXT}; font-family: 'Montserrat', sans-serif; }}
    section {{
        width: 1280px; height: 720px; padding: 64px 88px;
        page-break-after: always; position: relative;
        background: {BACKGROUND}; display: flex; flex-direction: column;
    }}
    section::before {{
        content: ''; position: absolute; left: 0; top: 0; width: 6px; height: 720px;
        background: linear-gradient(180deg, #410913, {ACCENT}, {HIGHLIGHT});
    }}
    h1 {{ font-family: 'Tektur', sans-serif; font-weight: 600; font-size: 40px;
          margin: 0 0 18px; color: {TEXT}; }}
    h2 {{ font-family: 'Tektur', sans-serif; font-weight: 600; font-size: 30px;
          margin: 0 0 16px; color: {TEXT}; }}
    h3 {{ font-family: 'Tektur', sans-serif; font-weight: 500; font-size: 22px;
          margin: 0 0 12px; color: {SECONDARY}; }}
    p {{ font-size: 22px; line-height: 1.35; margin: 8px 0; }}
    p.step {{ margin: 6px 0; }}
    ul {{ margin: 8px 0; padding-left: 26px; }}
    li {{ font-size: 21px; line-height: 1.4; margin: 6px 0; }}
    code {{ color: {HIGHLIGHT}; font-family: 'DejaVu Sans Mono', monospace; font-size: 20px; }}
    hr {{ border: none; border-top: 1px solid #2A2C2E; margin: 16px 0; }}
    table {{ border-collapse: collapse; margin: 14px 0; }}
    td, th {{ border: 1px solid #2A2C2E; padding: 8px 16px; font-size: 20px; }}
    td:first-child {{ color: {SECONDARY}; }}
    figure {{ margin: 10px 0 0; }}
    img {{ max-width: 100%; max-height: 470px; border: 1px solid #2A2C2E; border-radius: 4px; }}
    .figrow {{ display: flex; gap: 20px; margin-top: 12px; align-items: flex-start; }}
    .figrow figure {{ flex: 1 1 0; margin: 0; }}
    .figrow img {{ width: 100%; max-height: 440px; object-fit: contain; }}
    .title-slide {{ justify-content: center; }}
    .title-slide h1 {{ font-size: 56px; }}
    """
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{css}</style></head><body>"
        + "\n".join(slides)
        + "</body></html>"
    )


def _split_slides(markdown: str) -> list[list[str]]:
    slides: list[list[str]] = [[]]
    for line in markdown.splitlines():
        if line.strip() == "---":
            slides.append([])
        else:
            slides[-1].append(line)
    return [s for s in slides if any(line.strip() for line in s)]


def render(out_html: Path = OUT_HTML, out_pdf: Path = OUT_PDF) -> Path:
    markdown = SLIDES_MD.read_text(encoding="utf-8")
    out_html.write_text(build_html(markdown), encoding="utf-8")
    chromium = find_chromium()
    if chromium is None:
        raise SystemExit(
            "no Chromium or Chrome binary found; set PRESENTATION_PDF to one"
        )
    command = [
        chromium,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        f"--print-to-pdf={out_pdf}",
        out_html.as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if not out_pdf.is_file():
        sys.stderr.write(result.stderr)
        raise SystemExit("Chromium did not produce a PDF")
    return out_pdf


def main() -> int:
    out_pdf = render()
    print(out_pdf.relative_to(REPO_ROOT), f"{out_pdf.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
