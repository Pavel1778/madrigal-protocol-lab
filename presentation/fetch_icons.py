"""Copy the Lucide line icons the deck uses into ``presentation/icons/``.

Lucide (MIT) is fetched once with ``npm pack lucide-static``; this script takes
the icons the slides name, tints the stroke with the Madrigal text colour and
drops the rest. Run from the repository root:

    npm pack lucide-static && tar xzf lucide-static-*.tgz
    python -m presentation.fetch_icons
"""

from __future__ import annotations

from pathlib import Path

SOURCE = Path("/tmp/package/icons")
DEST = Path("presentation/icons")

ICONS = [
    "database", "radio", "git-branch", "braces", "globe", "lock", "shield-check",
    "activity", "layers", "cpu", "camera", "film", "monitor", "list-tree", "tag",
    "hash", "diff", "circle-check", "circle-x", "alert-triangle", "help-circle",
    "search", "refresh-cw", "target", "git-compare", "folder-tree", "binary",
    "network", "file-json", "clipboard-check",
]


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    missing = []
    for name in ICONS:
        source = SOURCE / f"{name}.svg"
        if not source.is_file():
            missing.append(name)
            continue
        text = source.read_text(encoding="utf-8")
        text = text.replace('stroke="currentColor"', 'stroke="#E0E0E0"')
        (DEST / f"{name}.svg").write_text(text, encoding="utf-8")
    print("copied", len(list(DEST.glob("*.svg"))), "icons")
    if missing:
        print("missing:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
