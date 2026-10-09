"""Definitional physical constants with their sources (decision D-054).

These define the Earth ellipsoid, the Sun and the astronomical unit. They are not project policy
numbers; margins, losses and standards tables stay in the project configuration files.
"""

from __future__ import annotations

from dataclasses import dataclass

from sgp4.earth_gravity import wgs84


@dataclass(frozen=True)
class Constant:
    name: str
    value: float
    unit: str
    source: str


# Taken from the sgp4 library's WGS-84 set so geometry and propagation use the same Earth.
EARTH_RADIUS = Constant(
    "Earth equatorial radius",
    wgs84.radiusearthkm * 1000.0,
    "m",
    "WGS 84 (NIMA TR8350.2), value as used by the sgp4 library",
)
EARTH_MU = Constant(
    "Earth gravitational parameter",
    wgs84.mu * 1.0e9,
    "m3/s2",
    "WGS 84 (NIMA TR8350.2), value as used by the sgp4 library",
)
EARTH_FLATTENING = Constant(
    "Earth flattening", 1.0 / 298.257223563, "ratio", "WGS 84 (NIMA TR8350.2) defining constant"
)
SUN_RADIUS = Constant(
    "Solar radius (nominal)", 695_700_000.0, "m", "IAU 2015 Resolution B3 (nominal solar radius)"
)
ASTRONOMICAL_UNIT = Constant("Astronomical unit", 149_597_870_700.0, "m", "IAU 2012 Resolution B2")

ALL = (EARTH_RADIUS, EARTH_MU, EARTH_FLATTENING, SUN_RADIUS, ASTRONOMICAL_UNIT)
