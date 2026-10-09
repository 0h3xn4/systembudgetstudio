"""Report document of the time-domain power budget (renderer independent)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from budget_core.model import Project
from budget_core.plots.power import power_plot
from budget_core.plots.render import render_png
from budget_core.power.static_budget import static_power_budget
from budget_core.power.time_domain import (
    CODES_TEXT,
    CaseResult,
    TimeDomainResult,
    Violation,
    format_offset,
    violation_problems,
)
from budget_core.problems import Problem
from budget_core.provenance import Provenance
from budget_core.reports.common import BANNER, closing_sections, sheet_name
from budget_core.reports.document import (
    Cell,
    Column,
    Figure,
    ReportDocument,
    Section,
    Table,
)
from budget_core.reports.power_report import power_summary_table
from budget_core.timeutil import format_utc


def _facts(result: TimeDomainResult) -> tuple[str, ...]:
    env, sc = result.run.env, result.run.scenario
    phase = result.mission_phase or "not set"
    return (
        f"Scenario {result.run.scenario_id}: {sc.name}.",
        f"Environment source: {env.source}; shadow model: {env.shadow_model}; start "
        f"{format_utc(env.grid.start)}; duration {sc.duration_s:.0f} s; step {sc.step_s:g} s "
        f"({result.steps} steps).",
        f"Eclipse fraction {env.eclipse_fraction * 100:.2f} % of the scenario; "
        f"{len(result.windows)} complete orbit(s).",
        f"Demand basis: {result.load_basis}; mission phase for the depth-of-discharge limit: "
        f"{phase}.",
        "Beginning of life (BOL): no array degradation or battery fade. End of life (EOL): the "
        "design life applied to both.",
    )


Getter = Callable[[CaseResult], float | None]


def _percent(value: float | None) -> float | None:
    return None if value is None else value * 100.0


def _case_table(result: TimeDomainResult) -> Table:
    metrics: list[tuple[str, str, Getter]] = [
        ("Battery capacity", "Wh", lambda c: c.capacity_wh),
        ("Average generation", "W", lambda c: c.summary.average_generation_w),
        ("Average demand at source", "W", lambda c: c.summary.average_demand_w),
        ("Energy generated", "Wh", lambda c: c.summary.generated_wh),
        ("Energy demanded", "Wh", lambda c: c.summary.demanded_wh),
        ("Smallest margin (generation - demand)", "W", lambda c: c.summary.minimum_margin_w),
        ("Lowest state of charge", "%", lambda c: _percent(c.summary.minimum_soc_ratio)),
        ("Deepest depth of discharge", "%", lambda c: _percent(c.summary.maximum_dod_ratio)),
        ("Energy not supplied", "Wh", lambda c: c.summary.unmet_wh),
        ("Energy curtailed (battery full)", "Wh", lambda c: c.summary.curtailed_wh),
        ("Stored energy change over the scenario", "Wh", lambda c: c.summary.energy_change_wh),
    ]
    rows: list[tuple[Cell, ...]] = [
        (label, unit, *(get(c) for c in result.cases)) for label, unit, get in metrics
    ]
    rows.append(("Violations", "count", *(str(len(c.violations)) for c in result.cases)))
    missing = any(v is None for r in rows for v in r)
    return Table(
        "Results by case",
        (
            Column("Quantity"),
            Column("Unit"),
            *(Column(c.case.upper(), "number", 3) for c in result.cases),
        ),
        tuple(rows),
        note="n/a: an input the result needs is a placeholder or missing (see Problems)."
        if missing
        else "",
    )


def _mode_table(result: TimeDomainResult) -> Table:
    total = result.run.scenario.duration_s
    return Table(
        "Spacecraft modes in the scenario",
        (
            Column("Mode"),
            Column("Name"),
            Column("Time (s)", "number", 1),
            Column("Share", "percent", 3),
            Column("Load (W)", "number", 3),
            Column("Demand at source (W)", "number", 3),
            Column("Peak at source (W)", "number", 3),
        ),
        tuple(
            (
                m.mode_id,
                m.mode_name,
                m.duration_s,
                m.duration_s / total,
                m.load_w,
                m.demand_w,
                m.peak_demand_w,
            )
            for m in result.modes
        ),
        note=f"Demand basis: {result.load_basis}.",
    )


def _balance_table(result: TimeDomainResult, case: CaseResult) -> Table:
    return Table(
        f"Orbit energy balance, {case.case.upper()}",
        (
            Column("Orbit"),
            Column("Start (T+)"),
            Column("Length (s)", "number", 1),
            Column("Eclipse (s)", "number", 1),
            Column("Generated (Wh)", "number", 3),
            Column("Demanded (Wh)", "number", 3),
            Column("Balance (Wh)", "number", 3),
            Column("Stored change (Wh)", "number", 3),
        ),
        tuple(
            (
                str(b.index),
                format_offset(b.start_s),
                b.end_s - b.start_s,
                b.eclipse_s,
                b.generation_wh,
                b.demand_wh,
                b.balance_wh,
                b.battery_change_wh,
            )
            for b in case.balances
        ),
        note="Complete orbits only; the balance is generation minus demand at the source.",
    )


def _violation_row(result: TimeDomainResult, v: Violation) -> tuple[Cell, ...]:
    where = v.path if v.file == "config/power_system.yaml" else f"{v.file}: {v.path}"
    shown = None if v.extreme is None else v.extreme
    return (
        v.case.upper() if v.case else "both",
        CODES_TEXT.get(v.code, v.code),
        format_offset(v.start_s),
        format_offset(v.end_s),
        v.end_s - v.start_s,
        shown,
        v.limit,
        v.unit,
        where,
    )


def violations_table(result: TimeDomainResult) -> Table:
    return Table(
        "Violations",
        (
            Column("Case"),
            Column("Finding"),
            Column("From (T+)"),
            Column("To (T+)"),
            Column("Duration (s)", "number", 1),
            Column("Worst value", "number", 4),
            Column("Limit", "number", 4),
            Column("Unit"),
            Column("Input to change"),
        ),
        tuple(_violation_row(result, v) for v in result.violations),
        note="No violations found." if not result.violations else "",
    )


def build_timeline_report(
    project: Project,
    result: TimeDomainResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
    *,
    plots: bool = True,
) -> ReportDocument:
    used: set[str] = set()
    sections: list[Section] = [
        Section(
            "Summary",
            sheet_name("Summary", used),
            paragraphs=_facts(result),
            tables=(_case_table(result), violations_table(result)),
        )
    ]
    if plots:
        for case in result.cases:
            if case.generation_w is None and result.demand_w is None and result.load_w is None:
                continue
            figure = Figure(
                f"Power over time, {case.case.upper()}",
                render_png(power_plot(result, case.case)),
                "Generation, demand, state of charge and margin with eclipses and passes shaded.",
            )
            sections.append(
                Section(
                    f"Plots, {case.case.upper()}",
                    sheet_name(f"Plots {case.case.upper()}", used),
                    figures=(figure,),
                )
            )
    sections.append(
        Section(
            "Modes and orbits",
            sheet_name("Modes and orbits", used),
            tables=(_mode_table(result), *(_balance_table(result, c) for c in result.cases)),
        )
    )
    sections.append(
        Section(
            "Static power",
            sheet_name("Static power", used),
            paragraphs=("The static budget of every mode, the input of the time-domain run.",),
            tables=(power_summary_table(static_power_budget(project)),),
        )
    )
    problems = [*load_problems, *result.problems, *violation_problems(result)]
    sections += closing_sections(used, result.assumptions, "TDP-", problems, provenance)
    incomplete = any(a.placeholder for a in result.assumptions)
    return ReportDocument(
        title=f"Power budget over time: {project.meta.name}",
        provenance=provenance,
        sections=tuple(sections),
        banner=BANNER if incomplete else "",
    )
