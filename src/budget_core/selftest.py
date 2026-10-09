"""Self-test of an installed or packaged build: no files read from the user, nothing written.

Builds an example project in memory, parses a unit string with pint, computes the static power
and mass budgets and renders XLSX and PDF with the bundled fonts. Used to verify the
PyInstaller bundle.
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
    except Exception as exc:  # report the kind of failure, never file content
        failures.append(f"{type(exc).__name__} during the self-test")
    return failures
