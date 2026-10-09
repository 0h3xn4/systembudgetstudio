"""Monotonic and scaling properties of the static power budget."""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from budget_core.power.static_budget import effective_power_w, source_power_w, with_margin_w

watts = st.floats(min_value=0.0, max_value=1e4, allow_nan=False)
ratio = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
eff = st.floats(min_value=0.05, max_value=1.0, allow_nan=False)
dist = st.floats(min_value=0.0, max_value=0.5, allow_nan=False)


@given(watts, ratio, ratio)
def test_more_duty_never_lowers_effective_power(avg: float, d1: float, d2: float) -> None:
    lo, hi = sorted((d1, d2))
    assert effective_power_w(avg, lo) <= effective_power_w(avg, hi)


@given(watts, ratio, ratio)
def test_more_margin_never_lowers_power(p: float, m1: float, m2: float) -> None:
    lo, hi = sorted((m1, m2))
    a, b = with_margin_w(p, lo), with_margin_w(p, hi)
    assert a is not None and b is not None and a <= b


@given(watts, eff, eff, dist)
def test_lower_efficiency_never_lowers_source_power(
    p: float, e1: float, e2: float, d: float
) -> None:
    lo, hi = sorted((e1, e2))
    a, b = source_power_w(p, lo, d), source_power_w(p, hi, d)
    assert a is not None and b is not None and a >= b


@given(watts, eff, dist)
def test_source_power_is_never_below_the_load(p: float, e: float, d: float) -> None:
    s = source_power_w(p, e, d)
    assert s is not None and s >= p - 1e-9


@settings(max_examples=50)
@given(
    st.floats(min_value=0.1, max_value=1e3, allow_nan=False),
    st.floats(min_value=0.1, max_value=50.0),
)
def test_scaling_the_load_scales_the_source_power(p: float, k: float) -> None:
    a = source_power_w(p, 0.9, 0.02)
    b = source_power_w(p * k, 0.9, 0.02)
    assert a is not None and b is not None and math.isclose(b, a * k, rel_tol=1e-12)
