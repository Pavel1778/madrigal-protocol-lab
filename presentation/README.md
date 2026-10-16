# Presentation

The defense deck for «Лаборатория протоколов» (UMIRHack 2026, case #02,
Мадригал). The deck is authored as a single self-contained HTML file and printed
to PDF and PPTX; the visualisations and the GUI screenshots are built from the
repository's own code. Every number is from `docs/METRICS.md`.

## Files

| Path | What it is |
| --- | --- |
| `Презентация Madrigal Protocol Lab.html` | the deck source, 15 slides, dark theme, all images inlined |
| `Презентация Madrigal Protocol Lab (светлая).html` | the same deck in the light theme |
| `slides.pdf` | the printed export, 15 pages, 2560×1440 |
| `slide-light.pdf` | the same deck exported for a washed-out projector |
| `slide.pptx` | the deck as a PPTX, one full-bleed image per slide, zip timestamps pinned to 1980-01-01 |
| `slide-light.pptx` | the light variant as a PPTX |
| `Презентация Madrigal Protocol Lab (13 слайдов).html` | the 13-slide cut, dark theme (`make_alt_deck.py`) |
| `Презентация Madrigal Protocol Lab (13 слайдов, светлая).html` | the same cut in the light theme |
| `slides-13.pdf` | the printed export of the 13-slide cut, 13 pages |
| `slide-light-13.pdf` | the light 13-slide export |
| `slide-13.pptx` | the 13-slide cut as a PPTX |
| `slide-light-13.pptx` | the light 13-slide cut as a PPTX |
| `screenshots/` | 11 real GUI captures at 1920×1080 (`generate_screenshots.py`), indexed below |
| `demo/screencast-short.mp4` | the core cycle in 54 s, cut from `screencast.mp4` (apply rule → counterexample → alternatives → corpus) |
| `demo/screencast-short.gif` | the same 54 s at 960×540, 6 fps, 96 colours (≈0.9 MB) for Markdown and GitHub |
| `assets/` | 8 branded SVG visualisations, dark and light, plus PNG copies |
| `assets/madrigal-logo.png` | the case owner's «Мадригал» wordmark, shown on the cover and closing slides |
| `assets/madrigal-mark.png` | the square monogram used as a watermark |
| `assets/brand/` | three abstract background textures from the case owner's site |
| `public/` | assets the deck serves: fonts, logo, QR codes, member photos |
| `public/screencast-poster.png` | the poster frame shown on slide 13 under `screencast.mp4` |
| `defense_script.md` | the 5- and 10-minute speaker routes, one section per slide |
| `defense_guide.md` | the author's technical guide: plain-language explanation, module map, demo walkthrough, glossary, judge questions and self-check |
| `Q_and_A.md` | the questions asked after the talk and the prepared answers |
| `VIDEO.md` | shot list for the reserve screen recording |
| `screencast.mp4` | the reserve recording of a full run (3:40, H.264, no sound), embedded on slide 13 |
| `record_demo.py` | drives the real window through the demo scenario for the recording |
| `generate_screenshots.py` | renders the eleven window captures offscreen |
| `make_assets.py` | panel crops, QR codes and the round member photos |
| `make_brand.py` | builds the «Мадригал» wordmark and monogram |
| `generate_qr.py` | writes the repository and release QR codes |
| `make_deck_pptx.py` | packages a rendered deck PDF into a PPTX, one full-bleed page per slide |
| `make_alt_deck.py` | derives the 13-slide cut from the 15-slide master; the master is left untouched |

## Building the deck

The HTML is the source of truth. Both PDFs are printed from it with headless
Chromium; the `@media print` block in each file pins the page to 2560×1440 pt
(16:9) with no margins and one slide per page, so the content fills the sheet.
Without that block Chromium falls back to Letter, drops slides and leaves the
lower half of every page blank. The PPTX packages one rendered page per slide
with python-pptx. The dark theme is the HTML as authored; the light theme is a
recolour of the same markup with the brand marks left dark and the surfaces
lifted, so the layout and the copy are identical between the two.

```bash
# print each theme to PDF (Chromium must be on PATH)
chromium --headless=new --no-pdf-header-footer --print-to-pdf=slides.pdf \
  "Презентация Madrigal Protocol Lab.html"
chromium --headless=new --no-pdf-header-footer --print-to-pdf=slide-light.pdf \
  "Презентация Madrigal Protocol Lab (светлая).html"

# package the PDFs into PPTX (from the repository root)
python -m presentation.make_deck_pptx presentation/slides.pdf presentation/slide.pptx
python -m presentation.make_deck_pptx presentation/slide-light.pdf presentation/slide-light.pptx
```

