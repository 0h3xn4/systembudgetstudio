"""CSV and JSON exports of the time-domain power budget (deterministic text, LF line endings).

The series CSV has one row per step: the powers are averages over the step, the battery state is
the value at the start of the step. Unavailable values (placeholders) are empty cells.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from typing import Any

import numpy as np

from budget_core.power.time_domain import (
    CaseResult,
    TimeDomainResult,
    Violation,
    format_offset,
    violation_problems,
)
from budget_core.provenance import Provenance
from budget_core.timeutil import format_utc

NDArray = np.ndarray[Any, np.dtype[Any]]

SERIES_COLUMNS = (
    "time_s",
    "time_utc",
    "mode",
    "sunlight_ratio",
    "load_w",
    "demand_w",
    "generation_w",
    "margin_w",
    "battery_power_w",
    "curtailed_w",
    "unmet_w",
    "energy_wh",
    "soc_ratio",
    "dod_ratio",
)


def _column(values: NDArray | None, count: int, every: int) -> tuple[str, list[Any]]:
    """(format, values) of a numeric column; a missing column is empty cells."""
    if values is None:
        return "%s", [""] * len(range(0, count, every))
    return "%.6f", values[:count:every].tolist()


def series_csv(result: TimeDomainResult, case: str, every: int = 1) -> str:
    """The step series of one case; `every` keeps every n-th step (a coarser file)."""
    c = result.case(case)
    n = result.steps
    every = max(every, 1)
    start = np.datetime64(result.run.env.grid.start.replace(tzinfo=None), "ms")
    times = result.edges_s[:-1][::every]
    utc = (start + np.round(times * 1000.0).astype("timedelta64[ms]")).astype(str)
    modes = np.array(result.mode_ids, dtype=object)[result.step_mode][::every]
    columns: list[tuple[str, list[Any]]] = [
        ("%.3f", times.tolist()),
        ("%sZ", utc.tolist()),
        ("%s", modes.tolist()),
        _column(result.lit_ratio, n, every),
        _column(result.load_w, n, every),
        _column(result.demand_w, n, every),
        _column(c.generation_w, n, every),
        _column(c.margin_w, n, every),
        _column(c.battery_power_w, n, every),
        _column(c.curtailed_w, n, every),
        _column(c.unmet_w, n, every),
        _column(c.energy_wh, n, every),
        _column(c.soc_ratio, n, every),
        _column(c.dod_ratio, n, every),
    ]
    row_format = ",".join(f for f, _ in columns) + "\n"
    body = "".join(map(row_format.__mod__, zip(*(v for _, v in columns), strict=True)))
    return ",".join(SERIES_COLUMNS) + "\n" + body


def _csv(header: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def _opt(value: float | None, decimals: int = 6) -> str:
    return "" if value is None else f"{value:.{decimals}f}"


def violations_csv(result: TimeDomainResult) -> str:
    def utc(seconds: float) -> str:
        from datetime import timedelta

        return format_utc(result.run.env.grid.start + timedelta(seconds=seconds))

    return _csv(
        [
            "case",
            "code",
            "start_s",
            "end_s",
            "duration_s",
            "start_utc",
            "end_utc",
            "worst_value",
            "limit",
            "unit",
            "file",
            "path",
        ],
        [
            [
                v.case or "",
                v.code,
                f"{v.start_s:.3f}",
                f"{v.end_s:.3f}",
                f"{v.end_s - v.start_s:.3f}",
                utc(v.start_s),
                utc(v.end_s),
                _opt(v.extreme),
                _opt(v.limit),
                v.unit,
                v.file,
                v.path,
            ]
            for v in result.violations
        ],
    )


def balance_csv(result: TimeDomainResult) -> str:
    rows = []
    for c in result.cases:
        for b in c.balances:
            rows.append(
                [
                    c.case,
                    str(b.index),
                    f"{b.start_s:.3f}",
                    f"{b.end_s:.3f}",
                    f"{b.eclipse_s:.3f}",
                    _opt(b.generation_wh),
                    _opt(b.demand_wh),
                    _opt(b.balance_wh),
                    _opt(b.battery_change_wh),
                ]
            )
    return _csv(
        [
            "case",
            "orbit",
            "start_s",
            "end_s",
            "eclipse_s",
            "generation_wh",
            "demand_wh",
            "balance_wh",
            "battery_change_wh",
        ],
        rows,
    )


def _violation_dict(v: Violation) -> dict[str, Any]:
    data = asdict(v)
    data["start_offset"] = format_offset(v.start_s)
    return data


def _case_dict(c: CaseResult) -> dict[str, Any]:
    return {
        "age_years": c.age_years,
        "capacity_wh": c.capacity_wh,
        "summary": asdict(c.summary),
        "balances": [asdict(b) for b in c.balances],
        "violations": [_violation_dict(v) for v in c.violations],
    }


def timeline_json(result: TimeDomainResult, provenance: Provenance) -> str:
    env, sc = result.run.env, result.run.scenario
    data: dict[str, Any] = {
        "scenario": result.run.scenario_id,
        "load_basis": result.load_basis,
        "mission_phase": result.mission_phase,
        "grid": {
            "start_utc": format_utc(env.grid.start),
            "duration_s": sc.duration_s,
            "step_s": sc.step_s,
            "steps": result.steps,
        },
        "environment": {
            "source": env.source,
            "shadow_model": env.shadow_model,
            "eclipse_fraction": env.eclipse_fraction,
            "orbits": len(result.windows),
        },
        "limits": {"peak_power_w": result.peak_limit_w, "dod_limit_ratio": result.dod_limit_ratio},
        "modes": [asdict(m) for m in result.modes],
        "cases": {c.case: _case_dict(c) for c in result.cases},
        "violations": [_violation_dict(v) for v in result.violations],
        "assumptions": [asdict(a) for a in result.assumptions],
        "problems": [p.to_dict() for p in [*result.problems, *violation_problems(result)]],
        "provenance": asdict(provenance),
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
