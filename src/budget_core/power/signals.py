"""Step-function helpers: exact averages of piecewise-constant signals over solver steps.

The time-domain solver works on steps [edges[i], edges[i+1]). Eclipses and mode segments change
at arbitrary instants, so their effect on a step is the exact overlap, not a sample (D-063).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]


def step_edges(duration_s: float, step_s: float) -> NDArray:
    """Edges of the solver steps: multiples of `step_s`, closed by the scenario end."""
    count = int(duration_s // step_s)
    edges = np.arange(count + 1, dtype=np.float64) * step_s
    if duration_s - edges[-1] > 1e-9:
        edges = np.append(edges, duration_s)
    else:
        edges[-1] = duration_s
    return edges


def integral_of_steps(
    starts: Sequence[float], ends: Sequence[float], values: Sequence[float], times: NDArray
) -> NDArray:
    """Integral from 0 to each time of a signal that equals `values[k]` on [starts[k], ends[k])
    and 0 elsewhere. The intervals must be sorted and must not overlap."""
    if len(starts) == 0:
        return np.zeros_like(times, dtype=np.float64)
    s = np.asarray(starts, dtype=np.float64)
    e = np.asarray(ends, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    areas = v * (e - s)
    before = np.concatenate(([0.0], np.cumsum(areas)))[:-1]  # integral up to the start of k
    idx = np.searchsorted(s, times, side="right") - 1
    safe = np.clip(idx, 0, len(s) - 1)
    inside = np.clip(times - s[safe], 0.0, e[safe] - s[safe])
    result = before[safe] + v[safe] * inside
    return np.where(idx < 0, 0.0, result).astype(np.float64)


def step_means(
    starts: Sequence[float], ends: Sequence[float], values: Sequence[float], edges: NDArray
) -> NDArray:
    """Average of the step-function signal over each solver step."""
    cumulative = integral_of_steps(starts, ends, values, edges)
    return np.diff(cumulative) / np.diff(edges)
