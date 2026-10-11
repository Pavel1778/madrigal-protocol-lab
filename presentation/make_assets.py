"""Prepare the image assets the redesigned deck needs.

Everything here is derived from a committed source, nothing is drawn by hand:

* ``team-avatar-round.png``  a circular crop of ``public/team-avatar.png``;
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

from pathlib import Path

import numpy as np
import qrcode
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = REPO_ROOT / "presentation" / "public"
SHOTS = REPO_ROOT / "presentation" / "screenshots"

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

# Per-member QR shown next to the handle on the team slide. The avatar is
# cropped to a circle and the role line stays visible, so a viewer can scan a
# contact without reading a URL.
MEMBER_QR = {
    "Сабадаш Павел": "qr_telegram_pasha.png",
    "Предков Никита": "qr_telegram_nikita.png",
}

# name -> (source, box). Boxes are (left, top, right, bottom) in the source.
CROPS = {
    # slide 2: square head for the corner avatar
    "team-avatar-square.png": ("team-avatar.png", None),
    # slide 7: the hex dump only, trimmed to the byte rows. The window is
    # 1920x1080 but the hex panel ends at y=400; cropping the dead space below
    # roughly doubles the byte size on the slide.
    "screenshot-provenance.png": ("09_provenance.png", (315, 52, 735, 260)),
    # slide 8: the rule JSON, cropped to the editor and cut above the Messages
    # and Counterexamples tabs so the JSON renders large.
    "screenshot-rule.png": ("07_rule_editor.png", (720, 44, 1460, 300)),
    # slide 8: the validation result panel, right tab only
    "screenshot-validation.png": ("05_validation.png", (1424, 44, 1920, 300)),
    # slide 9: the counterexample list, right tab only
    "screenshot-counterexamples.png": ("05_validation.png", (1424, 44, 1920, 1080)),
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


def _square(src: Path, dst: Path, size: int = 200) -> None:
    im = Image.open(src).convert("RGBA")
    side = min(im.size)
    left = (im.width - side) // 2
    top = (im.height - side) // 2
    im.crop((left, top, left + side, top + side)).resize(
        (size, size), Image.LANCZOS
    ).save(dst)
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

    for name, path in (("team-avatar.png", PUBLIC / "team-avatar.png"),
                       ("01_main.png", SHOTS / "01_main.png")):
        seams = _detect_seams(path)
        print(f"seams {name}: {[tuple(map(int, s)) for s in seams]}")

    _circular(PUBLIC / "team-avatar.png", PUBLIC / "team-avatar-round.png")
    for name, url in TELEGRAM.items():
        _qr(url, PUBLIC / name)

    for dst_name, (src_name, box) in CROPS.items():
        src = (PUBLIC / src_name) if (PUBLIC / src_name).is_file() else (SHOTS / src_name)
        if src_name == "team-avatar.png":
            _square(src, PUBLIC / dst_name)
        else:
            _crop(src, PUBLIC / dst_name, box)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
