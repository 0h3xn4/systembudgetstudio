"""`budget` command: `validate` and `export-schemas` (M1). Solvers and reports follow in M2+."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from budget_core import APP_NAME, __version__
from budget_core.examples import export_examples
from budget_core.io.project_loader import load_project
from budget_core.problems import Problem, Severity
from budget_core.schemas import export_schemas


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="budget", description=f"{APP_NAME} command line.")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command")

    val = sub.add_parser("validate", help="Check a project folder and list problems.")
    val.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    val.add_argument("--format", choices=("text", "json"), default="text")
    val.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args)
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
