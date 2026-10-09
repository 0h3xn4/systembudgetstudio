"""`budget` command: validate, run (static budgets), scenario, power-timeline, schemas, examples."""

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
from budget_core.mass.static_mass import static_mass_budget
from budget_core.power.static_budget import static_power_budget
from budget_core.power.time_domain import time_domain_budget, violation_problems
from budget_core.problems import Problem, Severity, sort_problems
from budget_core.provenance import make_provenance
from budget_core.reports.run import (
    REPORT_KINDS,
    BudgetOutput,
    mass_output,
    power_output,
    thermal_output,
    timeline_output,
    write_outputs,
)
from budget_core.scenario.export import write_scenario_outputs
from budget_core.scenario.run import ScenarioRunError, run_scenario
from budget_core.schemas import export_schemas
from budget_core.selftest import run_selftest
from budget_core.thermal.static_thermal import static_thermal_budget

REPORTS = REPORT_KINDS


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
        choices=("power", "mass", "thermal", "all"),
        default="all",
        help="Budget to compute (default: all).",
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

    scn = sub.add_parser(
        "scenario", help="Compute a scenario's eclipses, passes and mode timeline."
    )
    scn.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    scn.add_argument(
        "--scenario", help="Scenario id (file name in scenarios/); optional if only one."
    )
    scn.add_argument("--out", type=Path, help="Output folder (default: <project>/results).")
    scn.add_argument("--user", help="User name for the provenance block.")
    scn.add_argument("--date", type=_iso_datetime, help="Generation time, ISO 8601.")

    pt = sub.add_parser(
        "power-timeline",
        help="Compute the time-domain power budget of a scenario (array, battery, violations).",
    )
    pt.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    pt.add_argument(
        "--scenario", help="Scenario id (file name in scenarios/); optional if only one."
    )
    pt.add_argument(
        "--case",
        choices=("bol", "eol", "both"),
        default="both",
        help="Beginning of life, end of life or both (default: both).",
    )
    pt.add_argument(
        "--load-basis",
        choices=("nominal", "margined"),
        default="nominal",
        help="Demand without margins or with unit and system margins (default: nominal).",
    )
    pt.add_argument("--phase", help="Mission phase for the depth-of-discharge limit.")
    pt.add_argument(
        "--report",
        action="append",
        choices=REPORTS + ("all",),
        help="Output kind; repeat for several (default: all).",
    )
    pt.add_argument("--out", type=Path, help="Output folder (default: <project>/results).")
    pt.add_argument(
        "--series-every",
        type=int,
        default=1,
        metavar="N",
        help="Keep every N-th step in the series CSV (default 1: all steps).",
    )
    pt.add_argument("--no-plots", action="store_true", help="Leave the plots out of the reports.")
    pt.add_argument("--user", help="User name for the provenance block.")
    pt.add_argument("--date", type=_iso_datetime, help="Generation time, ISO 8601.")
    pt.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    sub.add_parser(
        "self-test", help="Check that this installation can compute and render a budget."
    )

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
    provenance = make_provenance(project, user=args.user, generated_at=args.date)
    outputs: list[BudgetOutput] = []
    problems: list[Problem] = list(loaded.problems)
    if args.budget in ("power", "all"):
        power = static_power_budget(project)
        outputs.append(power_output(project, power, provenance, loaded.problems))
        problems += power.problems
    if args.budget in ("mass", "all"):
        mass = static_mass_budget(project)
        outputs.append(mass_output(project, mass, provenance, loaded.problems))
        problems += mass.problems

    if args.budget in ("thermal", "all"):
        thermal = static_thermal_budget(project)
        outputs.append(thermal_output(project, thermal, provenance, loaded.problems))
        problems += thermal.problems

    wanted = set(args.report or ["all"])
    if "all" in wanted:
        wanted = set(REPORTS)
    out_dir = args.out or (args.project / "results")
    written = write_outputs(outputs, out_dir, wanted)

    problems = sort_problems(problems)
    result_errors = [p for p in problems if p.severity is Severity.ERROR]
    warnings = _count(problems, Severity.WARNING)
    for path in written:
        print(f"Wrote {path}")
    for problem in result_errors:  # findings such as an exceeded mass limit
        print(problem.format())
    if any(o.document.banner for o in outputs):
        print(outputs[0].document.banner)
    print(f"{_plural(len(result_errors), 'error')}, {_plural(warnings, 'warning')}.")
    return 1 if result_errors or (args.strict and warnings) else 0


