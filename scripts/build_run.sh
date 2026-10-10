#!/usr/bin/env bash
#
# Build a self-extracting .run installer from the PyInstaller binary.
#
# Run scripts/build_linux_binary.sh first: this script packages that binary and
# does not build it. makeself wraps the payload with a small shell header, so the
# result installs the binary, the desktop entry and the icons with a double click
# or `./madrigal-lab.run`.
#
#   scripts/build_run.sh
#
# Output: dist/madrigal-lab.run

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BINARY="$ROOT/dist/madrigal-lab"
if [[ ! -x "$BINARY" ]]; then
    echo "no binary at $BINARY; run scripts/build_linux_binary.sh first" >&2
    exit 1
fi

if ! command -v makeself >/dev/null 2>&1; then
    echo "makeself is not installed; apt install makeself" >&2
    exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

install -m 0755 "$BINARY" "$STAGE/madrigal-lab"
install -m 0644 "$ROOT/packaging/madrigal-protocol-lab.desktop" \
    "$STAGE/madrigal-protocol-lab.desktop"
install -m 0755 "$ROOT/packaging/install.sh" "$STAGE/install.sh"

while IFS= read -r -d '' png; do
    rel="${png#"$ROOT/packaging/icons/hicolor"/}"
    target="$STAGE/icons/$(dirname "$rel")"
    mkdir -p "$target"
    install -m 0644 "$png" "$target/$(basename "$png")"
done < <(find "$ROOT/packaging/icons/hicolor" -type f -name '*.png' -print0)

OUT="$ROOT/dist/madrigal-lab.run"
makeself --gzip "$STAGE" "$OUT" "Madrigal Protocol Lab" ./install.sh >/dev/null

echo "built: $OUT"
ls -lh "$OUT"
