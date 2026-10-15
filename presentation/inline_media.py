"""Inline the deck's media into the self-contained HTML sources.

The deck is one file: the screencast, its poster and the GUI screenshots are
embedded as ``data:`` URIs so the HTML opens, plays and prints without a web
server and without the rest of the repository. The images are produced by the
other scripts here (``generate_screenshots``, ``make_assets``, ``make_brand``);
this script folds them into the two theme files.

It rewrites the slot a value already sits in, so it is idempotent: running it
after a re-record or a re-render refreshes the deck in place, and running it
again changes nothing. The anchors are the ``<video src>`` and ``poster``
attributes and the ``data-shot`` marker on each screenshot, so the layout is
never rewritten, only the media it points at.

    python -m presentation.inline_media
"""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = REPO_ROOT / "presentation"
PUBLIC = PRESENTATION / "public"
SHOTS = PRESENTATION / "screenshots"

DECKS = (
    "Презентация Madrigal Protocol Lab.html",
    "Презентация Madrigal Protocol Lab (светлая).html",
)

# ``data-shot`` value -> screenshot file under ``presentation/screenshots``.
SHOT_SOURCES = {
    "welcome": "12_welcome.png",
    "main": "01_main.png",
    "validation": "05_validation.png",
    "hypotheses": "10_hypotheses.png",
}


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _raw_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{_b64(path.read_bytes())}"


def _image_uri(path: Path, fmt: str = "PNG", max_width: int | None = None) -> str:
    if fmt == "PNG" and max_width is None:
        return f"data:image/png;base64,{_b64(path.read_bytes())}"
    im = Image.open(path).convert("RGB")
    if max_width is not None and im.width > max_width:
        height = round(im.height * max_width / im.width)
        im = im.resize((max_width, height), Image.LANCZOS)
    buffer = io.BytesIO()
    im.save(buffer, format=fmt, quality=88 if fmt == "JPEG" else None)
    mime = "image/jpeg" if fmt == "JPEG" else "image/png"
    return f"data:{mime};base64,{_b64(buffer.getvalue())}"


def _replace(html: str, pattern: str, value: str) -> tuple[str, int]:
    return re.subn(pattern, lambda m: m.group(1) + value + m.group(2), html)


def inline(html: str) -> tuple[str, list[str]]:
    changes: list[str] = []

    video = PRESENTATION / "screencast.mp4"
    if video.is_file():
        html, n = _replace(
            html, r'(<video[^>]*\ssrc=")[^"]*(")', _raw_uri(video, "video/mp4")
        )
        if n:
            changes.append(f"video x{n}")

    poster = PUBLIC / "screencast-poster.png"
    if poster.is_file():
        html, n = _replace(
            html, r'(poster=")[^"]*(")', _image_uri(poster, fmt="JPEG", max_width=1600)
        )
        if n:
            changes.append(f"poster x{n}")

    for shot, name in SHOT_SOURCES.items():
        source = SHOTS / name
        if not source.is_file():
            continue
        pattern = rf'(<img[^>]*data-shot="{re.escape(shot)}"[^>]*\ssrc=")[^"]*(")'
        html, n = _replace(html, pattern, _image_uri(source))
        if n:
            changes.append(f"{shot} x{n}")
    return html, changes


def main() -> int:
    for name in DECKS:
        path = PRESENTATION / name
        html = path.read_text(encoding="utf-8")
        updated, changes = inline(html)
        if updated == html:
            print(f"{name}: unchanged")
            continue
        path.write_text(updated, encoding="utf-8")
        print(f"{name}: {', '.join(changes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
