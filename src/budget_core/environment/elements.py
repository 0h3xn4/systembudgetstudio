"""ElementsPropagator: TLE or mean elements propagated with sgp4 (no own propagator, spec).

Elements are used as SGP4 mean elements; the semi-major axis becomes mean motion by Kepler's third
law (DEVIATIONS DV-E2). Interval edges are refined by bisection (decision D-057).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sgp4.api import WGS84, Satrec, SatrecArray

from budget_core.environment import geometry as geo
from budget_core.environment.data import (
    EnvironmentData,
    Pass,
    PropagationError,
    SiteDef,
    SiteVisibility,
    TimeGrid,
)
from budget_core.environment.intervals import BoolArray, Interval, bisect_edge, mask_to_intervals
from budget_core.model import Orbit
from budget_core.timeutil import parse_utc

NDArray = np.ndarray[Any, np.dtype[np.float64]]
DETECTION_STEP_S = 20.0  # passes and eclipses shorter than this could be missed
LIT = 1.0 - 1e-12
UMBRA = 1e-12
EDGE_TOLERANCE_S = 1e-3


def build_satrec(orbit: Orbit) -> Satrec:
    """Create the sgp4 satellite record of an orbit definition."""
    if orbit.tle is not None:
        return Satrec.twoline2rv(orbit.tle[0], orbit.tle[1])
    el = orbit.elements
    assert el is not None  # validated: exactly one source
    jd, fr = geo.julian_date_parts(parse_utc(el.epoch_utc))
    motion_rad_per_min = math.sqrt(geo.EARTH_MU_M3S2 / el.semi_major_axis_m**3) * 60.0
    sat = Satrec()
    sat.sgp4init(
        WGS84,
        "i",
        1,
        (jd + fr) - 2433281.5,
        0.0,
        0.0,
        0.0,
        el.eccentricity_ratio,
        math.radians(el.arg_perigee_deg),
        math.radians(el.inclination_deg),
        math.radians(el.mean_anomaly_deg),
        motion_rad_per_min,
        math.radians(el.raan_deg),
    )
    return sat


def check_orbit(orbit: Orbit) -> str | None:
    """None if the orbit can be propagated at its own epoch, else a short reason."""
    try:
        sat = build_satrec(orbit)
        error, _, _ = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF)
    except Exception:  # sgp4 raises ValueError for malformed element sets
        return "the element set cannot be read by SGP4"
    return f"SGP4 cannot propagate this orbit at its epoch (error {error})" if error else None


class ElementsPropagator:
    name = "elements"

    def __init__(self, orbit: Orbit) -> None:
        self.orbit = orbit
        self.sat = build_satrec(orbit)

    # ---- states --------------------------------------------------------------------------------
    def state_teme(self, start: datetime, t_s: float) -> tuple[NDArray, NDArray]:
        """Position (m) and velocity (m/s) in TEME at `t_s` seconds after `start`."""
        jd, fr = geo.julian_date_parts(start + timedelta(seconds=t_s))
        error, r, v = self.sat.sgp4(jd, fr)
        if error:
            raise PropagationError(f"the orbit cannot be propagated (SGP4 error {error})")
        return np.array(r) * 1000.0, np.array(v) * 1000.0

    def _positions(self, start: datetime, times_s: NDArray) -> tuple[NDArray, NDArray]:
        """TEME positions (N, 3) in m and the Julian dates (N,) of a set of times."""
        jd0, fr0 = geo.julian_date_parts(start)
        fractions = fr0 + times_s / 86400.0
        error, pos, _ = SatrecArray([self.sat]).sgp4(np.full(len(times_s), jd0), fractions)
        if np.any(error):
            raise PropagationError("the orbit cannot be propagated over the whole scenario")
        return np.asarray(pos[0]) * 1000.0, jd0 + fractions

    # ---- environment ---------------------------------------------------------------------------
    def compute(
        self, grid: TimeGrid, sites: Sequence[SiteDef], shadow_model: str
    ) -> EnvironmentData:
        times = grid.times_s
        pos, jd = self._positions(grid.start, times)
        sun_dir, sun_dist = geo.sun_direction_and_distance(jd)
        ratio = geo.sun_visibility(pos, sun_dir * sun_dist[:, None], shadow_model)

        def nu_at(t: float) -> float:
            r, _ = self.state_teme(grid.start, t)
            jd_t = np.array([sum(geo.julian_date_parts(grid.start + timedelta(seconds=t)))])
            d, dist = geo.sun_direction_and_distance(jd_t)
            return float(geo.sun_visibility(r[None, :], d * dist[:, None], shadow_model)[0])

        detect = _detection_times(grid)
        det_pos, det_jd = self._positions(grid.start, detect)
        det_dir, det_dist = geo.sun_direction_and_distance(det_jd)
        det_ratio = geo.sun_visibility(det_pos, det_dir * det_dist[:, None], shadow_model)
        eclipses = _intervals(detect, det_ratio < LIT, lambda t: nu_at(t) < LIT, grid.duration_s)
        umbras = _intervals(
            detect, det_ratio <= UMBRA, lambda t: nu_at(t) <= UMBRA, grid.duration_s
        )

        visibility: dict[str, SiteVisibility] = {}
        gmst = geo.gmst_rad(jd)
        det_gmst = geo.gmst_rad(det_jd)
        for site in sites:
            site_ecef = geo.geodetic_to_ecef(site.latitude_deg, site.longitude_deg, site.altitude_m)

            def elevation_at(t: float, _site: SiteDef = site, _ecef: NDArray = site_ecef) -> float:
                r, _ = self.state_teme(grid.start, t)
                jd_t = np.array([sum(geo.julian_date_parts(grid.start + timedelta(seconds=t)))])
                ecef = geo.eci_to_ecef(r[None, :], geo.gmst_rad(jd_t))
                el, _, _ = geo.topocentric(ecef, _ecef, _site.latitude_deg, _site.longitude_deg)
                return float(el[0])

            det_ecef = geo.eci_to_ecef(det_pos, det_gmst)
            det_el, _, _ = geo.topocentric(
                det_ecef, site_ecef, site.latitude_deg, site.longitude_deg
            )
            passes = _passes(detect, det_el, site.min_elevation_deg, elevation_at, grid.duration_s)
            el, az, rng = geo.topocentric(
                geo.eci_to_ecef(pos, gmst), site_ecef, site.latitude_deg, site.longitude_deg
            )
            visibility[site.site_id] = SiteVisibility(site, tuple(passes), el, az, rng)

        return EnvironmentData(
            grid=grid,
            source=self.name,
            shadow_model=shadow_model,
            position_m=pos,
            sun_direction=sun_dir,
            sunlight_ratio=ratio,
            eclipses=tuple(eclipses),
            umbras=tuple(umbras),
            sites=visibility,
        )


def _detection_times(grid: TimeGrid) -> NDArray:
    step = min(grid.step_s, DETECTION_STEP_S)
    times = np.arange(0.0, grid.duration_s, step)
    return np.append(times, grid.duration_s)


def _edges(
    detect: NDArray,
    mask: BoolArray,
    predicate: Callable[[float], bool],
    duration_s: float,
) -> list[tuple[float, float, bool, bool]]:
    """(start, end, partial_start, partial_end) of the runs of `mask`, edges refined."""
    out = []
    for start, end in mask_to_intervals(detect, mask):
        s = 0.0 if start is None else bisect_edge(predicate, start[0], start[1], EDGE_TOLERANCE_S)
        e = duration_s if end is None else bisect_edge(predicate, end[0], end[1], EDGE_TOLERANCE_S)
        out.append((s, e, start is None, end is None))
    return out


def _intervals(
    detect: NDArray, mask: BoolArray, predicate: Callable[[float], bool], duration_s: float
) -> list[Interval]:
    return [Interval(s, e) for s, e, _, _ in _edges(detect, mask, predicate, duration_s)]


def _passes(
    detect: NDArray,
    elevation: NDArray,
    min_elevation: float,
    elevation_at: Callable[[float], float],
    duration_s: float,
) -> list[Pass]:
    mask = elevation >= min_elevation
    out: list[Pass] = []
    for start, end, partial_start, partial_end in _edges(
        detect, mask, lambda t: elevation_at(t) >= min_elevation, duration_s
    ):
        inside = (detect >= start) & (detect <= end)
        k = int(np.argmax(np.where(inside, elevation, -np.inf)))
        lo = float(detect[max(k - 1, 0)])
        hi = float(detect[min(k + 1, len(detect) - 1)])
        t_max, el_max = _maximise(elevation_at, max(lo, start), min(hi, end))
        out.append(Pass(start, end, max(el_max, min_elevation), t_max, partial_start, partial_end))
    return out


def _maximise(f: Callable[[float], float], lo: float, hi: float) -> tuple[float, float]:
    """Golden-section search for the maximum of a unimodal function on [lo, hi]."""
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = hi - ratio * (hi - lo), lo + ratio * (hi - lo)
    fc, fd = f(c), f(d)
    while hi - lo > 1e-2:
        if fc > fd:
            hi, d, fd = d, c, fc
            c = hi - ratio * (hi - lo)
            fc = f(c)
        else:
            lo, c, fc = c, d, fd
            d = lo + ratio * (hi - lo)
            fd = f(d)
    t = 0.5 * (lo + hi)
    return t, f(t)
