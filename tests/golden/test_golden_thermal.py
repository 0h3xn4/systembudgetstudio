"""Golden tests of the static thermal budget reports: the two-node test project and the complete
CubeSat example (pure arithmetic, so the numbers are the same on every platform)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.provenance import make_provenance
from budget_core.reports.docx import render_docx
from budget_core.reports.export import thermal_case_csv
from budget_core.reports.pdf import render_pdf
from budget_core.reports.run import thermal_output
from budget_core.reports.xlsx import render_xlsx
from budget_core.thermal.static_thermal import static_thermal_budget
from tests.golden_util import check_golden, dump_docx, dump_pdf, dump_xlsx
from tests.thermal_helpers import thermal_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def build(name: str):  # type: ignore[no-untyped-def]
    if name == "two_nodes":
        project, problems = thermal_project(), []
    else:
        loaded = load_project(EXAMPLES / name)
        assert loaded.project is not None
        project, problems = loaded.project, loaded.problems
    result = static_thermal_budget(project)
    prov = replace(
        make_provenance(project, user="Golden User", generated_at=WHEN),
        python_version="3.x",
        libraries=(("pinned", "for-golden-tests"),),
    )
    return result, thermal_output(project, result, prov, problems)


NAMES = ["two_nodes", "cubesat_3u_eps", "cubesat_3u"]


@pytest.mark.parametrize("name", NAMES)
def test_xlsx(name: str) -> None:
    _, out = build(name)
    check_golden(f"thermal_{name}.xlsx.txt", dump_xlsx(render_xlsx(out.document)))


@pytest.mark.parametrize("name", NAMES)
def test_pdf(name: str) -> None:
    _, out = build(name)
    check_golden(f"thermal_{name}.pdf.txt", dump_pdf(render_pdf(out.document)))


@pytest.mark.parametrize("name", NAMES)
def test_docx(name: str) -> None:
    _, out = build(name)
    check_golden(f"thermal_{name}.docx.txt", dump_docx(render_docx(out.document)))


@pytest.mark.parametrize("name", NAMES)
def test_json(name: str) -> None:
    from budget_core.reports.export import result_json

    result, out = build(name)
    check_golden(f"thermal_{name}.json.txt", result_json(result, out.provenance))


def test_csv_files() -> None:
    result, out = build("cubesat_3u_eps")
    files = dict(out.csv_files)
    check_golden("thermal_cubesat_3u_eps_hot.csv", files["thermal_case_hot.csv"])
    check_golden("thermal_cubesat_3u_eps_imaging.csv", files["thermal_static_imaging.csv"])
    assert files["thermal_case_cold.csv"] == thermal_case_csv(result.cases[0])
