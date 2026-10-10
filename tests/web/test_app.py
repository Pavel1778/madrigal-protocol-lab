"""Tests for the optional local web interface.

They exercise the real capture engine and the real rule engine against the
reference corpus: no PCAP parsing is mocked, no verdict is faked. The FastAPI
app is driven in-process with ``httpx``/``TestClient``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="web extra is not installed")
pytest.importorskip("httpx", reason="web test client is not installed")

from fastapi.testclient import TestClient  # noqa: E402

from src.web.app import create_app  # noqa: E402
from src.web.engine import WebEngine, WebEngineError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPTURE = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
RULE = REPO_ROOT / "examples" / "corpus_rule_v1.json"
RAW_PCAP = REPO_ROOT / "tests" / "corpus" / "corpus_capture_01.pcapng"
DEFECTS = (
    REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_defects.normalized.json"
)

corpus_required = pytest.mark.skipif(
    not CAPTURE.is_file() or not RULE.is_file(),
    reason="reference corpus not present",
)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(CAPTURE, RULE))


@pytest.fixture()
def client_no_rule() -> TestClient:
    return TestClient(create_app(CAPTURE, None))


# -- pages ------------------------------------------------------------------


@corpus_required
def test_root_returns_session_list(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Sessions" in response.text
    assert "s1" in response.text


@corpus_required
def test_sessions_fragment_lists_every_session(client: TestClient) -> None:
    response = client.get("/sessions")
    assert response.status_code == 200
    engine = WebEngine.open(CAPTURE, RULE)
    for session in engine.sessions():
        assert session.session_id in response.text


@corpus_required
def test_hex_page_renders_the_stream(client: TestClient) -> None:
    response = client.get("/session/s1/hex")
    assert response.status_code == 200
    assert "hex" in response.text
    # The hex view marks up individual bytes with their offsets.
    assert 'data-offset="0"' in response.text


# -- apply ------------------------------------------------------------------


@corpus_required
def test_apply_rule_reports_matched_and_mismatched(client: TestClient) -> None:
    response = client.post("/apply", data={"session": "s1", "direction": "A_to_B"})
    assert response.status_code == 200
    body = response.text.lower()
    assert "matched" in body


@corpus_required
def test_apply_on_defects_yields_a_mismatch() -> None:
    app_client = TestClient(create_app(DEFECTS, RULE))
    response = app_client.post("/apply", data={"session": "s1"})
    assert response.status_code == 200
    # The defects corpus exists to produce counterexamples; at least one
    # message must be classified mismatched.
    assert "mismatched" in response.text.lower()


# -- provenance -------------------------------------------------------------


@corpus_required
def test_provenance_returns_packet_index_seq_and_ts(client: TestClient) -> None:
    response = client.get("/message/0/provenance", params={"session": "s1", "direction": "A_to_B"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["offset"] == 0
    assert payload["packet_index"] is not None
    assert payload["seq"] is not None
    assert payload["ts"] is not None


@corpus_required
def test_provenance_card_fragment(client: TestClient) -> None:
    response = client.get(
        "/message/0/provenance/card", params={"session": "s1", "direction": "A_to_B"}
    )
    assert response.status_code == 200
    assert "packet index" in response.text


@corpus_required
def test_provenance_out_of_range_is_404(client: TestClient) -> None:
    response = client.get(
        "/message/999999/provenance", params={"session": "s1", "direction": "A_to_B"}
    )
    assert response.status_code == 404


# -- messages ---------------------------------------------------------------


@corpus_required
def test_messages_fragment_shows_offsets_and_lengths(client: TestClient) -> None:
    response = client.get("/session/s1/messages", params={"direction": "A_to_B"})
    assert response.status_code == 200
    assert "offset" in response.text
    assert "length" in response.text


# -- report -----------------------------------------------------------------


@corpus_required
def test_export_report_is_self_contained_html(client: TestClient) -> None:
    response = client.get("/export/report", params={"session": "s1", "direction": "A_to_B"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in response.text
    # Self-contained: no external http(s) references.
    assert "http://" not in response.text
    assert "https://" not in response.text


# -- errors -----------------------------------------------------------------


@corpus_required
def test_unknown_session_is_404(client: TestClient) -> None:
    response = client.get("/session/does-not-exist/hex")
    assert response.status_code == 404
    assert "does-not-exist" in response.text


@corpus_required
def test_invalid_capture_is_400_with_message() -> None:
    with pytest.raises(WebEngineError) as excinfo:
        WebEngine.open(REPO_ROOT / "no-such-file.json")
    assert "not found" in str(excinfo.value)


@corpus_required
def test_capture_with_wrong_shape_is_400() -> None:
    with pytest.raises(WebEngineError):
        WebEngine.open(REPO_ROOT / "pyproject.toml")


@corpus_required
def test_no_capture_open_returns_400() -> None:
    empty = TestClient(create_app(None, None))
    response = empty.get("/")
    assert response.status_code == 400
    assert "--capture" in response.text


# -- no rule ----------------------------------------------------------------


@corpus_required
def test_without_rule_every_byte_is_uncovered(client_no_rule: TestClient) -> None:
    response = client_no_rule.get("/session/s1/hex")
    assert response.status_code == 200
    assert "is-uncovered" in response.text
    assert "is-mismatched" not in response.text


# -- raw pcap ---------------------------------------------------------------


@corpus_required
def test_raw_pcap_is_normalized_on_open() -> None:
    engine = WebEngine.open(RAW_PCAP, RULE)
    assert engine.sessions()
    assert engine.capture_id.startswith("sha256:")


def test_unsupported_capture_type_is_rejected() -> None:
    with pytest.raises(WebEngineError) as excinfo:
        WebEngine.open(REPO_ROOT / "README.md")
    assert "unsupported" in str(excinfo.value)


# -- port / host ------------------------------------------------------------


def test_port_in_use_reports_plainly() -> None:
    import socket

    from src.web.app import _port_available

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        assert _port_available(port) is False


def test_main_refuses_non_local_host(capsys) -> None:
    from src.web.app import main

    code = main(["--host", "0.0.0.0", "--capture", str(CAPTURE)])
    assert code == 2
    assert "local-only" in capsys.readouterr().err


def test_main_reports_missing_capture(capsys) -> None:
    from src.web.app import main

    code = main(["--capture", str(REPO_ROOT / "nope.json"), "--port", "0"])
    assert code == 2
    assert "could not start" in capsys.readouterr().err
