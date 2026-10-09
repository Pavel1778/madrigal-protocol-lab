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
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . .

RUN pip install --upgrade pip && pip install -e ".[dev]"

CMD ["python", "-m", "src.ui.main_window"]
