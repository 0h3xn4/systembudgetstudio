"""Sun, sidereal time, shadow and ground geometry on NumPy arrays (SI units, no I/O).

Equations (named in budget_core.equations): ENV-SUN (Astronomical Almanac low-precision Sun),
ENV-GMST (IAU-82 GMST, Vallado), ENV-SHADOW-CYL, ENV-SHADOW-CON (Montenbruck and Gill,
Satellite Orbits, section 3.4.2), ENV-GEODETIC (WGS-84 ellipsoid), ENV-TOPO (local ENU frame).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sgp4.api import jday

from budget_core.environment import constants as c

NDArray = np.ndarray[Any, np.dtype[np.float64]]

EARTH_RADIUS_M = c.EARTH_RADIUS.value
EARTH_MU_M3S2 = c.EARTH_MU.value
EARTH_FLATTENING = c.EARTH_FLATTENING.value
SUN_RADIUS_M = c.SUN_RADIUS.value
ASTRONOMICAL_UNIT_M = c.ASTRONOMICAL_UNIT.value


def julian_date_parts(moment: datetime) -> tuple[float, float]:
    """(whole, fraction) Julian date of a UTC time, as the sgp4 library wants it."""
    utc = moment.astimezone(UTC)
    seconds = utc.second + utc.microsecond * 1e-6
    whole, fraction = jday(utc.year, utc.month, utc.day, utc.hour, utc.minute, seconds)
    return float(whole), float(fraction)


def sun_direction_and_distance(jd: NDArray) -> tuple[NDArray, NDArray]:
    """ENV-SUN: unit vector to the Sun (mean equator and equinox of date, close to TEME) and its
    distance in metres. Accuracy about 0.01 degree (Astronomical Almanac, low precision)."""
    n = jd - 2451545.0
    mean_longitude = np.radians(280.460 + 0.9856474 * n)
    anomaly = np.radians(357.528 + 0.9856003 * n)
    longitude = (
        mean_longitude
        + np.radians(1.915) * np.sin(anomaly)
        + np.radians(0.020) * np.sin(2.0 * anomaly)
    )
    obliquity = np.radians(23.439 - 0.0000004 * n)
    direction = np.column_stack(
        [
            np.cos(longitude),
            np.cos(obliquity) * np.sin(longitude),
            np.sin(obliquity) * np.sin(longitude),
        ]
    )
    distance_au = 1.00014 - 0.01671 * np.cos(anomaly) - 0.00014 * np.cos(2.0 * anomaly)
    return direction, distance_au * ASTRONOMICAL_UNIT_M


def gmst_rad(jd_ut1: NDArray) -> NDArray:
    """ENV-GMST: Greenwich mean sidereal time in radians, IAU-82 (Vallado)."""
    t = (jd_ut1 - 2451545.0) / 36525.0
    seconds = (
        67310.54841 + (876600.0 * 3600.0 + 8640184.812866) * t + 0.093104 * t**2 - 6.2e-6 * t**3
    )
    return np.asarray(np.mod(seconds, 86400.0) * (2.0 * math.pi / 86400.0))


def eci_to_ecef(r: NDArray, gmst: NDArray) -> NDArray:
    """Rotate TEME vectors about the polar axis by GMST (no polar motion, decision D-053)."""
    cos_t, sin_t = np.cos(gmst), np.sin(gmst)
    x = r[:, 0] * cos_t + r[:, 1] * sin_t
    y = -r[:, 0] * sin_t + r[:, 1] * cos_t
    return np.column_stack([x, y, r[:, 2]])


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> NDArray:
    """ENV-GEODETIC: WGS-84 geodetic position to Earth-fixed Cartesian metres."""
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    e2 = EARTH_FLATTENING * (2.0 - EARTH_FLATTENING)
    n = EARTH_RADIUS_M / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
    return np.array(
        [
            (n + alt_m) * math.cos(lat) * math.cos(lon),
            (n + alt_m) * math.cos(lat) * math.sin(lon),
            (n * (1.0 - e2) + alt_m) * math.sin(lat),
        ]
    )


def topocentric(
    r_ecef: NDArray, site_ecef: NDArray, lat_deg: float, lon_deg: float
) -> tuple[NDArray, NDArray, NDArray]:
    """ENV-TOPO: elevation (deg), azimuth (deg from north through east) and range (m) of
    Earth-fixed positions seen from a site (geodetic up, no refraction)."""
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    east = np.array([-math.sin(lon), math.cos(lon), 0.0])
    north = np.array(
        [-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)]
    )
    up = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
    rel = r_ecef - site_ecef
    rng = np.linalg.norm(rel, axis=1)
    e, n, u = rel @ east, rel @ north, rel @ up
    elevation = np.degrees(np.arcsin(np.clip(u / rng, -1.0, 1.0)))
    azimuth = np.mod(np.degrees(np.arctan2(e, n)), 360.0)
    return elevation, azimuth, rng


def sun_visibility(r: NDArray, sun: NDArray, model: str = "cylindrical") -> NDArray:
    """Fraction of the Sun's disk visible from `r` (1 lit, 0 umbra); positions and the Earth to
    Sun vectors in metres. `cylindrical` gives 0 or 1 (ENV-SHADOW-CYL); `conical` includes
    penumbra and annular geometry (ENV-SHADOW-CON)."""
    if model == "cylindrical":
        direction = sun / np.linalg.norm(sun, axis=1, keepdims=True)
        along = np.sum(r * direction, axis=1)
        perpendicular = np.linalg.norm(r - along[:, None] * direction, axis=1)
        return np.where((along < 0.0) & (perpendicular < EARTH_RADIUS_M), 0.0, 1.0)
    if model != "conical":
        raise ValueError("shadow model must be 'cylindrical' or 'conical'")

    to_sun = sun - r
    dist_sun = np.linalg.norm(to_sun, axis=1)
    dist_earth = np.linalg.norm(r, axis=1)
    a = np.arcsin(np.clip(SUN_RADIUS_M / dist_sun, -1.0, 1.0))  # apparent Sun radius
    b = np.arcsin(np.clip(EARTH_RADIUS_M / dist_earth, -1.0, 1.0))  # apparent Earth radius
    cos_c = -np.sum(r * to_sun, axis=1) / (dist_earth * dist_sun)
    sep = np.arccos(np.clip(cos_c, -1.0, 1.0))  # angular separation of the two disk centres

    with np.errstate(divide="ignore", invalid="ignore"):
        x = (sep**2 + a**2 - b**2) / (2.0 * sep)
        y = np.sqrt(np.maximum(a**2 - x**2, 0.0))
        area = (
            a**2 * np.arccos(np.clip(x / a, -1.0, 1.0))
            + b**2 * np.arccos(np.clip((sep - x) / b, -1.0, 1.0))
            - sep * y
        )
        partial = 1.0 - area / (math.pi * a**2)
    annular = 1.0 - (b / a) ** 2
    nu = np.where(sep >= a + b, 1.0, partial)
    nu = np.where((sep <= a - b) & (a > b), annular, nu)
    nu = np.where((sep <= b - a) & (b > a), 0.0, nu)
    return np.asarray(np.clip(nu, 0.0, 1.0))
