"""Solar array model: pure functions over NumPy arrays (equations TDP-ARRAY and friends).

    P = E * sum_faces( N_cells * A_cell ) * eta_ref * k_T * (1 - l_pack) * (1 - l_harness)
          * k_age * lit * max(0, cos(theta_face))

No state, no I/O. Every argument is in the unit its name says.
"""

from __future__ import annotations

from typing import Any

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]


def temperature_factor(
    cell_temperature_k: float, reference_temperature_k: float, coeff_perk: float
) -> float:
    """TDP-TEMP: efficiency relative to the reference temperature, never below zero."""
    return max(0.0, 1.0 + coeff_perk * (cell_temperature_k - reference_temperature_k))


def degradation_factor(annual_degradation_ratio: float, years: float) -> float:
    """TDP-AGE: remaining output fraction after `years`, compounding yearly."""
    if not 0.0 <= annual_degradation_ratio < 1.0 or years < 0.0:
        raise ValueError("annual degradation must be in [0, 1) and years not negative")
    return float((1.0 - annual_degradation_ratio) ** years)


def face_cosines(normals_body: NDArray, sun_body: NDArray) -> NDArray:
    """TDP-COS: cosine of the sun incidence angle per step and face, zero on the back side.

    normals_body: (F, 3) outward normals (need not be unit length); sun_body: (N, 3) directions
    to the Sun in the body frame (need not be unit length). Returns (N, F)."""
    n = np.asarray(normals_body, dtype=np.float64)
    s = np.asarray(sun_body, dtype=np.float64)
    n = n / np.linalg.norm(n, axis=1, keepdims=True)
    norm = np.linalg.norm(s, axis=1, keepdims=True)
    s = s / np.where(norm > 0.0, norm, 1.0)
    return np.asarray(np.maximum(s @ n.T, 0.0), dtype=np.float64)


def array_power_w(
    *,
    irradiance_wm2: float,
    cell_counts: NDArray,
    cell_area_m2: float,
    efficiency_ratio: float,
    temperature_factor_ratio: float,
    packing_loss_ratio: float,
    harness_loss_ratio: float,
    age_factor_ratio: float,
    cosines: NDArray,
    lit_ratio: NDArray,
) -> NDArray:
    """TDP-ARRAY: electrical power at the array output per step, shape (N,).

    cell_counts: (F,) cells per face; cosines: (N, F); lit_ratio: (N,) share of the step in
    sunlight."""
    per_face_w = (
        irradiance_wm2
        * np.asarray(cell_counts, dtype=np.float64)
        * cell_area_m2
        * efficiency_ratio
        * temperature_factor_ratio
        * (1.0 - packing_loss_ratio)
        * (1.0 - harness_loss_ratio)
        * age_factor_ratio
    )
    return np.asarray((cosines @ per_face_w) * lit_ratio, dtype=np.float64)