def _scenario(args: argparse.Namespace) -> int:
    loaded = load_project(args.project)
    errors = _count(loaded.problems, Severity.ERROR)
    if loaded.project is None or errors:
        for problem in loaded.problems:
            print(problem.format())
        print(f"{_plural(errors, 'error')}; nothing was written.")
        return 1
    project = loaded.project
    scenario_id = args.scenario
    if scenario_id is None and len(project.scenarios) == 1:
        scenario_id = next(iter(project.scenarios))
    try:
        run = run_scenario(project, scenario_id or "")
    except ScenarioRunError as exc:
        print(exc.problem.format())
        return 1
    provenance = make_provenance(
        project, scenario=run.scenario_id, user=args.user, generated_at=args.date
    )
    written = write_scenario_outputs(run, provenance, args.out or (args.project / "results"))
    env = run.env
    passes = ", ".join(f"{sid} {len(v.passes)}" for sid, v in sorted(env.sites.items()))
    print(
        f"Scenario {run.scenario_id} ({env.source}): {len(env.eclipses)} eclipse(s)"
        + (f"; passes: {passes}" if passes else "")
        + f"; {len(run.timeline)} timeline segment(s)."
    )
    for note in run.notes:
        print(f"Note: {note}")
    for path in written:
        print(f"Wrote {path}")
    return 0


def _power_timeline(args: argparse.Namespace) -> int:
    loaded = load_project(args.project)
    errors = _count(loaded.problems, Severity.ERROR)
    if loaded.project is None or errors:
        for problem in loaded.problems:
            print(problem.format())
        print(f"{_plural(errors, 'error')}; nothing was written.")
        return 1
    project = loaded.project
    scenario_id = args.scenario
    if scenario_id is None and len(project.scenarios) == 1:
        scenario_id = next(iter(project.scenarios))
    try:
        run = run_scenario(project, scenario_id or "")
    except ScenarioRunError as exc:
        print(exc.problem.format())
        return 1
    cases = ("bol", "eol") if args.case == "both" else (args.case,)
    result = time_domain_budget(
        project, run, load_basis=args.load_basis, cases=cases, mission_phase=args.phase
    )
    provenance = make_provenance(
        project, scenario=run.scenario_id, user=args.user, generated_at=args.date
    )
    output = timeline_output(
        project,
        result,
        provenance,
        loaded.problems,
        plots=not args.no_plots,
        series_every=args.series_every,
    )
    wanted = set(args.report or ["all"])
    if "all" in wanted:
        wanted = set(REPORTS)
    written = write_outputs([output], args.out or (args.project / "results"), wanted)
    for path in written:
        print(f"Wrote {path}")
    for case in result.cases:
        s = case.summary
        if s.generated_wh is None:
            print(f"{case.case.upper()}: n/a (inputs missing, see the problems below).")
            continue
        soc = "n/a" if s.minimum_soc_ratio is None else f"{s.minimum_soc_ratio * 100:.1f} %"
        print(
            f"{case.case.upper()}: generated {s.generated_wh:.1f} Wh, lowest state of charge "
            f"{soc}, {len(case.violations)} violation(s)."
        )
    problems = sort_problems([*result.problems, *violation_problems(result)])
    findings = [p for p in problems if p.severity is Severity.ERROR]
    warnings = _count(problems, Severity.WARNING)
    for problem in findings:
        print(problem.format())
    if output.document.banner:
        print(output.document.banner)
    print(f"{_plural(len(findings), 'error')}, {_plural(warnings, 'warning')}.")
    return 1 if findings or (args.strict and warnings) else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args)
    if args.command == "scenario":
        return _scenario(args)
    if args.command == "power-timeline":
        return _power_timeline(args)
    if args.command == "self-test":
        failures = run_selftest()
        for failure in failures:
            print(f"FAILED: {failure}")
        print("Self-test passed." if not failures else f"{len(failures)} check(s) failed.")
        return 1 if failures else 0
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
