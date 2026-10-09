"""Build the static mass budget report document (renderer independent)."""

from __future__ import annotations

from budget_core.mass.static_mass import PhaseMass, StaticMassResult
from budget_core.model import Project
from budget_core.problems import Problem
from budget_core.provenance import Provenance
from budget_core.reports.common import BANNER, closing_sections, sheet_name
from budget_core.reports.document import Cell, Column, ReportDocument, Section, Table


def _kg(header: str) -> Column:
    return Column(f"{header} (kg)", "number", 3, "kg")


def _m(header: str) -> Column:
    return Column(f"{header} (m)", "number", 4, "m")


def _summary(result: StaticMassResult) -> Table:
    rows: list[tuple[Cell, ...]] = []
    for p in result.phases:
        c = p.cog
        x, y, z = c.position_m if c else (None, None, None)
        rows.append(
            (
                p.phase,
                p.total_kg,
                p.unit_margined_kg,
                p.system_margined_kg,
                x,
                y,
                z,
                c.coverage_ratio if c else None,
            )
        )
    return Table(
        "Mass and centre of gravity by mission phase",
        (
            Column("Phase"),
            _kg("Total"),
            _kg("With unit margins"),
            _kg("With system margin"),
            _m("CG x"),
            _m("CG y"),
            _m("CG z"),
            Column("CG coverage", "percent", 3),
        ),
        tuple(rows),
        note="CG and inertia use nominal masses of items with a position; coverage is their share "
        "of the nominal total.",
    )


def _limits(result: StaticMassResult) -> Table:
    rows: list[tuple[Cell, ...]] = []
    for p in result.phases:
        for check in p.limits:
            rows.append(
                (p.phase, check.name, check.limit_kg, check.total_kg, check.margin_kg, check.status)
            )
    return Table(
        "Mass limits (checked against the system-margined total)",
        (
            Column("Phase"),
            Column("Limit"),
            _kg("Limit value"),
            _kg("Total"),
            _kg("Margin"),
            Column("Status"),
        ),
        tuple(rows),
    )


def _items(p: PhaseMass) -> Table:
    rows: list[tuple[Cell, ...]] = []
    for r in p.rows:
        x, y, z = r.position_m if r.position_m else (None, None, None)
        rows.append(
            (
                r.item_id,
                r.name,
                r.kind,
                r.subsystem,
                r.maturity,
                r.mass_kg,
                r.margin_ratio,
                r.margined_mass_kg,
                x,
                y,
                z,
                "yes" if r.has_inertia else "no",
            )
        )
    return Table(
        "Items",
        (
            Column("Item"),
            Column("Name"),
            Column("Kind"),
            Column("Subsystem"),
            Column("Maturity"),
            _kg("Mass"),
            Column("Margin", "percent", 3),
            _kg("With margin"),
            _m("x"),
            _m("y"),
            _m("z"),
            Column("Own inertia"),
        ),
        tuple(rows),
    )


def _subsystems(p: PhaseMass) -> Table:
    return Table(
        "By subsystem",
        (Column("Subsystem"), _kg("Mass"), _kg("With margin")),
        tuple((s.subsystem, s.mass_kg, s.margined_kg) for s in p.subsystems),
    )


def _totals(p: PhaseMass) -> Table:
    rows: list[tuple[Cell, ...]] = [
        ("Total, nominal", p.total_kg),
        ("Total, with unit margins", p.unit_margined_kg),
        ("Total, with system margin", p.system_margined_kg),
    ]
    if p.cog is not None:
        for axis, value in zip("xyz", p.cog.position_m, strict=True):
            rows.append((f"Centre of gravity {axis} (m)", value))
        rows.append(("Mass in the CG calculation (kg)", p.cog.mass_kg))
    else:
        rows.append(("Centre of gravity", None))
    return Table(
        "Totals and centre of gravity",
        (Column("Quantity"), Column("Value", "number", 4)),
        tuple(rows),
    )


def _inertia(p: PhaseMass) -> Table:
    names = ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")
    if p.cog is None:
        return Table(
            "Inertia tensor",
            (Column("Entry"), Column("About CG"), Column("About origin")),
            tuple((n, None, None) for n in names),
        )
    cg, origin = p.cog.inertia_cg.entries(), p.cog.inertia_origin.entries()
    return Table(
        "Inertia tensor",
        (
            Column("Entry"),
            Column("About CG (kg m2)", "number", 5),
            Column("About origin (kg m2)", "number", 5),
        ),
        tuple((n, a, b) for n, a, b in zip(names, cg, origin, strict=True)),
        note="Tensor entries in the body frame; Ixy, Ixz, Iyz are tensor elements (minus the "
        "products of inertia), see docs/DECISIONS.md D-048.",
    )


def build_mass_report(
    project: Project,
    result: StaticMassResult,
    provenance: Provenance,
    load_problems: list[Problem] | tuple[Problem, ...] = (),
) -> ReportDocument:
    used: set[str] = set()
    sections = [
        Section(
            "Summary",
            sheet_name("Summary", used),
            tables=(_summary(result), _limits(result)),
            paragraphs=(f"Body frame: {project.spacecraft.body_frame or 'not described'}",),
        )
    ]
    for p in result.phases:
        sections.append(
            Section(
                f"Phase: {p.phase}",
                sheet_name(f"Phase {p.phase}", used),
                tables=(_items(p), _subsystems(p), _totals(p), _inertia(p)),
            )
        )
    sections += closing_sections(
        used, result.assumptions, "MASS-", [*load_problems, *result.problems], provenance
    )
    incomplete = any(a.placeholder for a in result.assumptions)
    return ReportDocument(
        title=f"Mass budget (static): {project.meta.name}",
        provenance=provenance,
        sections=tuple(sections),
        banner=BANNER if incomplete else "",
    )
