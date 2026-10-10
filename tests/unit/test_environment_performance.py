"""Performance target (spec): a one-week scenario at 1 s resolution in well under 10 s."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from budget_core.environment.data import SiteDef, TimeGrid
from budget_core.environment.elements import ElementsPropagator
from budget_core.model import Elements, Orbit
from tests.perf_limits import LIMIT_S, TARGET_S

pytestmark = pytest.mark.perf


def test_one_week_at_one_second_with_three_sites() -> None:
    orbit = Orbit(
        name="o",
        elements=Elements(
            epoch_utc="2026-01-01T00:00:00Z",
            semi_major_axis_m=6878137.0,
            eccentricity_ratio=0.001,
            inclination_deg=97.5,
            raan_deg=100.0,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=0.0,
        ),
    )
    sites = [
        SiteDef("a", "ground_station", 60.0, 10.0, 100.0, 5.0),
        SiteDef("b", "ground_station", -45.0, 170.0, 0.0, 5.0),
        SiteDef("c", "target", 10.0, -60.0, 0.0, 30.0),
    ]
    grid = TimeGrid(datetime(2026, 1, 1, tzinfo=UTC), 7 * 86400.0, 1.0)
    started = time.perf_counter()
    env = ElementsPropagator(orbit).compute(grid, sites, "conical")
    elapsed = time.perf_counter() - started
    assert env.position_m.shape == (604801, 3)
    assert len(env.eclipses) > 90
    assert {k: len(v.passes) > 10 for k, v in env.sites.items() if k != "c"} == {
        "a": True,
        "b": True,
    }
    assert len(env.sites["c"].passes) >= 1  # 30 degree minimum elevation: few passes
    assert elapsed < LIMIT_S, f"took {elapsed:.1f} s; the target is {TARGET_S:.0f} s"
