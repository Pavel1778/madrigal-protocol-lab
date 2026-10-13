"""Build the «Мадригал» brand assets used by the deck.

The case owner's wordmark was not published in a form we could redistribute, so
the deck carries a neutral placeholder instead: a dark plate with the name set
in the deck's own display face (Tektur) and the brand accent bar. It reads as a
deliberate client badge on both the dark and the light deck, and it contains no
third-party mark.

Outputs (overwritten on every run, so a rebuild is reproducible):

* ``assets/madrigal-logo.png``  -- the wide wordmark (cover and closing slides)
* ``assets/madrigal-mark.png``  -- the square monogram (slide watermark)

Run from the repository root::

    python -m presentation.make_brand
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PRES = Path(__file__).resolve().parent
ASSETS = PRES / "assets"
FONTS = PRES / "public" / "fonts"

WORD = "Мадригал"

# Brand tokens, matching style.css (dark theme).
PLATE = (23, 19, 15, 255)          # #17130F, a warm near-black
PLATE_EDGE = (255, 255, 255, 26)   # a hairline lighter than the plate
TEXT = (244, 241, 236, 255)        # #F4F1EC
ACCENT_TOP = (65, 9, 19, 255)      # #410913, bordeaux
ACCENT_BOT = (162, 57, 29, 255)    # #A2391D, rust


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _vgradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    """A vertical gradient, used for the accent bar and the monogram glyph."""
    width, height = size
    grad = Image.new("RGBA", (1, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        grad.putpixel(
            (0, y),
            tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)),
        )
    return grad.resize((width, height))


def _paste_masked(base: Image.Image, layer: Image.Image, xy: tuple[int, int]) -> None:
    base.alpha_composite(layer, dest=xy)


def wordmark() -> Image.Image:
    """The wide «Мадригал» plate, transparent outside the rounded card."""
    scale = 3  # supersample, then downsample for clean edges
    w, h = 960 * scale, 232 * scale
    radius = 26 * scale
    font = _font(FONTS / "Tektur-SemiBold.ttf", 118 * scale)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=PLATE,
                           outline=PLATE_EDGE, width=2 * scale)
    img.alpha_composite(card)

    # Accent bar hugging the left edge, inside the radius.
    bar_w = 9 * scale
    bar = _vgradient((bar_w, h - 2 * radius), ACCENT_TOP, ACCENT_BOT)
    _paste_masked(img, bar, (0, radius))

    # The name, optically centred with a little extra room on the right.
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), WORD, font=font)
    text_w = bbox[2] - bbox[0]
    x = bar_w + int((w - bar_w - text_w) / 2) - bbox[0]
    y = int((h - (bbox[3] - bbox[1])) / 2) - bbox[1]
    d.text((x, y), WORD, font=font, fill=TEXT)

    return img.resize((960, 232), Image.LANCZOS)


def monogram() -> Image.Image:
    """The square «М» mark, for a faint corner watermark."""
    scale = 4
    size = 256 * scale
    radius = 40 * scale
    font = _font(FONTS / "Tektur-SemiBold.ttf", 168 * scale)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=PLATE,
        outline=PLATE_EDGE, width=2 * scale,
    )
    img.alpha_composite(card)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).text((0, 0), "М", font=font, fill=255)
    bbox = mask.getbbox()
    if bbox is None:
        return img.resize((256, 256), Image.LANCZOS)
    mask = mask.crop(bbox)
    grad = _vgradient(mask.size, ACCENT_TOP, ACCENT_BOT)
    grad.putalpha(mask)
    _paste_masked(img, grad, ((size - mask.width) // 2, (size - mask.height) // 2))

    return img.resize((256, 256), Image.LANCZOS)


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    wordmark().save(ASSETS / "madrigal-logo.png")
    monogram().save(ASSETS / "madrigal-mark.png")
    print("wrote assets/madrigal-logo.png, assets/madrigal-mark.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
