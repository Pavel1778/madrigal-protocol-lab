"""FastAPI application for the optional local web interface.

Run it with::

    python -m src.web.app --capture capture.normalized.json --rule rule.yaml --port 8765

The server binds ``127.0.0.1`` only. All state lives in memory: one capture and
one rule are held in ``app.state``; there is no database and no user model.
Rendering is server-side Jinja2 with HTMX swapping fragments in place, and the
few assets (the stylesheet and ``htmx.min.js``) are served from ``static/`` so
the page works offline.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .engine import WebEngine, WebEngineError

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
TEMPLATES_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"
FONTS_DIR = REPO_ROOT / "assets" / "fonts"

# The byte-annotation and status colours, mirroring the desktop brand so the
# web page and the application agree on what a verdict looks like.
STATUS_CLASSES = {
    "matched": "is-matched",
    "mismatched": "is-mismatched",
    "gap": "is-gap",
    "ambiguity": "is-ambiguous",
    "uncovered": "is-uncovered",
    "not_applicable": "is-na",
    "field": "is-field",
}


def _templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.globals["status_class"] = lambda status: STATUS_CLASSES.get(
        status, "is-uncovered"
    )
    return templates


def create_app(
    capture: str | Path | None = None,
    rule: str | Path | None = None,
) -> FastAPI:
    """Build the application, optionally opening a capture and rule.

    Opening is lazy-safe: when ``capture`` is given it is opened now, so a
    startup mistake is reported immediately rather than on the first request.
    """
    app = FastAPI(title="Protocol laboratory (web)", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    if FONTS_DIR.is_dir():
        # Reuse the same font files the desktop window uses, rather than
        # committing a second copy under the web package.
        app.mount("/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")
    templates = _templates()
    app.state.templates = templates
    app.state.engine = None

    if capture is not None:
        app.state.engine = WebEngine.open(capture, rule)

    @app.exception_handler(WebEngineError)
    async def _engine_error(_request: Request, exc: WebEngineError) -> HTMLResponse:
        # A caller-facing problem is a 400 with the message, never a traceback.
        return HTMLResponse(
            templates.get_template("error.html").render(message=str(exc)),
            status_code=400,
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        engine = _require_engine(app)
        return templates.TemplateResponse(
            request,
            "sessions.html",
            _session_context(request, engine),
        )

    @app.get("/sessions", response_class=HTMLResponse)
    async def sessions(request: Request) -> HTMLResponse:
        engine = _require_engine(app)
        return templates.TemplateResponse(
            request,
            "_sessions.html",
            _session_context(request, engine),
        )

    @app.get("/session/{session_id}/hex", response_class=HTMLResponse)
    async def session_hex(
        request: Request, session_id: str, direction: str | None = None
    ) -> HTMLResponse:
        engine = _require_engine(app)
        session = engine.session(session_id)
        if session is None:
            return _not_found(templates, f"no session {session_id!r} in this capture")
        direction = _resolve_direction(session, direction)
        if direction is None:
            return _not_found(
                templates, f"session {session_id!r} has no direction {direction!r}"
            )
        return templates.TemplateResponse(
            request,
            "hex.html",
            {
                "capture_id": engine.capture_id,
                "session": session,
                "direction": direction,
                "lines": engine.hex_lines(session_id, direction),
                "messages": engine.message_rows(session_id, direction),
                "has_rule": engine.has_rule,
            },
        )

    @app.get("/session/{session_id}/messages", response_class=HTMLResponse)
    async def session_messages(
        request: Request, session_id: str, direction: str | None = None
    ) -> HTMLResponse:
        engine = _require_engine(app)
        session = engine.session(session_id)
        if session is None:
            return _not_found(templates, f"no session {session_id!r} in this capture")
        direction = _resolve_direction(session, direction)
        return templates.TemplateResponse(
            request,
            "_messages.html",
            {
                "session": session,
                "direction": direction,
                "messages": engine.message_rows(session_id, direction),
                "has_rule": engine.has_rule,
            },
        )

    @app.post("/apply", response_class=HTMLResponse)
    async def apply(
        request: Request,
        session: str = Form(...),
        direction: str = Form(""),
    ) -> HTMLResponse:
        engine = _require_engine(app)
        row = engine.session(session)
        if row is None:
            return _not_found(templates, f"no session {session!r} in this capture")
        resolved = _resolve_direction(row, direction or None)
        return templates.TemplateResponse(
            request,
            "_messages.html",
            {
                "session": row,
                "direction": resolved,
                "messages": engine.message_rows(session, resolved),
                "has_rule": engine.has_rule,
            },
        )

    @app.get("/message/{offset}/provenance", response_class=JSONResponse)
    async def provenance(
        offset: int,
        session: str | None = None,
        direction: str | None = None,
    ) -> JSONResponse:
        engine = _require_engine(app)
        row = engine.session(session) if session else _first_session(engine)
        if row is None:
            return JSONResponse({"error": f"no session {session!r}"}, status_code=404)
        resolved = _resolve_direction(row, direction)
        if resolved is None:
            return JSONResponse(
                {"error": f"session {row.session_id!r} has no direction {direction!r}"},
                status_code=404,
            )
        info = engine.provenance(row.session_id, resolved, offset)
        if info is None:
            return JSONResponse(
                {"error": f"offset {offset} is outside the stream"}, status_code=404
            )
        return JSONResponse(info)

    @app.get("/message/{offset}/provenance/card", response_class=HTMLResponse)
    async def provenance_card(
        request: Request,
        offset: int,
        session: str | None = None,
        direction: str | None = None,
    ) -> HTMLResponse:
        # The HTMX fragment for the provenance panel, rendered from the same
        # engine answer the JSON route returns.
        engine = _require_engine(app)
        row = engine.session(session) if session else _first_session(engine)
        if row is None:
            return _not_found(templates, f"no session {session!r}")
        resolved = _resolve_direction(row, direction)
        info = engine.provenance(row.session_id, resolved, offset) if resolved else None
        if info is None:
            return _not_found(templates, f"offset {offset} is outside the stream")
        return templates.TemplateResponse(
            request, "_provenance.html", {"info": info}
        )

    @app.get("/export/report", response_class=HTMLResponse)
    async def export_report(
        session: str | None = None, direction: str | None = None
    ) -> HTMLResponse:
        engine = _require_engine(app)
        return HTMLResponse(engine.report_html(session, direction))

    @app.post("/open")
    async def open_capture(
        capture: str = Form(...), rule: str = Form("")
    ) -> RedirectResponse:
        # Opening a different capture replaces the in-memory state. A bad path
        # or a malformed file raises WebEngineError, which the handler turns
        # into a 400 with the message.
        app.state.engine = WebEngine.open(capture, rule or None)
        return RedirectResponse(url="/", status_code=303)

    return app


def _require_engine(app: FastAPI) -> WebEngine:
    engine = app.state.engine
    if engine is None:
        raise WebEngineError(
            "no capture is open; start the server with --capture <file>"
        )
    return engine


def _first_session(engine: WebEngine):
    sessions = engine.sessions()
    return sessions[0] if sessions else None


def _resolve_direction(session, direction: str | None) -> str | None:
    if direction and direction in session.directions:
        return direction
    return session.directions[0] if session.directions else None


def _not_found(templates: Jinja2Templates, message: str) -> HTMLResponse:
    return HTMLResponse(
        templates.get_template("error.html").render(message=message),
        status_code=404,
    )


def _session_context(request: Request, engine: WebEngine) -> dict:
    return {
        "request": request,
        "capture_id": engine.capture_id,
        "source_file": engine.source_file,
        "sessions": engine.sessions(),
        "has_rule": engine.has_rule,
        "rule_id": engine.rule_id,
        "rule_version": engine.rule_version,
    }


def _port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Whether ``port`` can be bound on ``host`` right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Run the server on ``127.0.0.1``; report startup problems plainly."""
    parser = argparse.ArgumentParser(
        prog="python -m src.web.app",
        description="Serve the local web interface for a capture and a rule.",
    )
    parser.add_argument("--capture", type=Path, help="normalized JSON, or a raw pcap/pcapng")
    parser.add_argument("--rule", type=Path, default=None, help="rule JSON or YAML")
    parser.add_argument("--port", type=int, default=8765, help="TCP port (default 8765)")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address; defaults to localhost only",
    )
    args = parser.parse_args(argv)

    if args.host != "127.0.0.1":
        # The interface is meant for the local machine; refuse to expose it.
        print(
            f"refusing to bind {args.host}: this interface is local-only. "
            "Use --host 127.0.0.1.",
            file=sys.stderr,
        )
        return 2

    if not _port_available(args.port, args.host):
        print(
            f"port {args.port} is already in use; stop the other process or pass "
            f"--port <other>.",
            file=sys.stderr,
        )
        return 2

    try:
        app = create_app(args.capture, args.rule)
    except WebEngineError as exc:
        print(f"could not start: {exc}", file=sys.stderr)
        return 2

    import uvicorn

    print(f"serving on http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    except OSError as exc:  # pragma: no cover - depends on the runtime
        print(f"could not start the server: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
