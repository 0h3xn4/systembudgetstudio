"""Plot specification of a link's pass time series."""

from __future__ import annotations

from typing import Any

import numpy as np

from budget_core.link.evaluate import LinkSeries
from budget_core.plots.spec import BLUE, GREEN, GREY, PURPLE, RED, HLine, Panel, PlotSpec, Series

NDArray = np.ndarray[Any, np.dtype[np.float64]]
RATE_COLORS = (BLUE, GREEN, PURPLE, "#007d79", "#9f1853", "#b28600")


def _per_pass(
    series: LinkSeries,
    label: str,
    values: np.ndarray,
    color: str,
    step: bool,
) -> list[Series]:
    """One Series per pass, so lines are not drawn across the gaps between passes; they share
    the label."""
    out: list[Series] = []
    step_s = float(np.min(np.diff(series.times_s))) if len(series.times_s) > 1 else 1.0
    for k in sorted(set(int(i) for i in series.pass_index)):
        mask = series.pass_index == k
        x = series.times_s[mask]
        out.append(
            Series(
                label,
                x,
                values[mask],
                color,
                step,
                float(x[-1]) + step_s if step else None,
            )
        )
    return out


def link_plot(
    series: LinkSeries, duration_s: float, rates: tuple[float, ...] | None = None
) -> PlotSpec:
    """Margin at the listed rates with the required margin, the selected rate, and the elevation."""
    panels: list[Panel] = []
    if series.margin_db is not None and len(series.times_s):
        shown = list(range(len(series.rates_bps)))
        margin_series: list[Series] = []
        for i in shown:
            label = f"Margin at {series.rates_bps[i] / 1000:g} kbit/s"
            margin_series += _per_pass(
                series, label, series.margin_db[:, i], RATE_COLORS[i % len(RATE_COLORS)], False
            )
        hlines = (
            (HLine("Required margin", series.required_margin_db, RED),)
            if series.required_margin_db is not None
            else ()
        )
        panels.append(Panel("Link margin", "Margin (dB)", tuple(margin_series), hlines))
    if series.selected_rate_bps is not None and len(series.times_s):
        panels.append(
            Panel(
                "Selected rate",
                "Selected data rate (kbit/s)",
                tuple(
                    _per_pass(
                        series, "Selected rate", series.selected_rate_bps / 1000.0, GREEN, True
                    )
                ),
                y_min=0.0,
            )
        )
    if len(series.times_s):
        panels.append(
            Panel(
                "Elevation",
                "Elevation (deg)",
                tuple(_per_pass(series, "Elevation", series.elevation_deg, GREY, False)),
                y_min=0.0,
                y_max=90.0,
            )
        )
    return PlotSpec(
        f"Link {series.link_name} ({series.direction}) to {series.site}",
        tuple(panels),
        (),
        0.0,
        duration_s,
    )
