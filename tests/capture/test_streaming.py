"""Tests for streaming normalization."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_benchmark_pcap import build
from src.capture.export import export_capture
from src.capture.pipeline import normalize
from src.capture.session import Direction
from src.capture.streaming import process_streaming

from .conftest import fixture


def _regular_json(path: Path, out: Path) -> dict:
    capture = normalize(path)
    export_capture(
        capture.sessions,
        out,
        source_file=str(path),
        capture_id=capture.capture_id,
        streams=capture.streams,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def _streaming_json(path: Path, out: Path, chunk_size: int) -> dict:
    process_streaming(path, out, chunk_size=chunk_size)
    return json.loads(out.read_text(encoding="utf-8"))


def test_streaming_matches_regular_on_a_fixture(tmp_path: Path) -> None:
    source = fixture("normal.pcapng")
    regular = _regular_json(source, tmp_path / "regular.json")
    streamed = _streaming_json(source, tmp_path / "stream.json", chunk_size=2)
    assert streamed == regular


def test_streaming_matches_regular_on_the_whole_corpus(tmp_path: Path) -> None:
    import scripts.generate_corpus as corpus

    corpus.generate(tmp_path / "corpus", scale=3)
    for name in (
        "corpus_capture_01.pcapng",
        "corpus_capture_02.pcapng",
        "corpus_capture_defects.pcapng",
    ):
        source = tmp_path / "corpus" / name
        regular = _regular_json(source, tmp_path / f"reg_{name}.json")
        streamed = _streaming_json(source, tmp_path / f"st_{name}.json", chunk_size=4)
        assert streamed == regular, name


def test_streaming_flushes_a_session_before_the_end(tmp_path: Path) -> None:
    source = fixture("port_reuse.pcapng")
    out = tmp_path / "stream.json"
    stats = process_streaming(source, out, chunk_size=1, close_linger=1)
    assert stats.sessions == 2
    assert stats.flushes == 2


def test_streaming_handles_unclosed_session_at_eof(tmp_path: Path) -> None:
    # no_syn has no handshake and no close, so the session stays open until EOF.
    source = fixture("no_syn.pcapng")
    regular = _regular_json(source, tmp_path / "regular.json")
    streamed = _streaming_json(source, tmp_path / "stream.json", chunk_size=1)
    assert streamed == regular
    assert len(streamed["sessions"]) == 1


def test_streaming_on_a_larger_capture(tmp_path: Path) -> None:
    data = build(packets=2000, sessions=20, target_mib=2, max_response=4096)
    source = tmp_path / "large.pcapng"
    source.write_bytes(data)
    out = tmp_path / "stream.json"
    stats = process_streaming(source, out, chunk_size=256)
    assert stats.packets == 2000
    assert stats.sessions == 20
    document = json.loads(out.read_text(encoding="utf-8"))
    assert len(document["sessions"]) == 20


def test_streaming_preserves_streams_and_diagnostics(tmp_path: Path) -> None:
    source = fixture("gap.pcapng")
    streamed = _streaming_json(source, tmp_path / "stream.json", chunk_size=1)
    diagnostics = streamed["sessions"][0]["directions"]["A_to_B"]["diagnostics"]
    assert [d["type"] for d in diagnostics] == ["gap"]

    capture = normalize(source)
    session = capture.sessions[0]
    stream = capture.streams[session.session_id][Direction.A_TO_B]
    import base64

    encoded = streamed["sessions"][0]["directions"]["A_to_B"]["bytes_b64"]
    assert base64.b64decode(encoded) == bytes(stream.bytes_)
