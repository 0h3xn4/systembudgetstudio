"""Build the static power budget report document from a result (renderer independent)."""

from __future__ import annotations

import re

from budget_core.equations import EQUATIONS
from budget_core.model import Project
from budget_core.power.static_budget import Flow, ModePowerResult, StaticPowerResult
from budget_core.problems import Problem, sort_problems
from budget_core.provenance import Provenance
from budget_core.reports.document import Cell, Column, ReportDocument, Section, Table

W = Column("", "number", 3, "W")


def _w(header: str) -> Column:
    return Column(f"{header} (W)", "number", 3, "W")


BANNER = (
    "INCOMPLETE: some inputs are placeholders (source TBD or missing). Entries marked n/a depend "
    "on them and are not computed. Do not use this report as evidence until the placeholders are "
    "replaced with sourced values."
)


def _sheet_name(raw: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "_", raw)[:31]
    name, i = base, 2
    while name in used:
        suffix = f" {i}"
        name = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(name)
    return name


def _summary(result: StaticPowerResult) -> Table:
    rows: list[tuple[Cell, ...]] = []
    for m in result.modes:
        a, p = m.average, m.peak
        rows.append(
            (
                m.mode_name,
                a.load_w,
                a.unit_margined_w,
                a.system_margined_w,
                a.source_w,
                a.source_margined_w,
                p.load_w,
                p.source_margined_w,
            )
        )
    return Table(
        "Power by spacecraft mode",
        (
            Column("Mode"),
            _w("Average load"),
            _w("Average, unit margins"),
            _w("Average, system margin"),
            _w("Average at source"),
            _w("Average at source, with margins"),
            _w("Peak load"),
            _w("Peak at source, with margins"),
        ),
        tuple(rows),
        note="Average = sum of unit power x duty cycle. Peak = sum of unit peak powers. "
        "Source = after converter and distribution losses.",
    )


def _unit_table(m: ModePowerResult) -> Table:
    return Table(
        f"Units in mode {m.mode_name}",
        (
            Column("Unit"),
            Column("Name"),
            Column("Subsystem"),
            Column("Bus"),
            Column("Power mode"),
            _w("Average"),
            Column("Duty", "number", 2),
            _w("Effective"),
            Column("Margin", "percent", 3),
            _w("With margin"),
            _w("Peak"),
        ),
        tuple(
            (
                r.unit_id,
                r.unit_name,
                r.subsystem,
                r.bus,
                r.power_mode,
                r.avg_power_w,
                r.duty_cycle_ratio,
                r.effective_power_w,
                r.margin_ratio,
                r.margined_power_w,
                r.peak_power_w,
            )
            for r in m.rows
        ),
    )


def _subsystem_table(m: ModePowerResult) -> Table:
    return Table(
        "By subsystem",
        (
            Column("Subsystem"),
            _w("Effective"),
            _w("With margin"),
            _w("Peak"),
            _w("Peak with margin"),
        ),
        tuple(
            (s.subsystem, s.effective_w, s.margined_w, s.peak_w, s.margined_peak_w)
            for s in m.subsystems
        ),
    )


def _bus_table(m: ModePowerResult) -> Table:
    def row(label: str, eta: float | None, a: Flow, p: Flow) -> tuple[Cell, ...]:
        return (
            label,
            eta,
            a.load_w,
            a.system_margined_w,
            a.source_w,
            a.source_margined_w,
            p.load_w,
            p.source_margined_w,
        )

    return Table(
        "By supply bus",
        (
            Column("Bus"),
            Column("Converter efficiency", "number", 3),
            _w("Average load"),
            _w("Average load, with margins"),
            _w("Average at source"),
            _w("Average at source, with margins"),
            _w("Peak load"),
            _w("Peak at source, with margins"),
        ),
        tuple(row(b.bus, b.converter_efficiency_ratio, b.average, b.peak) for b in m.buses),
    )


def _totals_table(m: ModePowerResult) -> Table:
    a, p = m.average, m.peak
    return Table(
        "Totals",
        (Column("Quantity"), _w("Average"), _w("Peak")),
        (
            ("Load, nominal", a.load_w, p.load_w),
            ("Load, with unit margins", a.unit_margined_w, p.unit_margined_w),
            ("Load, with system margin", a.system_margined_w, p.system_margined_w),
            ("Source, nominal", a.source_w, p.source_w),
            ("Source, with margins", a.source_margined_w, p.source_margined_w),
        ),
        emphasise_last_row=True,
    )


def build_power_report(
    project: Project,
    result: StaticPowerResult,
    provenance: Provenance,
    load_problems: list[Problem] | tuple[Problem, ...] = (),
) -> ReportDocument:
    used: set[str] = set()
    sections: list[Section] = [
        Section("Summary", _sheet_name("Summary", used), tables=(_summary(result),))
    ]
    for m in result.modes:
        sections.append(
            Section(
                f"Mode: {m.mode_name}",
                _sheet_name(f"Mode {m.mode_id}", used),
                tables=(_unit_table(m), _subsystem_table(m), _bus_table(m), _totals_table(m)),
            )
        )

    assumption_table = Table(
        "Configuration numbers used",
        (
            Column("Name"),
            Column("Value", "number", 4),
            Column("Unit"),
            Column("Source"),
            Column("Status"),
        ),
        tuple(
            (a.name, a.value, a.unit, a.source, "PLACEHOLDER" if a.placeholder else "sourced")
            for a in result.assumptions
        ),
    )
    equation_table = Table(
        "Equations",
        (Column("ID"), Column("Name"), Column("Formula"), Column("Source")),
        tuple((e.id, e.name, e.formula, e.source_text) for e in EQUATIONS.values()),
        note="SOURCE_MISSING: the formula is a project convention whose reference text is not "
        "available to the tool yet (decision D-040).",
    )
    sections.append(
        Section(
            "Assumptions",
            _sheet_name("Assumptions", used),
            tables=(assumption_table, equation_table),
        )
    )

    problems = sort_problems([*load_problems, *result.problems])
    problem_table = Table(
        "Problems and open items",
        (Column("Severity"), Column("Code"), Column("Location"), Column("Message")),
        tuple(
            (
                p.severity.value,
                p.code,
                (p.file or "") + (f":{p.line}" if p.line is not None else ""),
                p.message,
            )
            for p in problems
        ),
    )
    sections.append(Section("Problems", _sheet_name("Problems", used), tables=(problem_table,)))

    prov_table = Table(
        "Provenance",
        (Column("Item"), Column("Value")),
        tuple((k, v) for k, v in provenance.rows()),
    )
    sections.append(Section("Provenance", _sheet_name("Provenance", used), tables=(prov_table,)))

    incomplete = any(a.placeholder for a in result.assumptions)
    return ReportDocument(
        title=f"Power budget (static): {project.meta.name}",
        provenance=provenance,
        sections=tuple(sections),
        banner=BANNER if incomplete else "",
    )
