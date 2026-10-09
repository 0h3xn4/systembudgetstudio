"""Pass geometry against the analytic equatorial-orbit pass duration (hand calculation).

For a circular orbit of radius a over an equatorial site (equatorial orbit, overhead pass) the
Earth central half-angle of visibility above elevation e is
    lam(e) = acos( (Re/a) cos(e) ) - e,
and the pass lasts 2 lam / (n - w_E) with n = sqrt(mu / a^3) and w_E the Earth rotation rate
(7.2921159e-5 rad/s, IERS). Tolerance: 1.5 percent of the duration plus 2 s (SGP4 mean motion
differs from Kepler's by about 0.1 percent; osculating radius varies about 1 km).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from budget_core.environment import geometry as geo
from budget_core.environment.data import SiteDef, TimeGrid
from budget_core.environment.elements import ElementsPropagator
from budget_core.model import Elements, Orbit

START = datetime(2026, 1, 1, tzinfo=UTC)
RE = geo.EARTH_RADIUS_M
EARTH_RATE = 7.2921159e-5


def equatorial(alt_km: float) -> Orbit:
    return Orbit(
        name="eq",
        elements=Elements(
            epoch_utc="2026-01-01T00:00:00Z",
            semi_major_axis_m=RE + alt_km * 1000.0,
            eccentricity_ratio=1e-7,
            inclination_deg=0.0,
            raan_deg=0.0,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=0.0,
        ),
    )


def expected_duration(alt_km: float, min_el_deg: float) -> float:
    a = RE + alt_km * 1000.0
    e = math.radians(min_el_deg)
    lam = math.acos((RE / a) * math.cos(e)) - e
    n = math.sqrt(geo.EARTH_MU_M3S2 / a**3)
    return 2.0 * lam / (n - EARTH_RATE)


def site_under_the_satellite(prop: ElementsPropagator, t_s: float, min_el: float) -> SiteDef:
    """An equatorial site whose longitude equals the sub-satellite longitude at time t_s."""
    r, _ = prop.state_teme(START, t_s)
    when = START + timedelta(seconds=t_s)
    jd, fr = geo.julian_date_parts(when)
    ecef = geo.eci_to_ecef(r[None, :], geo.gmst_rad(np.array([jd + fr])))[0]
    lon = math.degrees(math.atan2(ecef[1], ecef[0]))
    return SiteDef("gs", "ground_station", 0.0, lon, 0.0, min_el)


CASES = [(alt, el) for alt in (500.0, 800.0) for el in (0.0, 5.0, 10.0, 20.0, 30.0)]


@pytest.mark.parametrize(("alt", "min_el"), CASES)
def test_overhead_pass_duration_matches_the_formula(alt: float, min_el: float) -> None:
    prop = ElementsPropagator(equatorial(alt))
    t_center = 1500.0
    site = site_under_the_satellite(prop, t_center, min_el)
    env = prop.compute(TimeGrid(START, 3600.0, 10.0), [site], "cylindrical")
    passes = env.sites["gs"].passes
    mid = [p for p in passes if p.aos_s < t_center < p.los_s]
    assert len(mid) == 1
    p = mid[0]
    expected = expected_duration(alt, min_el)
    assert p.los_s - p.aos_s == pytest.approx(expected, rel=0.015, abs=2.0)
    assert (p.aos_s + p.los_s) / 2.0 == pytest.approx(t_center, abs=0.015 * expected + 2.0)
    assert p.max_elevation_deg == pytest.approx(90.0, abs=0.5)
    assert p.time_of_max_s == pytest.approx(t_center, abs=0.02 * expected + 2.0)


def test_pass_edges_sit_on_the_minimum_elevation() -> None:
    prop = ElementsPropagator(equatorial(500.0))
    site = site_under_the_satellite(prop, 1500.0, 10.0)
    env = prop.compute(TimeGrid(START, 3600.0, 10.0), [site], "cylindrical")
    p = next(p for p in env.sites["gs"].passes if p.aos_s < 1500.0 < p.los_s)
    for t in (p.aos_s, p.los_s):
        r, _ = prop.state_teme(START, t)
        when = START + timedelta(seconds=t)
        jd, fr = geo.julian_date_parts(when)
        ecef = geo.eci_to_ecef(r[None, :], geo.gmst_rad(np.array([jd + fr])))
        el, _, _ = geo.topocentric(
            ecef, geo.geodetic_to_ecef(0.0, site.longitude_deg, 0.0), 0.0, site.longitude_deg
        )
        assert el[0] == pytest.approx(10.0, abs=0.005)


def test_pass_times_do_not_depend_on_the_grid_step() -> None:
    prop = ElementsPropagator(equatorial(500.0))
    site = site_under_the_satellite(prop, 1500.0, 5.0)
    a = prop.compute(TimeGrid(START, 14000.0, 2.0), [site], "cylindrical").sites["gs"].passes
    b = prop.compute(TimeGrid(START, 14000.0, 60.0), [site], "cylindrical").sites["gs"].passes
    assert len(a) == len(b) >= 2
    for x, y in zip(a, b, strict=True):
        assert x.aos_s == pytest.approx(y.aos_s, abs=0.01) and x.los_s == pytest.approx(
            y.los_s, abs=0.01
        )
        assert x.max_elevation_deg == pytest.approx(y.max_elevation_deg, abs=0.01)


def test_a_site_at_the_pole_never_sees_an_equatorial_satellite() -> None:
    prop = ElementsPropagator(equatorial(500.0))
    pole = SiteDef("pole", "ground_station", 89.0, 0.0, 0.0, 0.0)
    env = prop.compute(TimeGrid(START, 86400.0, 60.0), [pole], "cylindrical")
    assert env.sites["pole"].passes == ()


def test_pass_invariants_over_a_day() -> None:
    prop = ElementsPropagator(
        Orbit(
            name="o",
            elements=Elements(
                epoch_utc="2026-01-01T00:00:00Z",
                semi_major_axis_m=RE + 600e3,
                eccentricity_ratio=0.001,
                inclination_deg=97.0,
                raan_deg=30.0,
                arg_perigee_deg=0.0,
                mean_anomaly_deg=0.0,
            ),
        )
    )
    sites = [
        SiteDef("a", "ground_station", 60.0, 10.0, 100.0, 5.0),
        SiteDef("b", "target", -33.0, 150.0, 0.0, 20.0),
    ]
    env = prop.compute(TimeGrid(START, 86400.0, 30.0), sites, "cylindrical")
    for site in sites:
        vis = env.sites[site.site_id]
        assert len(vis.passes) >= {"a": 4, "b": 1}[site.site_id]  # 20 deg minimum: few passes
        previous_los = -1.0
        for p in vis.passes:
            assert previous_los < p.aos_s < p.time_of_max_s < p.los_s
            assert p.max_elevation_deg >= site.min_elevation_deg - 1e-6
            assert p.los_s - p.aos_s < 1800.0  # LEO passes last minutes, never hours
            previous_los = p.los_s
        times = env.grid.times_s
        inside = np.zeros(len(times), dtype=bool)
        for p in vis.passes:
            inside |= (times >= p.aos_s) & (times <= p.los_s)
        above = vis.elevation_deg >= site.min_elevation_deg
        # outside every pass the satellite is below the minimum elevation (grid samples)
        assert not np.any(above & ~inside)


def test_partial_passes_at_the_scenario_edges_are_flagged() -> None:
    prop = ElementsPropagator(equatorial(500.0))
    site = site_under_the_satellite(prop, 1500.0, 5.0)
    env = prop.compute(TimeGrid(START, 1500.0, 10.0), [site], "cylindrical")  # ends mid-pass
    last = env.sites["gs"].passes[-1]
    assert last.partial_end and last.los_s == pytest.approx(1500.0)
