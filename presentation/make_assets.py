"""Prepare the image assets the redesigned deck needs.

Everything here is derived from a committed source, nothing is drawn by hand:

* ``avatar_pavel_round.png`` / ``avatar_nikita_round.png``  the per-member team
  photos (``assets/team/pavel.jpg`` / ``assets/team/nikita.jpg``), cropped to
  circles;
* ``qr_telegram_pasha.png`` / ``qr_telegram_nikita.png``  Telegram codes;
* ``screenshot-*.png``  crops of the real GUI captures at the panel seams
  detected in the pixel data, so each slide can show the region it talks about
  at a readable scale instead of a shrunken 1920x1080 frame;
* the two schematics of slides 3 and 5, which live in
  ``presentation/assets/`` and are built by ``build_visualizations``.

Run from the repository root:

    python -m presentation.make_assets
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import qrcode
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = REPO_ROOT / "presentation" / "public"
SHOTS = REPO_ROOT / "presentation" / "screenshots"
SCREENCAST = REPO_ROOT / "presentation" / "screencast.mp4"

# Panel seams in the 1920x1080 captures. The GUI splits at 300 / 720 / 420 px
# (``main_window`` ``setSizes``); the matching bands in the pixels are 285-317
# (sessions|centre) and 942-953, 1423-1436 (centre|right). Crops cut on the
# inside edge of each seam so no separator line is left dangling.
SEAM_LEFT = 317
SEAM_C1 = 942
SEAM_C2 = 1436
RIGHT_X = 1436

TELEGRAM = {
    "qr_telegram_pasha.png": "https://t.me/Pasha1778",
    "qr_telegram_nikita.png": "https://t.me/petruan",
}

# Per-member team photos, kept under ``assets/team/`` so a teammate can drop in
# a replacement without hunting through the presentation tree. Cropped to a
# circle and sized for the 180 px slot on slide 2 (2x for crisp rendering).
MEMBER_PHOTOS = (("assets/team/pavel.jpg", "avatar_pavel_round.png"),
                 ("assets/team/nikita.jpg", "avatar_nikita_round.png"))

# Per-member QR shown next to the handle on the team slide. The avatar is
# cropped to a circle and the role line stays visible, so a viewer can scan a
# contact without reading a URL.
MEMBER_QR = {
    "Сабадаш Павел": "qr_telegram_pasha.png",
    "Предков Никита": "qr_telegram_nikita.png",
}

# name -> (source, box). Boxes are (left, top, right, bottom) in the source.
CROPS = {
    # slide 7: the hex dump only, trimmed to six byte rows so the bytes read
    # from the back of the room. The window is 1920x1080 but the hex panel ends
    # at y=400; cropping the dead space below roughly triples the byte size.
    "screenshot-provenance.png": ("09_provenance.png", (317, 98, 735, 268)),
    # slide 8: the rule JSON, cropped to the editor and cut above the Messages
    # and Counterexamples tabs so the JSON renders large.
    "screenshot-rule.png": ("07_rule_editor.png", (720, 44, 1460, 300)),
    # slide 8: the validation result panel, right tab only
    "screenshot-validation.png": ("05_validation.png", (1436, 44, 1920, 300)),
    # slide 9: six counterexample rows, right tab only, no empty tail
    "screenshot-counterexamples.png": ("05_validation.png", (1436, 96, 1920, 300)),
    # slide 15: the three key zones of the full window (sessions | hex | rule)
    "screenshot-main.png": ("01_main.png", (300, 44, 1920, 460)),
}


def _circular(src: Path, dst: Path, size: int = 760) -> None:
    """Mask a picture to a circle with a transparent outside."""
    im = Image.open(src).convert("RGBA")
    side = min(im.size)
    left = (im.width - side) // 2
    top = (im.height - side) // 2
    im = im.crop((left, top, left + side, top + side)).resize(
        (size, size), Image.LANCZOS
    )
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    out.save(dst)
    print(f"presentation/public/{dst.name}")


def _qr(url: str, dst: Path, box: int = 10) -> None:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color="#0E1011", back_color="#FFFFFF").save(dst)
    print(f"presentation/public/{dst.name}  <- {url}")


def _crop(src: Path, dst: Path, box) -> None:
    im = Image.open(src).convert("RGB")
    im.crop(box).save(dst)
    print(f"presentation/public/{dst.name}  <- {src.name}{box}")


def _poster(src: Path, dst: Path) -> None:
    """Frame the recording into a slide poster (play glyph drawn in CSS).

    The frame is chosen by sharpness so the poster shows the settled UI rather
    than a mid-scroll moment.
    """
    if shutil.which("ffmpeg") is None:
        print("ffmpeg missing — keeping existing poster")
        return
    best: tuple[float, int, Image.Image] | None = None
    for t in (5, 20, 40, 60, 90, 120):
        tmp = dst.with_suffix(".frame.png")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(src),
             "-frames:v", "1", str(tmp), "-y"], check=True)
        frame = Image.open(tmp).convert("RGB")
        tmp.unlink()
        grey = np.asarray(frame.convert("L"), dtype=float)
        lap = np.abs(np.diff(grey, axis=1)).var() + np.abs(np.diff(grey, axis=0)).var()
        if best is None or lap > best[0]:
            best = (lap, t, frame)
    assert best is not None
    _, at, frame = best
    frame.resize((1600, 900), Image.LANCZOS).save(dst)
    print(f"presentation/public/{dst.name}  <- {src.name} (sharpest frame @{at}s)")


def _detect_seams(path: Path) -> list[int]:
    """Report near-uniform column runs — the panel seams — for verification."""
    grey = np.asarray(Image.open(path).convert("L")).astype(float)
    std = grey.std(axis=0)
    uniform = np.where(std < 2)[0]
    runs = []
    if len(uniform):
        start = prev = int(uniform[0])
        for x in uniform[1:]:
            x = int(x)
            if x == prev + 1:
                prev = x
            else:
                runs.append((start, prev))
                start = prev = x
        runs.append((start, prev))
    return [r for r in runs if r[1] - r[0] >= 1]


def main() -> int:
    PUBLIC.mkdir(parents=True, exist_ok=True)

    for name, path in (("01_main.png", SHOTS / "01_main.png"),):
        seams = _detect_seams(path)
        print(f"seams {name}: {[tuple(map(int, s)) for s in seams]}")

    for src_name, dst_name in MEMBER_PHOTOS:
        _circular(REPO_ROOT / src_name, PUBLIC / dst_name, size=360)
    for name, url in TELEGRAM.items():
        _qr(url, PUBLIC / name)

    if SCREENCAST.is_file():
        _poster(SCREENCAST, PUBLIC / "screencast-poster.png")

    for dst_name, (src_name, box) in CROPS.items():
        src = (PUBLIC / src_name) if (PUBLIC / src_name).is_file() else (SHOTS / src_name)
        _crop(src, PUBLIC / dst_name, box)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
