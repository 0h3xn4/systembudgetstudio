"""Plot helpers shared by the GUI widget and the report renderer."""

from __future__ import annotations

import numpy as np
import pytest

from budget_core.plots.spec import Series, decimate, nice_ticks, plot_points, step_points, time_axis


def test_decimate_keeps_a_single_spike() -> None:
    x = np.arange(100_000, dtype=float)
    y = np.zeros_like(x)
    y[54_321] = 7.0
    y[12_345] = -3.0
    px, py = decimate(x, y, 500)
    assert len(px) <= 1000
    assert py.max() == 7.0 and py.min() == -3.0
    assert (np.diff(px) > 0).all()


def test_decimate_leaves_short_series_alone() -> None:
    x, y = np.arange(10.0), np.arange(10.0)
    assert decimate(x, y, 100)[0] is x


def test_step_points_hold_values_until_the_next_x() -> None:
    series = Series("s", np.array([0.0, 10.0, 20.0]), np.array([1.0, 2.0, 3.0]), step=True)
    px, py = step_points(series, 30.0)
    assert list(px) == [0.0, 10.0, 10.0, 20.0, 20.0, 30.0]
    assert list(py) == [1.0, 1.0, 2.0, 2.0, 3.0, 3.0]


def test_plot_points_zoomed_in_is_the_exact_step() -> None:
    x = np.arange(0.0, 1000.0, 10.0)
    y = np.where(x < 500, 1.0, 5.0)
    series = Series("s", x, y, step=True, x_end=1000.0)
    px, py = plot_points(series, 480.0, 520.0, 1000.0, buckets=400)
    assert py.max() == 5.0 and py.min() == 1.0
    assert px[0] <= 480.0 and px[-1] >= 520.0


def test_plot_points_zoomed_out_is_an_envelope_that_keeps_the_peak() -> None:
    x = np.arange(0.0, 200_000.0)
    y = np.sin(x / 5000.0)
    y[77_777] = 9.0
    series = Series("s", x, y, step=True, x_end=200_000.0)
    px, py = plot_points(series, 0.0, 200_000.0, 200_000.0, buckets=300)
    assert len(px) <= 600 and py.max() == 9.0


@pytest.mark.parametrize(
    ("lo", "hi", "expected"),
    [
        (0.0, 100.0, [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]),
        (0.0, 1.0, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]),
    ],
)
def test_nice_ticks(lo: float, hi: float, expected: list[float]) -> None:
    assert nice_ticks(lo, hi, 5) == pytest.approx(expected)


def test_nice_ticks_cover_a_negative_range() -> None:
    ticks = nice_ticks(-130.0, 12.0, 5)
    assert ticks[0] >= -130.0 and ticks[-1] <= 12.0 and 0.0 in ticks


@pytest.mark.parametrize(
    ("span", "unit"), [(300.0, "s"), (3600.0, "min"), (86400.0, "h"), (7 * 86400.0, "days")]
)
def test_time_axis_unit(span: float, unit: str) -> None:
    assert time_axis(span)[1] == unit
