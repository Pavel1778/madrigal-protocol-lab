"""Cross-check the capture engine's TCP reassembly against tshark follow.

For every capture given on the command line this runs the project's capture
engine and ``tshark -q -z follow,tcp,raw,<k>`` for each stream, then compares
the reassembled bytes of both directions.

tshark's raw follow format is one hex line per data run: a line that starts with
a tab belongs to Node 1, any other hex line belongs to Node 0. Lines up to and
including the ``Node N:`` headers are ignored.

A divergence is expected on a capture with a hole in the middle: tshark inserts
a synthetic marker ``[<n> bytes missing in capture file]`` into the stream,
while this project keeps only observed bytes and records a ``gap`` diagnostic.
The runner reports such cases separately instead of counting them as failures.

Usage:
    python scripts/cross_check_tshark.py tests/corpus/real/**/*.pcap*
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.capture.cli import main as capture_main  # noqa: E402


def normalized(path: Path) -> dict:
    out = Path(tempfile.mkstemp(suffix=".json")[1])
    capture_main(["--pcap", str(path), "--out", str(out), "--quiet"])
    try:
        return json.loads(out.read_text())
    finally:
        out.unlink(missing_ok=True)


def tshark_streams(path: Path) -> dict[int, tuple[bytes, bytes]]:
    listed = subprocess.run(
        ["tshark", "-r", str(path), "-T", "fields", "-e", "tcp.stream"],
        capture_output=True, text=True,
    )
    indices = sorted({int(x) for x in listed.stdout.split() if x.strip().isdigit()})
    streams: dict[int, tuple[bytes, bytes]] = {}
    for index in indices:
        proc = subprocess.run(
            ["tshark", "-r", str(path), "-q", "-z", f"follow,tcp,raw,{index}"],
            capture_output=True, text=True,
        )
        node0, node1 = bytearray(), bytearray()
        for line in proc.stdout.splitlines():
            if not line or line.startswith(("=", "Follow:", "Filter:", "Node ")):
                continue
            target = node1 if line.startswith("\t") else node0
            target += bytes.fromhex(line.strip())
        streams[index] = (bytes(node0), bytes(node1))
    return streams


def gap_total(session: dict) -> int:
    total = 0
    for direction in session["directions"].values():
        for diagnostic in direction.get("diagnostics", []):
            if diagnostic.get("type") == "gap":
                total += diagnostic.get("length", 0)
    return total


def compare(path: Path) -> tuple[int, int, list[str]]:
    """Return (checked, mismatched, notes) for one capture."""
    data = normalized(path)
    streams = tshark_streams(path)
    checked = mismatched = 0
    notes: list[str] = []
    for session in data["sessions"]:
        a = base64.b64decode(session["directions"]["A_to_B"]["bytes_b64"])
        b = base64.b64decode(session["directions"]["B_to_A"]["bytes_b64"])
        checked += 1
        exact = any(n0 == a and n1 == b for n0, n1 in streams.values())
        if exact:
            continue
        # A gap-only divergence: tshark pads the hole with a marker of exactly
        # the recorded gap width, so the observed runs still match after the
        # marker is removed from both directions.
        gaps = gap_total(session)
        matched_despite_gap = False
        for n0, n1 in streams.values():
            removed = (len(n0) - len(_strip_tshark_markers(n0))) + (
                len(n1) - len(_strip_tshark_markers(n1))
            )
            if (
                _strip_tshark_markers(n0) == a
                and _strip_tshark_markers(n1) == b
                and removed == gaps
            ):
                matched_despite_gap = True
                break
        if matched_despite_gap:
            notes.append(
                f"{session['session_id']}: tshark inserts a {gaps}-byte "
                f"'bytes missing' marker; engine stores only observed bytes "
                f"and records gap(offset, length={gaps})"
            )
            continue
        mismatched += 1
        notes.append(
            f"{session['session_id']}: UNEXPECTED divergence "
            f"(engine A={len(a)}B B={len(b)}B; "
            f"tshark {[ (len(x), len(y)) for x, y in streams.values() ]})"
        )
    return checked, mismatched, notes


def _strip_tshark_markers(data: bytes) -> bytes:
    """Drop ``[<n> bytes missing in capture file]\\x00`` markers."""
    marker = b" bytes missing in capture file]"
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i : i + 1] == b"[":
            end = data.find(marker, i)
            if end != -1:
                i = end + len(marker) + 1
                continue
        out.append(data[i])
        i += 1
    return bytes(out)


def main(paths: list[str]) -> int:
    if not paths:
        print("usage: python scripts/cross_check_tshark.py <capture>...", file=sys.stderr)
        return 2
    total = mismatched = 0
    for raw in paths:
        path = Path(raw)
        checked, bad, notes = compare(path)
        total += checked
        mismatched += bad
        status = "OK" if bad == 0 else "MISMATCH"
        print(f"{status}  {path.name}: {checked} direction(s)")
        for note in notes:
            print(f"    {note}")
    print(f"\nstreams checked: {total}  unexpected divergences: {mismatched}")
    return 1 if mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
