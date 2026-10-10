"""CSV and JSON exports of the link budget (deterministic text, LF line endings).

Unavailable values (placeholders) are empty cells in CSV and null in JSON."""

from __future__ import annotations

import io
import json
from dataclasses import asdict
from datetime import timedelta
from typing import Any

import numpy as np

from budget_core.link.evaluate import LinkSeries, LinkSeriesResult, StaticLinkResult
from budget_core.provenance import Provenance
from budget_core.reports.csvutil import csv_writer
from budget_core.timeutil import format_utc


def _csv(header: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv_writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def _rate_label(rate_bps: float) -> str:
    return str(int(rate_bps)) if float(rate_bps).is_integer() else f"{rate_bps:g}"


def _opt(value: float | None, decimals: int = 6) -> str:
    return "" if value is None else f"{value:.{decimals}f}"


def static_csv(result: StaticLinkResult) -> str:
    """One row per link, point and data rate (a row without rates when the result is n/a)."""
    header = [
        "link",
        "direction",
        "point",
        "elevation_deg",
        "range_m",
        "frequency_hz",
        "eirp_dbw",
        "g_over_t_dbk",
        "path_loss_db",
        "atmospheric_loss_db",
        "other_losses_db",
        "cn0_dbhz",
        "required_ebn0_db",
        "required_margin_db",
        "data_rate_bps",
        "ebn0_db",
        "margin_db",
        "closes",
    ]
    rows: list[list[str]] = []
    for r in result.rows:
        common = [
            r.link_id,
            r.direction,
            r.point,
            _opt(r.elevation_deg, 3),
            _opt(r.range_m, 3),
            _opt(r.frequency_hz, 1),
            _opt(r.eirp_dbw),
            _opt(r.g_over_t_dbk),
            _opt(r.path_loss_db),
            _opt(r.atmospheric_loss_db),
            _opt(r.other_losses_db),
            _opt(r.cn0_dbhz),
            _opt(r.required_ebn0_db),
            _opt(r.required_margin_db),
        ]
        if not r.rates:
            rows.append([*common, "", "", "", ""])
        for rate in r.rates:
            rows.append(
                [
                    *common,
                    _opt(rate.data_rate_bps, 1),
                    _opt(rate.ebn0_db),
                    _opt(rate.margin_db),
                    str(rate.closes).lower(),
                ]
            )
    return _csv(header, rows)


def series_csv(result: LinkSeriesResult, series: LinkSeries) -> str:
    """The samples inside the passes: geometry, budget terms, margin per rate, selected rate."""
    start = np.datetime64(result.run.env.grid.start.replace(tzinfo=None), "ms")
    utc = (start + np.round(series.times_s * 1000.0).astype("timedelta64[ms]")).astype(str)
    header = [
        "time_s",
        "time_utc",
        "pass",
        "elevation_deg",
        "range_m",
        "active",
        "path_loss_db",
        "atmospheric_loss_db",
        "eirp_dbw",
        "g_over_t_dbk",
        "cn0_dbhz",
        *[f"margin_db_{_rate_label(rate)}bps" for rate in series.rates_bps],
        "selected_rate_bps",
    ]
    n = len(series.times_s)

    def col(values: Any) -> list[str]:
        return [""] * n if values is None else [f"{v:.6f}" for v in values.tolist()]

    margins = [
        col(None if series.margin_db is None else series.margin_db[:, i])
        for i in range(len(series.rates_bps))
    ]
    columns = [
        [f"{t:.3f}" for t in series.times_s.tolist()],
        [f"{u}Z" for u in utc.tolist()],
        [str(int(k) + 1) for k in series.pass_index.tolist()],
        col(series.elevation_deg),
        col(series.range_m),
        [str(bool(a)).lower() for a in series.active.tolist()],
        col(series.path_loss_db),
        col(series.atmospheric_loss_db),
        col(series.eirp_dbw),
        col(series.g_over_t_dbk),
        col(series.cn0_dbhz),
        *margins,
        col(series.selected_rate_bps),
    ]
    buffer = io.StringIO()
    buffer.write(",".join(header) + "\n")
    for row in zip(*columns, strict=True):
        buffer.write(",".join(row) + "\n")
    return buffer.getvalue()


def passes_csv(result: LinkSeriesResult) -> str:
    run = result.run
    rows: list[list[str]] = []
    for s in result.series:
        for p in s.passes:
            rows.append(
                [
                    s.link_id,
                    s.site,
                    str(p.index),
                    f"{p.aos_s:.3f}",
                    f"{p.los_s:.3f}",
                    format_utc(run.env.grid.start + timedelta(seconds=p.aos_s)),
                    f"{p.max_elevation_deg:.3f}",
                    _opt(p.usable_s, 3),
                    _opt(p.minimum_margin_db),
                    _opt(p.volume_bits, 1),
                ]
            )
    return _csv(
        [
            "link",
            "station",
            "pass",
            "aos_s",
            "los_s",
            "aos_utc",
            "max_elevation_deg",
            "usable_s",
            "minimum_margin_db",
            "volume_bits",
        ],
        rows,
    )


def link_json(
    static: StaticLinkResult, passes: LinkSeriesResult | None, provenance: Provenance
) -> str:
    data: dict[str, Any] = {
        "static": [asdict(r) for r in static.rows],
        "assumptions": [asdict(a) for a in static.assumptions],
        "problems": [p.to_dict() for p in static.problems],
        "provenance": asdict(provenance),
    }
    if passes is not None:
        env = passes.run.env
        data["scenario"] = {
            "id": passes.run.scenario_id,
            "start_utc": format_utc(env.grid.start),
            "duration_s": env.grid.duration_s,
            "step_s": env.grid.step_s,
        }
        data["links"] = [
            {
                "link": s.link_id,
                "direction": s.direction,
                "station": s.site,
                "rates_bps": list(s.rates_bps),
                "required_margin_db": s.required_margin_db,
                "volume_bits": s.volume_bits,
                "volume_per_day_bits": s.volume_per_day_bits,
                "passes": [asdict(p) for p in s.passes],
            }
            for s in passes.series
        ]
        data["problems"] += [p.to_dict() for p in passes.problems]
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
