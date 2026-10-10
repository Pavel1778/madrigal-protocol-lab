#!/usr/bin/env bash
#
# Build a single-file AppImage from the PyInstaller binary.
#
# Run scripts/build_linux_binary.sh first: this script packages that binary and
# does not build it. The AppImage bundles the executable, the launcher, the
# desktop entry and the icons, so the application runs on a target with no
# Python setup and no installation step.
#
#   scripts/build_appimage.sh
#
# Output: dist/protocol-lab-x86_64.AppImage
#
# appimagetool itself ships as an AppImage and needs FUSE to run from the file.
# Where FUSE is absent (a container), the script extracts the tool and runs the
# extracted AppRun, which needs no mount.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BINARY="$ROOT/dist/madrigal-lab"
if [[ ! -x "$BINARY" ]]; then
    echo "no binary at $BINARY; run scripts/build_linux_binary.sh first" >&2
    exit 1
fi

TOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
TOOL="$ROOT/.agent-cache/appimagetool-x86_64.AppImage"
APPIMAGETOOL=""

if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGETOOL="$(command -v appimagetool)"
else
    mkdir -p "$(dirname "$TOOL")"
    if [[ ! -f "$TOOL" ]]; then
        echo "downloading appimagetool"
        curl -sL -o "$TOOL" "$TOOL_URL"
        chmod +x "$TOOL"
    fi
    # appimagetool is itself an AppImage; run it extracted so no FUSE is needed.
    EXTRACT_DIR="$ROOT/.agent-cache/appimagetool-extract"
    if [[ ! -x "$EXTRACT_DIR/AppRun" ]]; then
        rm -rf "$EXTRACT_DIR"
        ( cd "$ROOT/.agent-cache" && "$TOOL" --appimage-extract >/dev/null )
        mv "$ROOT/.agent-cache/squashfs-root" "$EXTRACT_DIR"
    fi
    APPIMAGETOOL="$EXTRACT_DIR/AppRun"
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

APPDIR="$STAGE/AppDir"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor"

install -m 0755 "$BINARY" "$APPDIR/usr/bin/madrigal-lab"

# The launcher resolves its own directory, so the AppImage works wherever the
# user stores it.
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
exec "$HERE/usr/bin/madrigal-lab" "$@"
APPRUN
chmod 0755 "$APPDIR/AppRun"

install -m 0644 "$ROOT/packaging/madrigal-protocol-lab.desktop" \
    "$APPDIR/madrigal-protocol-lab.desktop"
install -m 0644 "$ROOT/packaging/madrigal-protocol-lab.desktop" \
    "$APPDIR/usr/share/applications/madrigal-protocol-lab.desktop"

# The top-level icon must carry the name the desktop entry points at.
install -m 0644 "$ROOT/assets/icons/app/madrigal-protocol-lab-256.png" \
    "$APPDIR/madrigal-protocol-lab.png"

while IFS= read -r -d '' png; do
    rel="${png#"$ROOT/packaging/icons/hicolor"/}"
    target="$APPDIR/usr/share/icons/hicolor/$(dirname "$rel")"
    mkdir -p "$target"
    install -m 0644 "$png" "$target/$(basename "$png")"
done < <(find "$ROOT/packaging/icons/hicolor" -type f -name '*.png' -print0)

OUT="$ROOT/dist/protocol-lab-x86_64.AppImage"
ARCH=x86_64 "$APPIMAGETOOL" --no-appstream "$APPDIR" "$OUT" >/dev/null

echo "built: $OUT"
ls -lh "$OUT"
