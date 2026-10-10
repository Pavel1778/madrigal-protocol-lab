# Presentation

The defense deck for «Лаборатория протоколов» (UMIRHack 2026, case #02,
Мадригал). The deck is authored in Markdown and rendered by
[Slidev](https://sli.dev/); the visualisations and the GUI screenshots are built
from the repository's own code. Every number is from `docs/METRICS.md`.

## Files

| Path | What it is |
| --- | --- |
| `slides.md` | the deck source (18 slides, Madrigal theme, `v-click` build-ins) |
| `style.css` | the Madrigal theme: palette, Tektur + Montserrat, layout |
| `slides.pdf` | the printed export, 18 pages (archive copy for submission) |
| `slides.pptx` | the PPTX export (26 pages: 18 slides plus the build-in steps) |
| `screenshots/` | 11 real GUI captures at 1920×1080 (`generate_screenshots.py`) |
| `assets/` | 6 branded SVG visualisations (`build_visualizations.py`) |
| `icons/` | Lucide line icons used by the deck (`fetch_icons.py`) |
| `public/` | assets the deck serves: fonts, logo, QR code |
| `defense_script.md` | the 8-minute speaker script, one section per slide |
| `VIDEO.md` | shot list for the reserve screen recording |
| `export_pdf.sh` | exports `slides.pdf` with a retry for the Slidev race |
| `bundle_html.py` | packs the built `dist/` into `presentation_html.zip` |

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

# six branded SVG visualisations
python -m presentation.build_visualizations

# icons (after npm pack lucide-static)
python -m presentation.fetch_icons
```

## Notes

- Fonts (Tektur, Montserrat) are bundled: `public/fonts/` for Slidev,
  `assets/fonts/` for the visualisation script.
- `node_modules/`, `dist/` and `.vite-cache/` are ignored by git.
- The deck uses the Madrigal palette. Brand fills stay `#131516` / `#6D071F` /
  `#410913 → #A2391D`; the page background is `#0E1011` and body text is
  `#F0F0F0`, so every label passes WCAG AA. The accent orange used for links and
  inline code is `#E0603A` (the dark `#A2391D` is decoration only). Rounded
  corners 4–5 px. Slide transition is `slide-left`; build-ins are `v-click`.
