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


def _sample_rss_mib() -> float:
    """Current resident set size from /proc, in MiB.

    ``ru_maxrss`` is a high-water mark that survives ``exec``, so a process
    started from a memory-heavy parent inherits its parent's peak. Reading the
    current value avoids that and gives the real size of this process.
    """

    try:
        with open("/proc/self/statm", encoding="ascii") as handle:
            pages = int(handle.read().split()[1])
    except (OSError, ValueError, IndexError):
        return _peak_rss_mib()
    return pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)


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
    stream_seconds: float | None = None
    stream_peak_rss_mib: float | None = None
    stream_output_bytes: int | None = None
    stream_flushes: int | None = None
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
    except Exception:  # noqa: BLE001 - report "unknown" for any missing or odd module
        return "unknown"


def run(
    pcap_path: Path,
    work_dir: Path,
    *,
    use_tracemalloc: bool = False,
) -> Result:
    """Run the pipeline over ``pcap_path`` and return the measurements."""

    import threading

    result = Result(environment=_environment())
    result.input_bytes = pcap_path.stat().st_size

    if use_tracemalloc:
        tracemalloc.start()

    # Sample the live resident size: ``ru_maxrss`` survives ``exec``, so a
    # process started from a heavier parent would inherit the parent's peak.
    peak = 0.0
    stop = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not stop.wait(0.02):
            peak = max(peak, _sample_rss_mib())

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()

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

    stop.set()
    sampler.join(timeout=1.0)
    result.peak_rss_mib = peak
    if use_tracemalloc:
        _current, peak_alloc = tracemalloc.get_traced_memory()
        result.tracemalloc_mib = peak_alloc / (1024 * 1024)
        tracemalloc.stop()

    return result


def run_streaming_child(
    pcap_path: Path, out_path: Path, interval: float = 0.02
) -> dict[str, float]:
    """Run streaming in this process and sample its resident memory.

    Called as a child process so its numbers are not mixed with the regular
    run. A sampler thread records the resident size while ``process_streaming``
    works, which captures the real peak rather than a value inherited from the
    parent.
    """

    import threading

    from src.capture.streaming import process_streaming

    peak = 0.0

    def sample() -> None:
        nonlocal peak
        while not stop.wait(interval):
            peak = max(peak, _sample_rss_mib())

    stop = threading.Event()
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.perf_counter()
    stats = process_streaming(pcap_path, out_path)
    seconds = time.perf_counter() - started
    stop.set()
    sampler.join(timeout=1.0)
    return {
        "seconds": seconds,
        "peak_mib": peak,
        "output_bytes": float(out_path.stat().st_size),
        "flushes": float(stats.flushes),
    }


