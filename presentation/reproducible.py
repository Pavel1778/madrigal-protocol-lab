"""Make the generated OOXML packages byte-identical across builds.

python-pptx stamps every zip entry with the wall clock, so two builds of the
same deck differ byte-for-byte and a committed ``.pptx`` churns in git on every
run. Pinning the entry timestamps leaves the parts themselves untouched.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

EPOCH = (1980, 1, 1, 0, 0, 0)


def freeze_zip(path: Path) -> None:
    """Rewrite ``path`` in place with fixed entry timestamps."""
    buffer = io.BytesIO(path.read_bytes())
    with zipfile.ZipFile(buffer) as src, zipfile.ZipFile(
        path, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for item in src.infolist():
            info = zipfile.ZipInfo(item.filename, date_time=EPOCH)
            info.compress_type = item.compress_type
            info.external_attr = item.external_attr
            dst.writestr(info, src.read(item.filename))
