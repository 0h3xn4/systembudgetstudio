import math

import numpy as np
import pytest

from budget_core.environment.intervals import Interval, bisect_edge, mask_to_intervals


def test_edges_are_reported_as_sample_pairs() -> None:
    t = np.arange(10.0)
    mask = np.array([0, 0, 1, 1, 0, 0, 1, 1, 1, 0], dtype=bool)
    spans = mask_to_intervals(t, mask)
    assert spans == [((1.0, 2.0), (3.0, 4.0)), ((5.0, 6.0), (8.0, 9.0))]


def test_intervals_touching_the_ends() -> None:
    t = np.arange(5.0)
    spans = mask_to_intervals(t, np.array([1, 1, 0, 1, 1], dtype=bool))
    assert spans == [(None, (1.0, 2.0)), ((2.0, 3.0), None)]


def test_all_true_and_all_false() -> None:
    t = np.arange(4.0)
    assert mask_to_intervals(t, np.ones(4, dtype=bool)) == [(None, None)]
    assert mask_to_intervals(t, np.zeros(4, dtype=bool)) == []


def test_bisect_edge_finds_the_crossing() -> None:
    edge = bisect_edge(lambda t: t > math.pi, 3.0, 4.0, tol=1e-9)
    assert edge == pytest.approx(math.pi, abs=1e-8)
    falling = bisect_edge(lambda t: t < math.e, 2.0, 3.0, tol=1e-9)
    assert falling == pytest.approx(math.e, abs=1e-8)


def test_bisect_edge_needs_a_bracket() -> None:
    with pytest.raises(ValueError):
        bisect_edge(lambda t: True, 0.0, 1.0)


def test_interval_duration() -> None:
    assert Interval(10.0, 25.5).duration_s == 15.5
