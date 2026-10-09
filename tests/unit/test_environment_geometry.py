"""Pure geometry: Sun, sidereal time, shadow, geodetic and topocentric conversions."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import pytest
from sgp4.api import jday
from sgp4.propagation import gstime

from budget_core.environment import geometry as g

A = g.EARTH_RADIUS_M


def jd(dt: datetime) -> float:
    whole, frac = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    return float(whole + frac)


def declination_deg(v: np.ndarray) -> float:
    return math.degrees(math.asin(float(v[2])))


def right_ascension_deg(v: np.ndarray) -> float:
    return math.degrees(math.atan2(float(v[1]), float(v[0]))) % 360.0


# ---- Sun (Astronomical Almanac low-precision formulae) ---------------------------------------
# Published instants (USNO) of the year 2000 equinoxes and solstices: at each, the Sun's
# apparent right ascension and declination are known from the definition of the instant.


@pytest.mark.parametrize(
    ("when", "ra_deg", "dec_deg"),
    [
        (datetime(2000, 3, 20, 7, 35, tzinfo=UTC), 0.0, 0.0),  # March equinox
        (datetime(2000, 6, 21, 1, 48, tzinfo=UTC), 90.0, 23.44),  # June solstice
        (datetime(2000, 9, 22, 17, 27, tzinfo=UTC), 180.0, 0.0),  # September equinox
        (datetime(2000, 12, 21, 13, 37, tzinfo=UTC), 270.0, -23.44),  # December solstice
    ],
)
def test_sun_direction_at_equinoxes_and_solstices(
    when: datetime, ra_deg: float, dec_deg: float
) -> None:
    v, _ = g.sun_direction_and_distance(np.array([jd(when)]))
    ra = right_ascension_deg(v[0])
    assert abs((ra - ra_deg + 180.0) % 360.0 - 180.0) < 0.05
    assert declination_deg(v[0]) == pytest.approx(dec_deg, abs=0.05)
    assert float(np.linalg.norm(v[0])) == pytest.approx(1.0, abs=1e-12)


def test_sun_distance_at_perihelion_and_aphelion() -> None:
    peri = g.sun_direction_and_distance(np.array([jd(datetime(2000, 1, 3, 5, tzinfo=UTC))]))[1]
    aph = g.sun_direction_and_distance(np.array([jd(datetime(2000, 7, 4, 0, tzinfo=UTC))]))[1]
    assert peri[0] / g.ASTRONOMICAL_UNIT_M == pytest.approx(0.98330, abs=0.0005)
    assert aph[0] / g.ASTRONOMICAL_UNIT_M == pytest.approx(1.01667, abs=0.0005)


# ---- sidereal time ----------------------------------------------------------------------------


def test_gmst_matches_the_sgp4_library() -> None:
    epochs = np.array(
        [
            jd(datetime(2000 + k, 1 + k % 12, 1 + k % 28, 3 * k % 24, tzinfo=UTC))
            for k in range(0, 26)
        ]
    )
    ours = g.gmst_rad(epochs)
    theirs = np.array([gstime(e) for e in epochs])
    assert np.max(np.abs(np.angle(np.exp(1j * (ours - theirs))))) < 1e-8


def test_eci_to_ecef_rotation() -> None:
    x = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    assert np.allclose(g.eci_to_ecef(x, np.array([0.0, 0.0])), x)
    out = g.eci_to_ecef(x, np.array([math.pi / 2, math.pi / 2]))
    assert np.allclose(out, [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0]], atol=1e-12)


# ---- geodetic and topocentric ----------------------------------------------------------------


def test_geodetic_to_ecef_known_points() -> None:
    assert np.allclose(g.geodetic_to_ecef(0.0, 0.0, 0.0), [A, 0.0, 0.0], atol=1e-6)
    pole = g.geodetic_to_ecef(90.0, 0.0, 0.0)
    assert pole[2] == pytest.approx(A * (1 - g.EARTH_FLATTENING), abs=1e-6)
    mid = g.geodetic_to_ecef(45.0, 0.0, 0.0)  # WGS-84: x about 4517.59 km, z about 4487.35 km
    assert mid[0] / 1000 == pytest.approx(4517.59, abs=0.05)
    assert mid[2] / 1000 == pytest.approx(4487.35, abs=0.05)
    assert np.allclose(g.geodetic_to_ecef(0.0, 90.0, 100.0), [0.0, A + 100.0, 0.0], atol=1e-6)


def test_topocentric_overhead_and_horizon() -> None:
    site = g.geodetic_to_ecef(0.0, 0.0, 0.0)
    over = np.array([[A + 500e3, 0.0, 0.0]])
    el, az, rng = g.topocentric(over, site, 0.0, 0.0)
    assert el[0] == pytest.approx(90.0, abs=1e-9) and rng[0] == pytest.approx(500e3, abs=1e-6)
    east = np.array([[A, 1000e3, 0.0]])
    el, az, _ = g.topocentric(east, site, 0.0, 0.0)
    assert el[0] == pytest.approx(0.0, abs=1e-9) and az[0] == pytest.approx(90.0, abs=1e-9)
    north = np.array([[A, 0.0, 1000e3]])
    el, az, _ = g.topocentric(north, site, 0.0, 0.0)
    assert el[0] == pytest.approx(0.0, abs=1e-9) and az[0] % 360.0 == pytest.approx(0.0, abs=1e-9)
    below = np.array([[A - 1000e3, 0.0, 0.0]])
    assert g.topocentric(below, site, 0.0, 0.0)[0][0] == pytest.approx(-90.0, abs=1e-9)


# ---- shadow ------------------------------------------------------------------------------------

SUN = np.array([[g.ASTRONOMICAL_UNIT_M, 0.0, 0.0]])


@pytest.mark.parametrize(
    ("position_km", "lit"),
    [
        ((7000, 0, 0), True),  # sunward
        ((-7000, 0, 0), False),  # directly behind the Earth
        ((-7000, 6000, 0), False),  # behind, inside the cylinder (perpendicular 6000 < Re)
        ((-7000, 7000, 0), True),  # behind but outside the cylinder
        ((0, 7000, 0), True),  # on the terminator plane, outside the Earth
        ((0, 0, 7000), True),
    ],
)
def test_cylindrical_shadow(position_km: tuple[float, float, float], lit: bool) -> None:
    r = np.array([position_km]) * 1000.0
    nu = g.sun_visibility(r, SUN, "cylindrical")
    assert nu[0] == (1.0 if lit else 0.0)


def test_conical_shadow_has_umbra_penumbra_and_light() -> None:
    far = np.array([[-7000e3, 0.0, 0.0]])
    assert g.sun_visibility(far, SUN, "conical")[0] == 0.0  # umbra
    lit = np.array([[7000e3, 0.0, 0.0]])
    assert g.sun_visibility(lit, SUN, "conical")[0] == 1.0
    # walk across the shadow boundary: visibility rises monotonically from 0 to 1
    ys = np.linspace(5800e3, 7000e3, 400)
    r = np.column_stack([np.full_like(ys, -7000e3), ys, np.zeros_like(ys)])
    nu = g.sun_visibility(r, np.repeat(SUN, len(ys), axis=0), "conical")
    assert nu[0] == 0.0 and nu[-1] == 1.0 and np.all(np.diff(nu) >= -1e-12)
    assert 0.0 < nu[(nu > 0) & (nu < 1)].min() < 1.0  # a genuine penumbra exists


def test_conical_and_cylindrical_agree_far_from_the_edge() -> None:
    for pos in (
        (-7000e3, 0.0, 0.0),
        (7000e3, 0.0, 0.0),
        (0.0, 0.0, 9000e3),
        (-7000e3, 3000e3, 0.0),
    ):
        r = np.array([pos])
        assert g.sun_visibility(r, SUN, "conical")[0] == g.sun_visibility(r, SUN, "cylindrical")[0]


def test_penumbra_straddles_the_cylinder_edge() -> None:
    """The geometric cylinder edge lies between full light and umbra in the conical model."""
    edge = np.array([[-7000e3, A, 0.0]])
    assert 0.0 < g.sun_visibility(edge, SUN, "conical")[0] < 1.0


def test_annular_eclipse_beyond_the_umbra_tip() -> None:
    """Behind the umbra tip the Earth is smaller than the Sun: ratio 1 - (b/a)^2 on the axis."""
    x = -2.0e9  # well beyond the umbra tip (about 1.4e9 m)
    r = np.array([[x, 0.0, 0.0]])
    nu = g.sun_visibility(r, SUN, "conical")[0]
    dist_sun = g.ASTRONOMICAL_UNIT_M - x
    a = math.asin(g.SUN_RADIUS_M / dist_sun)
    b = math.asin(A / abs(x))
    assert nu == pytest.approx(1.0 - (b / a) ** 2, rel=1e-9)


def test_unknown_shadow_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="shadow"):
        g.sun_visibility(np.zeros((1, 3)), SUN, "spherical")
