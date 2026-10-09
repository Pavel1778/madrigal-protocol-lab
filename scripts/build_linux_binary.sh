#!/usr/bin/env bash
#
# Build a single-file Linux binary of the window.
#
# The binary bundles the interpreter, PySide6, the fonts, the docs and the
# corpus, so it runs on a target without a Python setup. Build it on the oldest
# glibc you intend to support; the result does not run on an older one.
#
#   scripts/build_linux_binary.sh
#
# Output: dist/madrigal-lab (one file). The assets, docs and corpus are unpacked
# next to the executable at /tmp at run time by PyInstaller's own loader.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "pyinstaller is not installed; pip install pyinstaller" >&2
    exit 1
fi

pyinstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name madrigal-lab \
    --add-data "assets:assets" \
    --add-data "docs:docs" \
    --add-data "tests/corpus:corpus" \
    --paths "$ROOT" \
    scripts/madrigal_lab.py

echo "built: $ROOT/dist/madrigal-lab"
ls -lh "$ROOT/dist/madrigal-lab"
