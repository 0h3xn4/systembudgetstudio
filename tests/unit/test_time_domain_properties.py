"""Monotonic and conservation properties of the time-domain power budget (Hypothesis)."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from budget_core.model import ArrayFace
from budget_core.power import array as arr
from budget_core.power.battery import integrate_battery
from budget_core.power.time_domain import time_domain_budget
from tests.power_helpers import power_system, synthetic_env, synthetic_run, td_project

counts = st.integers(min_value=1, max_value=2000)
ratio = st.floats(min_value=0.0, max_value=0.99, allow_nan=False)
positive = st.floats(min_value=0.01, max_value=2000.0, allow_nan=False)
unit_ratio = st.floats(min_value=0.05, max_value=1.0, allow_nan=False)


def generation(n_cells: float, **changes: float) -> float:
    kwargs: dict[str, object] = {
        "irradiance_wm2": 1300.0,
        "cell_counts": np.array([n_cells]),
        "cell_area_m2": 0.003,
        "efficiency_ratio": 0.3,
        "temperature_factor_ratio": 0.95,
        "packing_loss_ratio": 0.05,
        "harness_loss_ratio": 0.02,
        "age_factor_ratio": 0.9,
        "cosines": np.array([[0.8]]),
        "lit_ratio": np.array([1.0]),
    }
    kwargs.update(changes)
    return float(arr.array_power_w(**kwargs)[0])  # type: ignore[arg-type]


@given(counts, counts)
def test_more_array_area_never_reduces_generation(a: int, b: int) -> None:
    lo, hi = sorted((a, b))
    assert generation(lo) <= generation(hi)


@given(counts, counts)
def test_more_cell_area_never_reduces_generation(a: int, b: int) -> None:
    lo, hi = sorted((a, b))
    assert generation(100, cell_area_m2=lo * 1e-4) <= generation(100, cell_area_m2=hi * 1e-4)


@given(ratio, ratio)
def test_more_loss_never_raises_generation(a: float, b: float) -> None:
    lo, hi = sorted((a, b))
    assert generation(100, packing_loss_ratio=hi) <= generation(100, packing_loss_ratio=lo)
    assert generation(100, harness_loss_ratio=hi) <= generation(100, harness_loss_ratio=lo)


@given(unit_ratio, unit_ratio)
def test_more_sunlight_never_reduces_generation(a: float, b: float) -> None:
    lo, hi = sorted((a, b))
    assert generation(100, lit_ratio=np.array([lo])) <= generation(100, lit_ratio=np.array([hi]))


@given(st.floats(min_value=0.0, max_value=0.5), st.floats(0.0, 30.0), st.floats(0.0, 30.0))
def test_degradation_never_increases_with_age(annual: float, y1: float, y2: float) -> None:
    lo, hi = sorted((y1, y2))
    assert arr.degradation_factor(annual, hi) <= arr.degradation_factor(annual, lo)


profiles = st.lists(
    st.tuples(
        st.floats(min_value=1.0, max_value=3600.0),
        st.floats(min_value=0.0, max_value=300.0),
        st.floats(min_value=0.0, max_value=300.0),
    ),
    min_size=1,
    max_size=40,
)


@settings(max_examples=100)
@given(profiles, st.floats(10.0, 500.0), unit_ratio, unit_ratio, st.floats(0.0, 1.0))
def test_stored_energy_stays_between_empty_and_full(
    steps: list[tuple[float, float, float]], cap: float, eta_c: float, eta_d: float, soc0: float
) -> None:
    dt, gen, dem = (np.array(x) for x in zip(*steps, strict=True))
    trace = integrate_battery(dt, gen, dem, cap, eta_c, eta_d, soc0 * cap)
    assert trace.energy_wh.min() >= 0.0
    assert trace.energy_wh.max() <= cap * (1.0 + 1e-12)
    assert (trace.unmet_w >= 0.0).all() and (trace.curtailed_w >= 0.0).all()


@settings(max_examples=100)
@given(profiles, st.floats(10.0, 500.0), unit_ratio, unit_ratio, st.floats(0.0, 1.0))
def test_energy_is_conserved(
    steps: list[tuple[float, float, float]], cap: float, eta_c: float, eta_d: float, soc0: float
) -> None:
    """Stored change = eta_c * charged - discharged / eta_d, and every offered watt is accounted
    for as used by the load, stored, or curtailed."""
    dt, gen, dem = (np.array(x) for x in zip(*steps, strict=True))
    trace = integrate_battery(dt, gen, dem, cap, eta_c, eta_d, soc0 * cap)
    hours = dt / 3600.0
    charged = np.clip(trace.battery_power_w, 0.0, None) * hours
    discharged = np.clip(-trace.battery_power_w, 0.0, None) * hours
    change = trace.energy_wh[-1] - trace.energy_wh[0]
    assert abs(change - (eta_c * charged.sum() - discharged.sum() / eta_d)) < 1e-6 * (1 + cap)
    balance = gen - dem - trace.battery_power_w - trace.curtailed_w + trace.unmet_w
    assert np.abs(balance).max() < 1e-6 * (1 + 300.0)


@settings(max_examples=60)
@given(profiles, st.floats(10.0, 500.0), st.floats(0.0, 100.0), st.floats(0.0, 1.0))
def test_more_generation_never_lowers_the_stored_energy(
    steps: list[tuple[float, float, float]], cap: float, extra: float, soc0: float
) -> None:
    dt, gen, dem = (np.array(x) for x in zip(*steps, strict=True))
    low = integrate_battery(dt, gen, dem, cap, 0.9, 0.9, soc0 * cap)
    high = integrate_battery(dt, gen + extra, dem, cap, 0.9, 0.9, soc0 * cap)
    assert (high.energy_wh >= low.energy_wh - 1e-9).all()


@settings(max_examples=12, deadline=None)
@given(st.integers(min_value=1, max_value=60), st.integers(min_value=1, max_value=60))
def test_more_array_area_never_reduces_the_generated_energy(a: int, b: int) -> None:
    """Whole pipeline: a face with more cells, same pointing and environment."""
    lo, hi = sorted((a, b))
    env = synthetic_env(1200.0, 20.0, [(300.0, 700.0)])

    def energy(strings: int) -> float:
        system = power_system()
        face = ArrayFace(name="top", normal_body=[0, 0, 1], strings=strings, cells_per_string=20)
        array = system.solar_array.model_copy(update={"faces": [face]})
        result = time_domain_budget(
            td_project(system=system.model_copy(update={"solar_array": array})),
            synthetic_run(env),
        )
        value = result.case("bol").summary.generated_wh
        assert value is not None
        return value

    assert energy(lo) <= energy(hi) + 1e-9
