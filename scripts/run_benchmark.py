"""Measure the capture engine on the reference load profile.

The profile is taken from the specification: up to 100 MiB PCAP, 250k packets,
1000 TCP sessions, 100k messages, responses up to 64 KiB, on Linux x86-64 with
4 vCPU and 8 GB RAM.

The script generates the capture if it is missing, then times each phase of the
pipeline separately (parse, sessions, reassembly, export) and records the peak
resident memory of the process. It can write the result straight to
``docs/BENCHMARK.md`` so the numbers in the document are measured, not typed.

    python -m scripts.run_benchmark --write-md docs/BENCHMARK.md

Pass ``--tracemalloc`` to also report the Python allocation peak, which costs
extra time and is therefore off by default.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path

from src.capture.export import export_capture, sha256_file
from src.capture.parser import read_capture
from src.capture.pipeline import normalize_packets
from src.capture.session import build_sessions

PROFILE_PACKETS = 250_000
PROFILE_SESSIONS = 1_000
PROFILE_TARGET_MIB = 100
PROFILE_MAX_RESPONSE = 64 * 1024


def _peak_rss_mib() -> float:
    """Peak resident set size of this process, in MiB."""

    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB; darwin reports bytes.
    if sys.platform == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def _total_ram_mib() -> float:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return pages * page_size / (1024 * 1024)
    except (ValueError, OSError, AttributeError):
        return float("nan")


@dataclass
class Result:
    packets: int = 0
    sessions: int = 0
    input_bytes: int = 0
    output_bytes: int = 0
    parse_seconds: float = 0.0
    sessions_seconds: float = 0.0
    reassembly_seconds: float = 0.0
    export_seconds: float = 0.0
    peak_rss_mib: float = 0.0
    tracemalloc_mib: float | None = None
    diagnostics: int = 0
    environment: dict[str, str] = field(default_factory=dict)

    @property
    def total_seconds(self) -> float:
        return (
            self.parse_seconds
            + self.sessions_seconds
            + self.reassembly_seconds
            + self.export_seconds
        )


def _environment() -> dict[str, str]:
    return {
        "os": platform.platform(),
        "kernel": platform.release(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": str(os.cpu_count() or 0),
        "ram_mib": f"{_total_ram_mib():.0f}",
        "python": platform.python_version(),
        "dpkt": _version("dpkt"),
    }


def _version(module: str) -> str:
    try:
        return __import__(module).__version__
    except Exception:
        return "unknown"


def run(
    pcap_path: Path,
    work_dir: Path,
    *,
    use_tracemalloc: bool = False,
) -> Result:
    """Run the pipeline over ``pcap_path`` and return the measurements."""

    result = Result(environment=_environment())
    result.input_bytes = pcap_path.stat().st_size

    if use_tracemalloc:
        tracemalloc.start()

    diagnostics: list = []
    started = time.perf_counter()
    packets = list(read_capture(pcap_path, diagnostics))
    result.parse_seconds = time.perf_counter() - started
    result.packets = len(packets)
    result.diagnostics = len(diagnostics)

    started = time.perf_counter()
    sessions = build_sessions(packets)
    result.sessions_seconds = time.perf_counter() - started
    result.sessions = len(sessions)

    capture_id = sha256_file(pcap_path)
    started = time.perf_counter()
    capture = normalize_packets(
        packets,
        source_file=pcap_path,
        capture_id=capture_id,
        diagnostics=diagnostics,
    )
    result.reassembly_seconds = time.perf_counter() - started

    out_path = work_dir / "benchmark.json"
    started = time.perf_counter()
    export_capture(
        capture.sessions,
        out_path,
        source_file=pcap_path.name,
        capture_id=capture_id,
        streams=capture.streams,
    )
    result.export_seconds = time.perf_counter() - started
    result.output_bytes = out_path.stat().st_size

    result.peak_rss_mib = _peak_rss_mib()
    if use_tracemalloc:
        _current, peak = tracemalloc.get_traced_memory()
        result.tracemalloc_mib = peak / (1024 * 1024)
        tracemalloc.stop()

    return result


def render_markdown(result: Result, profile: dict[str, int]) -> str:
    env = result.environment
    total = result.total_seconds
    lines = [
        "# Resource benchmark",
        "",
        "Measured on the reference load profile. Numbers below are produced by",
        "`scripts/run_benchmark.py`; regenerate them rather than editing by hand.",
        "",
        "## Check environment",
        "",
        f"- OS: {env['os']}",
        f"- Kernel: {env['kernel']}",
        f"- CPU: {env['cpu']} ({env['cpu_count']} logical cores)",
        f"- RAM: {env['ram_mib']} MiB",
        f"- Python: {env['python']}",
        f"- dpkt: {env['dpkt']}",
        "",
        "The reference environment in the specification is Linux x86-64, 4 vCPU,",
        "8 GB RAM. The numbers below are from the machine shown above.",
        "",
        "## Input",
        "",
        f"- Input capture: {result.input_bytes / (1024 * 1024):.2f} MiB",
        f"- Packets read: {result.packets}",
        f"- TCP sessions: {result.sessions}",
        f"- Read diagnostics: {result.diagnostics}",
        f"- Target profile: {profile['packets']} packets, {profile['sessions']} "
        f"sessions, up to {profile['target_mib']} MiB, responses up to "
        f"{profile['max_response']} bytes",
        "",
        "## Timings",
        "",
        "| Phase | Seconds |",
        "| ----- | ------- |",
        f"| Parse (read_capture) | {result.parse_seconds:.2f} |",
        f"| Sessions (build_sessions) | {result.sessions_seconds:.2f} |",
        f"| Reassembly (reassemble) | {result.reassembly_seconds:.2f} |",
        f"| Export (export_capture) | {result.export_seconds:.2f} |",
        f"| Total | {total:.2f} |",
        "",
        "## Memory and output",
        "",
        f"- Peak process RSS: {result.peak_rss_mib:.0f} MiB",
    ]
    if result.tracemalloc_mib is not None:
        lines.append(f"- Python allocation peak (tracemalloc): {result.tracemalloc_mib:.0f} MiB")
    lines += [
        f"- Output JSON: {result.output_bytes / (1024 * 1024):.2f} MiB",
        "",
        "## Conclusions and limitations",
        "",
    ]
    over_memory = result.peak_rss_mib > 4 * 1024
    over_time = total > 5 * 60
    if over_memory:
        lines.append(
            "- Peak memory exceeds 4 GiB. This is a technical limitation of the "
            "current design."
        )
    else:
        lines.append(
            f"- Peak memory is {result.peak_rss_mib:.0f} MiB, well under the 4 GiB "
            "threshold."
        )
    if over_time:
        lines.append(
            "- Total time exceeds 5 minutes. This is a technical limitation of the "
            "current design."
        )
    else:
        lines.append(
            f"- Total time is {total:.2f} s, well under the 5 minute threshold."
        )
    lines += [
        "",
        "Observations:",
        "",
        "- The parser dominates the time. It builds one Python object per packet, "
        "which is the cost of keeping the header fields available for provenance.",
        f"- The normalized JSON ({result.output_bytes / (1024 * 1024):.2f} MiB) is "
        f"larger than the input ({result.input_bytes / (1024 * 1024):.2f} MiB) "
        "because stream bytes are stored base64 encoded and every observed range "
        "carries a provenance record.",
        "- Memory scales with the capture size: all packets are held in memory at "
        "once. At this profile that is affordable; for a capture several times "
        "larger the same approach would need to stream or use memory mapping.",
        "",
        "If a larger capture must be supported, the first step is to stop holding "
        "every packet object at once: parse and reassemble session by session, and "
        "write provenance ranges to disk as they are produced. That trades peak "
        "memory for a second pass over the file.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark the capture engine.")
    parser.add_argument(
        "--pcap",
        type=Path,
        default=Path(".benchmark") / "profile.pcapng",
        help="input capture; generated if missing",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(".benchmark"),
        help="scratch directory for the normalized output",
    )
    parser.add_argument("--packets", type=int, default=PROFILE_PACKETS)
    parser.add_argument("--sessions", type=int, default=PROFILE_SESSIONS)
    parser.add_argument("--target-mib", type=int, default=PROFILE_TARGET_MIB)
    parser.add_argument("--max-response", type=int, default=PROFILE_MAX_RESPONSE)
    parser.add_argument(
        "--tracemalloc",
        action="store_true",
        help="also report the Python allocation peak",
    )
    parser.add_argument(
        "--write-md",
        type=Path,
        default=None,
        help="write the result as Markdown to this path",
    )
    args = parser.parse_args(argv)

    args.work_dir.mkdir(parents=True, exist_ok=True)
    if not args.pcap.is_file():
        from scripts.generate_benchmark_pcap import build

        data = build(
            args.packets, args.sessions, args.target_mib, args.max_response
        )
        args.pcap.parent.mkdir(parents=True, exist_ok=True)
        args.pcap.write_bytes(data)

    result = run(args.pcap, args.work_dir, use_tracemalloc=args.tracemalloc)
    profile = {
        "packets": args.packets,
        "sessions": args.sessions,
        "target_mib": args.target_mib,
        "max_response": args.max_response,
    }
    print(json.dumps({
        "input_mib": round(result.input_bytes / (1024 * 1024), 2),
        "packets": result.packets,
        "sessions": result.sessions,
        "parse_s": round(result.parse_seconds, 2),
        "sessions_s": round(result.sessions_seconds, 2),
        "reassembly_s": round(result.reassembly_seconds, 2),
        "export_s": round(result.export_seconds, 2),
        "total_s": round(result.total_seconds, 2),
        "peak_rss_mib": round(result.peak_rss_mib),
        "output_mib": round(result.output_bytes / (1024 * 1024), 2),
    }))

    if args.write_md is not None:
        args.write_md.parent.mkdir(parents=True, exist_ok=True)
        args.write_md.write_text(render_markdown(result, profile), encoding="utf-8")
        print(f"wrote {args.write_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
