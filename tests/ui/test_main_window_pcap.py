"""The window opens a capture whatever its on-disk form.

The window is input-driven: it is handed a path and must decide from the file
itself whether it is a normalized capture JSON or a raw pcap/pcapng, then load
it. A file of neither kind must produce a clear error rather than a decode
traceback. These tests exercise the real pipeline and the real engine on the
corpus that ships with the project.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

try:
    from PySide6 import QtWidgets  # noqa: E402

    from src.ui import theme  # noqa: E402
    from src.ui.main_window import MainWindow  # noqa: E402
    from src.ui.model import CaptureModel, CaptureModelError  # noqa: E402
except ImportError as exc:  # pragma: no cover - depends on the runner
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
NORMALIZED = REPO_ROOT / "tests" / "corpus" / "reference_export" / "corpus_capture_01.normalized.json"
PCAP = REPO_ROOT / "tests" / "corpus" / "real" / "research" / "01_configuration.pcap"
PCAPNG = REPO_ROOT / "tests" / "corpus" / "real" / "research" / "02_variations.pcapng"


@pytest.fixture(scope="module")
def app():
    try:
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # noqa: BLE001 - a missing Qt runtime is a skip
        pytest.skip(f"Qt platform could not start: {exc}")
    theme.load_fonts(application)
    application.setStyleSheet(theme.build_stylesheet())
    return application


def test_gui_opens_normalized_json(app):
    model = CaptureModel.from_file(NORMALIZED)
    assert model.sessions
    assert model.capture_id.startswith("sha256:")


def test_gui_opens_raw_pcap(app):
    # The reported defect: a raw pcap passed to --capture raised a decode
    # error. It must load as a capture with its sessions.
    model = CaptureModel.from_file(PCAP)
    assert len(model.sessions) >= 1
    session = model.sessions[0]
    assert model.directions(session.session_id)


def test_gui_opens_raw_pcapng(app):
    model = CaptureModel.from_file(PCAPNG)
    assert len(model.sessions) >= 1


def test_gui_rejects_unknown_format_with_message(app, tmp_path):
    bad = tmp_path / "not-a-capture.bin"
    bad.write_bytes(b"\x00\x01\x02 this is neither json nor a capture")
    with pytest.raises(CaptureModelError) as excinfo:
        CaptureModel.from_file(bad)
    message = str(excinfo.value)
    assert "PCAP" in message
    assert "src.capture.cli" in message


def test_window_opens_raw_pcap_and_applies_rule(app):
    # The live path: build the window, hand it the raw pcap and a rule, and
    # check the capture and the rule are both in place.
    window = MainWindow()
    window.open_capture(PCAP)
    assert len(window._capture.sessions) == 2
    window.load_rule(REPO_ROOT / "examples" / "thermostand_request_v2.json")
    assert window._rule.rule.rule_version == 2
    window.close()


def test_window_reports_unknown_capture(app, tmp_path):
    window = MainWindow()
    bad = tmp_path / "mystery.dat"
    bad.write_bytes(b"\xde\xad\xbe\xef")
    with pytest.raises(CaptureModelError):
        window.open_capture(bad)
    assert window._capture is None
    window.close()
