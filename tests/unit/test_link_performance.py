"""Performance target: one week at 1 s, 200 units, two links with their pass series, under 10 s."""

from __future__ import annotations

import time
from dataclasses import replace

import pytest

from budget_core.examples import _microsat_link_tables, _microsat_links, _stress
from budget_core.link.evaluate import link_pass_series
from budget_core.scenario.run import run_scenario
from tests.perf_limits import LIMIT_S, TARGET_S

pytestmark = pytest.mark.perf


def test_one_week_at_one_second_with_two_links() -> None:
    project = _stress()
    ebn0, attenuation = _microsat_link_tables()
    project = replace(
        project,
        links=_microsat_links(),
        config=replace(project.config, ebn0_table=ebn0, attenuation_table=attenuation),
    )
    started = time.perf_counter()
    run = run_scenario(project, "stress_week")
    result = link_pass_series(project, run)
    elapsed = time.perf_counter() - started
    assert [s.link_id for s in result.series] == ["sband_down", "xband_down"]
    assert all(s.volume_bits is not None and len(s.passes) > 10 for s in result.series)
    assert elapsed < LIMIT_S, f"took {elapsed:.1f} s; the target is {TARGET_S:.0f} s"
