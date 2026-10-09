"""Decibel conversions on plain floats. Linear values must be positive.

Conventions: dB = 10 log10(power ratio); dBW is referenced to 1 W; dBm to 1 mW.
"""

from __future__ import annotations

import math


def _positive(x: float, what: str) -> float:
    if not x > 0.0:
        raise ValueError(f"{what} must be positive to convert to dB")
    return x


def ratio_to_db(ratio: float) -> float:
    return 10.0 * math.log10(_positive(ratio, "ratio"))


def db_to_ratio(db: float) -> float:
    return float(10.0 ** (db / 10.0))


def watt_to_dbw(power_w: float) -> float:
    return 10.0 * math.log10(_positive(power_w, "power"))


def dbw_to_watt(power_dbw: float) -> float:
    return float(10.0 ** (power_dbw / 10.0))


def watt_to_dbm(power_w: float) -> float:
    return 10.0 * math.log10(_positive(power_w, "power") * 1000.0)


def dbm_to_watt(power_dbm: float) -> float:
    return float(10.0 ** (power_dbm / 10.0)) / 1000.0


def dbw_to_dbm(power_dbw: float) -> float:
    return power_dbw + 30.0


def dbm_to_dbw(power_dbm: float) -> float:
    return power_dbm - 30.0
