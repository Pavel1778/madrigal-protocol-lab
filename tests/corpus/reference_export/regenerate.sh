#!/usr/bin/env bash
# Rebuild the reference normalized exports from the corpus captures.
#
# Run from anywhere; the script resolves the repository root itself. The
# generator validates every document against docs/schemas/capture.schema.json
# before writing it, so a build that succeeds is a build that conforms.
#
# Exports at or above 1 MiB are written gzip compressed and unpacked back to
# plain .json here, so callers always find *.normalized.json on disk.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

python3 -m scripts.generate_reference_export

# Expand any compressed export so consumers never have to handle gzip.
for archive in tests/corpus/reference_export/*.json.gz; do
  [ -e "$archive" ] || continue
  gunzip -kf "$archive"
done
