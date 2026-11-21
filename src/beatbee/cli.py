import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .discogs_client import DiscogsSearchClient
from .html_report import render_html_report
from .publisher import Publisher, UnavailablePublisher
from .search import FakeSearchAdapter, SearchAdapter, SearchOutcome
from .service import search_all
from .summary import ManifestExporter
from .token import load_discogs_token
from .validation import InputValidationError, load_input


EXIT_OK = 0
EXIT_UNRESOLVED = 1
EXIT_INVALID_INPUT = 2
EXIT_SEARCH_FAILED = 3
EXIT_PUBLISHING_FAILED = 4


def _same_path(first: Path, second: Path) -> bool:
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and first.samefile(second)
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="beatbee",
        description="Validate Discogs Master searches and export manual lists.",
    )
    subcommands = parser.add_subparsers(dest="command")
    validate = subcommands.add_parser("validate")
    validate.add_argument("input", help="Path to input JSON")
    run = subcommands.add_parser("run")
    run.add_argument("input", help="Path to input JSON")
    run.add_argument(
        "--manifest",
        help="Write the ordered Master manifest JSON for an all-OK run",
    )
    export = subcommands.add_parser(
        "export",
        help="Export a manual Discogs list checklist; never publish",
    )
    export.add_argument("input", help="Path to input JSON")
    export.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        dest="export_format",
    )
    export.add_argument(
        "--output",
        required=True,
        help="Output file for the manual checklist",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    adapter: SearchAdapter | None = None,
    publisher: Publisher | None = None,
    token: str | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_OK
    try:
        validated = load_input(args.input)
    except InputValidationError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    if adapter is not None:
        selected_adapter = adapter
    else:
        if token is None:
            token = load_discogs_token()
        if token is None:
            selected_adapter = FakeSearchAdapter(
                default=SearchOutcome(
                    error="Discogs token unavailable; set DISCOGS_TOKEN or discogsToken.json."
                )
            )
        else:
            selected_adapter = DiscogsSearchClient(token)
    total = len(validated.records)
    interactive = sys.stderr.isatty()

    def show_progress(completed: int, total: int) -> None:
        width = 20
        filled = completed * width // total
        percent = completed * 100 // total
        bar = "#" * filled + "-" * (width - filled)
        end = "\n" if not interactive or completed == total else "\r"
        print(
            f"Progress: [{bar}] {percent:3d}% ({completed}/{total} processed)",
            file=sys.stderr,
            end=end,
            flush=True,
        )

    show_progress(0, total)
    summary = search_all(validated, selected_adapter, on_progress=show_progress)
    input_path = Path(args.input)
    report_path = input_path.with_name(input_path.stem + ".summary.html")
    try:
        if report_path.is_symlink() or _same_path(report_path, input_path):
            raise OSError("Report path points to the input file or is a symbolic link.")
        output_path = None
        if args.command == "export":
            output_path = Path(args.output)
        elif args.command == "run" and args.manifest:
            output_path = Path(args.manifest)
        if output_path and (
            _same_path(output_path, report_path) or _same_path(output_path, input_path)
        ):
            raise OSError("Export or manifest path conflicts with the input or report path.")
        report_path.write_text(render_html_report(summary), encoding="utf-8")
    except OSError as exc:
        print(f"Could not write HTML report: {exc}", file=sys.stderr)
        return EXIT_SEARCH_FAILED
    print(f"HTML report: {report_path}")

    if any(
        result.status.value == "ERROR"
        for result in summary.results
    ):
        exit_code = EXIT_SEARCH_FAILED
    elif not summary.all_ok:
        exit_code = EXIT_UNRESOLVED
    elif args.command == "run":
        manifest_path = getattr(args, "manifest", None)
        if manifest_path:
            manifest = ManifestExporter().export_json(summary, manifest_path)
            print(f"Manifest written: {manifest_path}")
        selected_publisher = publisher or UnavailablePublisher()
        outcome = selected_publisher.publish(summary)
        print(outcome.message)
        exit_code = EXIT_OK if outcome.confirmed else EXIT_PUBLISHING_FAILED
    elif args.command == "export":
        exporter = ManifestExporter()
        if args.export_format == "markdown":
            exporter.export_markdown(summary, args.output)
        else:
            exporter.export_json(summary, args.output)
        print(
            f"Manual checklist written: {args.output}\n"
            "This file is not proof that a Discogs list was created."
        )
        exit_code = EXIT_OK
    else:
        exit_code = EXIT_OK

    return exit_code