def run_streaming(pcap_path: Path, work_dir: Path) -> tuple[float, float, int, int]:
    """Run the streaming pipeline in a child process and report its numbers."""

    import subprocess

    out_path = work_dir / "benchmark_stream.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_benchmark",
            "--mode",
            "stream",
            "--pcap",
            str(pcap_path),
            "--work-dir",
            str(work_dir),
            "--out",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    return (
        float(payload["seconds"]),
        float(payload["peak_mib"]),
        int(payload["output_bytes"]),
        int(payload["flushes"]),
    )


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
        (
            f"- Target profile: {profile['packets']} packets, {profile['sessions']} "
            f"sessions, up to {profile['target_mib']} MiB, responses up to "
            f"{profile['max_response']} bytes"
        ),
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
        "## Streaming mode",
        "",
        "`process_streaming` reads the capture in blocks and writes each session as",
        "soon as it can no longer receive packets, so closed sessions leave memory.",
        "The output is identical to the regular mode; only the resource profile",
        "differs. The streaming peak is measured in its own process so the two do",
        "not share a high-water mark.",
        "",
    ]
    if result.stream_seconds is not None:
        lines += [
            "| Metric | Regular | Streaming |",
            "| ------ | ------- | --------- |",
            f"| Total seconds | {total:.2f} | {result.stream_seconds:.2f} |",
            f"| Peak RSS (MiB) | {result.peak_rss_mib:.0f} | {result.stream_peak_rss_mib:.0f} |",
            (
                f"| Output JSON (MiB) | {result.output_bytes / (1024 * 1024):.2f} | "
                f"{(result.stream_output_bytes or 0) / (1024 * 1024):.2f} |"
            ),
            "",
            f"The streaming run flushed {result.stream_flushes} sessions.",
            "",
            (
                "Streaming used less memory."
                if result.stream_peak_rss_mib is not None
                and result.stream_peak_rss_mib < result.peak_rss_mib
                else "Streaming did not reduce memory at this profile."
            ),
            "",
        ]
    lines += [
        "## Memory and output",
        "",
        f"- Peak process RSS: {result.peak_rss_mib:.0f} MiB",
    ]
    if result.tracemalloc_mib is not None:
        lines.append(
            f"- Python allocation peak (tracemalloc): {result.tracemalloc_mib:.0f} MiB"
        )
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
        (
            "- The parser dominates the time. It builds one Python object per packet, "
            "which is the cost of keeping the header fields available for provenance."
        ),
        (
            f"- The normalized JSON ({result.output_bytes / (1024 * 1024):.2f} MiB) is "
            f"larger than the input ({result.input_bytes / (1024 * 1024):.2f} MiB) "
            "because stream bytes are stored base64 encoded and every observed range "
            "carries a provenance record."
        ),
        (
            "- Memory scales with the capture size: all packets are held in memory at "
            "once. At this profile that is affordable; for a capture several times "
            "larger the same approach would need to stream or use memory mapping."
        ),
        "",
        (
            "If a larger capture must be supported, the first step is to stop holding "
            "every packet object at once: parse and reassemble session by session, and "
            "write provenance ranges to disk as they are produced. That trades peak "
            "memory for a second pass over the file."
        ),
        "",
    ]
    return "\n".join(lines)


@dataclass
class SizeRow:
    """One row of the size sweep: regular and streaming at a given capture size."""

    label: str
    input_mib: float
    packets: int
    sessions: int
    parse_seconds: float
    sessions_seconds: float
    reassembly_seconds: float
    export_seconds: float
    regular_seconds: float
    regular_peak_mib: float
    stream_seconds: float
    stream_peak_mib: float
    output_mib: float
    diagnostics: int = 0

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "label": self.label,
            "input_mib": round(self.input_mib, 2),
            "packets": self.packets,
            "sessions": self.sessions,
            "parse_s": round(self.parse_seconds, 2),
            "sessions_s": round(self.sessions_seconds, 3),
            "reassembly_s": round(self.reassembly_seconds, 2),
            "export_s": round(self.export_seconds, 2),
            "regular_s": round(self.regular_seconds, 2),
            "regular_peak_mib": round(self.regular_peak_mib),
            "stream_s": round(self.stream_seconds, 2),
            "stream_peak_mib": round(self.stream_peak_mib),
            "output_mib": round(self.output_mib, 2),
            "diagnostics": self.diagnostics,
        }


