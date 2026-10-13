#!/usr/bin/env bash
# Export the Slidev deck to presentation/slides.pdf, retrying because Slidev's
# per-slide export occasionally races the dev server and renders a slide blank.
set -u
cd "$(dirname "$0")"

# The CLI is a project dependency; fall back to a global install if present.
SLIDEV=./node_modules/.bin/slidev
[ -x "$SLIDEV" ] || SLIDEV=slidev
# The render check needs pypdfium2; use the project interpreter when asked.
PYTHON="${PYTHON:-python3}"

for attempt in 1 2 3 4 5; do
  "$SLIDEV" export --per-slide --wait-until networkidle --wait 500 \
    --format pdf --output slides.pdf >/tmp/slidev_export.log 2>&1
  check=$("$PYTHON" - <<'PY'
import pypdfium2 as pdfium
try:
    d = pdfium.PdfDocument('slides.pdf')
except Exception as exc:  # noqa: BLE001
    print(f'BAD {exc}')
else:
    bad = sum(1 for i in range(len(d))
              if 'error occurred' in d[i].get_textpage().get_text_range())
    print('OK' if (len(d) == 14 and bad == 0) else f'BAD pages={len(d)} errors={bad}')
PY
)
  echo "attempt ${attempt}: ${check}"
  [ "${check}" = "OK" ] && break
done
