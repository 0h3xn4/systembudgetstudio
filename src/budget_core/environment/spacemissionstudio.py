"""SpaceMissionStudio environment adapter (INTERIM file format, decision D-055).

No sample export was available, so this reads the documented interim CSV format in
docs/ENVIRONMENT_FORMAT.md: orbit.csv, eclipse.csv, passes_<site>.csv and an optional
profile_<site>.csv. `export_spacemissionstudio` writes the same files from any environment so the
two adapters can be compared. Replace the format when real exports are available.
Error messages name the file and line but never echo file content.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from budget_core.environment import geometry as geo
from budget_core.environment.data import (
    EnvironmentData,
    Pass,
    SiteDef,
    SiteVisibility,
    TimeGrid,
)
from budget_core.environment.intervals import Interval
from budget_core.timeutil import format_utc, parse_utc

NDArray = np.ndarray[Any, np.dtype[np.float64]]

ORBIT_HEADER = ["time_utc", "x_m", "y_m", "z_m", "vx_mps", "vy_mps", "vz_mps"]
ECLIPSE_HEADER = ["start_utc", "end_utc"]
PASS_HEADER = ["aos_utc", "los_utc", "max_elevation_deg"]
PROFILE_HEADER = ["time_utc", "elevation_deg", "azimuth_deg", "range_m"]


class EnvironmentInputError(Exception):
    """An environment input file is missing or malformed."""

    def __init__(self, message: str, file: str, line: int | None = None) -> None:
        super().__init__(message)
        self.file = file
        self.line = line


def _rows(
    folder: Path, name: str, header: list[str], optional: bool = False
) -> list[tuple[int, list[str]]]:
    path = folder / name
    if not path.is_file():
        if optional:
            return []
        raise EnvironmentInputError("the file is missing", name)
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise EnvironmentInputError("the file is not valid UTF-8 text", name) from None
    lines = list(csv.reader(text.splitlines()))
    if not lines or [c.strip() for c in lines[0]][: len(header)] != header:
        raise EnvironmentInputError("the header does not match the documented format", name, 1)
    return [(i, row) for i, row in enumerate(lines[1:], start=2) if any(c.strip() for c in row)]


def _time(text: str, start: datetime, file: str, line: int) -> float:
    try:
        return (parse_utc(text) - start).total_seconds()
    except ValueError:
        raise EnvironmentInputError("the time is not a valid UTC time", file, line) from None


def _number(text: str, file: str, line: int) -> float:
    try:
        value = float(text)
    except ValueError:
        raise EnvironmentInputError("a value is not a number", file, line) from None
    if value != value or value in (float("inf"), float("-inf")):
        raise EnvironmentInputError("a value is not finite", file, line)
    return value


def _hermite(t: NDArray, p: NDArray, v: NDArray | None, tau: NDArray) -> NDArray:
    """Cubic Hermite interpolation of positions (with velocities) or linear without them."""
    k = np.clip(np.searchsorted(t, tau, side="right") - 1, 0, len(t) - 2)
    h = (t[k + 1] - t[k])[:, None]
    s = ((tau - t[k])[:, None]) / h
    if v is None:
        return np.asarray(p[k] * (1.0 - s) + p[k + 1] * s)
    h00, h10 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s
    h01, h11 = -2 * s**3 + 3 * s**2, s**3 - s**2
    return np.asarray(h00 * p[k] + h10 * h * v[k] + h01 * p[k + 1] + h11 * h * v[k + 1])


class SpaceMissionStudioImport:
    name = "spacemissionstudio"

    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.notes: list[str] = []

    def compute(
        self, grid: TimeGrid, sites: Sequence[SiteDef], shadow_model: str
    ) -> EnvironmentData:
        self.notes = []
        times = grid.times_s
        position = self._orbit(grid, times)
        jd0, fr0 = geo.julian_date_parts(grid.start)
        jd = jd0 + fr0 + times / 86400.0
        sun_dir, _ = geo.sun_direction_and_distance(jd)
        eclipses = self._eclipses(grid)
        ratio = np.ones(len(times))
        for e in eclipses:
            ratio[(times >= e.start_s) & (times <= e.end_s)] = 0.0
        visibility = {site.site_id: self._site(grid, times, site) for site in sites}
        return EnvironmentData(
            grid=grid,
            source=self.name,
            shadow_model=shadow_model,
            position_m=position,
            sun_direction=sun_dir,
            sunlight_ratio=ratio,
            eclipses=tuple(eclipses),
            umbras=tuple(eclipses),  # the interim format has no penumbra information
            sites=visibility,
        )

    def _orbit(self, grid: TimeGrid, times: NDArray) -> NDArray:
        file = "orbit.csv"
        rows = _rows(self.folder, file, ORBIT_HEADER)
        if len(rows) < 2:
            raise EnvironmentInputError("at least two rows are needed", file)
        t, p, v = [], [], []
        for line, row in rows:
            if len(row) < 7:
                raise EnvironmentInputError("a row has too few columns", file, line)
            t.append(_time(row[0], grid.start, file, line))
            p.append([_number(c, file, line) for c in row[1:4]])
            v.append([_number(c, file, line) for c in row[4:7]])
        ta, pa, va = np.array(t), np.array(p), np.array(v)
        if np.any(np.diff(ta) <= 0):
            raise EnvironmentInputError("times must increase strictly", file)
        if ta[0] > 1e-6 or ta[-1] < grid.duration_s - 1e-6:
            raise EnvironmentInputError(
                "the file does not cover the scenario time range (start to start + duration)", file
            )
        return _hermite(ta, pa, va, times)

    def _eclipses(self, grid: TimeGrid) -> list[Interval]:
        file = "eclipse.csv"
        out: list[Interval] = []
        for line, row in _rows(self.folder, file, ECLIPSE_HEADER):
            if len(row) < 2:
                raise EnvironmentInputError("a row has too few columns", file, line)
            a = _time(row[0], grid.start, file, line)
            b = _time(row[1], grid.start, file, line)
            if b < a:
                raise EnvironmentInputError("an interval ends before it starts", file, line)
            if b > 0.0 and a < grid.duration_s:
                out.append(Interval(max(a, 0.0), min(b, grid.duration_s)))
        return sorted(out, key=lambda i: i.start_s)

    def _site(self, grid: TimeGrid, times: NDArray, site: SiteDef) -> SiteVisibility:
        file = f"passes_{site.site_id}.csv"
        passes: list[Pass] = []
        for line, row in _rows(self.folder, file, PASS_HEADER):
            if len(row) < 3:
                raise EnvironmentInputError("a row has too few columns", file, line)
            aos = _time(row[0], grid.start, file, line)
            los = _time(row[1], grid.start, file, line)
            peak = _number(row[2], file, line)
            if los < aos:
                raise EnvironmentInputError("a pass ends before it starts", file, line)
            if los > 0.0 and aos < grid.duration_s:
                passes.append(
                    Pass(
                        max(aos, 0.0),
                        min(los, grid.duration_s),
                        peak,
                        (aos + los) / 2.0,
                        aos < 0.0,
                        los > grid.duration_s,
                    )
                )
        passes.sort(key=lambda p: p.aos_s)
        el, az, rng = self._profile(grid, times, site, passes)
        return SiteVisibility(site, tuple(passes), el, az, rng)

    def _profile(
        self, grid: TimeGrid, times: NDArray, site: SiteDef, passes: list[Pass]
    ) -> tuple[NDArray, NDArray, NDArray]:
        file = f"profile_{site.site_id}.csv"
        rows = _rows(self.folder, file, PROFILE_HEADER, optional=True)
        nan = np.full(len(times), np.nan)
        if not rows:
            self.notes.append(
                f"{file} not found: elevation, azimuth and range are unavailable (NaN) for "
                f"'{site.site_id}'"
            )
            return nan.copy(), nan.copy(), nan.copy()
        t, e, a, r = [], [], [], []
        for line, row in rows:
            if len(row) < 4:
                raise EnvironmentInputError("a row has too few columns", file, line)
            t.append(_time(row[0], grid.start, file, line))
            e.append(_number(row[1], file, line))
            a.append(_number(row[2], file, line))
            r.append(_number(row[3], file, line))
        order = np.argsort(t)
        ta = np.array(t)[order]
        el = np.interp(times, ta, np.array(e)[order])
        az = np.degrees(np.interp(times, ta, np.unwrap(np.radians(np.array(a)[order])))) % 360.0
        rg = np.interp(times, ta, np.array(r)[order])
        inside = np.zeros(len(times), dtype=bool)
        for p in passes:
            inside |= (times >= p.aos_s - 1e-9) & (times <= p.los_s + 1e-9)
        el[~inside], az[~inside], rg[~inside] = np.nan, np.nan, np.nan
        return el, az, rg


def _write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def export_spacemissionstudio(env: EnvironmentData, folder: Path) -> list[Path]:
    """Write the interim-format files of an environment (positions with finite-difference
    velocities, eclipse intervals, passes and elevation profiles of every site)."""
    folder = Path(folder)
    start = env.grid.start

    def stamp(t: float) -> str:
        return format_utc(start + timedelta(seconds=float(t)))

    times = env.grid.times_s
    velocity = np.gradient(env.position_m, times, axis=0) if len(times) > 1 else np.zeros((1, 3))
    _write(
        folder / "orbit.csv",
        ORBIT_HEADER,
        [
            [stamp(t), *(repr(float(c)) for c in pos), *(repr(float(c)) for c in vel)]
            for t, pos, vel in zip(times, env.position_m, velocity, strict=True)
        ],
    )
    _write(
        folder / "eclipse.csv",
        ECLIPSE_HEADER,
        [[stamp(e.start_s), stamp(e.end_s)] for e in env.eclipses],
    )
    for site_id, vis in sorted(env.sites.items()):
        _write(
            folder / f"passes_{site_id}.csv",
            PASS_HEADER,
            [
                [stamp(p.aos_s), stamp(p.los_s), repr(float(p.max_elevation_deg))]
                for p in vis.passes
            ],
        )
        rows = []
        for i, t in enumerate(times):
            if any(p.aos_s <= t <= p.los_s for p in vis.passes):
                rows.append(
                    [
                        stamp(t),
                        repr(float(vis.elevation_deg[i])),
                        repr(float(vis.azimuth_deg[i])),
                        repr(float(vis.range_m[i])),
                    ]
                )
        _write(folder / f"profile_{site_id}.csv", PROFILE_HEADER, rows)
    return sorted(folder.iterdir())
