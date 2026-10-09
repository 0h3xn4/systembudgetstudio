"""Eclipse duration against the closed-form circular-orbit formula (hand calculation).

For a circular orbit of radius a with the Sun at beta (the angle between the Sun direction and the
orbit plane), the cylindrical shadow lasts a fraction
    f = acos( sqrt(1 - (Re/a)^2) / cos(beta) ) / pi          when |beta| < asin(Re/a), else 0
of the orbit. At the March equinox the Sun is along +X, so for inclination i and RAAN W
    beta = asin( sin(i) sin(W) ).
Tolerance: 0.004 absolute on the fraction (SGP4 osculating radius varies about 1 km, DV-E1/E2).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import pytest

from budget_core.environment import geometry as geo
from budget_core.environment.data import TimeGrid
from budget_core.environment.elements import ElementsPropagator
from budget_core.model import Elements, Orbit

EQUINOX = datetime(2026, 3, 20, 14, 46, tzinfo=UTC)
RE = geo.EARTH_RADIUS_M


def orbit(alt_km: float, inc: float, raan: float, ma: float = 0.0) -> Orbit:
    return Orbit(
        name="t",
        elements=Elements(
            epoch_utc="2026-03-20T14:46:00Z",
            semi_major_axis_m=RE + alt_km * 1000.0,
            eccentricity_ratio=1e-7,
            inclination_deg=inc,
            raan_deg=raan,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=ma,
        ),
    )


def analytic_fraction(alt_km: float, beta_deg: float) -> float:
    a = RE + alt_km * 1000.0
    beta = math.radians(beta_deg)
    if abs(math.sin(beta)) >= RE / a:
        return 0.0
    return math.acos(math.sqrt(1.0 - (RE / a) ** 2) / math.cos(beta)) / math.pi


def period_s(alt_km: float) -> float:
    return 2.0 * math.pi * math.sqrt((RE + alt_km * 1000.0) ** 3 / geo.EARTH_MU_M3S2)


CASES = [
    (alt, inc, raan)
    for alt in (500.0, 800.0)
    for inc, raan in (
        (51.6, 0.0),
        (51.6, 40.0),
        (51.6, 90.0),
        (51.6, 200.0),
        (98.0, 0.0),
        (98.0, 25.0),
        (98.0, 60.0),
        (98.0, 90.0),
    )
]


@pytest.mark.parametrize(("alt", "inc", "raan"), CASES)
def test_cylindrical_eclipse_fraction_matches_the_formula(
    alt: float, inc: float, raan: float
) -> None:
    beta = math.degrees(math.asin(math.sin(math.radians(inc)) * math.sin(math.radians(raan))))
    expected = analytic_fraction(alt, beta)
    t_orbit = period_s(alt)
    grid = TimeGrid(EQUINOX, 3.0 * t_orbit, 30.0)
    env = ElementsPropagator(orbit(alt, inc, raan)).compute(grid, [], "cylindrical")

    if expected == 0.0:
        assert env.eclipses == ()
        return
    # three full orbits are covered; the first and last eclipse may be cut by the window edges
    durations = [e.duration_s for e in env.eclipses]
    assert len(durations) in (3, 4)
    full = [d for d in durations if abs(d / t_orbit - expected) < 0.05]
    assert full, "no complete eclipse found"
    assert max(full) / t_orbit == pytest.approx(expected, abs=0.004)


@pytest.mark.parametrize(("alt", "inc", "raan"), CASES)
def test_the_numeric_beta_angle_matches_the_closed_form(
    alt: float, inc: float, raan: float
) -> None:
    """Checks the sun position, frame and propagation pipeline against beta = asin(sin i sin W)."""
    prop = ElementsPropagator(orbit(alt, inc, raan))
    r, v = prop.state_teme(EQUINOX, 0.0)
    normal = np.cross(r, v)
    normal /= np.linalg.norm(normal)
    jd, fr = geo.julian_date_parts(EQUINOX)
    sun, _ = geo.sun_direction_and_distance(np.array([jd + fr]))
    beta = math.degrees(math.asin(float(sun[0] @ normal)))
    closed = math.degrees(math.asin(math.sin(math.radians(inc)) * math.sin(math.radians(raan))))
    assert beta == pytest.approx(closed, abs=0.5)


def test_eclipse_period_is_the_orbital_period() -> None:
    alt = 500.0
    t_orbit = period_s(alt)
    env = ElementsPropagator(orbit(alt, 51.6, 0.0)).compute(
        TimeGrid(EQUINOX, 4.0 * t_orbit, 30.0), [], "cylindrical"
    )
    starts = [e.start_s for e in env.eclipses]
    gaps = np.diff(starts)
    assert np.allclose(gaps, t_orbit, rtol=0.005)


def test_conical_shadow_adds_a_short_penumbra() -> None:
    alt = 500.0
    grid = TimeGrid(EQUINOX, period_s(alt) * 2.0, 10.0)
    prop = ElementsPropagator(orbit(alt, 51.6, 0.0))
    cyl = prop.compute(grid, [], "cylindrical")
    con = prop.compute(grid, [], "conical")
    assert len(con.eclipses) == len(cyl.eclipses) and len(con.umbras) == len(cyl.umbras)
    for c, k, u in zip(cyl.eclipses, con.eclipses, con.umbras, strict=True):
        assert k.duration_s >= u.duration_s  # shadow includes umbra
        assert abs(k.duration_s - c.duration_s) < 25.0  # penumbra adds seconds, not minutes
        assert u.duration_s <= c.duration_s + 5.0
    ratio = con.sunlight_ratio
    assert ratio.min() == 0.0 and ratio.max() == 1.0 and np.any((ratio > 0.0) & (ratio < 1.0))


def test_eclipse_edges_do_not_depend_on_the_grid_step() -> None:
    alt = 500.0
    prop = ElementsPropagator(orbit(alt, 51.6, 0.0))
    t_orbit = period_s(alt)
    a = prop.compute(TimeGrid(EQUINOX, 2 * t_orbit, 5.0), [], "cylindrical")
    b = prop.compute(TimeGrid(EQUINOX, 2 * t_orbit, 120.0), [], "cylindrical")
    assert len(a.eclipses) == len(b.eclipses) >= 2
    for x, y in zip(a.eclipses, b.eclipses, strict=True):
        assert x.start_s == pytest.approx(y.start_s, abs=0.01)
        assert x.end_s == pytest.approx(y.end_s, abs=0.01)


def test_scenario_starting_inside_an_eclipse() -> None:
    alt = 500.0
    prop = ElementsPropagator(orbit(alt, 51.6, 0.0))
    t_orbit = period_s(alt)
    first = prop.compute(TimeGrid(EQUINOX, t_orbit, 30.0), [], "cylindrical").eclipses[0]
    mid = first.start_s + first.duration_s / 2.0
    start = datetime.fromtimestamp(EQUINOX.timestamp() + mid, UTC)
    env = prop.compute(TimeGrid(start, 600.0, 30.0), [], "cylindrical")
    assert env.eclipses[0].start_s == 0.0 and env.sunlight_ratio[0] == 0.0
