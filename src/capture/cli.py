"""Command line entry point for the capture engine.

    python -m src.capture.cli --pcap path/to/cap.pcapng --out normalized.json

The command reads a PCAP or PCAPNG file, groups the TCP packets into sessions,
reassembles both directions of every session, and writes the normalized capture
described in ``docs/CONTRACT.md``.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import dpkt

from src.capture.export import export_capture
from src.capture.export_wireshark import export_reassembled_pcap
from src.capture.logging_setup import configure_logging
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
        "--wireshark-pcap",
        type=Path,
        default=None,
        help="also write reassembled streams as a pcap for inspection",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="do not print the summary",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="log progress to stderr",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    configure_logging(args.verbose)

    if not args.pcap.is_file():
        print(
            f"capture not found: {args.pcap} (check the path and try again)",
            file=sys.stderr,
        )
        return 2

    if args.stream and args.wireshark_pcap is not None:
        print(
            "--wireshark-pcap is not supported in --stream mode; "
            "run without --stream to write the reassembled pcap",
            file=sys.stderr,
        )
        return 2

    source_name = args.source_name if args.source_name is not None else str(args.pcap)

    try:
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

        if args.wireshark_pcap is not None:
            export_reassembled_pcap(
                capture.sessions,
                args.wireshark_pcap,
                streams=capture.streams,
            )
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except (OSError, dpkt.dpkt.Error, ValueError, struct.error) as exc:
        print(
            f"cannot read capture {args.pcap}: {exc} "
            "(expected a valid PCAP or PCAPNG file)",
            file=sys.stderr,
        )
        return 2

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
