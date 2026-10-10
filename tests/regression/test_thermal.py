"""Static thermal budget against hand calculations (invented numbers, see thermal_helpers)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from budget_core.model import TemperatureLimits
from budget_core.thermal.static_thermal import (
    absorbed_w,
    dissipation_by_mode,
    dissipation_w,
    static_thermal_budget,
)
from budget_core.thermal.steady_state import (
    STEFAN_BOLTZMANN_WM2K4,
    ThermalSolveError,
    components,
    node_balance_w,
    solve_steady_state,
)
from tests.thermal_helpers import SIGMA, thermal_project

S = STEFAN_BOLTZMANN_WM2K4


def one_node(q: float, rad: float, space: float = 4.0) -> float:
    return float(solve_steady_state(np.zeros((1, 1)), np.array([rad]), np.array([q]), space)[0])


# ---- 1-8: solver against closed forms -------------------------------------------------------


def test_constant_matches_the_defined_value() -> None:
    # sigma = 2 pi^5 k^4 / (15 h^3 c^2) with the SI 2019 exact constants
    h, k, c = 6.62607015e-34, 1.380649e-23, 299792458.0
    assert pytest.approx(2.0 * math.pi**5 * k**4 / (15.0 * h**3 * c**2), rel=1e-9) == S


def test_single_node_radiating_to_space() -> None:
    # Q = eps sigma A (T^4 - Ts^4): choose Q so that T = 300 K, Ts = 4 K, eps A = 1 m2
    q = S * (300.0**4 - 4.0**4)
    assert one_node(q, S) == pytest.approx(300.0, abs=1e-6)


def test_radiator_sizing() -> None:
    # 100 W at 290 K with eps = 0.8: A = Q / (eps sigma (T^4 - Ts^4))
    area = 100.0 / (0.8 * S * (290.0**4 - 4.0**4))
    assert one_node(100.0, 0.8 * S * area) == pytest.approx(290.0, abs=1e-6)


def test_no_heat_gives_the_space_temperature() -> None:
    assert one_node(0.0, S) == pytest.approx(4.0, abs=1e-9)


def test_two_nodes_in_series() -> None:
    # node 1 radiates (R = 0.9 sigma), node 2 only conducts to it (G = 2 W/K) and has 10 W:
    # T1 from 10 W alone, T2 = T1 + 10 / 2 = T1 + 5 K
    g = np.array([[0.0, 2.0], [2.0, 0.0]])
    t = solve_steady_state(g, np.array([0.9 * S, 0.0]), np.array([0.0, 10.0]), 4.0)
    t1 = (10.0 / (0.9 * S) + 4.0**4) ** 0.25
    assert t[0] == pytest.approx(t1, abs=1e-6) and t[1] == pytest.approx(t1 + 5.0, abs=1e-6)


def test_symmetric_nodes_have_equal_temperatures() -> None:
    g = np.array([[0.0, 1.0], [1.0, 0.0]])
    t = solve_steady_state(g, np.array([S, S]), np.array([5.0, 5.0]), 4.0)
    assert t[0] == pytest.approx(t[1], abs=1e-9)
    assert t[0] == pytest.approx((5.0 / S + 4.0**4) ** 0.25, abs=1e-6)


def test_three_node_chain_conserves_energy() -> None:
    g = np.array([[0.0, 3.0, 0.0], [3.0, 0.0, 1.5], [0.0, 1.5, 0.0]])
    r = np.array([0.0, 0.5 * S, 0.7 * S])
    q = np.array([20.0, 0.0, 8.0])
    t = solve_steady_state(g, r, q, 4.0)
    radiated = float(np.sum(r * (t**4 - 4.0**4)))
    assert radiated == pytest.approx(q.sum(), rel=1e-9)
    assert np.max(np.abs(node_balance_w(g, r, q, 4.0, t))) < 1e-8


def test_a_node_without_a_path_to_space_has_no_equilibrium() -> None:
    g = np.zeros((3, 3))
    g[0, 1] = g[1, 0] = 1.0
    with pytest.raises(ThermalSolveError) as info:
        solve_steady_state(g, np.array([0.0, 0.0, S]), np.array([1.0, 1.0, 1.0]), 4.0)
    assert info.value.nodes == (0, 1)
    assert components(g) == [[0, 1], [2]]


# ---- 9-10: heat inputs ----------------------------------------------------------------------


def test_dissipation_follows_the_ratio() -> None:
    # 20 W * duty 0.5 = 10 W effective; ratio 0.6 gives 6 W; ratio missing gives None
    assert dissipation_w(10.0, 0.6) == pytest.approx(6.0)
    assert dissipation_w(10.0, None) is None


def test_absorbed_heat_terms() -> None:
    # A = 2 m2: sun 0.3 * 0.5 * 1000 = 150; albedo 0.3 * 0.5 * 0.3 * 1000 = 45;
    # infrared 0.8 * 0.5 * 200 = 80 W/m2; total 275 * 2 = 550 W
    assert absorbed_w(2.0, 0.3, 0.8, 0.5, 0.5, 1000.0, 0.3, 200.0) == pytest.approx(550.0)


# ---- 11-16: the project ---------------------------------------------------------------------


def hot_temperatures() -> tuple[float, float]:
    # node A: 10 W + 275 W absorbed = 285 W... plus node B's 6 W conducted through: 291 W leave
    # through the 0.8 m2-equivalent radiator; node B sits 6 W / 2 W/K = 3 K above node A
    t_a = (291.0 / (0.8 * SIGMA) + 4.0**4) ** 0.25
    return t_a, t_a + 3.0


def test_dissipation_roll_up_by_mode() -> None:
    modes = {m.mode_id: m for m in dissipation_by_mode(thermal_project())}
    hot = modes["hot"]
    assert [r.dissipation_w for r in hot.rows] == pytest.approx([10.0, 6.0])
    assert hot.total_w == pytest.approx(16.0) and hot.peak_total_w == pytest.approx(
        15.0 + 30.0 * 0.6  # peaks: u1 15 W * 1.0, u2 30 W * 0.6
    )
    assert {n.name: n.dissipation_w for n in hot.nodes} == pytest.approx({"A": 10.0, "B": 6.0})
    assert modes["cold"].total_w == 0.0


def test_hot_case_temperatures() -> None:
    result = static_thermal_budget(thermal_project())
    hot = next(c for c in result.cases if c.case == "hot")
    t_a, t_b = hot_temperatures()
    temps = {n.node: n for n in hot.nodes}
    assert hot.complete
    assert temps["A"].temperature_k == pytest.approx(t_a, abs=1e-6)
    assert temps["B"].temperature_k == pytest.approx(t_b, abs=1e-6)
    assert temps["A"].absorbed_w == pytest.approx(275.0)
    assert temps["A"].radiated_w == pytest.approx(291.0, rel=1e-9)
    assert temps["B"].conducted_out_w == pytest.approx(6.0, rel=1e-9)
    assert hot.balance_residual_w is not None and hot.balance_residual_w < 1e-8


def test_cold_case_sits_at_the_space_temperature() -> None:
    result = static_thermal_budget(thermal_project())
    cold = next(c for c in result.cases if c.case == "cold")
    assert [round(n.temperature_k, 6) for n in cold.nodes] == [4.0, 4.0]


def test_limit_checks_ok_margin_and_exceeded() -> None:
    t_a, t_b = hot_temperatures()  # about 283.0 K and 286.0 K
    ok = TemperatureLimits(operating_min_k=250.0, operating_max_k=330.0)
    near = TemperatureLimits(operating_min_k=250.0, operating_max_k=t_b + 2.0)  # 2 K < margin 5 K
    over = TemperatureLimits(operating_min_k=250.0, operating_max_k=t_b - 1.0)
    for limits, status, code in (
        (ok, "ok", None),
        (near, "margin", "THERMAL_MARGIN_INSUFFICIENT"),
        (over, "exceeded", "THERMAL_LIMIT_EXCEEDED"),
    ):
        result = static_thermal_budget(thermal_project(limits_u2=limits))
        hot = next(c for c in result.cases if c.case == "hot")
        check = next(c for c in hot.checks if c.unit_id == "u2")
        assert check.status == status
        assert check.temperature_k == pytest.approx(t_b, abs=1e-6)
        if code:
            assert code in {p.code for p in result.problems}
    exceeded = next(c for c in hot.checks if c.unit_id == "u2")
    assert exceeded.upper_headroom_k == pytest.approx(-1.0, abs=1e-6)  # 1 K above its limit


def test_survival_cases_use_the_survival_limits() -> None:
    limits = TemperatureLimits(
        operating_min_k=250.0, operating_max_k=330.0, survival_min_k=10.0, survival_max_k=340.0
    )
    project = thermal_project(limits_u1=limits)
    case = project.config.thermal_environment.cases["cold"]  # type: ignore[union-attr]
    env = project.config.thermal_environment.model_copy(  # type: ignore[union-attr]
        update={"cases": {"cold": case.model_copy(update={"limit_set": "survival"})}}
    )
    project = type(project)(
        **{
            **project.__dict__,
            "config": type(project.config)(
                thermal_model=project.config.thermal_model, thermal_environment=env
            ),
        }
    )
    cold = static_thermal_budget(project).cases[0]
    check = next(c for c in cold.checks if c.unit_id == "u1")
    # 4 K is far below the survival minimum of 10 K
    assert check.status == "exceeded" and check.lower_limit_k == 10.0


def test_units_without_limits_are_reported_not_failed() -> None:
    result = static_thermal_budget(thermal_project())
    assert {p.code for p in result.problems} >= {"THERMAL_NO_LIMITS"}
    assert all(c.status == "no limits" for case in result.cases for c in case.checks)


# ---- 17-19: gaps give n/a -------------------------------------------------------------------


def test_missing_dissipation_ratio_gives_na() -> None:
    result = static_thermal_budget(thermal_project(ratio_u2=None))
    hot = next(m for m in result.modes if m.mode_id == "hot")
    assert hot.rows[1].dissipation_w is None and hot.total_w is None
    case = next(c for c in result.cases if c.case == "hot")
    assert not case.complete and case.nodes == ()
    assert any(p.code == "RESULT_INCOMPLETE" and p.file == "units/u2.yaml" for p in result.problems)
    cold = next(c for c in result.cases if c.case == "cold")
    assert cold.complete  # the cold case does not depend on the missing ratio... of the 'on' mode


def test_placeholder_flux_and_conductance_give_na_not_zero() -> None:
    for kwargs, path in (
        ({"hot_flux": None}, "cases.hot.solar_flux_wm2"),
        ({"conductance": None}, "conductances[0].conductance_wk"),
    ):
        result = static_thermal_budget(thermal_project(**kwargs))
        assert any(p.code == "RESULT_INCOMPLETE" and p.path == path for p in result.problems)
        assert all(not c.complete for c in result.cases) or path.startswith("cases.hot")
        hot = next(c for c in result.cases if c.case == "hot")
        assert not hot.complete and hot.nodes == ()
        assert all(c.status in ("n/a", "no limits") for c in hot.checks)


def test_missing_files_are_reported() -> None:
    result = static_thermal_budget(thermal_project(with_model=False))
    assert result.cases == ()
    files = {p.file for p in result.problems if p.code == "RESULT_INCOMPLETE"}
    assert {"config/thermal_model.yaml", "config/thermal_environment.yaml"} <= files


def test_placeholder_conductance_blocks_every_case() -> None:
    result = static_thermal_budget(thermal_project(conductance=None))
    assert all(not c.complete for c in result.cases)


def test_a_node_without_a_path_to_space_is_an_error_naming_it() -> None:
    project = thermal_project()
    model = project.config.thermal_model.model_copy(update={"conductances": []})  # type: ignore[union-attr]
    project = type(project)(
        **{
            **project.__dict__,
            "config": type(project.config)(
                thermal_model=model, thermal_environment=project.config.thermal_environment
            ),
        }
    )
    result = static_thermal_budget(project)
    failed = [p for p in result.problems if p.code == "THERMAL_SOLVE_FAILED"]
    assert len(failed) == 2  # hot and cold
    assert all("(B)" in p.message for p in failed)
    assert all(not c.complete for c in result.cases)


def stiff_network(stiffness_wk: float):  # type: ignore[no-untyped-def]
    s = STEFAN_BOLTZMANN_WM2K4
    g = np.zeros((3, 3))
    g[0, 1] = g[1, 0] = stiffness_wk
    g[1, 2] = g[2, 1] = 1.0
    return g, np.array([0.1 * s, 0.0, 0.001 * s]), np.array([5.0, 0.0, 5.0])


def test_stiff_network_matches_the_merged_body() -> None:
    # nodes 0 and 1 are so tightly coupled that they act as one body; node 2 hangs on it by 1 W/K.
    # Hand solution of the two-body balance (bisection, see the comments): 204.36669, 209.25796 K
    g, r, q = stiff_network(1.0e6)
    t = solve_steady_state(g, r, q, 3.0)
    assert t[0] == pytest.approx(204.36669, abs=1e-4)
    assert t[2] == pytest.approx(209.25796, abs=1e-4)


def test_unresolvable_stiffness_is_refused_not_answered_wrongly() -> None:
    g, r, q = stiff_network(1.0e12)
    with pytest.raises(ThermalSolveError, match="double precision"):
        solve_steady_state(g, r, q, 3.0)


def test_within_limits_with_a_placeholder_margin_is_not_called_ok() -> None:
    limits = TemperatureLimits(operating_min_k=250.0, operating_max_k=330.0)
    result = static_thermal_budget(thermal_project(limits_u2=limits, margin=None))
    hot = next(c for c in result.cases if c.case == "hot")
    check = next(c for c in hot.checks if c.unit_id == "u2")
    assert check.status == "ok (margin not checked)"
    assert any(p.code == "RESULT_INCOMPLETE" for p in result.problems)
