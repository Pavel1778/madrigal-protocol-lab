"""Application main window.

Layout: a menu bar, a horizontal splitter with the session tree on the left, the
hex view in the centre and the interpretation panel on the right, and a status
bar carrying the byte provenance, a progress indicator and a message area.

The window holds a :class:`CaptureModel` and a :class:`RuleModel`. It opens a
normalized capture (the contract JSON), never a pcap; the capture module is a
separate concern.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from . import theme
from .compare_view import CompareView
from .hex_view import HexView, annotations_from_application, annotations_from_stream
from .model import CaptureModel, RuleModel, verify_rule_on_corpus
from .session_tree import SessionTree
from .validation_view import ValidationView

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / "REPORT.md"


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Madrigal protocol laboratory")
        self.resize(1400, 860)

        self._capture: CaptureModel | None = None
        self._rule: RuleModel | None = None
        self._session_id: str = ""
        self._direction: str = ""
        self._corpus_report = None

        self._build_menu()
        self._build_central()
        self._build_status()
        self._wire()

    # -- construction ------------------------------------------------------

    def _build_menu(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("File")
        self._action(file_menu, "Open capture...", self.open_capture_dialog, "Ctrl+O")
        self._action(file_menu, "Open rule...", self.open_rule_dialog, "Ctrl+R")
        self._action(file_menu, "Save result...", self.save_result_dialog, "Ctrl+S")
        file_menu.addSeparator()
        self._action(file_menu, "Quit", self.close, "Ctrl+Q")

        rule_menu = bar.addMenu("Rule")
        self._action(rule_menu, "Apply to current direction", self.apply_rule, "F5")
        self._action(rule_menu, "Apply to whole capture", self.apply_to_capture, "F6")
        self._action(rule_menu, "Compare versions", self.show_version_diff)

        report_menu = bar.addMenu("Report")
        self._action(report_menu, "Show REPORT.md", self.show_report)
        self._action(report_menu, "Export Markdown...", self.export_markdown)
        self._action(report_menu, "Export HTML...", self.export_html)

        help_menu = bar.addMenu("Help")
        self._action(help_menu, "About", self.show_about)

    def _action(self, menu, text, slot, shortcut: str | None = None) -> QtGui.QAction:
        action = QtGui.QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_central(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        self.session_tree = SessionTree()
        splitter.addWidget(self._wrap("Sessions", self.session_tree))

        centre = QtWidgets.QWidget()
        centre_layout = QtWidgets.QVBoxLayout(centre)
        centre_layout.setContentsMargins(0, 0, 0, 0)
        centre_layout.setSpacing(6)
        controls = QtWidgets.QHBoxLayout()
        self.direction_combo = QtWidgets.QComboBox()
        self.direction_combo.setFont(theme.body_font(9))
        self.direction_combo.currentTextChanged.connect(self._on_direction_changed)
        controls.addWidget(QtWidgets.QLabel("direction"))
        controls.addWidget(self.direction_combo)
        controls.addStretch(1)
        self.annotation_legend = QtWidgets.QLabel(
            "gap / ambiguity / matched / mismatched / uncovered"
        )
        self.annotation_legend.setProperty("role", "secondary")
        self.annotation_legend.setFont(theme.body_font(8))
        controls.addWidget(self.annotation_legend)
        centre_layout.addLayout(controls)
        self.hex_view = HexView()
        centre_layout.addWidget(self.hex_view, 1)
        splitter.addWidget(self._wrap("Bytes", centre))

        self.right_tabs = QtWidgets.QTabWidget()
        self.validation_view = ValidationView()
        self.right_tabs.addTab(self.validation_view, "Interpretation")
        self.compare_view = CompareView()
        self.right_tabs.addTab(self.compare_view, "Compare")
        self.report_view = QtWidgets.QPlainTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setFont(theme.mono_font(9))
        self.right_tabs.addTab(self.report_view, "Report")
        self.diff_view = QtWidgets.QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(theme.mono_font(9))
        self.right_tabs.addTab(self.diff_view, "Version diff")
        splitter.addWidget(self.right_tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([300, 720, 420])
        self.setCentralWidget(splitter)

    def _wrap(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(widget)
        return box

    def _build_status(self) -> None:
        bar = self.statusBar()
        self._provenance_label = QtWidgets.QLabel("no byte selected")
        self._provenance_label.setFont(theme.body_font(9))
        bar.addWidget(self._provenance_label, 1)
        self._progress = QtWidgets.QProgressBar()
        self._progress.setFixedWidth(140)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        bar.addPermanentWidget(self._progress)

    def _wire(self) -> None:
        self.session_tree.directionSelected.connect(self._on_direction_selected)
        self.hex_view.byteHovered.connect(self._on_byte_hovered)
        self.hex_view.byteClicked.connect(self._on_byte_clicked)
        self.validation_view.applyRequested.connect(self.apply_rule)
        self.validation_view.counterexampleSelected.connect(self.reveal_offset)

    # -- loading -----------------------------------------------------------

    def open_capture(self, path: str | Path) -> None:
        model = CaptureModel.from_file(path)
        self._capture = model
        self.session_tree.load(model)
        self.setWindowTitle(f"Madrigal protocol laboratory - {Path(path).name}")
        diagnostics = ", ".join(f"{d.type}@{d.offset}" for d in model.diagnostics) or "none"
        self._provenance_label.setText(
            f"{len(model.sessions)} sessions  capture_id {model.capture_id[:19]}  diagnostics {diagnostics}"
        )
        if model.sessions:
            self._on_direction_selected(
                model.sessions[0].session_id, model.directions(model.sessions[0].session_id)[0]
            )

    def open_capture_dialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open normalized capture", str(REPO_ROOT), "JSON (*.json)"
        )
        if path:
            self.open_capture(path)

    def load_rule(self, path: str | Path) -> None:
        previous_rule = self._rule.rule if self._rule is not None else None
        previous_report = self._rule.corpus_report if self._rule is not None else None
        self._rule = RuleModel.from_file(path)
        self._rule.previous_rule = previous_rule
        self._rule.previous_report = previous_report
        self.validation_view.set_rule_text(self._rule.text)
        self.validation_view.set_rule_status(
            f"loaded {Path(path).name}  rule v{self._rule.rule.rule_version}"
        )

    def open_rule_dialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open rule", str(REPO_ROOT / "examples"), "Rules (*.json *.yaml *.yml)"
        )
        if path:
            self.load_rule(path)

    # -- selection ---------------------------------------------------------

    def _on_direction_selected(self, session_id: str, direction: str) -> None:
        if self._capture is None:
            return
        self._session_id = session_id
        self._direction = direction
        self.direction_combo.blockSignals(True)
        self.direction_combo.clear()
        for name in self._capture.directions(session_id):
            self.direction_combo.addItem(name)
        self.direction_combo.setCurrentText(direction)
        self.direction_combo.blockSignals(False)
        self.validation_view.set_context(session_id, direction)
        self._render_stream()

    def _on_direction_changed(self, direction: str) -> None:
        if self._capture is None or not direction or direction == self._direction:
            return
        self.session_tree.select_direction(self._session_id, direction)

    def _render_stream(self) -> None:
        if self._capture is None:
            return
        stream = self._capture.stream(self._session_id, self._direction)
        self.hex_view.set_stream(stream.data, annotations_from_stream(stream))

    # -- rule --------------------------------------------------------------

    def apply_rule(self) -> None:
        if self._capture is None or self._rule is None:
            self._notify("open a capture and a rule first")
            return
        try:
            self._rule.reload(self.validation_view.rule_text())
        except Exception as exc:  # noqa: BLE001 - the message is shown to the user
            self.validation_view.set_rule_status(f"rule error: {exc}", error=True)
            return
        application = self._rule.apply(self._capture, self._session_id, self._direction)
        self.validation_view.show_application(application)
        self.compare_view.show_application(application)
        stream = self._capture.stream(self._session_id, self._direction)
        self.hex_view.set_annotations(annotations_from_application(application, stream))
        counts = ", ".join(f"{k}={v}" for k, v in sorted(application.counts.items()))
        self.validation_view.set_rule_status(
            f"rule v{application.rule.rule_version}  {counts}"
        )
        self._notify(
            f"applied rule v{application.rule.rule_version} to {self._session_id} {self._direction}"
        )

    def apply_to_capture(self) -> None:
        if self._capture is None or self._rule is None:
            self._notify("open a capture and a rule first")
            return
        try:
            self._rule.reload(self.validation_view.rule_text())
        except Exception as exc:  # noqa: BLE001
            self.validation_view.set_rule_status(f"rule error: {exc}", error=True)
            return
        self._set_progress(20)
        report = verify_rule_on_corpus(self._rule.rule, self._capture)
        self._set_progress(100)
        if self._rule.previous_report is not None and self._rule.previous_report.rule_id == report.rule_id:
            self._show_report_diff(self._rule.previous_report, report)
        self._rule.corpus_report = report
        self._corpus_report = report
        counts = ", ".join(f"{k}={v}" for k, v in sorted(report.counts().items()))
        self.validation_view.set_rule_status(
            f"rule v{self._rule.rule.rule_version} over the capture: "
            f"{counts}  counterexamples={len(report.contradictions)}"
        )
        self._notify(f"verified rule over the whole capture: {counts}")

    def _show_report_diff(self, report_a, report_b) -> None:
        from ..hypothesis.diff import diff_reports, format_report_diff

        diff = diff_reports(report_a, report_b)
        self.diff_view.setPlainText(format_report_diff(diff))
        self.right_tabs.setCurrentWidget(self.diff_view)

    def show_version_diff(self) -> None:
        report = self._rule.corpus_report if self._rule is not None else None
        previous = self._rule.previous_report if self._rule is not None else None
        if report is None or previous is None or previous.rule_id != report.rule_id:
            self._notify("no previous rule version to compare")
            return
        self._show_report_diff(previous, report)
        self._notify(
            f"rule v{report.rule_version} supersedes v{previous.rule_version}; "
            f"the old run is marked outdated"
        )

    # -- bytes -------------------------------------------------------------

    def reveal_offset(self, offset: int) -> None:
        self.hex_view.scroll_to_byte(offset)
        self._show_provenance(offset)

    def _on_byte_clicked(self, offset: int) -> None:
        self._show_provenance(offset)

    def _on_byte_hovered(self, offset: int) -> None:
        self._show_provenance(offset)

    def _show_provenance(self, offset: int) -> None:
        if self._capture is None:
            return
        stream = self._capture.stream(self._session_id, self._direction)
        parts = [f"{self._session_id} {self._direction}  offset {offset}"]
        for hole in stream.provenance:
            if hole.offset <= offset < hole.end:
                parts.append(
                    f"packet {hole.packet_index}  seq {hole.seq}  ts {hole.ts}"
                )
                break
        diagnostics = stream.holes(offset, offset + 1)
        for hole in diagnostics:
            parts.append(f"{hole.type} ({hole.offset}+{hole.length})")
        self._provenance_label.setText("   ".join(str(p) for p in parts))

    # -- report ------------------------------------------------------------

    def show_report(self) -> None:
        if DEFAULT_REPORT.is_file():
            self.report_view.setPlainText(DEFAULT_REPORT.read_text(encoding="utf-8"))
            self.right_tabs.setCurrentWidget(self.report_view)

    def export_markdown(self) -> None:
        self._export(DEFAULT_REPORT, "Markdown (*.md)")

    def export_html(self) -> None:
        self._export(DEFAULT_REPORT, "HTML (*.html)", html=True)

    def _export(self, source: Path, file_filter: str, html: bool = False) -> None:
        if not source.is_file():
            self._notify(f"{source.name} is not available")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export report", str(source.parent / source.name), file_filter)
        if not path:
            return
        text = source.read_text(encoding="utf-8")
        if html:
            text = _markdown_to_html(text)
        Path(path).write_text(text, encoding="utf-8")
        self._notify(f"wrote {path}")

    def save_result_dialog(self) -> None:
        if self._rule is None or self._rule.root is None:
            self._notify("apply a rule before saving a result")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save result", str(REPO_ROOT), "JSON (*.json)")
        if not path:
            return
        application = self._rule.root
        payload = {
            "rule_id": application.rule.rule_id,
            "rule_version": application.rule.rule_version,
            "session_id": application.session_id,
            "direction": application.direction,
            "counts": application.counts,
            "messages": [
                {
                    "offset": m.offset,
                    "length": m.length,
                    "status": m.status.value,
                    "bytes_hex": m.bytes_hex,
                }
                for m in application.messages
            ],
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._notify(f"wrote {path}")

    def show_about(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "About",
            "Madrigal protocol laboratory\n"
            "A local tool for reconstructing an undocumented binary protocol "
            "over TCP.\nThe bytes are the source of truth; a rule is an "
            "interpretation checked against them.",
        )

    # -- helpers -----------------------------------------------------------

    def _set_progress(self, value: int) -> None:
        self._progress.setValue(value)

    def _notify(self, text: str) -> None:
        self.statusBar().showMessage(text, 6000)


def _markdown_to_html(text: str) -> str:
    """Minimal Markdown to HTML for the report export.

    Only the constructs the report uses are handled: headings, paragraphs and
    pipe tables. A general Markdown renderer is out of scope.
    """
    import html as html_module

    lines = text.splitlines()
    out: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<style>body{background:#131516;color:#E0E0E0;font-family:Montserrat,sans-serif;"
        "max-width:960px;margin:2rem auto;padding:0 1rem} "
        "h1,h2,h3{font-family:Tektur,sans-serif;color:#E0E0E0} "
        "table{border-collapse:collapse;margin:1rem 0} "
        "td,th{border:1px solid #2A2C2E;padding:4px 8px} code{color:#A2391D}</style>",
        "</head><body>",
    ]
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
            tag = "th" if out[-1] == "<table>" else "td"
            row = "".join(f"<{tag}>{html_module.escape(c)}</{tag}>" for c in cells)
            out.append(f"<tr>{row}</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            out.append(f"<h{level}>{html_module.escape(stripped[level:].strip())}</h{level}>")
        elif stripped:
            out.append(f"<p>{html_module.escape(stripped)}</p>")
    if in_table:
        out.append("</table>")
    out.append("</body></html>")
    return "\n".join(out)


def open_default_window(
    app: QtWidgets.QApplication | None = None,
    capture: str | Path | None = None,
    rule: str | Path | None = None,
) -> MainWindow:
    """Build a window, optionally opening *capture* and *rule*.

    The window is input-driven: nothing is loaded unless the caller passes a
    path. Tests, the screenshot script and the manual smoke run supply the
    reference corpus and rule explicitly, so no capture or rule name is
    embedded in the application itself.
    """
    window = MainWindow()
    if capture is not None and Path(capture).is_file():
        window.open_capture(capture)
    if rule is not None and Path(rule).is_file():
        window.load_rule(rule)
    return window


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="src.ui.main_window",
        description="Open the protocol laboratory window.",
    )
    parser.add_argument("--capture", type=Path, help="normalized capture JSON to open")
    parser.add_argument("--rule", type=Path, help="rule JSON or YAML to open")
    args, qt_argv = parser.parse_known_args(argv)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([sys.argv[0], *qt_argv])
    app.setApplicationName("Madrigal protocol laboratory")
    theme.load_fonts(app)
    app.setStyleSheet(theme.build_stylesheet())
    window = open_default_window(app, capture=args.capture, rule=args.rule)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
