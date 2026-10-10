"""The power budget must not depend on the solver step (audit round N1).

The battery is integrated on the scenario grid plus every eclipse edge and mode-segment edge, so a
coarse step cannot average a discharge away. Numbers are invented and worked out by hand.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from budget_core.environment.data import EnvironmentData
from budget_core.environment.intervals import Interval, merge_intervals
from budget_core.power.time_domain import (
    DOD_EXCEEDED,
    _exceeding,
    time_domain_budget,
)
from tests.power_helpers import power_system, sv, synthetic_env, synthetic_run, td_project

PERIOD = 6000.0
# 1750 s in shadow at 40 W = 19.4444 Wh of a 100 Wh pack; the edges fall inside coarse steps
ECLIPSE = (3100.0, 4850.0)
EXPECTED_DOD = 40.0 * 1750.0 / 3600.0 / 100.0


def solve(env: EnvironmentData, **kw: object):  # type: ignore[no-untyped-def]
    system = kw.pop("system", None)
    return time_domain_budget(td_project(system=system), synthetic_run(env), **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize("step", [10.0, 50.0, 100.0, 300.0, 600.0, 1200.0])
def test_maximum_depth_of_discharge_does_not_depend_on_the_step(step: float) -> None:
    result = solve(synthetic_env(PERIOD, step, [ECLIPSE]))
    bol = result.case("bol")
    assert bol.summary.maximum_dod_ratio == pytest.approx(EXPECTED_DOD, abs=1e-9)
    assert bol.summary.minimum_soc_ratio == pytest.approx(1.0 - EXPECTED_DOD, abs=1e-9)


@pytest.mark.parametrize("step", [10.0, 300.0, 1200.0])
def test_dod_violation_is_found_at_any_step(step: float) -> None:
    system = power_system()
    battery = system.battery.model_copy(update={"max_dod_ratio": {"eol": sv(0.15)}})
    system = system.model_copy(update={"battery": battery})
    result = solve(synthetic_env(PERIOD, step, [ECLIPSE]), system=system)
    found = [v for v in result.case("bol").violations if v.code == DOD_EXCEEDED]
    assert len(found) == 1
    # 15 Wh at 40 W = 1350 s after the eclipse starts
    assert found[0].start_s == pytest.approx(ECLIPSE[0] + 1350.0, abs=1e-6)
    assert found[0].extreme == pytest.approx(EXPECTED_DOD, abs=1e-9)


@pytest.mark.parametrize("step", [10.0, 300.0, 1200.0])
def test_orbit_energy_does_not_depend_on_the_step(step: float) -> None:
    result = solve(synthetic_env(PERIOD, step, [ECLIPSE]))
    bol = result.case("bol")
    assert bol.summary.generated_wh == pytest.approx((PERIOD - 1750.0) * 100.0 / 3600.0)
    assert bol.balances[0].eclipse_s == pytest.approx(1750.0)


def test_reported_series_stay_on_the_scenario_grid() -> None:
    result = solve(synthetic_env(PERIOD, 600.0, [ECLIPSE]))
    bol = result.case("bol")
    assert len(result.edges_s) == 11
    assert bol.energy_wh is not None and len(bol.energy_wh) == 11
    assert bol.generation_w is not None and len(bol.generation_w) == 10
    assert bol.unmet_w is not None and len(bol.unmet_w) == 10
    # the stored energy at a grid edge is exact: 40 W for the 1100 s of shadow before 4200 s
    edge = list(result.edges_s).index(4200.0)
    assert bol.energy_wh[edge] == pytest.approx(100.0 - 40.0 * 1100.0 / 3600.0)


def test_overlapping_eclipses_count_once() -> None:
    env = synthetic_env(PERIOD, 10.0, [(3000.0, 4800.0)])
    env = replace(env, eclipses=(Interval(3000.0, 4800.0), Interval(4000.0, 5000.0)))
    bol = solve(env).case("bol")
    assert bol.balances[0].eclipse_s == pytest.approx(2000.0)
    assert bol.summary.generated_wh == pytest.approx((PERIOD - 2000.0) * 100.0 / 3600.0)


def test_merge_intervals_sorts_and_joins() -> None:
    merged = merge_intervals(
        [Interval(50.0, 60.0), Interval(0.0, 10.0), Interval(5.0, 20.0), Interval(20.0, 30.0)]
    )
    assert [(m.start_s, m.end_s) for m in merged] == [(0.0, 30.0), (50.0, 60.0)]
    assert merge_intervals([]) == []


def test_soft_shadow_energy_is_the_trapezoid_integral() -> None:
    env = synthetic_env(300.0, 100.0)
    env = replace(
        env,
        sunlight_ratio=np.array([1.0, 1.0, 0.5, 0.0]),
        eclipses=(Interval(100.0, 300.0),),
    )
    gen = solve(env).case("bol").summary.generated_wh
    # (1.0 * 100 + 0.75 * 100 + 0.25 * 100) s * 100 W
    assert gen == pytest.approx(200.0 * 100.0 / 3600.0)


def test_a_limit_met_exactly_is_not_a_violation() -> None:
    edges = np.array([0.0, 10.0, 20.0])
    just_over = np.array([0.0, 0.2 + 1e-13, 0.2])
    assert _exceeding(edges, just_over, 0.2) == []
    assert len(_exceeding(edges, np.array([0.0, 0.2 + 1e-6, 0.2]), 0.2)) == 1
