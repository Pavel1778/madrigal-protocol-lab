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
    src/ui/corpus_dialog.py
    src/ui/welcome_view.py
    src/ui/settings.py
    src/ui/legend.py
    src/ui/rule_builder.py
    src/ui/timeline_view.py
    src/ui/tutor.py
    src/ui/help_dialog.py
    src/ui/learning.py
    src/ui/help.py
)
TS_RU="src/ui/locale/madrigal_ru.ts"
QM_RU="src/ui/locale/madrigal_ru.qm"
TS_EN="src/ui/locale/madrigal_en.ts"
QM_EN="src/ui/locale/madrigal_en.qm"

# Russian carries hand-written translations. -no-obsolete drops messages whose
# source string no longer exists, so the catalogue never keeps a stale entry.
"$LUPDATE" "${SOURCES[@]}" -no-obsolete -ts "$TS_RU"
"$LRELEASE" "$TS_RU" -qm "$QM_RU"

# English is the source language, so its catalogue mirrors the source strings
# one for one. It is regenerated and filled so it is complete and checkable,
# not left half-unfinished.
"$LUPDATE" "${SOURCES[@]}" -no-obsolete -ts "$TS_EN"
python3 scripts/fill_english_catalogue.py "$TS_EN"
"$LRELEASE" "$TS_EN" -qm "$QM_EN"

echo "updated: $TS_RU"
echo "compiled: $QM_RU"
echo "updated: $TS_EN"
echo "compiled: $QM_EN"
