# Presentation

The defense deck for «Лаборатория протоколов» (UMIRHack 2026, case #02,
Мадригал). The deck is authored in Markdown and rendered by
[Slidev](https://sli.dev/); the visualisations and the GUI screenshots are built
from the repository's own code. Every number is from `docs/METRICS.md`.

## Files

| Path | What it is |
| --- | --- |
| `slides.md` | the deck source (14 slides, Madrigal theme, `v-click` build-ins) |
| `style.css` | the Madrigal theme: palette, Tektur + Montserrat, layout |
| `slides-light.md` | the light variant, derived from `slides.md` by `build_light.py` |
| `slides.pdf` | the printed export, 14 pages (archive copy for submission) |
| `slides-light.pdf` | the same deck exported for a washed-out projector |
| `slides.pptx` | the editable PPTX: native text, entrance animations, transitions |
| `scripts/build_pptx.py` | builds `slides.pptx` from code (python-pptx), not a picture dump |
| `fonts.py` | embeds Tektur, Montserrat and JetBrains Mono into the PPTX as `.fntdata` parts |
| `screenshots/` | 11 real GUI captures at 1920×1080 (`generate_screenshots.py`) |
| `assets/` | 8 branded SVG visualisations, dark and light (`build_visualizations.py`) |
| `icons/` | Lucide line icons used by the deck (`fetch_icons.py`) |
| `public/` | assets the deck serves: fonts, logo, QR codes, member photos |
| `public/screencast-poster.png` | the fallback-screencast frame, kept for the reserve recording (not a slide) |
| `defense_script.md` | the 8-minute speaker script, one section per slide |
| `VIDEO.md` | shot list for the reserve screen recording |
| `export_pdf.sh` | exports `slides.pdf` with a retry for the Slidev race |
| `bundle_html.py` | packs the built `dist/` into `presentation_html.zip` |

The two member photos on slide 2 come from `assets/team/pavel.jpg` and
`assets/team/nikita.jpg`; `presentation/make_assets.py` crops them to the round
`public/avatar_*_round.png` the slide uses. Replace either JPEG and re-run
`make_assets.py` to update a face.

## Build (one command)

```bash
cd presentation && npm install && npm run export
```

`npm run export` runs `slidev export --format pdf` and writes `slides.pdf`.
For the deterministic path used in CI-like runs, use `bash export_pdf.sh`, which
retries until every page renders (Slidev's per-slide export occasionally races
the dev server and leaves a slide blank).

The animated version is the built deck itself:

```bash
cd presentation && npm run build   # writes dist/, a static SPA with transitions
cd presentation && npm run dev     # live deck with v-click build-ins
```

## Dependencies

Install once, from the repository root and from `presentation/`:

- Python 3.12+ with `matplotlib`, `numpy`, `PySide6` (see `pyproject.toml`).
- Node.js 20+ and `@slidev/cli` (global or `npx`), `playwright-chromium`.
- `xvfb` for the offscreen GUI capture (`QT_QPA_PLATFORM=offscreen`).
- `pypdfium2` for the PDF page checks the build scripts run.
- `qrcode[pil]` to regenerate `public/qr_repo.png`.
- Lucide icons: `npm pack lucide-static && tar xzf lucide-static-*.tgz`.

## Regenerate the assets

```bash
# real GUI screenshots (1920x1080)
QT_QPA_PLATFORM=offscreen python -m presentation.generate_screenshots

# eight branded SVG visualisations
python -m presentation.build_visualizations

# panel crops, QR codes and the round member photos
python -m presentation.make_assets

# icons (after npm pack lucide-static)
python -m presentation.fetch_icons
```

## Notes

- Fonts (Tektur, Montserrat) are bundled: `public/fonts/` for Slidev,
  `assets/fonts/` for the visualisation script. The PPTX embeds them too
  (`fonts.py`), subset to the glyphs the deck uses, so a viewer without the
  families installed still shows the deck's own typefaces instead of Calibri.
- `node_modules/`, `dist/` and `.vite-cache/` are ignored by git.
- Every generated artifact is reproducible: the charts are written without a
  date stamp and with sequential ids (`build_visualizations.py`), and the PPTX
  package pins its zip timestamps to 1980-01-01 (`_freeze_zip` in
  `scripts/build_pptx.py`). A rebuild of unchanged input is byte-identical, so
  the `checksums.txt` entries stay valid. Rebuild `presentation_html.zip` from a
  clean `dist/` — Vite caches content-hashed copies of the charts.
- The deck uses the Madrigal palette, defined once as CSS custom properties in
  `style.css`. Dark theme: background `#0E1011`, surface `#1F2124`, body text
  `#F4F1EC`, secondary `#A8A29E`, accent `#D0603A`. Light theme (`html.light`):
  background `#FAF9F7`, surface `#FFFFFF`, text `#1C1917`, secondary `#57534E`,
  accent `#C2410C`. Rounded corners 12 px. Slide transition is a plain `fade`;
  build-ins are `v-click`, kept to at most three per slide.
- Slide 16 shows `public/screencast-poster.png` — a still baked from
  `screencast.mp4` (the sharpest of six sampled frames) with a small 40 px play
  badge in the bottom-right corner drawn in CSS; the frame stays an image so the
  build does not depend on a
  video codec.
