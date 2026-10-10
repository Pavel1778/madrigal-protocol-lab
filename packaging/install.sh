#!/bin/bash
#
# Install the protocol laboratory from the self-extracting archive.
#
# The archive carries the frozen binary, the desktop entry and the icons. This
# script copies them into a user prefix (no root needed), or into a system
# prefix when PREFIX points at one and the caller can write there.
#
#   ./madrigal-lab.run                 # install into ~/.local
#   PREFIX=/usr/local ./madrigal-lab.run
#   ./madrigal-lab.run --help
#   ./madrigal-lab.run --target DIR    # extract only, no install (makeself)

set -e

HERE="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<'USAGE'
Madrigal Protocol Lab installer

  ./madrigal-lab.run [--help]

Installs the window and its launcher. The prefix defaults to ~/.local and can be
overridden with the PREFIX environment variable:

  PREFIX=/usr/local ./madrigal-lab.run

Files installed:
  PREFIX/bin/madrigal-lab
  PREFIX/share/applications/madrigal-protocol-lab.desktop
  PREFIX/share/icons/hicolor/<size>/apps/madrigal-protocol-lab.png
USAGE
}

case "${1:-}" in
    --help|-h)
        usage
        exit 0
        ;;
esac

PREFIX="${PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin"
APPS="$PREFIX/share/applications"
ICONS="$PREFIX/share/icons/hicolor"

mkdir -p "$BIN" "$APPS" "$ICONS"
install -m 0755 "$HERE/madrigal-lab" "$BIN/madrigal-lab"
install -m 0644 "$HERE/madrigal-protocol-lab.desktop" \
    "$APPS/madrigal-protocol-lab.desktop"

for size in 16 32 48 64 128 256 512; do
    src="$HERE/icons/${size}x${size}/apps/madrigal-protocol-lab.png"
    [ -f "$src" ] || continue
    mkdir -p "$ICONS/${size}x${size}/apps"
    install -m 0644 "$src" "$ICONS/${size}x${size}/apps/madrigal-protocol-lab.png"
done

echo "installed $BIN/madrigal-lab"
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "add $BIN to PATH to run 'madrigal-lab' from any directory" ;;
esac
