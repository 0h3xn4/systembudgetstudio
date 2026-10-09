"""Link budget report document: the static table and, with a scenario, the pass series."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from budget_core.link.evaluate import LinkSeriesResult, StaticLinkResult
from budget_core.model import Project
from budget_core.plots.link import link_plot
from budget_core.plots.render import render_png
from budget_core.power.time_domain import format_offset
from budget_core.problems import Problem
from budget_core.provenance import Provenance
from budget_core.reports.common import BANNER, closing_sections, sheet_name
from budget_core.reports.document import Cell, Column, Figure, ReportDocument, Section, Table
from budget_core.timeutil import format_utc


def _db(header: str, decimals: int = 2) -> Column:
    return Column(f"{header} (dB)", "number", decimals, "dB")


def _static_table(result: StaticLinkResult) -> Table:
    return Table(
        "Link budget at the static points",
        (
            Column("Link"),
            Column("Direction"),
            Column("Point"),
            Column("Elevation (deg)", "number", 1),
            Column("Range (km)", "number", 1),
            Column("EIRP (dBW)", "number", 2),
            Column("G/T (dB/K)", "number", 2),
            _db("Path loss"),
            _db("Atmospheric"),
            _db("Other losses"),
            Column("C/N0 (dBHz)", "number", 2),
            Column("Required Eb/N0 (dB)", "number", 2),
            Column("Highest closing rate (kbit/s)", "number", 3),
            Column("Rate at required margin (kbit/s)", "number", 3),
        ),
        tuple(
            (
                r.link_id,
                r.direction,
                r.point,
                r.elevation_deg,
                r.range_m / 1000.0,
                r.eirp_dbw,
                r.g_over_t_dbk,
                r.path_loss_db,
                r.atmospheric_loss_db,
                r.other_losses_db,
                r.cn0_dbhz,
                r.required_ebn0_db,
                None if r.max_rate_bps is None and r.rates else _kbps(r.max_rate_bps),
                _kbps(r.max_rate_continuous_bps),
            )
            for r in result.rows
        ),
        note="Other losses = pointing, polarisation and implementation. A link closes at a rate "
        "when its margin is at least the required margin of the link. n/a: an input is a "
        "placeholder or missing. Highest closing rate empty (n/a with a result): no listed rate "
        "closes.",
    )


def _kbps(value: float | None) -> float | None:
    return None if value is None else value / 1000.0


def _rate_table(result: StaticLinkResult) -> Table:
    rows: list[tuple[Cell, ...]] = []
    for r in result.rows:
        for rate in r.rates:
            rows.append(
                (
                    r.link_id,
                    r.point,
                    rate.data_rate_bps / 1000.0,
                    rate.ebn0_db,
                    rate.margin_db,
                    r.required_margin_db,
                    "yes" if rate.closes else "no",
                )
            )
    return Table(
        "Margin by data rate",
        (
            Column("Link"),
            Column("Point"),
            Column("Data rate (kbit/s)", "number", 3),
            _db("Eb/N0"),
            _db("Margin"),
            _db("Required margin"),
            Column("Closes"),
        ),
        tuple(rows),
    )


def _pass_tables(result: LinkSeriesResult) -> list[Table]:
    run = result.run

    def utc(seconds: float) -> str:
        return format_utc(run.env.grid.start + timedelta(seconds=seconds))

    summary: list[tuple[Cell, ...]] = []
    for s in result.series:
        summary.append(
            (
                s.link_id,
                s.site,
                float(len(s.passes)),
                None if s.volume_bits is None else s.volume_bits / 1e6,
                None if s.volume_per_day_bits is None else s.volume_per_day_bits / 1e6,
                None if s.volume_per_day_bits is None else s.volume_per_day_bits / 8e6,
            )
        )
    tables = [
        Table(
            "Data volume per link",
            (
                Column("Link"),
                Column("Station"),
                Column("Passes", "number", 0),
                Column("Scenario total (Mbit)", "number", 2),
                Column("Per day (Mbit)", "number", 2),
                Column("Per day (MByte)", "number", 2),
            ),
            tuple(summary),
            note="From the highest listed rate that closes at each sample while the link is "
            "active (its modes, below its tracking limit). Per day = scenario total scaled to "
            "86 400 s.",
        )
    ]
    for s in result.series:
        tables.append(
            Table(
                f"Passes of link {s.link_id} over {s.site}",
                (
                    Column("Pass"),
                    Column("AOS (T+)"),
                    Column("AOS (UTC)"),
                    Column("Duration (s)", "number", 1),
                    Column("Max elevation (deg)", "number", 1),
                    Column("Usable (s)", "number", 1),
                    _db("Lowest margin"),
                    Column("Volume (Mbit)", "number", 2),
                ),
                tuple(
                    (
                        str(p.index),
                        format_offset(p.aos_s),
                        utc(p.aos_s),
                        p.los_s - p.aos_s,
                        p.max_elevation_deg,
                        p.usable_s,
                        p.minimum_margin_db,
                        None if p.volume_bits is None else p.volume_bits / 1e6,
                    )
                    for p in s.passes
                ),
                note="Lowest margin is at the lowest listed rate over the active samples.",
            )
        )
    return tables


def build_link_report(
    project: Project,
    static: StaticLinkResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
    passes: LinkSeriesResult | None = None,
    *,
    plots: bool = True,
) -> ReportDocument:
    used: set[str] = set()
    sections: list[Section] = [
        Section(
            "Summary",
            sheet_name("Summary", used),
            tables=(_static_table(static), _rate_table(static)),
        )
    ]
    assumptions = list(static.assumptions)
    problems = [*load_problems, *static.problems]
    if passes is not None:
        run = passes.run
        sections.append(
            Section(
                "Passes",
                sheet_name("Passes", used),
                paragraphs=(
                    f"Scenario {run.scenario_id}: {run.scenario.name}. "
                    f"Step {run.env.grid.step_s:g} s, duration {run.env.grid.duration_s:.0f} s.",
                ),
                tables=tuple(_pass_tables(passes)),
            )
        )
        if plots:
            for s in passes.series:
                if s.margin_db is None or not len(s.times_s):
                    continue
                png = render_png(link_plot(s, run.env.grid.duration_s))
                sections.append(
                    Section(
                        f"Plot, {s.link_id}",
                        sheet_name(f"Plot {s.link_id}", used),
                        figures=(
                            Figure(
                                f"Link {s.link_id} over {s.site}",
                                png,
                                "Margin at each listed rate with the required margin, the selected "
                                "data rate and the elevation, inside the passes.",
                            ),
                        ),
                    )
                )
        known = {(a.file, a.path) for a in assumptions}
        assumptions += [a for a in passes.assumptions if (a.file, a.path) not in known]
        problems += list(passes.problems)
    sections += closing_sections(used, assumptions, "LNK-", problems, provenance)
    incomplete = any(a.placeholder for a in assumptions) or any(
        r.cn0_dbhz is None for r in static.rows
    )
    title = (
        f"Link budget: {project.meta.name}"
        if passes is None
        else f"Link budget over passes: {project.meta.name}"
    )
    return ReportDocument(
        title=title,
        provenance=provenance,
        sections=tuple(sections),
        banner=BANNER if incomplete else "",
    )
