#!/usr/bin/env bash
#
# Package the binary into a .deb.
#
# Run scripts/build_linux_binary.sh first: this script installs that binary and
# does not build it. The package drops the executable into /usr/bin, the icon
# and desktop entry into /usr/share, and the docs, fonts and corpus into
# /usr/share/madrigal-protocol-lab.
#
#   scripts/build_deb.sh
#
# Output: dist/madrigal-protocol-lab_<version>_amd64.deb

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BINARY="$ROOT/dist/madrigal-lab"
if [[ ! -x "$BINARY" ]]; then
    echo "no binary at $BINARY; run scripts/build_linux_binary.sh first" >&2
    exit 1
fi

if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "dpkg-deb is not installed" >&2
    exit 1
fi

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
NAME="madrigal-protocol-lab"
ARCH="amd64"

# Stage outside the tree: a setgid parent propagates its group bit to the
# control directory, and dpkg-deb rejects control with a setgid bit.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/usr/share/madrigal-protocol-lab"

install -m 0755 "$BINARY" "$STAGE/usr/bin/madrigal-lab"
install -m 0644 "$ROOT/assets/icons/madrigal-lab.svg" \
    "$STAGE/usr/share/icons/hicolor/scalable/apps/madrigal-lab.svg"

install -m 0644 "$ROOT/docs/demo.md" "$STAGE/usr/share/madrigal-protocol-lab/demo.md"
cp -r "$ROOT/assets/fonts" "$STAGE/usr/share/madrigal-protocol-lab/fonts"
cp -r "$ROOT/tests/corpus" "$STAGE/usr/share/madrigal-protocol-lab/corpus"

cat > "$STAGE/usr/share/applications/madrigal-lab.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Madrigal Protocol Lab
Comment=Investigate an undocumented binary protocol over TCP
Exec=madrigal-lab
Icon=madrigal-lab
Terminal=false
Categories=Development;Utility;
DESKTOP

cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: ${NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Sabadash Pavel <sabadaspaha@gmail.com>
Description: Laboratory for investigating an undocumented binary protocol
 Reads a PCAP or PCAPNG capture, rebuilds TCP streams, frames messages,
 applies declarative interpretation rules and verifies them on a corpus.
CONTROL

DEB="$ROOT/dist/${NAME}_${VERSION}_${ARCH}.deb"
chmod 0755 "$STAGE"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB"
echo "built: $DEB"
ls -lh "$DEB"
