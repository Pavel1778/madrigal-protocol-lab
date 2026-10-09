"""Write the reference normalized exports of the corpus.

These files are the input the protocol module and the GUI use for their corpus
smoke test and reference investigation, so they must be reproducible. This
script rebuilds them from the captures in ``tests/corpus`` and validates each
one against ``docs/schemas/capture.schema.json`` before writing it, so a broken
export is never published.

    python -m scripts.generate_reference_export

The exports are small (well under a megabyte), so they are written as plain
JSON. If a future record grows past the threshold, this script writes it gzip
compressed with a ``.json.gz`` suffix instead.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.capture.export import export_capture
from src.capture.pipeline import normalize

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "corpus"
OUT_DIR = CORPUS / "reference_export"
SCHEMA = ROOT / "docs" / "schemas" / "capture.schema.json"

RECORDS = (
    "corpus_capture_01.pcapng",
    "corpus_capture_02.pcapng",
    "corpus_capture_defects.pcapng",
)

# Files at or above this size are stored gzip compressed.
GZIP_THRESHOLD = 1 << 20


def _write(path: Path, document: dict) -> None:
    text = json.dumps(document, ensure_ascii=True, separators=(",", ":"))
    if len(text) >= GZIP_THRESHOLD:
        path = path.with_suffix(".json.gz")
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(text)
    else:
        path.write_text(text + "\n", encoding="utf-8")


def generate(out_dir: Path = OUT_DIR) -> list[Path]:
    """Build every reference export and return the written paths."""

    out_dir.mkdir(parents=True, exist_ok=True)
    validator = Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8"))
    )
    written: list[Path] = []
    for name in RECORDS:
        capture = normalize(CORPUS / name)
        out_path = out_dir / f"{Path(name).stem}.normalized.json"
        export_capture(
            capture.sessions,
            out_path,
            source_file=f"tests/corpus/{name}",
            capture_id=capture.capture_id,
            streams=capture.streams,
        )
        document = json.loads(out_path.read_text(encoding="utf-8"))
        validator.validate(document)
        written.append(out_path)
    return written


def main() -> int:
    for path in generate():
        size = path.stat().st_size
        print(f"{path.relative_to(ROOT)} ({size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
