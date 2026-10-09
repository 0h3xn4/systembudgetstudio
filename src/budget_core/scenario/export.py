"""Scenario outputs: environment JSON and CSV tables (deterministic, LF, fixed decimals)."""

from __future__ import annotations

import csv
import io
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from budget_core.provenance import Provenance
from budget_core.scenario.run import ScenarioRun
from budget_core.timeutil import format_utc


def _t(run: ScenarioRun, seconds: float) -> str:
    return format_utc(run.env.grid.start + timedelta(seconds=seconds))


def _s(value: float) -> str:
    return f"{value:.3f}"


def _csv(header: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def eclipses_csv(run: ScenarioRun) -> str:
    return _csv(
        ["start_s", "end_s", "duration_s", "start_utc", "end_utc"],
        [
            [_s(e.start_s), _s(e.end_s), _s(e.duration_s), _t(run, e.start_s), _t(run, e.end_s)]
            for e in run.env.eclipses
        ],
    )


def passes_csv(run: ScenarioRun) -> str:
    rows = []
    for site_id, vis in sorted(run.env.sites.items()):
        for p in vis.passes:
            rows.append(
                [
                    site_id,
                    vis.site.kind,
                    _s(p.aos_s),
                    _s(p.los_s),
                    _s(p.duration_s),
                    f"{p.max_elevation_deg:.4f}",
                    _s(p.time_of_max_s),
                    _t(run, p.aos_s),
                    _t(run, p.los_s),
                    str(p.partial_start).lower(),
                    str(p.partial_end).lower(),
                ]
            )
    return _csv(
        [
            "site",
            "kind",
            "aos_s",
            "los_s",
            "duration_s",
            "max_elevation_deg",
            "time_of_max_s",
            "aos_utc",
            "los_utc",
            "partial_start",
            "partial_end",
        ],
        rows,
    )


def timeline_csv(run: ScenarioRun) -> str:
    return _csv(
        ["start_s", "end_s", "duration_s", "mode", "start_utc", "end_utc"],
        [
            [
                _s(s.start_s),
                _s(s.end_s),
                _s(s.duration_s),
                s.mode,
                _t(run, s.start_s),
                _t(run, s.end_s),
            ]
            for s in run.timeline
        ],
    )


def environment_json(run: ScenarioRun, provenance: Provenance) -> str:
    env = run.env
    data: dict[str, Any] = {
        "scenario": run.scenario_id,
        "source": env.source,
        "shadow_model": env.shadow_model,
        "grid": {
            "start_utc": format_utc(env.grid.start),
            "duration_s": env.grid.duration_s,
            "step_s": env.grid.step_s,
            "samples": env.grid.count,
        },
        "eclipse_fraction": round(env.eclipse_fraction, 6),
        "eclipses": [
            {
                "start_s": round(e.start_s, 3),
                "end_s": round(e.end_s, 3),
                "duration_s": round(e.duration_s, 3),
            }
            for e in env.eclipses
        ],
        "umbras": [
            {
                "start_s": round(e.start_s, 3),
                "end_s": round(e.end_s, 3),
                "duration_s": round(e.duration_s, 3),
            }
            for e in env.umbras
        ],
        "sites": {
            site_id: {
                "kind": vis.site.kind,
                "passes": [
                    {
                        "aos_s": round(p.aos_s, 3),
                        "los_s": round(p.los_s, 3),
                        "duration_s": round(p.duration_s, 3),
                        "max_elevation_deg": round(p.max_elevation_deg, 4),
                        "time_of_max_s": round(p.time_of_max_s, 3),
                        "partial_start": p.partial_start,
                        "partial_end": p.partial_end,
                    }
                    for p in vis.passes
                ],
            }
            for site_id, vis in sorted(env.sites.items())
        },
        "timeline": [
            {"start_s": round(s.start_s, 3), "end_s": round(s.end_s, 3), "mode": s.mode}
            for s in run.timeline
        ],
        "notes": list(run.notes),
        "provenance": {
            "tool": provenance.tool,
            "tool_version": provenance.tool_version,
            "project_name": provenance.project_name,
            "project_revision": provenance.project_revision,
            "scenario": run.scenario_id,
            "generated": provenance.generated,
            "user": provenance.user,
        },
    }
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def write_scenario_outputs(run: ScenarioRun, provenance: Provenance, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sid = run.scenario_id
    files = {
        f"{sid}_environment.json": environment_json(run, provenance),
        f"{sid}_eclipses.csv": eclipses_csv(run),
        f"{sid}_passes.csv": passes_csv(run),
        f"{sid}_timeline.csv": timeline_csv(run),
    }
    written = []
    for name, text in files.items():
        path = out_dir / name
        path.write_bytes(text.encode("utf-8"))
        written.append(path)
    return written
