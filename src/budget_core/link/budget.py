"""Link budget equations: pure functions over floats or NumPy arrays (decibel units).

    EIRP = P_tx - L_line + G_tx                              (LNK-EIRP)
    L_fs = 20 log10(4 pi d f / c)                            (LNK-FSPL, free space)
    G/T  = G_rx - L_feed - 10 log10(T_sys)                   (LNK-GT)
    C/N0 = EIRP - L_fs - L_other + G/T - 10 log10(k)         (LNK-CN0)
    Eb/N0 = C/N0 - 10 log10(R_b)                             (LNK-EBN0)
    margin = Eb/N0 - Eb/N0_required                          (LNK-MARGIN)

L_other is the sum of the atmospheric, pointing, polarisation and implementation losses.
No state, no I/O.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from budget_core.link.constants import (
    BOLTZMANN_DBW_HZ_K,
    EARTH_RADIUS_M,
    SPEED_OF_LIGHT_MS,
)

Number = float | np.ndarray[Any, np.dtype[np.float64]]


def watt_to_dbw(power_w: float) -> float:
    if power_w <= 0.0:
        raise ValueError("power must be positive to convert to dBW")
    return 10.0 * math.log10(power_w)


def eirp_dbw(power_w: float, line_loss_db: float, gain_dbi: Number) -> Number:
    """LNK-EIRP."""
    return watt_to_dbw(power_w) - line_loss_db + gain_dbi


def free_space_path_loss_db(range_m: Number, freq_hz: float) -> Number:
    """LNK-FSPL: spreading loss between isotropic antennas."""
    if freq_hz <= 0.0:
        raise ValueError("the frequency must be positive")
    return 20.0 * np.log10(4.0 * math.pi * np.asarray(range_m) * freq_hz / SPEED_OF_LIGHT_MS)


def g_over_t_dbk(
    gain_dbi: Number, feed_loss_db: float, system_noise_temperature_k: float
) -> Number:
    """LNK-GT: receiver figure of merit, referenced to the antenna output as given."""
    if system_noise_temperature_k <= 0.0:
        raise ValueError("the system noise temperature must be positive")
    return gain_dbi - feed_loss_db - 10.0 * math.log10(system_noise_temperature_k)


def cn0_dbhz(
    eirp: Number, path_loss_db: Number, other_losses_db: Number, g_over_t: Number
) -> Number:
    """LNK-CN0: carrier to noise density ratio."""
    return eirp - path_loss_db - other_losses_db + g_over_t - BOLTZMANN_DBW_HZ_K


def ebn0_db(cn0: Number, data_rate_bps: float) -> Number:
    """LNK-EBN0."""
    if data_rate_bps <= 0.0:
        raise ValueError("the data rate must be positive")
    return cn0 - 10.0 * math.log10(data_rate_bps)


def margin_db(ebn0: Number, required_ebn0_db: float) -> Number:
    """LNK-MARGIN: positive means the link closes with room to spare."""
    return ebn0 - required_ebn0_db


def max_rate_for_margin_bps(
    cn0: Number, required_ebn0_db: float, required_margin_db: float
) -> Number:
    """The data rate at which the margin equals the required margin: C/N0 - Eb/N0_req - margin."""
    return 10.0 ** ((np.asarray(cn0) - required_ebn0_db - required_margin_db) / 10.0)


def spacecraft_range_for(elevation_deg: Number, range_m: Number) -> Number:
    """Distance of the spacecraft from the Earth's centre for a slant range and elevation
    (spherical Earth): r^2 = R^2 + d^2 + 2 R d sin(el)."""
    el = np.radians(np.asarray(elevation_deg))
    d = np.asarray(range_m)
    return np.sqrt(EARTH_RADIUS_M**2 + d**2 + 2.0 * EARTH_RADIUS_M * d * np.sin(el))


def nadir_angle_deg(elevation_deg: Number, range_m: Number) -> Number:
    """Angle at the spacecraft between nadir and the line of sight to a ground site:
    sin(eta) = R cos(el) / r (law of sines in the centre-site-spacecraft triangle)."""
    r = spacecraft_range_for(elevation_deg, range_m)
    ratio = EARTH_RADIUS_M * np.cos(np.radians(np.asarray(elevation_deg))) / r
    return np.degrees(np.arcsin(np.clip(ratio, -1.0, 1.0)))


def interpolate_gain_dbi(
    angles_deg: list[float], gains_dbi: list[float], angle_deg: Number
) -> Number:
    """Linear interpolation in the pattern table; angles beyond the table use its end values."""
    return np.asarray(np.interp(np.asarray(angle_deg), angles_deg, gains_dbi), dtype=np.float64)


def interpolate_attenuation_db(
    elevations_deg: list[float], losses_db: list[float], elevation_deg: Number
) -> Number:
    """Atmospheric loss by elevation from table entries (sorted by elevation); one entry (or
    entries without elevation) give a constant."""
    if len(elevations_deg) == 1:
        return float(losses_db[0]) + 0.0 * np.asarray(elevation_deg)
    return np.asarray(
        np.interp(np.asarray(elevation_deg), elevations_deg, losses_db), dtype=np.float64
    )
