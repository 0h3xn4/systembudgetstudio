"""`budget` command: `validate` and `export-schemas` (M1). Solvers and reports follow in M2+."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from budget_core import APP_NAME, __version__
from budget_core.examples import export_examples
from budget_core.io.project_loader import load_project
from budget_core.power.static_budget import static_power_budget
from budget_core.problems import Problem, Severity, sort_problems
from budget_core.provenance import make_provenance
from budget_core.reports.export import result_csv, result_json
from budget_core.reports.power_report import build_power_report
from budget_core.schemas import export_schemas

REPORTS = ("xlsx", "pdf", "json", "csv")


def _iso_datetime(text: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected an ISO 8601 date and time, e.g. 2026-01-02T03:04:05Z"
        ) from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="budget", description=f"{APP_NAME} command line.")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command")

    val = sub.add_parser("validate", help="Check a project folder and list problems.")
    val.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    val.add_argument("--format", choices=("text", "json"), default="text")
    val.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    run = sub.add_parser("run", help="Compute a budget and write reports and exports.")
    run.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    run.add_argument(
        "--budget",
        choices=("power",),
        default="power",
        help="Budget to compute (static power in M2a).",
    )
    run.add_argument(
        "--report",
        action="append",
        choices=REPORTS + ("all",),
        help="Output kind; repeat for several (default: all).",
    )
    run.add_argument("--out", type=Path, help="Output folder (default: <project>/results).")
    run.add_argument(
        "--user", help="User name for the provenance block (default: BUDGET_USER or login)."
    )
    run.add_argument(
        "--date",
        type=_iso_datetime,
        help="Generation time, ISO 8601 (default: SOURCE_DATE_EPOCH or now).",
    )
    run.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    sch = sub.add_parser("export-schemas", help="Write the JSON Schema of every file kind.")
    sch.add_argument("out_dir", type=Path)

    exa = sub.add_parser("export-examples", help="Write the three synthetic example projects.")
    exa.add_argument("out_dir", type=Path)
    return parser


def _count(problems: list[Problem], severity: Severity) -> int:
    return sum(1 for p in problems if p.severity is severity)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _validate(args: argparse.Namespace) -> int:
    result = load_project(args.project)
    problems = result.problems
    errors = _count(problems, Severity.ERROR)
    warnings = _count(problems, Severity.WARNING)
    if args.format == "json":
        payload = {
            "errors": errors,
            "warnings": warnings,
            "problems": [p.to_dict() for p in problems],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif not problems:
        print("No problems found.")
    else:
        for problem in problems:
            print(problem.format())
        print(f"{_plural(errors, 'error')}, {_plural(warnings, 'warning')}.")
    return 1 if errors or (args.strict and warnings) else 0


def _run(args: argparse.Namespace) -> int:
    loaded = load_project(args.project)
    errors = _count(loaded.problems, Severity.ERROR)
    if loaded.project is None or errors:
        for problem in loaded.problems:
            print(problem.format())
        print(f"{_plural(errors, 'error')}; nothing was written.")
        return 1

    project = loaded.project
    power = static_power_budget(project)
    provenance = make_provenance(project, user=args.user, generated_at=args.date)
    document = build_power_report(project, power, provenance, loaded.problems)
    wanted = set(args.report or ["all"])
    if "all" in wanted:
        wanted = set(REPORTS)

    out_dir = args.out or (args.project / "results")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def write(name: str, data: bytes | str) -> None:
        path = out_dir / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        written.append(path)

    # Renderers are imported only when needed: ReportLab pulls in networking modules (never used).
    if "xlsx" in wanted:
        from budget_core.reports.xlsx import render_xlsx

        write("power_static.xlsx", render_xlsx(document))
    if "pdf" in wanted:
        from budget_core.reports.pdf import render_pdf

        write("power_static.pdf", render_pdf(document))
    if "json" in wanted:
        write("power_static.json", result_json(power, provenance))
    if "csv" in wanted:
        for mode in power.modes:
            write(f"power_static_{mode.mode_id}.csv", result_csv(mode))

    problems = sort_problems([*loaded.problems, *power.problems])
    warnings = _count(problems, Severity.WARNING)
    for path in written:
        print(f"Wrote {path}")
    if document.banner:
        print(document.banner)
    print(f"{_plural(warnings, 'warning')}.")
    return 1 if args.strict and warnings else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args)
    if args.command == "run":
        return _run(args)
    if args.command == "export-schemas":
        for path in export_schemas(args.out_dir):
            print(path.name)
        return 0
    if args.command == "export-examples":
        for name in export_examples(args.out_dir):
            print(name)
        return 0
    parser.print_help(sys.stderr if argv else sys.stdout)
    return 0
