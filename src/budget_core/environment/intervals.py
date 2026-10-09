"""Interval helpers: turn sampled booleans into intervals and refine their edges by bisection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]
BoolArray = np.ndarray[Any, np.dtype[np.bool_]]
Bracket = tuple[float, float]  # (sample time before the change, sample time after it)


@dataclass(frozen=True)
class Interval:
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def mask_to_intervals(
    times: NDArray, mask: BoolArray
) -> list[tuple[Bracket | None, Bracket | None]]:
    """Runs of True in `mask`. Each run gives (start bracket, end bracket): the pair of sample
    times between which the mask changed, or None where the run touches the first or last sample."""
    runs: list[tuple[Bracket | None, Bracket | None]] = []
    n = len(mask)
    i = 0
    while i < n:
        if not mask[i]:
            i += 1
            continue
        start: Bracket | None = None if i == 0 else (float(times[i - 1]), float(times[i]))
        j = i
        while j + 1 < n and mask[j + 1]:
            j += 1
        end: Bracket | None = None if j == n - 1 else (float(times[j]), float(times[j + 1]))
        runs.append((start, end))
        i = j + 1
    return runs


def bisect_edge(
    predicate: Callable[[float], bool], lo: float, hi: float, tol: float = 1e-3
) -> float:
    """Time of the change of `predicate` between lo and hi (it must differ at the two ends)."""
    at_lo = predicate(lo)
    if at_lo == predicate(hi):
        raise ValueError("the predicate must differ at the two ends of the bracket")
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if predicate(mid) == at_lo:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
