# Container image for the protocol laboratory.
#
# The image carries the source, the tests, the corpus and the pinned
# dependencies, so the suite can be run and the window can be started without a
# host setup. The suite needs no display; the window needs one, which is what
# the volume and the environment variable below are for.
#
#   docker build -t madrigal-lab .
#   docker run --rm madrigal-lab pytest tests/ -q
#   docker run --rm -e QT_QPA_PLATFORM=offscreen madrigal-lab \
#       python -m src.ui.main_window --capture \
#       tests/corpus/reference_export/corpus_capture_01.normalized.json
#
# A visible window additionally needs an X or Wayland socket, for example
# `-v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY`.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QT_QPA_PLATFORM=offscreen

WORKDIR /app

# Runtime libraries for the Qt window: glib, GL, xcb and the X client stack.
# The suite runs without them, but the default CMD starts the window, so they
# belong in the image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        libegl1 \
        libxkbcommon0 \
        libdbus-1-3 \
        libxcb1 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-xinerama0 \
        libfontconfig1 \
        libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --upgrade pip && pip install -e ".[dev]"

CMD ["python", "-m", "src.ui.main_window"]
