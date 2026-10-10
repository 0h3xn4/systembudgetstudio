"""Compare two projects (revisions) or two scenarios: runs the budgets and diffs the reports."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from budget_core.compare import ComparisonResult, compare_documents, comparison_output
from budget_core.link.evaluate import link_pass_series, link_static_budget
from budget_core.mass.static_mass import static_mass_budget
from budget_core.model import Project
from budget_core.power.static_budget import static_power_budget
from budget_core.power.time_domain import time_domain_budget
from budget_core.provenance import Provenance, make_provenance
from budget_core.reports.document import ReportDocument
from budget_core.reports.link_report import build_link_report
from budget_core.reports.mass_report import build_mass_report
from budget_core.reports.power_report import build_power_report
from budget_core.reports.run import BudgetOutput
from budget_core.reports.thermal_report import build_thermal_report
from budget_core.reports.timeline_report import build_timeline_report
from budget_core.scenario.run import run_scenario
from budget_core.thermal.static_thermal import static_thermal_budget

STATIC_KINDS = ("power", "mass", "thermal", "link")
SCENARIO_KINDS = ("timeline", "link-passes")
ALL_KINDS = STATIC_KINDS + SCENARIO_KINDS
KIND_NAMES = {
    "power": "Static power budget",
    "mass": "Mass budget",
    "thermal": "Thermal budget",
    "link": "Link budget",
    "timeline": "Power timeline",
    "link-passes": "Link passes",
}


@dataclass(frozen=True)
class Side:
    """One side of a comparison: a project and, for the scenario budgets, a scenario id."""

    project: Project
    scenario: str | None = None

    @property
    def label(self) -> str:
        base = f"{self.project.meta.name} rev {self.project.meta.revision}"
        return base if self.scenario is None else f"{base}, {self.scenario}"


def short_labels(a: Side, b: Side) -> tuple[str, str]:
    """Column labels: only what differs between the sides (revision, scenario), else the full
    description; 'A' and 'B' when nothing differs."""

    def parts(side: Side, other: Side) -> list[str]:
        found: list[str] = []
        if side.project.meta.name != other.project.meta.name:
            found.append(side.project.meta.name)
        if side.project.meta.revision != other.project.meta.revision or found:
            found.append(f"rev {side.project.meta.revision}")
        if side.scenario != other.scenario:
            found.append(side.scenario or "no scenario")
        return found

    label_a, label_b = ", ".join(parts(a, b)), ", ".join(parts(b, a))
    return (label_a or "A", label_b or "B")


def default_kinds(a: Side, b: Side, same_project: bool) -> tuple[str, ...]:
    kinds: list[str] = [] if same_project else list(STATIC_KINDS)
    if a.scenario is not None and b.scenario is not None:
        kinds += SCENARIO_KINDS
    return tuple(kinds)


def _document(kind: str, side: Side, provenance: Provenance) -> ReportDocument | None:
    project = side.project
    if kind == "power":
        return build_power_report(project, static_power_budget(project), provenance, [])
    if kind == "mass":
        return build_mass_report(project, static_mass_budget(project), provenance, [])
    if kind == "thermal":
        return build_thermal_report(project, static_thermal_budget(project), provenance, [])
    if kind == "link":
        if not project.links:
            return None
        return build_link_report(project, link_static_budget(project), provenance, [], None)
    if side.scenario is None:
        return None
    run = run_scenario(project, side.scenario)
    if kind == "timeline":
        result = time_domain_budget(project, run)
        return build_timeline_report(project, result, provenance, [], plots=False)
    if not project.links:
        return None
    static = link_static_budget(project)
    return build_link_report(
        project, static, provenance, [], link_pass_series(project, run), plots=False
    )


def compare_sides(
    a: Side,
    b: Side,
    kinds: Sequence[str],
    *,
    user: str | None = None,
    generated_at: datetime | None = None,
    max_rows: int = 200,
) -> tuple[BudgetOutput, list[str]]:
    """Run each kind on both sides and diff. Returns the output and plain-language notes about
    kinds that could not be compared (for example a side without links)."""
    results: list[ComparisonResult] = []
    notes: list[str] = []
    short_a, short_b = short_labels(a, b)
    for kind in kinds:
        prov_a = make_provenance(
            a.project, a.scenario or "static (no scenario)", user=user, generated_at=generated_at
        )
        prov_b = make_provenance(
            b.project, b.scenario or "static (no scenario)", user=user, generated_at=generated_at
        )
        doc_a, doc_b = _document(kind, a, prov_a), _document(kind, b, prov_b)
        if doc_a is None or doc_b is None:
            notes.append(f"{KIND_NAMES[kind]}: not compared (missing links or scenario).")
            continue
        results.append(
            compare_documents(KIND_NAMES[kind], doc_a, doc_b, short_a, short_b, max_rows=max_rows)
        )
    scenario = f"{a.scenario or 'static'} vs {b.scenario or 'static'}"
    provenance = make_provenance(a.project, scenario, user=user, generated_at=generated_at)
    title = f"Comparison: {a.label} and {b.label}"
    return comparison_output(results, short_a, short_b, provenance, title), notes
