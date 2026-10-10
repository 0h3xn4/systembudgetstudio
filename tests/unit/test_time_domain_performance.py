"""Performance target (spec): a one-week, 1 s, 200-unit scenario, environment plus power budget,
in under 10 s.

A wall-clock limit is only meaningful on the reference machine. Shared CI runners are slower and
noisy, so the hard limit is three times the target (a regression that matters, such as a
quadratic loop, is far above it); the measured time is printed, and the scaling test checks that
the cost grows with the number of steps and not faster."""

from __future__ import annotations

import time
from dataclasses import replace

import pytest

from budget_core.examples import _config, _power_system, _stress
from budget_core.power.time_domain import time_domain_budget
from budget_core.scenario.run import run_scenario
from tests.perf_limits import LIMIT_S, TARGET_S

pytestmark = pytest.mark.perf


def test_one_week_at_one_second_with_two_cases() -> None:
    project = _stress()
    project = replace(
        project,
        config=_config(
            ["main", "aux"], _power_system(True, ["launch", "eol"], {"imaging": "nadir"}), True
        ),
        scenarios={
            "stress_week": project.scenarios["stress_week"].model_copy(
                update={"mission_phase": "eol"}
            )
        },
    )
    started = time.perf_counter()
    run = run_scenario(project, "stress_week")
    result = time_domain_budget(project, run)
    elapsed = time.perf_counter() - started
    assert result.steps == 604800
    assert {c.case for c in result.cases} == {"bol", "eol"}
    assert all(c.energy_wh is not None for c in result.cases)
    print(f"week at 1 s, 200 units: {elapsed:.1f} s (target 10 s)")
    assert elapsed < LIMIT_S, f"took {elapsed:.1f} s; the target is {TARGET_S:.0f} s"


def _time_budget(duration_s: float) -> float:
    project = _stress()
    project = replace(
        project,
        config=_config(
            ["main", "aux"], _power_system(True, ["launch", "eol"], {"imaging": "nadir"}), True
        ),
        scenarios={
            "stress_week": project.scenarios["stress_week"].model_copy(
                update={"mission_phase": "eol", "duration_s": duration_s}
            )
        },
    )
    run = run_scenario(project, "stress_week")
    started = time.perf_counter()
    time_domain_budget(project, run)
    return time.perf_counter() - started


def test_power_budget_cost_grows_no_faster_than_the_number_of_steps() -> None:
    _time_budget(3600.0)  # warm-up (imports, caches)
    short = min(_time_budget(86400.0) for _ in range(2))
    long = min(_time_budget(8 * 86400.0) for _ in range(2))
    # 8 times the steps: linear is 8x; allow 3x slack for cache effects and noise, not 64x
    assert long < 24.0 * max(short, 1e-3), f"{short:.2f} s for 1 day, {long:.2f} s for 8 days"
