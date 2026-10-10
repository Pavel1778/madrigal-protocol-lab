#!/usr/bin/env bash
# Export the Slidev deck to presentation/slides.pdf, retrying because Slidev's
# per-slide export occasionally races the dev server and renders a slide blank.
set -u
cd "$(dirname "$0")"

for attempt in 1 2 3 4 5; do
  slidev export --per-slide --wait-until networkidle --wait 500 \
    --format pdf --output slides.pdf >/tmp/slidev_export.log 2>&1
  check=$(python3 - <<'PY'
import pypdfium2 as pdfium
try:
    d = pdfium.PdfDocument('slides.pdf')
except Exception as exc:  # noqa: BLE001
    print(f'BAD {exc}')
else:
    bad = sum(1 for i in range(len(d))
              if 'error occurred' in d[i].get_textpage().get_text_range())
    print('OK' if (len(d) >= 17 and bad == 0) else f'BAD pages={len(d)} errors={bad}')
PY
)
  echo "attempt ${attempt}: ${check}"
  [ "${check}" = "OK" ] && break
done
