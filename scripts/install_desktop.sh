#!/usr/bin/env bash
#
# Install the desktop entry and the hicolor icons for the current user.
#
#   scripts/install_desktop.sh
#
# Copies packaging/madrigal-protocol-lab.desktop into
# ~/.local/share/applications and the rendered PNGs into
# ~/.local/share/icons/hicolor/<size>x<size>/apps, then refreshes the desktop
# and icon caches. It does not touch the system directories and needs no root.
#
# The launcher runs the "madrigal-lab" command, so install the package first:
#
#   pip install -e .
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS_DIR="$DATA_HOME/applications"
ICONS_DIR="$DATA_HOME/icons/hicolor"

DESKTOP_SRC="$ROOT/packaging/madrigal-protocol-lab.desktop"
ICONS_SRC="$ROOT/packaging/icons/hicolor"

if [[ ! -f "$DESKTOP_SRC" ]]; then
    echo "missing desktop entry: $DESKTOP_SRC" >&2
    exit 1
fi

mkdir -p "$APPS_DIR"
install -m 0644 "$DESKTOP_SRC" "$APPS_DIR/madrigal-protocol-lab.desktop"
echo "installed $APPS_DIR/madrigal-protocol-lab.desktop"

if [[ -d "$ICONS_SRC" ]]; then
    while IFS= read -r -d '' png; do
        rel="${png#"$ICONS_SRC"/}"
        target="$ICONS_DIR/$(dirname "$rel")"
        mkdir -p "$target"
        install -m 0644 "$png" "$target/$(basename "$png")"
    done < <(find "$ICONS_SRC" -type f -name '*.png' -print0)
    echo "installed icons under $ICONS_DIR"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f "$ICONS_DIR" >/dev/null 2>&1 || true
fi

echo "the launcher may need a fresh login session to appear in the menu"
