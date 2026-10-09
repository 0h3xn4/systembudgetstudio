"""Performance target (spec): a one-week, 1 s, 200-unit scenario, environment plus power budget,
in under 10 s."""

from __future__ import annotations

import time
from dataclasses import replace

import pytest

from budget_core.examples import _config, _power_system, _stress
from budget_core.power.time_domain import time_domain_budget
from budget_core.scenario.run import run_scenario

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
    assert elapsed < 10.0, f"took {elapsed:.1f} s"