### The 13-slide cut

If the defence brief fixes the deck at 13 slides, `make_alt_deck.py` derives
that cut from the 15-slide master without touching it. Two slides are folded:
the problem statement and «Дано и требуется» become one «Пакет, сообщение и
задача» slide, and «Гипотеза ≠ Правило» and «От интерпретации можно вернуться к
данным» become one core slide. The remaining slides keep their content and are
renumbered.

```bash
# regenerate the HTML, then print and package as above
python -m presentation.make_alt_deck
chromium --headless=new --no-pdf-header-footer --print-to-pdf=slides-13.pdf \
  "Презентация Madrigal Protocol Lab (13 слайдов).html"
chromium --headless=new --no-pdf-header-footer --print-to-pdf=slide-light-13.pdf \
  "Презентация Madrigal Protocol Lab (13 слайдов, светлая).html"
python -m presentation.make_deck_pptx presentation/slides-13.pdf presentation/slide-13.pptx
python -m presentation.make_deck_pptx presentation/slide-light-13.pdf presentation/slide-light-13.pptx
```

## Regenerate the assets

```bash
# real GUI screenshots (1920x1080)
QT_QPA_PLATFORM=offscreen python -m presentation.generate_screenshots

# panel crops, QR codes and the round member photos
python -m presentation.make_assets

# the «Мадригал» wordmark and monogram
python -m presentation.make_brand
```

## Demo materials

The reserve recording `screencast.mp4` is 3:40 and covers the whole run. For a
shorter take, `demo/screencast-short.mp4` (54 s) and its GIF cut the core cycle
out of it: apply rule v1, open a counterexample, show the alternative readings,
verify v1 over the corpus, then apply v2 and recheck with no counterexamples.

```bash
# rebuild the short clip and its GIF from the reserve recording
ffmpeg -y -ss 72.5 -t 54 -i screencast.mp4 -c:v libx264 -preset slow -crf 24 \
  -pix_fmt yuv420p -an demo/screencast-short.mp4
ffmpeg -y -i demo/screencast-short.mp4 \
  -vf "fps=6,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=3" \
  -loop 0 demo/screencast-short.gif
```

The recording itself comes from `record_demo.py`, which drives the real window
through the scenario under a display. The GIF is a compact fallback; the MP4 is
the primary material.

## Screenshot index

The eleven captures under `screenshots/` are rendered offscreen by
`generate_screenshots.py` against the captures in `tests/corpus/reference_export/`
and the rules in `examples/`. Each one shows a real state of the window.

| File | What it shows |
| --- | --- |
| `01_main.png` | the main window with the reference capture and rule v1 loaded, session `s1`, direction `A_to_B` |
| `02_sessions.png` | the session tree with its diagnostics on the defective capture |
| `03_hex_matched.png` | the hex view with matched bytes highlighted under rule v1 |
| `04_hex_gap.png` | the hex view over a reassembly gap on the defective capture |
| `05_validation.png` | the validation panel with a counterexample opened at its bytes |
| `06_compare.png` | two messages compared byte by byte |
| `07_rule_editor.png` | the rule editor with rule v2 loaded |
| `08_diff.png` | the v1 to v2 version diff over the whole capture |
| `09_provenance.png` | the provenance bar for a single byte: packet index, sequence, time |
| `10_hypotheses.png` | the hypotheses tab with the alternative readings and their scores |
| `11_version_diff.png` | the text view of the v1 to v2 diff |

## Notes

- The deck is one file: fonts, logos, QR codes, charts and the reserve screencast
  are all inlined as `data:` URIs, so it opens, plays and prints without a web
  server and without the rest of the repository.
- Fonts (Tektur, Montserrat, JetBrains Mono) are bundled under `public/fonts/`
  and shipped in the HTML, so a machine without the families installed still
  shows the deck's own typefaces.
- The two member photos on slide 2 come from `assets/team/`; `make_assets.py`
  crops them to the round `public/avatar_*_round.png` the slide uses.
- The deck uses the Madrigal palette: background `#131516`, panels `#1D1D1D`,
  accent `#6D071F`, text `#E0E0E0`, secondary `#9F9F9F`; corners 4 px. The light
  theme lifts the surfaces and keeps the accent.
- The PPTX pins its zip timestamps to 1980-01-01, so two builds of the same deck
  are byte-identical and the file does not churn in git.
