"""Scenario timeline: default mode, rules in order, manual segments last (decision D-056)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from budget_core.environment.data import EnvironmentData, Pass, SiteDef, SiteVisibility, TimeGrid
from budget_core.environment.intervals import Interval
from budget_core.model import Scenario
from budget_core.scenario.timeline import TimelineSegment, build_timeline, mode_index_on_grid

START = datetime(2026, 1, 1, tzinfo=UTC)
D = 1000.0


def fake_env(
    eclipses: list[tuple[float, float]] | None = None,
    passes: dict[str, list[tuple[float, float]]] | None = None,
    duration: float = D,
) -> EnvironmentData:
    grid = TimeGrid(START, duration, 10.0)
    n = grid.count
    zero = np.zeros((n, 3))
    sites = {}
    for site_id, spans in (passes or {}).items():
        site = SiteDef(site_id, "ground_station", 0.0, 0.0, 0.0, 5.0)
        sites[site_id] = SiteVisibility(
            site,
            tuple(Pass(a, b, 45.0, (a + b) / 2) for a, b in spans),
            np.zeros(n),
            np.zeros(n),
            np.zeros(n),
        )
    return EnvironmentData(
        grid=grid,
        source="fake",
        shadow_model="cylindrical",
        position_m=zero,
        sun_direction=zero,
        sunlight_ratio=np.ones(n),
        eclipses=tuple(Interval(a, b) for a, b in (eclipses or [])),
        umbras=(),
        sites=sites,
    )


def scenario(**kw: Any) -> Scenario:
    base: dict[str, Any] = {
        "name": "S",
        "orbit": "o",
        "start_utc": "2026-01-01T00:00:00Z",
        "duration_s": D,
        "step_s": 10,
        "default_mode": "nominal",
    }
    return Scenario.model_validate({**base, **kw})


def spans(timeline: tuple[TimelineSegment, ...]) -> list[tuple[float, float, str]]:
    return [(s.start_s, s.end_s, s.mode) for s in timeline]


def test_default_only() -> None:
    assert spans(build_timeline(scenario(), fake_env())) == [(0.0, D, "nominal")]


def test_one_pass_splits_the_timeline() -> None:
    sc = scenario(sites=["gs"], rules=[{"kind": "during_pass", "site": "gs", "mode": "downlink"}])
    t = build_timeline(sc, fake_env(passes={"gs": [(200.0, 300.0)]}))
    assert spans(t) == [(0.0, 200.0, "nominal"), (200.0, 300.0, "downlink"), (300.0, D, "nominal")]


def test_lead_and_lag_extend_and_clip() -> None:
    sc = scenario(
        sites=["gs"],
        rules=[
            {"kind": "during_pass", "site": "gs", "mode": "downlink", "lead_s": 50, "lag_s": 25}
        ],
    )
    t = build_timeline(sc, fake_env(passes={"gs": [(20.0, 100.0), (900.0, 990.0)]}))
    assert spans(t) == [(0.0, 125.0, "downlink"), (125.0, 850.0, "nominal"), (850.0, D, "downlink")]


def test_later_rules_win_where_they_overlap() -> None:
    sc = scenario(
        sites=["a", "b"],
        rules=[
            {"kind": "during_pass", "site": "a", "mode": "imaging"},
            {"kind": "during_pass", "site": "b", "mode": "downlink"},
        ],
    )
    t = build_timeline(sc, fake_env(passes={"a": [(100.0, 400.0)], "b": [(300.0, 500.0)]}))
    assert spans(t) == [
        (0.0, 100.0, "nominal"),
        (100.0, 300.0, "imaging"),
        (300.0, 500.0, "downlink"),
        (500.0, D, "nominal"),
    ]


def test_eclipse_and_sunlight_rules_partition_the_scenario() -> None:
    sc = scenario(
        rules=[{"kind": "in_sunlight", "mode": "charging"}, {"kind": "in_eclipse", "mode": "safe"}]
    )
    t = build_timeline(sc, fake_env(eclipses=[(300.0, 450.0), (800.0, 900.0)]))
    assert spans(t) == [
        (0.0, 300.0, "charging"),
        (300.0, 450.0, "safe"),
        (450.0, 800.0, "charging"),
        (800.0, 900.0, "safe"),
        (900.0, D, "charging"),
    ]


def test_manual_segments_win_over_rules() -> None:
    sc = scenario(
        sites=["gs"],
        rules=[{"kind": "during_pass", "site": "gs", "mode": "downlink"}],
        segments=[{"start_s": 250.0, "duration_s": 100.0, "mode": "safe"}],
    )
    t = build_timeline(sc, fake_env(passes={"gs": [(200.0, 400.0)]}))
    assert spans(t) == [
        (0.0, 200.0, "nominal"),
        (200.0, 250.0, "downlink"),
        (250.0, 350.0, "safe"),
        (350.0, 400.0, "downlink"),
        (400.0, D, "nominal"),
    ]


def test_adjacent_segments_with_the_same_mode_merge() -> None:
    sc = scenario(sites=["gs"], rules=[{"kind": "during_pass", "site": "gs", "mode": "downlink"}])
    t = build_timeline(sc, fake_env(passes={"gs": [(100.0, 200.0), (200.0, 300.0)]}))
    assert spans(t) == [(0.0, 100.0, "nominal"), (100.0, 300.0, "downlink"), (300.0, D, "nominal")]


def test_a_rule_that_matches_the_default_changes_nothing() -> None:
    sc = scenario(sites=["gs"], rules=[{"kind": "during_pass", "site": "gs", "mode": "nominal"}])
    assert spans(build_timeline(sc, fake_env(passes={"gs": [(100.0, 200.0)]}))) == [
        (0.0, D, "nominal")
    ]


def test_passes_outside_the_scenario_are_ignored_and_partial_ones_clipped() -> None:
    sc = scenario(sites=["gs"], rules=[{"kind": "during_pass", "site": "gs", "mode": "downlink"}])
    t = build_timeline(sc, fake_env(passes={"gs": [(-50.0, 40.0), (2000.0, 2100.0)]}))
    assert spans(t) == [(0.0, 40.0, "downlink"), (40.0, D, "nominal")]


def test_a_rule_for_a_site_without_results_is_an_error() -> None:
    sc = scenario(sites=["gs"], rules=[{"kind": "during_pass", "site": "gs", "mode": "x"}])
    with pytest.raises(ValueError, match="gs"):
        build_timeline(sc, fake_env(passes={}))


def test_mode_index_on_the_grid() -> None:
    sc = scenario(sites=["gs"], rules=[{"kind": "during_pass", "site": "gs", "mode": "downlink"}])
    t = build_timeline(sc, fake_env(passes={"gs": [(200.0, 300.0)]}))
    times = np.array([0.0, 199.9, 200.0, 250.0, 299.9, 300.0, 1000.0])
    idx = mode_index_on_grid(t, times, ["downlink", "nominal"])
    assert list(idx) == [1, 1, 0, 0, 0, 1, 1]  # segments are [start, end); the last includes D


times_ = st.floats(min_value=-100.0, max_value=1100.0, allow_nan=False)
interval = st.tuples(times_, st.floats(min_value=0.1, max_value=300.0)).map(
    lambda p: (p[0], p[0] + p[1])
)
modes = st.sampled_from(["m1", "m2", "m3"])


@given(
    passes=st.lists(interval, max_size=6),
    eclipses=st.lists(interval, max_size=4),
    rule_modes=st.lists(modes, min_size=3, max_size=3),
)
def test_timeline_always_covers_the_scenario_without_gaps_or_overlaps(
    passes: list[tuple[float, float]], eclipses: list[tuple[float, float]], rule_modes: list[str]
) -> None:
    # eclipse intervals in a real environment never overlap each other: normalise
    merged: list[tuple[float, float]] = []
    for a, b in sorted(eclipses):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    sc = scenario(
        sites=["gs"],
        rules=[
            {"kind": "during_pass", "site": "gs", "mode": rule_modes[0]},
            {"kind": "in_eclipse", "mode": rule_modes[1]},
            {"kind": "in_sunlight", "mode": rule_modes[2]},
        ],
    )
    t = build_timeline(sc, fake_env(eclipses=merged, passes={"gs": sorted(passes)}))
    assert t[0].start_s == 0.0 and t[-1].end_s == D
    for first, second in zip(t, t[1:], strict=False):
        assert first.end_s == second.start_s and first.mode != second.mode
    assert all(s.end_s > s.start_s for s in t)
