"""Orbit windows: one window per completed revolution, found from the positions alone.

Works for every environment source (it needs no orbital elements) and for equatorial and polar
orbits. Window k runs from the k-th to the (k+1)-th passage of the starting angle in the orbit
plane; the first window starts at the first sample. A partial last revolution is not a window.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]


def orbit_windows(times_s: NDArray, position_m: NDArray) -> list[tuple[float, float]]:
    r = np.asarray(position_m, dtype=np.float64)
    t = np.asarray(times_s, dtype=np.float64)
    if len(r) < 3:
        return []
    r0 = r[0] / np.linalg.norm(r[0])
    cross = np.cross(r0, r)
    sines = np.linalg.norm(cross, axis=1) / np.linalg.norm(r, axis=1)
    moved = np.nonzero(sines > math.sin(math.radians(10.0)))[0]
    if len(moved) == 0:
        return []
    normal = cross[moved[0]] / np.linalg.norm(cross[moved[0]])
    ey = np.cross(normal, r0)
    angle = np.unwrap(np.arctan2(r @ ey, r @ r0))
    revolutions = int(math.floor(angle[-1] / (2.0 * math.pi) + 1e-9))
    marks = [float(t[0])]
    for k in range(1, revolutions + 1):
        target = 2.0 * math.pi * k
        j = int(np.searchsorted(angle, target - 1e-9, side="left"))
        if j <= 0 or j >= len(angle):
            break
        a0, a1 = angle[j - 1], angle[j]
        fraction = 1.0 if a1 == a0 else min(max((target - a0) / (a1 - a0), 0.0), 1.0)
        marks.append(float(t[j - 1] + fraction * (t[j] - t[j - 1])))
    return list(zip(marks[:-1], marks[1:], strict=True))
