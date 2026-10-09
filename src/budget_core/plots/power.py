"""Plot specifications of the time-domain power budget."""

from __future__ import annotations

from budget_core.plots.spec import (
    BAND_COLORS,
    BAND_ECLIPSE,
    BLUE,
    GREEN,
    GREY,
    PURPLE,
    RED,
    Band,
    HLine,
    Panel,
    PlotSpec,
    Series,
)
from budget_core.power.time_domain import TimeDomainResult


def power_bands(result: TimeDomainResult) -> tuple[Band, ...]:
    """Eclipses and, per site, the passes: the shading shared by all panels."""
    env = result.run.env
    bands = [Band("Eclipse", tuple((e.start_s, e.end_s) for e in env.eclipses), BAND_ECLIPSE)]
    for i, (site_id, vis) in enumerate(sorted(env.sites.items())):
        intervals = tuple((p.aos_s, p.los_s) for p in vis.passes)
        bands.append(Band(f"Passes {site_id}", intervals, BAND_COLORS[i % len(BAND_COLORS)]))
    return tuple(b for b in bands if b.intervals)


def power_plot(result: TimeDomainResult, case: str, *, shading: bool = True) -> PlotSpec:
    """Generation and demand, state of charge and margin of one case."""
    c = result.case(case)
    edges = result.edges_s
    steps = edges[:-1]
    end = float(edges[-1])
    limit = result.peak_limit_w

    power_series: list[Series] = []
    if c.generation_w is not None:
        power_series.append(Series("Generation", steps, c.generation_w, GREEN, True, end))
    if result.demand_w is not None:
        power_series.append(Series("Demand at source", steps, result.demand_w, BLUE, True, end))
    elif result.load_w is not None:
        power_series.append(Series("Load (source side n/a)", steps, result.load_w, GREY, True, end))
    panels = [
        Panel(
            "Power",
            "Power (W)",
            tuple(power_series),
            (HLine("Peak limit", limit, RED),) if limit is not None else (),
            y_min=0.0,
        )
    ]
    if c.soc_ratio is not None:
        dod_limit = next((v.limit for v in c.violations if v.code == "BATTERY_DOD_EXCEEDED"), None)
        panels.append(
            Panel(
                "Battery",
                "State of charge (%)",
                (Series("State of charge", edges, c.soc_ratio, PURPLE),),
                (HLine("Minimum allowed", 1.0 - dod_limit, RED),) if dod_limit is not None else (),
                y_min=0.0,
                y_max=1.0,
                y_scale=100.0,
            )
        )
    if c.margin_w is not None:
        panels.append(
            Panel(
                "Margin",
                "Generation - demand (W)",
                (Series("Margin", steps, c.margin_w, BLUE, True, end),),
                (HLine("Zero", 0.0, GREY),),
            )
        )
    return PlotSpec(
        f"Power over time, {case.upper()}",
        tuple(panels),
        power_bands(result) if shading else (),
        float(edges[0]),
        end,
    )
