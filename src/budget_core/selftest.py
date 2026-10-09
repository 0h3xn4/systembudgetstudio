"""Self-test of an installed or packaged build: no files read from the user, nothing written.

Builds an example project in memory, parses a unit string with pint, propagates one orbit,
computes the static power and mass budgets and the time-domain power budget, and renders XLSX,
PDF and DOCX (with a plot) using the bundled fonts. Used to verify the PyInstaller bundle.
"""

from __future__ import annotations

from budget_core.environment.data import TimeGrid
from budget_core.environment.elements import ElementsPropagator
from budget_core.examples import EXAMPLES
from budget_core.mass.static_mass import static_mass_budget
from budget_core.power.static_budget import static_power_budget
from budget_core.provenance import make_provenance
from budget_core.reports.mass_report import build_mass_report
from budget_core.reports.power_report import build_power_report
from budget_core.units.quantity import parse_quantity


def run_selftest() -> list[str]:
    """Return a list of failures (empty means everything works)."""
    # Imported here, not at module level: ReportLab pulls in networking modules (never used).
    from budget_core.reports.docx import render_docx
    from budget_core.reports.pdf import render_pdf
    from budget_core.reports.xlsx import render_xlsx

    failures: list[str] = []
    try:
        if abs(parse_quantity("2.2 GHz", "freq_hz") - 2.2e9) > 1.0:
            failures.append("unit parsing gave a wrong value")
        project = EXAMPLES["cubesat_3u"]()
        orbit = next(iter(project.orbits.values()))
        scenario = next(iter(project.scenarios.values()))
        from budget_core.scenario.run import grid_for, sites_for

        env = ElementsPropagator(orbit).compute(
            TimeGrid(grid_for(scenario).start, 6000.0, 30.0),
            sites_for(project, scenario),
            "cylindrical",
        )
        if not env.eclipses:
            failures.append("the orbit propagation found no eclipse in one orbit")
        power = static_power_budget(project)
        provenance = make_provenance(project, user="self-test")
        document = build_power_report(project, power, provenance)
        mass_document = build_mass_report(project, static_mass_budget(project), provenance)
        if not render_xlsx(mass_document).startswith(b"PK"):
            failures.append("mass XLSX output is not a ZIP file")
        if not render_xlsx(document).startswith(b"PK"):
            failures.append("XLSX output is not a ZIP file")
        pdf = render_pdf(document)
        if not pdf.startswith(b"%PDF-") or b"IBMPlexSans" not in pdf:
            failures.append("PDF output is missing or lacks the bundled font")
        if not render_docx(document).startswith(b"PK"):
            failures.append("DOCX output is not a ZIP file")
        failures += _time_domain_check()
    except Exception as exc:  # report the kind of failure, never file content
        failures.append(f"{type(exc).__name__} during the self-test")
    return failures


def _time_domain_check() -> list[str]:
    """One orbit of the complete-power example: array, battery, plot, DOCX with the picture."""
    from budget_core.power.time_domain import time_domain_budget
    from budget_core.reports.docx import render_docx
    from budget_core.reports.run import timeline_output
    from budget_core.scenario.run import ScenarioRun, grid_for, sites_for
    from budget_core.scenario.timeline import build_timeline

    project = EXAMPLES["cubesat_3u_eps"]()
    orbit = next(iter(project.orbits.values()))
    scenario = project.scenarios["one_day"].model_copy(
        update={"duration_s": 6000.0, "step_s": 30.0}
    )
    env = ElementsPropagator(orbit).compute(
        TimeGrid(grid_for(scenario).start, 6000.0, 30.0),
        sites_for(project, scenario),
        "cylindrical",
    )
    run = ScenarioRun("one_day", scenario, env, build_timeline(scenario, env), ())
    result = time_domain_budget(project, run)
    out = timeline_output(project, result, make_provenance(project, user="self-test"))
    failures: list[str] = []
    if any(c.energy_wh is None for c in result.cases):
        failures.append("the time-domain budget gave no battery state")
    if not any(s.figures for s in out.document.sections):
        failures.append("the time-domain report has no plot")
    elif not render_docx(out.document).startswith(b"PK"):
        failures.append("time-domain DOCX output is not a ZIP file")
    return failures
