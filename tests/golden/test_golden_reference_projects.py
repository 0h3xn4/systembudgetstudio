"""Acceptance (M6): every reference project produces golden reports for every budget it has.

Static power and mass goldens of the three reference projects are in test_golden_reports.py; this
file adds the thermal budget, the power timeline and the link passes, so that each of the three
(3U CubeSat, 150 kg microsatellite with two links, 200-unit stress case with a one-week scenario)
has a golden XLSX and PDF for all of them. The stress case golden covers the first rows and pages
(full-precision JSON is not compared here: last digits of solver and propagation results can
differ between platforms); completeness of the full outputs is checked elsewhere."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.link.evaluate import link_pass_series, link_static_budget
from budget_core.power.time_domain import time_domain_budget
from budget_core.provenance import make_provenance
from budget_core.reports.pdf import render_pdf
from budget_core.reports.run import BudgetOutput, link_output, thermal_output, timeline_output
from budget_core.reports.xlsx import render_xlsx
from budget_core.scenario.run import run_scenario
from budget_core.thermal.static_thermal import static_thermal_budget
from tests.golden_util import check_golden, dump_pdf, dump_xlsx

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
ROWS, PAGES = 40, 3

CASES = [
    (kind, name)
    for name in ("cubesat_3u", "microsat_150kg", "stress_200_units")
    for kind in ("thermal", "timeline", "link-passes")
    if not (kind == "link-passes" and name == "stress_200_units")  # the stress case has no links
]
_cache: dict[tuple[str, str], BudgetOutput] = {}


def build(kind: str, name: str) -> BudgetOutput:
    if (kind, name) in _cache:
        return _cache[(kind, name)]
    loaded = load_project(EXAMPLES / name)
    assert loaded.project is not None
    project = loaded.project
    prov = replace(
        make_provenance(project, user="Golden User", generated_at=WHEN),
        python_version="3.x",
        libraries=(("pinned", "for-golden-tests"),),
    )
    if kind == "thermal":
        out = thermal_output(project, static_thermal_budget(project), prov, loaded.problems)
    else:
        run = run_scenario(project, sorted(project.scenarios)[0])
        if kind == "timeline":
            result = time_domain_budget(project, run)
            out = timeline_output(
                project, result, prov, loaded.problems, plots=False, series_every=3600
            )
        else:
            out = link_output(
                project,
                link_static_budget(project),
                prov,
                loaded.problems,
                link_pass_series(project, run),
                plots=False,
            )
    _cache[(kind, name)] = out
    return out


def whole_seconds(text: str) -> str:
    """Pass times are refined by bisection to about a millisecond; the last digits depend on the
    platform's floating point, so compare them to the second."""
    return re.sub(r"(\d\d:\d\d:\d\d)\.\d+Z", r"\1Z", text)


@pytest.mark.parametrize(("kind", "name"), CASES)
def test_xlsx(kind: str, name: str) -> None:
    dump = dump_xlsx(render_xlsx(build(kind, name).document), ROWS, significant_digits=6)
    check_golden(f"ref_{kind}_{name}.xlsx.txt", whole_seconds(dump))


@pytest.mark.parametrize(("kind", "name"), CASES)
def test_pdf(kind: str, name: str) -> None:
    dump = dump_pdf(render_pdf(build(kind, name).document), PAGES)
    check_golden(f"ref_{kind}_{name}.pdf.txt", whole_seconds(dump))
