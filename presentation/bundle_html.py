#!/usr/bin/env python3
"""Bundle the built Slidev deck (dist/) into presentation_html.zip.

The exported HTML deck is the animated deliverable: it opens in a browser with
transitions and v-click build-ins. Run `slidev build` first.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"
OUT = HERE / "presentation_html.zip"


def main() -> int:
    if not DIST.is_dir():
        print("dist/ is missing; run `npm run build` first", file=sys.stderr)
        return 1
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(DIST.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(DIST))
    print(f"wrote {OUT.name}: {len(zipfile.ZipFile(OUT).namelist())} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
