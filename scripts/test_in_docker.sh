#!/usr/bin/env bash
#
# Run the test suite in a clean Ubuntu container.
#
# The project targets Linux x86-64 and Python 3.12 or newer, so the suite is
# checked on both ends of that range in throwaway containers. The repository is
# copied into the image (not mounted) so the run sees exactly what is committed.
#
#   scripts/test_in_docker.sh                       # ubuntu:22.04, python 3.12
#   scripts/test_in_docker.sh ubuntu:24.04 3.13     # ubuntu:24.04, python 3.13
#
# Requires a working Docker daemon. If the daemon is not reachable by the
# current user, either join the docker group or run under sudo.

set -euo pipefail

IMAGE="${1:-ubuntu:22.04}"
PYTHON="${2:-3.12}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Use the daemon directly when the current user can reach it, otherwise fall
# back to sudo so the script also works on a host where the socket is root-only.
if docker info >/dev/null 2>&1; then
    DOCKER=(docker)
elif sudo -n docker info >/dev/null 2>&1; then
    DOCKER=(sudo docker)
else
    echo "no usable Docker daemon" >&2
    exit 1
fi

# Ubuntu 22.04 and 24.04 ship an older Python than the target, so the requested
# interpreter comes from the deadsnakes PPA when the distribution one is too
# old. The base image's python3 is used to bootstrap the venv. The build steps
# are chained on one line so the Dockerfile stays a single RUN instruction.
INNER="set -eux; export DEBIAN_FRONTEND=noninteractive; \
apt-get update; \
apt-get install -y --no-install-recommends ca-certificates python3 python3-venv software-properties-common gnupg; \
if ! command -v python${PYTHON} >/dev/null 2>&1; then \
  add-apt-repository -y ppa:deadsnakes/ppa; \
  apt-get update; \
  apt-get install -y --no-install-recommends python${PYTHON} python${PYTHON}-venv; \
fi; \
python${PYTHON} -m venv /venv; \
. /venv/bin/activate; \
pip install --upgrade pip; \
pip install -e '.[dev]'; \
pytest tests/ -q"

echo "image=${IMAGE} python=${PYTHON}"

"${DOCKER[@]}" build -t madrigal-portability-check -f - "${ROOT}" <<DOCKERFILE
FROM ${IMAGE}
COPY . /app
WORKDIR /app
RUN bash -c '${INNER}'
DOCKERFILE

