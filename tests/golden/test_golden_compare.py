"""Golden tests of the comparison outputs: the 3U example against a copy with one unit's power
and the project revision changed (invented values)."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from budget_core.compare_run import Side, compare_sides
from budget_core.io.project_loader import load_project
from budget_core.reports.docx import render_docx
from budget_core.reports.pdf import render_pdf
from budget_core.reports.run import BudgetOutput
from budget_core.reports.xlsx import render_xlsx
from tests.golden_util import check_golden, dump_docx, dump_pdf, dump_xlsx
from tests.helpers import edit

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.fixture
def out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BudgetOutput:
    monkeypatch.setattr("budget_core.provenance.platform.python_version", lambda: "3.x")
    monkeypatch.setattr("budget_core.provenance._lib_version", lambda name: "for-golden-tests")
    b = tmp_path / "rev2"
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", b)
    edit(b, "units/adcs.yaml", "avg_power_w: 0.9", "avg_power_w: 1.3")
    edit(b, "project.yaml", "revision: '1'", "revision: '2'")
    sides = []
    for path in (EXAMPLES / "cubesat_3u_eps", b):
        project = load_project(path).project
        assert project is not None
        sides.append(Side(project))
    output, _ = compare_sides(
        sides[0],
        sides[1],
        ("power", "mass", "thermal", "link"),
        user="Golden User",
        generated_at=WHEN,
    )
    return output


def test_xlsx(out: BudgetOutput) -> None:
    check_golden("compare_cubesat_3u_eps.xlsx.txt", dump_xlsx(render_xlsx(out.document)))


def test_pdf(out: BudgetOutput) -> None:
    check_golden("compare_cubesat_3u_eps.pdf.txt", dump_pdf(render_pdf(out.document)))


def test_docx(out: BudgetOutput) -> None:
    check_golden("compare_cubesat_3u_eps.docx.txt", dump_docx(render_docx(out.document)))


def test_csv_and_json(out: BudgetOutput) -> None:
    check_golden("compare_cubesat_3u_eps.csv", out.csv_files[0][1])
    assert out.json_text is not None
    check_golden("compare_cubesat_3u_eps.json.txt", out.json_text)
