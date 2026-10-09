"""Sun direction in the body frame for the supported pointing modes (decision D-064).

`sun`: the Sun is at a fixed direction in the body frame (perfect pointing).
`nadir`: the body frame equals the local orbital frame: +Z to the Earth's centre, +X along the
velocity (for a circular orbit), +Y opposite the orbit normal. Both are idealisations (DV-P4).
"""

from __future__ import annotations

from typing import Any

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]


def orbital_axes(position_m: NDArray, times_s: NDArray) -> tuple[NDArray, NDArray, NDArray]:
    """Unit axes (x along track, y opposite the orbit normal, z nadir) of the local orbital frame
    at every sample, with the velocity taken from the positions by central differences."""
    r = np.asarray(position_m, dtype=np.float64)
    if len(r) < 2:
        raise ValueError("at least two samples are needed to derive the velocity")
    v = np.gradient(r, np.asarray(times_s, dtype=np.float64), axis=0)
    z = -r / np.linalg.norm(r, axis=1, keepdims=True)
    h = np.cross(r, v)
    h /= np.linalg.norm(h, axis=1, keepdims=True)
    y = -h
    x = np.cross(y, z)
    return x, y, z


def sun_in_orbital_frame(sun_direction: NDArray, position_m: NDArray, times_s: NDArray) -> NDArray:
    """Sun direction as seen in the nadir-pointing body frame, shape (N, 3)."""
    x, y, z = orbital_axes(position_m, times_s)
    s = np.asarray(sun_direction, dtype=np.float64)
    return np.stack([np.sum(s * x, axis=1), np.sum(s * y, axis=1), np.sum(s * z, axis=1)], axis=1)
