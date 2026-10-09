"""Static thermal budget report document (renderer independent)."""

from __future__ import annotations

from budget_core.model import Project
from budget_core.problems import Problem
from budget_core.provenance import Provenance
from budget_core.reports.common import BANNER, closing_sections, sheet_name
from budget_core.reports.document import Cell, Column, ReportDocument, Section, Table
from budget_core.thermal.static_thermal import CaseThermal, ModeHeat, StaticThermalResult

ABSOLUTE_ZERO_OFFSET_K = 273.15  # Celsius display only; the model works in kelvin


def _w(header: str) -> Column:
    return Column(f"{header} (W)", "number", 3, "W")


def _celsius(kelvin: float | None) -> float | None:
    return None if kelvin is None else kelvin - ABSOLUTE_ZERO_OFFSET_K


def _mode_summary(result: StaticThermalResult) -> Table:
    return Table(
        "Heat dissipation by spacecraft mode",
        (Column("Mode"), _w("Average"), _w("Peak")),
        tuple((m.mode_name, m.total_w, m.peak_total_w) for m in result.modes),
        note="Average = sum of unit power x duty cycle x heat dissipation ratio. Peak uses the "
        "unit peak powers. n/a: a unit has no heat dissipation ratio for its power mode.",
    )


def _unit_table(m: ModeHeat) -> Table:
    return Table(
        f"Units in mode {m.mode_name}",
        (
            Column("Unit"),
            Column("Name"),
            Column("Subsystem"),
            Column("Node"),
            Column("Power mode"),
            _w("Effective power"),
            Column("Dissipation ratio", "number", 2),
            _w("Dissipation"),
            _w("Peak dissipation"),
        ),
        tuple(
            (
                r.unit_id,
                r.unit_name,
                r.subsystem,
                r.node,
                r.power_mode,
                r.effective_power_w,
                r.heat_dissipation_ratio,
                r.dissipation_w,
                r.peak_dissipation_w,
            )
            for r in m.rows
        ),
    )


def _group_table(title: str, header: str, m: ModeHeat, nodes: bool) -> Table:
    groups = m.nodes if nodes else m.subsystems
    return Table(
        title,
        (Column(header), _w("Dissipation"), _w("Peak dissipation")),
        tuple((g.name, g.dissipation_w, g.peak_dissipation_w) for g in groups),
    )


def _node_table(c: CaseThermal) -> Table:
    if not c.complete:
        return Table(
            f"Node temperatures, case {c.case}",
            (Column("Node"), Column("Temperature (K)", "number", 2)),
            (("not computed (inputs missing, see Problems)", None),),
        )
    return Table(
        f"Node temperatures, case {c.case}",
        (
            Column("Node"),
            Column("Temperature (K)", "number", 2),
            Column("Temperature (C)", "number", 2),
            _w("Dissipated"),
            _w("Absorbed from environment"),
            _w("Radiated to space"),
            _w("Conducted to other nodes"),
        ),
        tuple(
            (
                n.node,
                n.temperature_k,
                _celsius(n.temperature_k),
                n.dissipation_w,
                n.absorbed_w,
                n.radiated_w,
                n.conducted_out_w,
            )
            for n in c.nodes
        ),
        note=f"Mode {c.mode_id}; limit set: {c.limit_set}. Largest node imbalance after solving: "
        + _imbalance(c.balance_residual_w),
    )


def _imbalance(watts: float | None) -> str:
    if watts is None:
        return "n/a."
    return "below 0.000001 W." if watts < 1e-6 else f"{watts:.6f} W."


def _check_table(c: CaseThermal) -> Table:
    rows: list[tuple[Cell, ...]] = [
        (
            k.unit_id,
            k.node,
            k.temperature_k,
            k.lower_limit_k,
            k.upper_limit_k,
            k.lower_headroom_k,
            k.upper_headroom_k,
            k.status,
        )
        for k in c.checks
    ]
    return Table(
        f"Unit temperature limits, case {c.case} ({c.limit_set})",
        (
            Column("Unit"),
            Column("Node"),
            Column("Temperature (K)", "number", 2),
            Column("Lower limit (K)", "number", 2),
            Column("Upper limit (K)", "number", 2),
            Column("Headroom to lower (K)", "number", 2),
            Column("Headroom to upper (K)", "number", 2),
            Column("Status"),
        ),
        tuple(rows),
        note="Status: ok; margin = within the limits but closer than the required temperature "
        "margin; exceeded; no limits = the unit has no limits for this set (not checked).",
    )


def build_thermal_report(
    project: Project,
    result: StaticThermalResult,
    provenance: Provenance,
    load_problems: list[Problem] | tuple[Problem, ...] = (),
) -> ReportDocument:
    used: set[str] = set()
    summary_tables = [_mode_summary(result)]
    sections: list[Section] = [
        Section("Summary", sheet_name("Summary", used), tables=tuple(summary_tables))
    ]
    for c in result.cases:
        sections.append(
            Section(
                f"Case: {c.case}",
                sheet_name(f"Case {c.case}", used),
                paragraphs=(c.description,) if c.description else (),
                tables=(_node_table(c), _check_table(c)),
            )
        )
    for m in result.modes:
        sections.append(
            Section(
                f"Mode: {m.mode_name}",
                sheet_name(f"Mode {m.mode_id}", used),
                tables=(
                    _unit_table(m),
                    _group_table("By subsystem", "Subsystem", m, False),
                    _group_table("By thermal node", "Node", m, True),
                ),
            )
        )
    sections += closing_sections(
        used, result.assumptions, "TH-", [*load_problems, *result.problems], provenance
    )
    incomplete = (
        any(a.placeholder for a in result.assumptions)
        or any(not c.complete for c in result.cases)
        or any(m.total_w is None for m in result.modes)
        or any(p.code == "RESULT_INCOMPLETE" for p in result.problems)
    )
    return ReportDocument(
        title=f"Thermal budget (static): {project.meta.name}",
        provenance=provenance,
        sections=tuple(sections),
        banner=BANNER if incomplete else "",
    )
