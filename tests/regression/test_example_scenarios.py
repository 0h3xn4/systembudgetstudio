"""The example scenarios run, and their results obey simple physical and logical invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.scenario.run import run_scenario
from tests.perf_limits import LIMIT_S

ROOT = Path(__file__).resolve().parents[2] / "examples"


@pytest.mark.parametrize(
    ("example", "scenario"),
    [("cubesat_3u", "one_day"), ("microsat_150kg", "commissioning_day")],
)
def test_example_scenario_results(example: str, scenario: str) -> None:
    project = load_project(ROOT / example).project
    assert project is not None
    run = run_scenario(project, scenario)
    env = run.env
    # roughly 15 orbits of 95 minutes per day; a sun-synchronous-like orbit has eclipses
    assert 12 <= len(env.eclipses) <= 16
    assert 0.1 < env.eclipse_fraction < 0.45
    assert all(len(v.passes) >= 1 for v in env.sites.values())
    modes = {s.mode for s in run.timeline}
    assert modes <= set(project.modes)
    assert "downlink" in modes
    assert run.timeline[0].start_s == 0.0 and run.timeline[-1].end_s == 86400.0


def test_manual_segment_overrides_the_start_of_the_microsat_scenario() -> None:
    project = load_project(ROOT / "microsat_150kg").project
    assert project is not None
    run = run_scenario(project, "commissioning_day")
    assert (run.timeline[0].start_s, run.timeline[0].end_s, run.timeline[0].mode) == (
        0.0,
        1800.0,
        "safe",
    )


def test_cubesat_layering_charges_in_the_sun_and_runs_nominal_in_eclipse() -> None:
    project = load_project(ROOT / "cubesat_3u").project
    assert project is not None
    run = run_scenario(project, "one_day")
    for e in run.env.eclipses[:3]:
        midpoint = (e.start_s + e.end_s) / 2.0
        mode = next(s.mode for s in run.timeline if s.start_s <= midpoint < s.end_s)
        assert mode in ("nominal", "downlink", "imaging")  # eclipse rule, unless a pass overrides


@pytest.mark.perf
def test_stress_week_runs_within_the_performance_target() -> None:
    import time

    project = load_project(ROOT / "stress_200_units").project
    assert project is not None
    started = time.perf_counter()
    run = run_scenario(project, "stress_week")
    assert time.perf_counter() - started < LIMIT_S
    assert run.env.grid.count == 604801 and len(run.env.eclipses) > 90
    assert {s.mode for s in run.timeline} <= set(project.modes)
