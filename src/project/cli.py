"""Command line entry point for the project container and the pipeline.

    python -m src.project.cli pipeline --pcap cap.pcapng --project project.madrigal
    python -m src.project.cli create --path project.madrigal
    python -m src.project.cli open --path project.madrigal --show
    python -m src.project.cli add-capture --project project.madrigal --pcap cap.pcapng
    python -m src.project.cli export --project project.madrigal --out project.zip
    python -m src.project.cli import --in project.zip --target /tmp/restored

``pipeline`` runs the full path: create the project, add the capture, normalize
it, optionally apply a rule, and write the report in Markdown and HTML.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.project.pipeline import PipelineError, PipelineOutcome, run_pipeline
from src.project.project import MANIFEST_FILE, Project, ProjectError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.project.cli",
        description="Manage an investigation project and run the full pipeline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pipeline = sub.add_parser(
        "pipeline", help="capture a PCAP into a project and write the report"
    )
    pipeline.add_argument("--pcap", required=True, type=Path, help="input capture")
    pipeline.add_argument("--project", required=True, type=Path, help="project directory")
    pipeline.add_argument("--name", default=None, help="project name")
    pipeline.add_argument("--rule", default=None, type=Path, help="rule to apply (JSON or YAML)")
    pipeline.add_argument("--report", default=None, type=Path, help="also write the Markdown report here")
    pipeline.add_argument("--no-html", action="store_true", help="do not write the HTML report")
    pipeline.add_argument("--wireshark-pcap", action="store_true", help="also write reassembled streams as a pcap")
    pipeline.add_argument("--stream", action="store_true", help="normalize in streaming mode")
    pipeline.add_argument("--chunk-size", type=int, default=10000, help="packets per block in streaming mode")
    pipeline.add_argument("--force", action="store_true", help="replace the project directory if it exists")
    pipeline.add_argument("--quiet", action="store_true", help="do not print the summary")

    create = sub.add_parser("create", help="create an empty project")
    create.add_argument("--path", required=True, type=Path, help="project directory")
    create.add_argument("--name", default=None, help="project name")

    open_ = sub.add_parser("open", help="open a project and print its manifest")
    open_.add_argument("--path", required=True, type=Path, help="project directory")
    open_.add_argument("--show", action="store_true", help="print the manifest")

    add = sub.add_parser("add-capture", help="copy a capture into the project")
    add.add_argument("--project", required=True, type=Path, help="project directory")
    add.add_argument("--pcap", required=True, type=Path, help="capture to add")

    export = sub.add_parser("export", help="export a project to a zip archive")
    export.add_argument("--project", required=True, type=Path, help="project directory")
    export.add_argument("--out", required=True, type=Path, help="output archive")

    import_ = sub.add_parser("import", help="import a project zip into a directory")
    import_.add_argument("--in", dest="in_zip", required=True, type=Path, help="archive to import")
    import_.add_argument("--target", required=True, type=Path, help="directory to create")

    return parser


def _run_pipeline(args: argparse.Namespace) -> int:
    try:
        outcome = run_pipeline(
            args.pcap,
            args.project,
            name=args.name,
            rule_path=args.rule,
            report_path=args.report,
            html=not args.no_html,
            wireshark=args.wireshark_pcap,
            streaming=args.stream,
            chunk_size=args.chunk_size,
            force=args.force,
        )
    except (ProjectError, PipelineError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - the CLI reports any failure
        print(f"pipeline failed: {exc}", file=sys.stderr)
        return 1
    _print_outcome(outcome, quiet=args.quiet)
    return 0


def _print_outcome(outcome: PipelineOutcome, *, quiet: bool) -> None:
    if quiet:
        return
    summary = {
        "project": str(outcome.project.root),
        "normalized": str(outcome.normalized),
        "sessions": outcome.sessions,
        "streaming": outcome.streaming,
    }
    if outcome.result is not None:
        summary["result"] = str(outcome.result)
    if outcome.report_md is not None:
        summary["report"] = str(outcome.report_md)
    if outcome.report_html is not None:
        summary["report_html"] = str(outcome.report_html)
    if outcome.wireshark is not None:
        summary["wireshark"] = str(outcome.wireshark)
    print(json.dumps(summary))


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "pipeline":
        return _run_pipeline(args)

    try:
        if args.command == "create":
            project = Project.create(args.path, args.name or f"{args.path.name} investigation")
            print(json.dumps({"project": str(project.root), "name": project.name}))
            return 0

        if args.command == "open":
            project = Project.open(args.path)
            payload = {
                "project": str(project.root),
                "name": project.name,
                "captures": project.manifest.captures,
                "rules": project.manifest.rules,
                "results": project.manifest.results,
            }
            if args.show:
                manifest = json.loads(
                    project.path(MANIFEST_FILE).read_text(encoding="utf-8")
                )
                payload["manifest"] = manifest
            print(json.dumps(payload, indent=2 if args.show else None))
            return 0

        if args.command == "add-capture":
            project = Project.open(args.project)
            relative = project.add_capture(args.pcap)
            project.save()
            print(json.dumps({"capture": relative}))
            return 0

        if args.command == "export":
            project = Project.open(args.project)
            project.export(args.out)
            print(json.dumps({"archive": str(args.out)}))
            return 0

        if args.command == "import":
            project = Project.import_(args.in_zip, args.target)
            broken = project.verify_captures()
            print(json.dumps({"project": str(project.root), "broken": broken}))
            return 0
    except ProjectError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