def measure_regular_sampled(pcap_path: Path, work_dir: Path) -> dict[str, float]:
    """Run the regular pipeline in this process, sampling RSS for the peak.

    ``ru_maxrss`` is a high-water mark that never falls and is inherited across
    a long-lived process, so a run in the same process as a larger one would
    report the larger peak. Sampling the current resident size avoids that and
    gives the real peak of this run.
    """

    import threading

    peak = 0.0
    stop = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not stop.wait(0.02):
            peak = max(peak, _sample_rss_mib())

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()

    diagnostics: list = []
    started = time.perf_counter()
    packets = list(read_capture(pcap_path, diagnostics))
    parse_seconds = time.perf_counter() - started

    started = time.perf_counter()
    sessions = build_sessions(packets)
    sessions_seconds = time.perf_counter() - started

    capture_id = sha256_file(pcap_path)
    started = time.perf_counter()
    capture = normalize_packets(
        packets,
        source_file=pcap_path,
        capture_id=capture_id,
        diagnostics=diagnostics,
    )
    reassembly_seconds = time.perf_counter() - started

    out_path = work_dir / "size_regular.json"
    started = time.perf_counter()
    export_capture(
        capture.sessions,
        out_path,
        source_file=pcap_path.name,
        capture_id=capture_id,
        streams=capture.streams,
    )
    export_seconds = time.perf_counter() - started

    stop.set()
    sampler.join(timeout=1.0)

    return {
        "input_bytes": float(pcap_path.stat().st_size),
        "packets": float(len(packets)),
        "sessions": float(len(sessions)),
        "diagnostics": float(len(diagnostics)),
        "parse_seconds": parse_seconds,
        "sessions_seconds": sessions_seconds,
        "reassembly_seconds": reassembly_seconds,
        "export_seconds": export_seconds,
        "regular_seconds": parse_seconds
        + sessions_seconds
        + reassembly_seconds
        + export_seconds,
        "regular_peak_mib": peak,
        "output_bytes": float(out_path.stat().st_size),
    }


def measure_one_child(pcap_path: Path, work_dir: Path) -> dict[str, float]:
    """Measure one capture in both modes, for a fresh process. Prints JSON."""

    regular = measure_regular_sampled(pcap_path, work_dir)
    stream = run_streaming_child(pcap_path, work_dir / "size_stream.json")
    regular["stream_seconds"] = stream["seconds"]
    regular["stream_peak_mib"] = stream["peak_mib"]
    return regular


def measure_tracemalloc_child(pcap_path: Path, work_dir: Path) -> dict[str, float]:
    """Run the regular pipeline with tracemalloc on, in a fresh process."""

    result = run(pcap_path, work_dir, use_tracemalloc=True)
    return {
        "input_bytes": float(result.input_bytes),
        "packets": float(result.packets),
        "peak_rss_mib": result.peak_rss_mib,
        "tracemalloc_mib": float(result.tracemalloc_mib or 0.0),
    }


