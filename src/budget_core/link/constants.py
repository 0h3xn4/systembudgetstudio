"""Definitional constants of the link budget with their sources (decisions D-054, D-078).

Both are exact in the 2019 SI, defined values rather than measurements."""

from __future__ import annotations

import math

SPEED_OF_LIGHT_MS = 299_792_458.0
SPEED_OF_LIGHT_SOURCE = "SI 2019 (exact: the definition of the metre)"
BOLTZMANN_JK = 1.380649e-23
BOLTZMANN_SOURCE = "SI 2019 (exact defining constant)"
BOLTZMANN_DBW_HZ_K = 10.0 * math.log10(BOLTZMANN_JK)  # about -228.6 dBW/(Hz K)
EARTH_RADIUS_M = 6_378_137.0  # WGS 84; the same value as budget_core.environment.constants
EARTH_RADIUS_SOURCE = "WGS 84 equatorial radius (spherical Earth for pointing angles, DV-L2)"
