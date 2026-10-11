"""Generate the QR codes the deck shows.

Two codes are needed: the repository and the release page. They are written to
``presentation/public/`` so Slidev serves them as static assets. Run from the
repository root:

    python -m presentation.generate_qr
"""

from __future__ import annotations

from pathlib import Path

import qrcode

PRES = Path(__file__).resolve().parent
OUT = PRES / "public"

CODES = {
    "qr_repo.png": "https://github.com/Pavel1778/madrigal-protocol-lab",
    "qr_release.png": "https://github.com/Pavel1778/madrigal-protocol-lab/releases/tag/v1.0.0",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in CODES.items():
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=12,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="#131516", back_color="#FFFFFF")
        image.save(OUT / name)
        print(f"presentation/public/{name}  <- {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
