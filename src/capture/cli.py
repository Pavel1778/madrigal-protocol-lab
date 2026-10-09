"""Command line entry point for the capture engine.

    python -m src.capture.cli --pcap path/to/cap.pcapng --out normalized.json

The command reads a PCAP or PCAPNG file, groups the TCP packets into sessions,
reassembles both directions of every session, and writes the normalized capture
described in ``docs/CONTRACT.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.capture.export import export_capture
from src.capture.pipeline import normalize
from src.capture.streaming import process_streaming


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.capture.cli",
        description="Normalize a PCAP or PCAPNG capture into the session contract.",
    )
    parser.add_argument("--pcap", required=True, type=Path, help="input capture file")
    parser.add_argument("--out", required=True, type=Path, help="output JSON file")
    parser.add_argument(
        "--source-name",
        default=None,
        help="value to record as source_file; defaults to the input path",
    )
    parser.add_argument(
        "--verify-checksums",
        action="store_true",
        help="report TCP checksum mismatches instead of ignoring them",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="process in blocks instead of holding every session at once",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10000,
        help="packets per block in streaming mode",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="do not print the summary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.pcap.is_file():
        print(f"capture not found: {args.pcap}", file=sys.stderr)
        return 2

    source_name = args.source_name if args.source_name is not None else str(args.pcap)

    if args.stream:
        stats = process_streaming(args.pcap, args.out, chunk_size=args.chunk_size)
        if not args.quiet:
            summary = {
                "mode": "streaming",
                "sessions": stats.sessions,
                "packets": stats.packets,
                "output": str(args.out),
                "diagnostics": 0,
            }
            print(json.dumps(summary))
        return 0

    capture = normalize(
        args.pcap,
        ignore_checksums=not args.verify_checksums,
    )

    export_capture(
        capture.sessions,
        args.out,
        source_file=source_name,
        capture_id=capture.capture_id,
        streams=capture.streams,
    )

    if not args.quiet:
        summary = {
            "capture_id": capture.capture_id,
            "sessions": len(capture.sessions),
            "output": str(args.out),
            "diagnostics": len(capture.diagnostics),
        }
        print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
