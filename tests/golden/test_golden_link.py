"""Golden tests of the link budget outputs: the static table of the microsatellite example (two
links, invented values) and the pass series of the synthetic test pass (pure arithmetic)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.link.evaluate import link_pass_series, link_static_budget
from budget_core.provenance import make_provenance
from budget_core.reports.docx import render_docx
from budget_core.reports.pdf import render_pdf
from budget_core.reports.run import link_output
from budget_core.reports.xlsx import render_xlsx
from tests.golden_util import check_golden, dump_docx, dump_pdf, dump_xlsx
from tests.link_helpers import link_project, pass_run

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def build(name: str):  # type: ignore[no-untyped-def]
    if name == "synthetic_passes":
        project, problems = link_project(), []
        static = link_static_budget(project)
        passes = link_pass_series(project, pass_run(aos_s=105.0, los_s=395.0))
    else:
        loaded = load_project(EXAMPLES / name)
        assert loaded.project is not None
        project, problems = loaded.project, loaded.problems
        static, passes = link_static_budget(project), None
    prov = replace(
        make_provenance(project, user="Golden User", generated_at=WHEN),
        python_version="3.x",
        libraries=(("pinned", "for-golden-tests"),),
    )
    return static, link_output(project, static, prov, problems, passes)


NAMES = ["microsat_150kg", "cubesat_3u", "synthetic_passes"]


@pytest.mark.parametrize("name", NAMES)
def test_xlsx(name: str) -> None:
    _, out = build(name)
    check_golden(f"link_{name}.xlsx.txt", dump_xlsx(render_xlsx(out.document)))


@pytest.mark.parametrize("name", NAMES)
def test_pdf(name: str) -> None:
    _, out = build(name)
    check_golden(f"link_{name}.pdf.txt", dump_pdf(render_pdf(out.document)))


@pytest.mark.parametrize("name", NAMES)
def test_docx(name: str) -> None:
    _, out = build(name)
    check_golden(f"link_{name}.docx.txt", dump_docx(render_docx(out.document)))


@pytest.mark.parametrize("name", NAMES)
def test_json(name: str) -> None:
    _, out = build(name)
    assert out.json_text is not None
    check_golden(f"link_{name}.json.txt", out.json_text)


def test_csv_files() -> None:
    _, out = build("microsat_150kg")
    check_golden("link_microsat_150kg_table.csv", dict(out.csv_files)["link_static_table.csv"])
    _, out = build("synthetic_passes")
    files = dict(out.csv_files)
    check_golden("link_synthetic_summary.csv", files["link_passes_synthetic_summary.csv"])
    head = "".join(files["link_passes_synthetic_dl.csv"].splitlines(keepends=True)[:5])
    check_golden("link_synthetic_dl_head.csv", head)
