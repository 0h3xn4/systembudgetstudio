"""Golden tests of the time-domain power outputs on a synthetic environment (pure arithmetic, so
the numbers are the same on every platform): report content in every format, CSV and JSON."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from budget_core.power.time_domain import time_domain_budget
from budget_core.provenance import make_provenance
from budget_core.reports.docx import render_docx
from budget_core.reports.pdf import render_pdf
from budget_core.reports.run import timeline_output
from budget_core.reports.xlsx import render_xlsx
from tests.golden_util import check_golden, dump_docx, dump_pdf, dump_xlsx
from tests.power_helpers import power_system, sv, synthetic_env, synthetic_run, td_project

WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.fixture(scope="module")
def output():  # type: ignore[no-untyped-def]
    """Two orbits of 6000 s, one eclipse each; mode B (100 W) during the eclipses, mode A (40 W)
    otherwise. The depth-of-discharge limit 0.3 is exceeded in the eclipses at end of life."""
    system = power_system()
    battery = system.battery.model_copy(update={"max_dod_ratio": {"eol": sv(0.15)}})
    project = td_project(system=system.model_copy(update={"battery": battery}))
    env = synthetic_env(12000.0, 20.0, [(3000.0, 4800.0), (9000.0, 10800.0)])
    from budget_core.model import ScenarioRule

    run = synthetic_run(env, rules=[ScenarioRule(kind="in_eclipse", mode="b")])
    result = time_domain_budget(project, run)
    prov = replace(
        make_provenance(project, scenario="synthetic", user="Golden User", generated_at=WHEN),
        python_version="3.x",
        libraries=(("pinned", "for-golden-tests"),),
    )
    return timeline_output(project, result, prov)


def test_xlsx(output) -> None:  # type: ignore[no-untyped-def]
    check_golden("timeline_synthetic.xlsx.txt", dump_xlsx(render_xlsx(output.document)))


def test_pdf(output) -> None:  # type: ignore[no-untyped-def]
    check_golden("timeline_synthetic.pdf.txt", dump_pdf(render_pdf(output.document)))


def test_docx(output) -> None:  # type: ignore[no-untyped-def]
    check_golden("timeline_synthetic.docx.txt", dump_docx(render_docx(output.document)))


def test_json(output) -> None:  # type: ignore[no-untyped-def]
    check_golden("timeline_synthetic.json.txt", output.json_text)


def test_csv_files(output) -> None:  # type: ignore[no-untyped-def]
    files = dict(output.csv_files)
    head = "".join(files["power_time_synthetic_bol.csv"].splitlines(keepends=True)[:6])
    check_golden("timeline_synthetic_bol_head.csv", head)
    check_golden("timeline_synthetic_violations.csv", files["power_time_synthetic_violations.csv"])
    check_golden("timeline_synthetic_orbits.csv", files["power_time_synthetic_orbits.csv"])
