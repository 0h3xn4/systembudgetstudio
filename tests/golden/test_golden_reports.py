"""Golden tests of report content for the three reference projects (power budget, static)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.mass.static_mass import static_mass_budget
from budget_core.power.static_budget import static_power_budget
from budget_core.provenance import make_provenance
from budget_core.reports.export import mass_csv, result_csv, result_json
from budget_core.reports.mass_report import build_mass_report
from budget_core.reports.pdf import render_pdf
from budget_core.reports.power_report import build_power_report
from budget_core.reports.xlsx import render_xlsx
from tests.golden_util import check_golden, dump_pdf, dump_xlsx

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
# Stress case: golden covers the first rows/pages only; the full run is checked for size below.
LIMITS = {"cubesat_3u": (None, None), "microsat_150kg": (None, None), "stress_200_units": (14, 2)}


def build(name: str):  # type: ignore[no-untyped-def]
    result = load_project(EXAMPLES / name)
    assert result.project is not None
    power = static_power_budget(result.project)
    # Library and Python versions differ between CI jobs; pin them so goldens compare content only.
    prov = replace(
        make_provenance(result.project, user="Golden User", generated_at=WHEN),
        python_version="3.x",
        libraries=(("pinned", "for-golden-tests"),),
    )
    return power, prov, build_power_report(result.project, power, prov, result.problems)


@pytest.mark.parametrize("name", sorted(LIMITS))
def test_xlsx_golden(name: str) -> None:
    _, _, doc = build(name)
    rows, _ = LIMITS[name]
    check_golden(f"{name}_power.xlsx.txt", dump_xlsx(render_xlsx(doc), rows))


@pytest.mark.parametrize("name", sorted(LIMITS))
def test_pdf_golden(name: str) -> None:
    _, _, doc = build(name)
    _, pages = LIMITS[name]
    check_golden(f"{name}_power.pdf.txt", dump_pdf(render_pdf(doc), pages))


@pytest.mark.parametrize("name", sorted(LIMITS))
def test_json_golden(name: str) -> None:
    power, prov, _ = build(name)
    text = result_json(power, prov)
    if name == "stress_200_units":  # keep the repository small: hash plus size only
        import hashlib

        text = f"sha256={hashlib.sha256(text.encode()).hexdigest()}\nlength={len(text)}\n"
    check_golden(f"{name}_power.json.txt", text)


def test_csv_golden_cubesat() -> None:
    power, _, _ = build("cubesat_3u")
    check_golden("cubesat_3u_power_nominal.csv", result_csv(power.modes[1]))


def test_stress_case_is_complete() -> None:
    power, _, doc = build("stress_200_units")
    assert len(power.modes) == 5 and all(len(m.rows) == 200 for m in power.modes)
    assert len(doc.sections) == 1 + 5 + 3


# ---- mass budget -------------------------------------------------------------------------------


def build_mass(name: str):  # type: ignore[no-untyped-def]
    result = load_project(EXAMPLES / name)
    assert result.project is not None
    mass = static_mass_budget(result.project)
    prov = replace(
        make_provenance(result.project, user="Golden User", generated_at=WHEN),
        python_version="3.x",
        libraries=(("pinned", "for-golden-tests"),),
    )
    return mass, prov, build_mass_report(result.project, mass, prov, result.problems)


@pytest.mark.parametrize("name", sorted(LIMITS))
def test_mass_xlsx_golden(name: str) -> None:
    _, _, doc = build_mass(name)
    rows, _ = LIMITS[name]
    check_golden(f"{name}_mass.xlsx.txt", dump_xlsx(render_xlsx(doc), rows))


@pytest.mark.parametrize("name", sorted(LIMITS))
def test_mass_pdf_golden(name: str) -> None:
    _, _, doc = build_mass(name)
    _, pages = LIMITS[name]
    check_golden(f"{name}_mass.pdf.txt", dump_pdf(render_pdf(doc), pages))


@pytest.mark.parametrize("name", sorted(LIMITS))
def test_mass_json_golden(name: str) -> None:
    mass, prov, _ = build_mass(name)
    check_golden(f"{name}_mass.json.txt", result_json(mass, prov))


def test_mass_csv_golden_microsat() -> None:
    mass, _, _ = build_mass("microsat_150kg")
    check_golden("microsat_150kg_mass_launch.csv", mass_csv(mass.phases[0]))
