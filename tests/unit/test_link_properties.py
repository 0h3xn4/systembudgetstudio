"""Monotonic properties of the link budget (Hypothesis): more range never increases the margin."""

from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from budget_core.link import budget as lb

freq = st.floats(min_value=1e8, max_value=4e10, allow_nan=False)
rng = st.floats(min_value=1e5, max_value=4e8, allow_nan=False)
db = st.floats(min_value=-30.0, max_value=60.0, allow_nan=False)
rate = st.floats(min_value=1e2, max_value=1e9, allow_nan=False)


def margin(
    r: float, f: float, power_w: float = 2.0, rate_bps: float = 1e5, other: float = 2.0
) -> float:
    eirp = lb.eirp_dbw(power_w, 1.0, 6.0)
    cn0 = lb.cn0_dbhz(eirp, lb.free_space_path_loss_db(r, f), other, -7.0)
    return float(lb.margin_db(lb.ebn0_db(cn0, rate_bps), 10.0))


@given(rng, rng, freq)
def test_more_range_never_increases_the_margin(a: float, b: float, f: float) -> None:
    lo, hi = sorted((a, b))
    assert margin(hi, f) <= margin(lo, f) + 1e-9


@given(rng, freq, rate, rate)
def test_a_higher_data_rate_never_increases_the_margin(
    r: float, f: float, x: float, y: float
) -> None:
    lo, hi = sorted((x, y))
    assert margin(r, f, rate_bps=hi) <= margin(r, f, rate_bps=lo) + 1e-9


@given(rng, freq, st.floats(0.1, 100.0), st.floats(0.1, 100.0))
def test_more_transmit_power_never_decreases_the_margin(
    r: float, f: float, p: float, q: float
) -> None:
    lo, hi = sorted((p, q))
    assert margin(r, f, power_w=hi) >= margin(r, f, power_w=lo) - 1e-9


@given(rng, freq, db, db)
def test_more_loss_never_increases_the_margin(r: float, f: float, a: float, b: float) -> None:
    lo, hi = sorted((max(a, 0.0), max(b, 0.0)))
    assert margin(r, f, other=hi) <= margin(r, f, other=lo) + 1e-9


@given(freq, st.floats(1.0, 90.0), rng)
def test_path_loss_round_trip_with_the_rate_that_just_closes(f: float, el: float, r: float) -> None:
    """At the rate returned by max_rate_for_margin_bps the margin equals the required margin."""
    eirp = lb.eirp_dbw(2.0, 1.0, 6.0)
    cn0 = lb.cn0_dbhz(eirp, lb.free_space_path_loss_db(r, f), 2.0, -7.0)
    rate_bps = float(lb.max_rate_for_margin_bps(cn0, 10.0, 3.0))
    assert abs(float(lb.margin_db(lb.ebn0_db(cn0, rate_bps), 10.0)) - 3.0) < 1e-6
    assert 0.0 <= el <= 90.0 and np.isfinite(rate_bps)
