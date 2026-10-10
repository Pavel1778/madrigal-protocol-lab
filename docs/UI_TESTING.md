# Interface tests

The interface is verified on three levels, all headless.

## End-to-end locale tests

`tests/ui/e2e/test_locale_en.py` and `test_locale_ru.py` drive the real window
through its public `set_language` and read every visible caption back: the
window title, the menu titles, the right-hand tabs, the group boxes, the
direction label, the legend chips, the session-tree header, the rule status
line. The English module asserts the source strings; the Russian module asserts
the strings in the catalogue, written out literally so a broken translation
cannot make the test agree with itself.

## Snapshot tests

`tests/ui/snapshot/` renders the window to an image and compares it with a
committed baseline, across the four combinations of theme (`dark`, `light`) and
language (`en`, `ru`), one image per supported window size:

    1024x768, 1280x800, 1366x768, 1440x900, 1600x900

`test_zoom_states.py` covers the three documented zoom levels (100, 150, 200
percent) and checks that the rendered image actually changes between them.

A render is pinned four ways so its layout is reproducible: the language,
the theme, the zoom and the window size are all set explicitly, and the window
is offscreen. `tests/ui/conftest.py` redirects `XDG_CONFIG_HOME` and pins
`LANG`, so neither the developer's saved preferences nor the desktop locale can
move the result.

The comparison is perceptual. A window rendered offscreen does not rasterise its
glyphs identically across Qt builds and platforms, so a byte comparison passes
on the machine that recorded a baseline and fails on a runner that draws the
same window a shade differently. Both frames are instead reduced to greyscale
and pooled into 8x8 blocks; a frame passes only when the mean difference is
under a small limit and no more than a small fraction of blocks differ strongly.
That absorbs antialiasing and a focus ring, while a swapped theme, a changed
layout or a resized frame moves whole regions a lot and fails. The limits live in
`tests/ui/snapshot/_diff.py`.

### Baselines

Baselines live in `tests/ui/snapshot/baselines` and are committed. Regenerate
one on purpose with:

```
MADRIGAL_UPDATE_SNAPSHOTS=1 pytest tests/ui/snapshot
```

A missing baseline is written and the test skipped, so the first run on a clean
checkout records rather than fails. A baseline that differs beyond tolerance
writes the actual image, a highlighted difference image and a text file with the
measured metrics under `.snapshot-actual` and fails with the paths. The CI job
publishes that directory as an artefact; the containing directory starts with a
dot, so the upload step sets `include-hidden-files: true`.

## No-state-loss tests

`tests/ui/test_no_state_loss.py` captures the window state — session,
direction, open capture, loaded rule, message rows, session rows — and compares
it before and after a language switch, a theme switch, a zoom change, a resize
and the round trips. Nothing may be rebuilt and nothing may be dropped.

## Running locally

```
QT_QPA_PLATFORM=offscreen LANG=C.UTF-8 pytest tests/ui
```

The `tests/ui/conftest.py` module sets the offscreen platform and the locale
itself when they are not already set, so the plain `pytest tests/ui` also works.

## In CI

The `ui-tests` job runs `tests/ui` on a matrix of both runner images
(`ubuntu-latest`, `ubuntu-22.04`) and both interpreters (`3.12`, `3.13`), always
offscreen. It installs the Qt runtime libraries the runner image lacks,
publishes the interface coverage as an artefact, uploads `.snapshot-actual` when
a snapshot fails, and posts the list of changed images to the pull request.
