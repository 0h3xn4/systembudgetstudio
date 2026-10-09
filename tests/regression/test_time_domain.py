"""Time-domain power budget against hand calculations (invented numbers, see power_helpers).

The reference values are worked out in the comments; no value is copied from the code under test.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import pytest

from budget_core.environment.data import TimeGrid
from budget_core.environment.elements import ElementsPropagator
from budget_core.model import Attitude, Elements, Orbit, ScenarioRule
from budget_core.power import array as arr
from budget_core.power.battery import integrate_battery, pack_capacity_wh
from budget_core.power.orbits import orbit_windows
from budget_core.power.signals import integral_of_steps, step_edges
from budget_core.power.time_domain import (
    BATTERY_DEPLETED,
    DOD_EXCEEDED,
    ORBIT_BALANCE_NEGATIVE,
    PEAK_POWER_EXCEEDED,
    format_offset,
    time_domain_budget,
    violation_problems,
)
from tests.power_helpers import power_system, sv, synthetic_env, synthetic_run, td_project

PERIOD = 6000.0
ECLIPSE = (3000.0, 4800.0)  # 30 % of the orbit


def hours(seconds: float) -> float:
    return seconds / 3600.0


# ---- 1-5: array and battery building blocks -------------------------------------------------


def test_temperature_factor() -> None:
    # 1 + (-0.0025 /K) * (340 K - 300 K) = 0.9
    assert arr.temperature_factor(340.0, 300.0, -0.0025) == pytest.approx(0.9)


def test_degradation_factor() -> None:
    # (1 - 0.03)^5 = 0.8587340257
    assert arr.degradation_factor(0.03, 5.0) == pytest.approx(0.8587340257)


def test_array_power_hand_calculation() -> None:
    # 1000 W/m2 * 100 cells * 0.003 m2 = 300 W; * 0.3 = 90; * 0.9 (temperature) = 81;
    # * 0.95 (packing) = 76.95; * 0.98 (harness) = 75.411; * cos 0.5 = 37.7055 W
    power = arr.array_power_w(
        irradiance_wm2=1000.0,
        cell_counts=np.array([100.0]),
        cell_area_m2=0.003,
        efficiency_ratio=0.3,
        temperature_factor_ratio=0.9,
        packing_loss_ratio=0.05,
        harness_loss_ratio=0.02,
        age_factor_ratio=1.0,
        cosines=np.array([[0.5]]),
        lit_ratio=np.array([1.0]),
    )
    assert power[0] == pytest.approx(37.7055)


def test_face_cosines_and_back_side() -> None:
    normals = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    sun = np.array([[1.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    c = arr.face_cosines(normals, sun)
    root_half = math.sqrt(0.5)
    assert c[0] == pytest.approx([root_half, root_half])
    assert c[1] == pytest.approx([0.0, 0.0])  # -X sun: the +X face looks away, +Y is edge-on
    assert c[2] == pytest.approx([0.0, 0.0])


def test_pack_capacity_with_fade() -> None:
    # 4 series * 2 parallel * 3.0 Ah * 3.6 V = 86.4 Wh; after 5 years at 2 %/yr: * 0.98^5
    assert pack_capacity_wh(3.0, 3.6, 4, 2, 0.0, 0.0) == pytest.approx(86.4)
    assert pack_capacity_wh(3.0, 3.6, 4, 2, 0.02, 5.0) == pytest.approx(86.4 * 0.9039207968)


# ---- 6-9: state-of-charge integration -------------------------------------------------------


def trace(dt: list[float], gen: float, demand: float, **kw: float):  # type: ignore[no-untyped-def]
    n = len(dt)
    return integrate_battery(
        np.array(dt),
        np.full(n, gen),
        np.full(n, demand),
        kw.get("cap", 1000.0),
        kw.get("eta_c", 1.0),
        kw.get("eta_d", 1.0),
        kw.get("e0", 500.0),
    )


def test_charging_applies_charge_efficiency() -> None:
    # 10 steps of 60 s, surplus 40 W: 40 W * 600 s = 6.667 Wh at the bus, * 0.9 = 6.0 Wh stored
    result = trace([60.0] * 10, 100.0, 60.0, eta_c=0.9)
    assert result.energy_wh[-1] == pytest.approx(506.0)


def test_discharging_applies_discharge_efficiency() -> None:
    # 100 W for 1 h at the bus needs 100 / 0.8 = 125 Wh from the cells
    result = trace([3600.0], 0.0, 100.0, eta_d=0.8)
    assert result.energy_wh[-1] == pytest.approx(375.0)


def test_full_battery_curtails_the_rest() -> None:
    # 5 Wh of room, 100 Wh offered in 1 h: 5 W stored (average), 95 W curtailed
    result = trace([3600.0], 100.0, 0.0, e0=995.0)
    assert result.energy_wh[-1] == pytest.approx(1000.0)
    assert result.battery_power_w[0] == pytest.approx(5.0)
    assert result.curtailed_w[0] == pytest.approx(95.0)


def test_empty_battery_leaves_demand_unmet() -> None:
    # 50 Wh stored, 100 Wh demanded in 1 h: 50 W average is not supplied
    result = trace([3600.0], 0.0, 100.0, e0=50.0)
    assert result.energy_wh[-1] == 0.0
    assert result.unmet_w[0] == pytest.approx(50.0)


# ---- 10-11: orbit windows and exact step averages -------------------------------------------


def test_orbit_windows_are_complete_revolutions() -> None:
    env = synthetic_env(3 * 5400.0 + 100.0, 10.0, period_s=5400.0)
    windows = orbit_windows(env.grid.times_s, env.position_m)
    assert len(windows) == 3
    for k, (start, end) in enumerate(windows):
        assert start == pytest.approx(k * 5400.0, abs=1e-6)
        assert end == pytest.approx((k + 1) * 5400.0, abs=1e-6)


def test_sunlit_share_is_exact_when_the_eclipse_is_off_the_grid() -> None:
    # eclipse from 1234.5 s to 4321.0 s (3086.5 s) inside 6000 s: 2913.5 s in sunlight
    env = synthetic_env(PERIOD, 100.0, [(1234.5, 4321.0)])
    result = time_domain_budget(td_project(), synthetic_run(env))
    dt = np.diff(result.edges_s)
    assert float(np.sum(result.lit_ratio * dt)) == pytest.approx(2913.5)


def test_integral_of_steps() -> None:
    # value 2 on [10, 20), value 5 on [30, 40): integral at 25 = 20, at 35 = 20 + 25 = 45
    got = integral_of_steps(
        [10.0, 30.0], [20.0, 40.0], [2.0, 5.0], np.array([5.0, 25.0, 35.0, 50.0])
    )
    assert got == pytest.approx([0.0, 20.0, 45.0, 70.0])


# ---- 12-14: whole-orbit energy, depth of discharge, peak ------------------------------------


def one_orbit(**kw: object):  # type: ignore[no-untyped-def]
    env = synthetic_env(PERIOD, 10.0, [ECLIPSE])
    rules = kw.pop("rules", None)
    system = kw.pop("system", None)
    project = td_project(system=system)
    return time_domain_budget(project, synthetic_run(env, rules=rules), **kw)  # type: ignore[arg-type]


def test_orbit_energy_balance_bol_and_eol() -> None:
    result = one_orbit()
    bol, eol = result.case("bol"), result.case("eol")
    # sunlit 4200 s * 100 W = 116.667 Wh; demand 40 W * 6000 s = 66.667 Wh; balance +50 Wh
    assert bol.summary.generated_wh == pytest.approx(hours(4200.0 * 100.0))
    assert bol.summary.demanded_wh == pytest.approx(hours(40.0 * 6000.0))
    assert bol.balances[0].balance_wh == pytest.approx(50.0)
    assert bol.balances[0].eclipse_s == pytest.approx(1800.0)
    # end of life: array output * 0.98^5
    assert eol.summary.generated_wh == pytest.approx(hours(4200.0 * 100.0) * 0.98**5)
    assert eol.generation_w is not None and bol.generation_w is not None
    assert eol.generation_w.max() / bol.generation_w.max() == pytest.approx(0.98**5)


def test_state_of_charge_through_an_eclipse() -> None:
    result = one_orbit()
    bol = result.case("bol")
    assert bol.energy_wh is not None and bol.soc_ratio is not None
    edges = result.edges_s
    at = lambda t: float(np.interp(t, edges, bol.energy_wh))  # noqa: E731
    # full at the start; the eclipse drains 40 W for 1800 s = 20 Wh; then +60 W refills in 1200 s
    assert at(3000.0) == pytest.approx(100.0)
    assert at(4800.0) == pytest.approx(80.0)
    assert at(6000.0) == pytest.approx(100.0)
    assert bol.summary.minimum_soc_ratio == pytest.approx(0.8)
    assert bol.summary.maximum_dod_ratio == pytest.approx(0.2)
    assert bol.capacity_wh == pytest.approx(100.0)


def test_depth_of_discharge_violation_has_the_hand_calculated_times() -> None:
    # limit 0.15 of 100 Wh: crossed after 15 Wh = 15 / 40 h = 1350 s into the eclipse (t = 4350 s);
    # recovery to 85 Wh needs 5 Wh / 60 W = 300 s after the eclipse (t = 5100 s)
    system = power_system()
    battery = system.battery.model_copy(update={"max_dod_ratio": {"eol": sv(0.15)}})
    result = one_orbit(system=system.model_copy(update={"battery": battery}))
    bol = [v for v in result.case("bol").violations if v.code == DOD_EXCEEDED]
    assert len(bol) == 1
    assert bol[0].start_s == pytest.approx(4350.0, abs=1e-6)
    assert bol[0].end_s == pytest.approx(5100.0, abs=1e-6)
    assert bol[0].extreme == pytest.approx(0.2)
    assert bol[0].limit == pytest.approx(0.15)
    assert bol[0].file == "config/power_system.yaml"
    assert bol[0].path == "battery.max_dod_ratio.eol"
    # end of life: capacity 100 * 0.99^5; the eclipse still drains 20 Wh
    cap = 100.0 * 0.99**5
    eol = [v for v in result.case("eol").violations if v.code == DOD_EXCEEDED]
    assert eol[0].start_s == pytest.approx(3000.0 + (0.15 * cap) / 40.0 * 3600.0, abs=1e-6)
    assert eol[0].extreme == pytest.approx(20.0 / cap)


def test_no_violation_when_the_limit_is_met() -> None:
    result = one_orbit()  # limit 0.3, depth reached 0.2
    assert not [v for v in result.violations if v.code == DOD_EXCEEDED]


def test_peak_power_violation_follows_the_mode_segments() -> None:
    # mode B peaks at 120 W against a 110 W limit; it runs during the eclipse only
    rules = [ScenarioRule(kind="in_eclipse", mode="b")]
    result = one_orbit(rules=rules)
    peaks = [v for v in result.violations if v.code == PEAK_POWER_EXCEEDED]
    assert [(v.start_s, v.end_s, v.extreme, v.limit) for v in peaks] == [
        (3000.0, 4800.0, 120.0, 110.0)
    ]
    assert peaks[0].path == "limits.peak_power_w"


def test_deplete_and_negative_orbit_balance() -> None:
    # mode B all the time: 100 W demand against 100 W in sunlight (70 % of the orbit); two orbits.
    # The battery starts at 90 Wh: the first eclipse takes 50 Wh (40 Wh left), sunlight changes
    # nothing (100 W in, 100 W out), the second eclipse needs 50 Wh and finds 40 Wh: 10 Wh unmet.
    system = power_system()
    battery = system.battery.model_copy(update={"initial_soc_ratio": sv(0.9)})
    system = system.model_copy(update={"battery": battery})
    env = synthetic_env(2 * PERIOD, 10.0, [ECLIPSE, (ECLIPSE[0] + PERIOD, ECLIPSE[1] + PERIOD)])
    result = time_domain_budget(td_project(system=system), synthetic_run(env, default_mode="b"))
    bol = result.case("bol")
    # per orbit: 4200 s * 100 W - 6000 s * 100 W = -50 Wh
    assert [round(b.balance_wh or 0.0, 6) for b in bol.balances] == [-50.0, -50.0]
    codes = {v.code for v in bol.violations}
    assert {ORBIT_BALANCE_NEGATIVE, DOD_EXCEEDED, BATTERY_DEPLETED} <= codes
    assert bol.summary.unmet_wh == pytest.approx(10.0)
    depleted = [v for v in bol.violations if v.code == BATTERY_DEPLETED]
    assert depleted[0].start_s > ECLIPSE[0] + PERIOD  # only in the second eclipse


# ---- 15: pointing ---------------------------------------------------------------------------


def test_nadir_pointing_average_is_one_over_pi() -> None:
    # Zenith-facing face (normal -Z of the local frame); the Sun is in the orbit plane. The face
    # sees cos(w t) while positive: the orbit average of max(0, cos) is 1/pi.
    system = power_system()
    array = system.solar_array.model_copy(
        update={
            "faces": [system.solar_array.faces[0].model_copy(update={"normal_body": [0, 0, -1]})]
        }
    )
    system = system.model_copy(update={"solar_array": array, "attitude": Attitude(default="nadir")})
    env = synthetic_env(PERIOD, 5.0)
    result = time_domain_budget(td_project(system=system), synthetic_run(env))
    energy_wh = result.case("bol").summary.generated_wh
    assert energy_wh == pytest.approx(hours(100.0 * PERIOD / math.pi), rel=2e-3)


# ---- 16-19: demand basis, losses, placeholders ----------------------------------------------


def test_margined_basis_uses_unit_and_system_margins() -> None:
    # 40 W * 1.10 (class) * 1.05 (system) = 46.2 W; converter efficiency 1, no distribution loss
    env = synthetic_env(PERIOD, 10.0, [ECLIPSE])
    result = time_domain_budget(td_project(), synthetic_run(env), load_basis="margined")
    assert result.demand_w is not None
    assert result.demand_w == pytest.approx(np.full(len(result.demand_w), 46.2))


def test_converter_and_distribution_losses_raise_the_demand() -> None:
    # 40 W / (0.9 * (1 - 0.02)) = 45.3515 W at the source
    env = synthetic_env(PERIOD, 10.0, [ECLIPSE])
    result = time_domain_budget(td_project(eta=0.9, loss=0.02), synthetic_run(env))
    assert result.demand_w is not None
    assert result.demand_w[0] == pytest.approx(40.0 / (0.9 * 0.98))
    assert result.load_w is not None and result.load_w[0] == pytest.approx(40.0)


def test_placeholder_array_value_gives_na_not_zero() -> None:
    system = power_system()
    array = system.solar_array.model_copy(update={"cell_efficiency_ratio": sv(None)})
    result = time_domain_budget(
        td_project(system=system.model_copy(update={"solar_array": array})),
        synthetic_run(synthetic_env(PERIOD, 10.0, [ECLIPSE])),
    )
    bol = result.case("bol")
    assert bol.generation_w is None and bol.energy_wh is None and bol.violations == ()
    assert bol.summary.generated_wh is None and bol.summary.minimum_soc_ratio is None
    assert result.load_w is not None  # the loads do not depend on the array
    paths = {p.path for p in result.problems if p.code == "RESULT_INCOMPLETE"}
    assert "solar_array.cell_efficiency_ratio" in paths


def test_placeholder_converter_efficiency_blocks_the_source_side() -> None:
    result = time_domain_budget(
        td_project(eta=None), synthetic_run(synthetic_env(PERIOD, 10.0, [ECLIPSE]))
    )
    assert result.demand_w is None and result.load_w is not None
    assert result.case("bol").generation_w is not None
    assert result.case("bol").energy_wh is None


def test_missing_power_system_file_is_reported() -> None:
    project = td_project()
    project = type(project)(
        **{
            **project.__dict__,
            "config": type(project.config)(
                margin_policy=project.config.margin_policy, power_config=project.config.power_config
            ),
        }
    )
    result = time_domain_budget(project, synthetic_run(synthetic_env(PERIOD, 10.0)))
    assert result.case("bol").generation_w is None
    assert any(
        p.code == "RESULT_INCOMPLETE" and p.file == "config/power_system.yaml"
        for p in result.problems
    )


def test_missing_phase_skips_only_the_depth_of_discharge_check() -> None:
    env = synthetic_env(PERIOD, 10.0, [ECLIPSE])
    run = synthetic_run(env, phase=None)
    result = time_domain_budget(td_project(), run)
    assert result.case("bol").energy_wh is not None
    assert not [v for v in result.violations if v.code == DOD_EXCEEDED]
    assert any(p.path == "mission_phase" for p in result.problems)
    assert any(p.file == "scenarios/synthetic.yaml" for p in result.problems)


# ---- 20: real orbit against the closed-form eclipse fraction --------------------------------


def test_orbit_average_generation_matches_the_eclipse_formula() -> None:
    # 500 km circular orbit at 51.6 deg, RAAN 40 deg, March equinox (Sun along +X):
    # beta = asin(sin(i) sin(RAAN)); eclipse fraction f = acos(sqrt(1 - (Re/a)^2) / cos(beta)) / pi.
    # A sun-pointing array of 100 W (cosine 1) averages 100 W * (1 - f) over a whole orbit.
    re, alt = 6378137.0, 500e3
    a = re + alt
    beta = math.asin(math.sin(math.radians(51.6)) * math.sin(math.radians(40.0)))
    fraction = math.acos(math.sqrt(1.0 - (re / a) ** 2) / math.cos(beta)) / math.pi
    orbit = Orbit(
        name="t",
        elements=Elements(
            epoch_utc="2026-03-20T14:46:00Z",
            semi_major_axis_m=a,
            eccentricity_ratio=1e-7,
            inclination_deg=51.6,
            raan_deg=40.0,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=0.0,
        ),
    )
    period = 2.0 * math.pi * math.sqrt(a**3 / 3.986004418e14)
    grid = TimeGrid(datetime(2026, 3, 20, 14, 46, tzinfo=UTC), 4.2 * period, 10.0)
    env = ElementsPropagator(orbit).compute(grid, [], "cylindrical")
    result = time_domain_budget(td_project(), synthetic_run(env))
    bol = result.case("bol")
    assert len(bol.balances) == 4
    for balance in bol.balances:
        mean_w = (balance.generation_wh or 0.0) * 3600.0 / (balance.end_s - balance.start_s)
        assert mean_w == pytest.approx(100.0 * (1.0 - fraction), abs=0.5)  # 0.4 % of the fraction


# ---- reporting helpers ----------------------------------------------------------------------


def test_violation_problems_group_by_kind_and_case() -> None:
    env = synthetic_env(2 * PERIOD, 10.0, [ECLIPSE, (ECLIPSE[0] + PERIOD, ECLIPSE[1] + PERIOD)])
    result = time_domain_budget(td_project(), synthetic_run(env, default_mode="b"))
    problems = violation_problems(result)
    codes = [p.code for p in problems]
    assert len(codes) == len(set((p.code, p.message) for p in problems))
    balance = [p for p in problems if p.code == ORBIT_BALANCE_NEGATIVE]
    assert {p.severity.value for p in balance} == {"error"}
    assert all("T+" in p.message for p in problems)
    assert all(
        p.file == "config/power_system.yaml" for p in problems if p.code != PEAK_POWER_EXCEEDED
    )


def test_format_offset() -> None:
    assert format_offset(0.0) == "T+00:00:00"
    assert format_offset(3725.9) == "T+01:02:05"
    assert format_offset(90000.0) == "T+25:00:00"


def test_step_edges_close_on_the_end() -> None:
    assert list(step_edges(100.0, 25.0)) == [0.0, 25.0, 50.0, 75.0, 100.0]
    assert list(step_edges(100.0, 30.0)) == [0.0, 30.0, 60.0, 90.0, 100.0]
