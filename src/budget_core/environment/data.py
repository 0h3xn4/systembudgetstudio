"""Environment results and the interface every environment source implements."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

import numpy as np

from budget_core.environment.intervals import Interval

NDArray = np.ndarray[Any, np.dtype[np.float64]]


@dataclass(frozen=True)
class TimeGrid:
    """Uniform time grid: `start` (UTC), seconds from the start, fixed step."""

    start: datetime
    duration_s: float
    step_s: float

    @property
    def count(self) -> int:
        return int(self.duration_s // self.step_s) + 1

    @property
    def times_s(self) -> NDArray:
        return np.arange(self.count, dtype=np.float64) * self.step_s


@dataclass(frozen=True)
class SiteDef:
    site_id: str
    kind: Literal["ground_station", "target"]
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    min_elevation_deg: float


@dataclass(frozen=True)
class Pass:
    aos_s: float
    los_s: float
    max_elevation_deg: float
    time_of_max_s: float
    partial_start: bool = False  # the pass began before the scenario start
    partial_end: bool = False  # the pass continues after the scenario end

    @property
    def duration_s(self) -> float:
        return self.los_s - self.aos_s


@dataclass(frozen=True, eq=False)
class SiteVisibility:
    site: SiteDef
    passes: tuple[Pass, ...]
    elevation_deg: NDArray  # on the scenario grid
    azimuth_deg: NDArray
    range_m: NDArray


@dataclass(frozen=True, eq=False)
class EnvironmentData:
    """Everything solvers need from an environment, independent of where it came from."""

    grid: TimeGrid
    source: str
    shadow_model: str
    position_m: NDArray  # (N, 3) inertial (TEME) on the scenario grid
    sun_direction: NDArray  # (N, 3) unit vectors
    sunlight_ratio: NDArray  # (N,) 1 lit, 0 umbra, between: penumbra
    eclipses: tuple[Interval, ...]  # sunlight ratio below 1
    umbras: tuple[Interval, ...]  # sunlight ratio 0
    sites: dict[str, SiteVisibility]

    @property
    def eclipse_fraction(self) -> float:
        total = self.grid.duration_s
        return sum(e.duration_s for e in self.eclipses) / total if total > 0 else 0.0


class PropagationError(Exception):
    """The orbit cannot be propagated (for example the orbit has decayed)."""


class Environment(Protocol):
    """One interface for every environment source (decision D-053 and spec architecture)."""

    name: str

    def compute(
        self, grid: TimeGrid, sites: Sequence[SiteDef], shadow_model: str
    ) -> EnvironmentData: ...
