#!/usr/bin/env bash
#
# Refresh the interface translation catalogue.
#
# Scans the window sources for translatable strings, updates the `.ts`
# catalogue in place, and compiles it into the `.qm` the application loads at
# run time. Run this after adding or changing a `tr()` string.
#
#   scripts/update_translations.sh
#
# The `.ts` file is the source of truth and is tracked in git; the compiled
# `.qm` is also tracked so the window works without a Qt toolchain installed.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LUPDATE="${LUPDATE:-.venv/bin/pyside6-lupdate}"
LRELEASE="${LRELEASE:-.venv/bin/pyside6-lrelease}"
if [[ ! -x "$LUPDATE" ]]; then
    LUPDATE="pyside6-lupdate"
    LRELEASE="pyside6-lrelease"
fi

SOURCES=(
    src/ui/main_window.py
    src/ui/session_tree.py
    src/ui/hex_view.py
    src/ui/compare_view.py
    src/ui/hypotheses_view.py
    src/ui/validation_view.py
)
TS="src/ui/locale/madrigal_ru.ts"
QM="src/ui/locale/madrigal_ru.qm"

"$LUPDATE" "${SOURCES[@]}" -ts "$TS"
"$LRELEASE" "$TS" -qm "$QM"

echo "updated: $TS"
echo "compiled: $QM"