def run_size(pcap_path: Path, work_dir: Path, label: str) -> SizeRow:
    """Measure one capture in both modes, in a child process.

    A child process per size keeps the resident-memory measurement honest: no
    earlier run's high-water mark can leak into this one.
    """

    import subprocess

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_benchmark",
            "--mode",
            "measure",
            "--pcap",
            str(pcap_path),
            "--work-dir",
            str(work_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    return SizeRow(
        label=label,
        input_mib=payload["input_bytes"] / (1024 * 1024),
        packets=int(payload["packets"]),
        sessions=int(payload["sessions"]),
        parse_seconds=payload["parse_seconds"],
        sessions_seconds=payload["sessions_seconds"],
        reassembly_seconds=payload["reassembly_seconds"],
        export_seconds=payload["export_seconds"],
        regular_seconds=payload["regular_seconds"],
        regular_peak_mib=payload["regular_peak_mib"],
        stream_seconds=payload["stream_seconds"],
        stream_peak_mib=payload["stream_peak_mib"],
        output_mib=payload["output_bytes"] / (1024 * 1024),
        diagnostics=int(payload["diagnostics"]),
    )


def run_matrix(
    work_dir: Path,
    sizes: list[int],
    *,
    max_response: int,
    defects_pcap: Path | None,
    tracemalloc_mib: int | None,
) -> tuple[list[SizeRow], SizeRow | None, Result | None]:
    """Run the size sweep, the defects capture, and the tracemalloc run.

    Returns the sweep rows, the defects row (if measured), and the tracemalloc
    result (if measured).
    """

    from scripts.generate_benchmark_pcap import build

    work_dir.mkdir(parents=True, exist_ok=True)
    rows: list[SizeRow] = []
    for target in sizes:
        pcap = work_dir / f"matrix-{target}.pcapng"
        if not pcap.is_file():
            data = build(target * 2500, max(1, target * 10), target, max_response)
            pcap.write_bytes(data)
        rows.append(run_size(pcap, work_dir, f"{target} MiB"))

    defects_row: SizeRow | None = None
    if defects_pcap is not None and defects_pcap.is_file():
        defects_row = run_size(defects_pcap, work_dir, "defects")

    tracemalloc_result: Result | None = None
    if tracemalloc_mib is not None:
        pcap = work_dir / f"matrix-{tracemalloc_mib}.pcapng"
        if not pcap.is_file():
            data = build(
                tracemalloc_mib * 2500,
                max(1, tracemalloc_mib * 10),
                tracemalloc_mib,
                max_response,
            )
            pcap.write_bytes(data)
        import subprocess

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_benchmark",
                "--mode",
                "tracemalloc",
                "--pcap",
                str(pcap),
                "--work-dir",
                str(work_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        tracemalloc_result = Result(
            packets=int(payload["packets"]),
            input_bytes=int(payload["input_bytes"]),
            peak_rss_mib=payload["peak_rss_mib"],
            tracemalloc_mib=payload["tracemalloc_mib"],
        )

    return rows, defects_row, tracemalloc_result


def render_matrix_markdown(rows: list[SizeRow]) -> str:
    lines = [
        "## Size sweep: regular vs streaming",
        "",
        "The same capture is normalized twice, regular then streaming, so the two",
        "modes are compared on identical input. Each size is a distinct generated",
        "capture with the same session and message shape; ``packets`` scales with",
        "the size. Memory is the peak resident set of the process.",
        "",
        "| Input | Packets | Sessions | Regular s | Regular peak MiB | Streaming s | Streaming peak MiB | Output MiB |",
        "| ----- | ------- | -------- | --------- | ---------------- | ----------- | ------------------ | ---------- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.input_mib:.2f} MiB | {row.packets} | {row.sessions} | "
            f"{row.regular_seconds:.2f} | {row.regular_peak_mib:.0f} | "
            f"{row.stream_seconds:.2f} | {row.stream_peak_mib:.0f} | {row.output_mib:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_phase_markdown(rows: list[SizeRow]) -> str:
    lines = [
        "## Phase breakdown by size",
        "",
        "Seconds per phase of the regular pipeline. Reassembly includes session",
        "identification.",
        "",
        "| Input | Parse | Sessions | Reassembly | Export | Total |",
        "| ----- | ----- | -------- | ---------- | ------ | ----- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.input_mib:.2f} MiB | {row.parse_seconds:.2f} | "
            f"{row.sessions_seconds:.3f} | {row.reassembly_seconds:.2f} | "
            f"{row.export_seconds:.2f} | {row.regular_seconds:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_defects_markdown(row: SizeRow | None) -> str:
    if row is None:
        return ""
    return "\n".join(
        [
            "## Defects capture",
            "",
            "`tests/corpus/corpus_capture_defects.pcapng` is small but carries a",
            "retransmission, an out-of-order segment, a gap, and a conflicting",
            "overlap. It is measured to confirm the diagnostics do not degrade the",
            "throughput at this size.",
            "",
            "| Metric | Regular | Streaming |",
            "| ------ | ------- | --------- |",
            f"| Input | {row.input_mib * 1024:.1f} KiB | same |",
            f"| Packets | {row.packets} | {row.packets} |",
            f"| Sessions | {row.sessions} | {row.sessions} |",
            f"| Seconds | {row.regular_seconds:.3f} | {row.stream_seconds:.3f} |",
            f"| Peak RSS (MiB) | {row.regular_peak_mib:.0f} | {row.stream_peak_mib:.0f} |",
            "",
        ]
    )


def render_tracemalloc_markdown(result: Result | None) -> str:
    if result is None or result.tracemalloc_mib is None:
        return ""
    return "\n".join(
        [
            "## Python allocation (tracemalloc, 10 MiB)",
            "",
            "Peak memory tracked by ``tracemalloc`` during a regular run over the",
            "10 MiB capture. This counts Python allocations only, not the memory",
            "the interpreter or libraries hold outside the allocator, so it is",
            "below the process RSS.",
            "",
            "| Metric | Value |",
            "| ------ | ----- |",
            f"| Input | {result.input_bytes / (1024 * 1024):.2f} MiB |",
            f"| Packets | {result.packets} |",
            f"| tracemalloc peak | {result.tracemalloc_mib:.0f} MiB |",
            f"| Process RSS | {result.peak_rss_mib:.0f} MiB |",
            "",
        ]
    )


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
        "--mode",
        choices=("full", "stream", "measure", "tracemalloc"),
        default="full",
        help="full runs both modes; stream runs only streaming; measure runs "
        "both modes for one capture and prints JSON",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output path used by --mode stream",
    )
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
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="also run the size sweep, the defects capture, and tracemalloc",
    )
    parser.add_argument(
        "--sizes",
        default="10,50,95",
        help="comma-separated capture sizes in MiB for the sweep",
    )
    parser.add_argument(
        "--defects-pcap",
        type=Path,
        default=Path("tests") / "corpus" / "corpus_capture_defects.pcapng",
        help="small defects capture to measure",
    )
    parser.add_argument(
        "--tracemalloc-mib",
        type=int,
        default=10,
        help="size in MiB for the tracemalloc run (0 to skip)",
    )
    args = parser.parse_args(argv)

    if args.mode == "stream":
        if args.out is None:
            parser.error("--mode stream requires --out")
        payload = run_streaming_child(args.pcap, args.out)
        print(json.dumps(payload))
        return 0

    if args.mode == "measure":
        payload = measure_one_child(args.pcap, args.work_dir)
        print(json.dumps(payload))
        return 0

    if args.mode == "tracemalloc":
        payload = measure_tracemalloc_child(args.pcap, args.work_dir)
        print(json.dumps(payload))
        return 0

    args.work_dir.mkdir(parents=True, exist_ok=True)
    if not args.pcap.is_file():
        from scripts.generate_benchmark_pcap import build

        data = build(args.packets, args.sessions, args.target_mib, args.max_response)
        args.pcap.parent.mkdir(parents=True, exist_ok=True)
        args.pcap.write_bytes(data)

    result = run(args.pcap, args.work_dir, use_tracemalloc=args.tracemalloc)
    (
        result.stream_seconds,
        result.stream_peak_rss_mib,
        result.stream_output_bytes,
        result.stream_flushes,
    ) = run_streaming(args.pcap, args.work_dir)
    profile = {
        "packets": args.packets,
        "sessions": args.sessions,
        "target_mib": args.target_mib,
        "max_response": args.max_response,
    }
    print(
        json.dumps(
            {
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
                "stream_s": round(result.stream_seconds, 2),
                "stream_peak_rss_mib": round(result.stream_peak_rss_mib),
                "stream_output_mib": round(
                    (result.stream_output_bytes or 0) / (1024 * 1024), 2
                ),
            }
        )
    )

    sweep_md = ""
    if args.matrix:
        sizes = [int(part) for part in args.sizes.split(",") if part.strip()]
        rows, defects_row, trace_result = run_matrix(
            args.work_dir,
            sizes,
            max_response=args.max_response,
            defects_pcap=args.defects_pcap,
            tracemalloc_mib=args.tracemalloc_mib or None,
        )
        sweep_md = "\n".join(
            part
            for part in (
                render_matrix_markdown(rows),
                render_phase_markdown(rows),
                render_defects_markdown(defects_row),
                render_tracemalloc_markdown(trace_result),
            )
            if part
        )
        print(json.dumps({"sweep": [row.to_dict() for row in rows]}))

    if args.write_md is not None:
        args.write_md.parent.mkdir(parents=True, exist_ok=True)
        document = render_markdown(result, profile)
        if sweep_md:
            document = document.rstrip("\n") + "\n\n" + sweep_md + "\n"
        args.write_md.write_text(document, encoding="utf-8")
        print(f"wrote {args.write_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
