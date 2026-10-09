"""Monotonic and conservation properties of the steady-state thermal solver (Hypothesis)."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from budget_core.thermal.steady_state import STEFAN_BOLTZMANN_WM2K4 as S
from budget_core.thermal.steady_state import node_balance_w, solve_steady_state

heat = st.floats(min_value=0.0, max_value=500.0, allow_nan=False)
conductance = st.floats(min_value=0.1, max_value=50.0, allow_nan=False)
area = st.floats(min_value=0.05, max_value=5.0, allow_nan=False)
space = st.floats(min_value=3.0, max_value=300.0, allow_nan=False)


def chain(n: int, links: list[float]) -> np.ndarray:
    g = np.zeros((n, n))
    for i in range(n - 1):
        g[i, i + 1] = g[i + 1, i] = links[i]
    return g


networks = st.integers(min_value=2, max_value=6).flatmap(
    lambda n: st.tuples(
        st.just(n),
        st.lists(conductance, min_size=n - 1, max_size=n - 1),
        st.lists(area, min_size=n, max_size=n),
        st.lists(heat, min_size=n, max_size=n),
        st.integers(min_value=0, max_value=n - 1),
        space,
    )
)


@settings(max_examples=60, deadline=None)
@given(networks)
def test_energy_is_conserved_and_the_balance_closes(net) -> None:  # type: ignore[no-untyped-def]
    n, links, areas, q, rad_node, ts = net
    g = chain(n, links)
    r = np.zeros(n)
    r[rad_node] = 0.8 * S * areas[rad_node]  # one radiating node: the whole chain depends on it
    t = solve_steady_state(g, r, np.array(q), ts)
    assert abs(float(np.sum(r * (t**4 - ts**4))) - sum(q)) < 1e-6 * (1.0 + sum(q))
    assert np.max(np.abs(node_balance_w(g, r, np.array(q), ts, t))) < 1e-5 * (1.0 + sum(q))
    assert (t >= ts - 1e-6).all()


@settings(max_examples=60, deadline=None)
@given(networks, st.integers(min_value=0, max_value=5), st.floats(0.0, 200.0))
def test_more_dissipation_never_lowers_any_temperature(net, which, extra) -> None:  # type: ignore[no-untyped-def]
    n, links, areas, q, rad_node, ts = net
    g = chain(n, links)
    r = np.zeros(n)
    r[rad_node] = 0.8 * S * areas[rad_node]
    base = solve_steady_state(g, r, np.array(q), ts)
    more = list(q)
    more[which % n] += extra
    hotter = solve_steady_state(g, r, np.array(more), ts)
    assert (hotter >= base - 1e-6).all()


@settings(max_examples=60, deadline=None)
@given(networks, area, area)
def test_more_radiator_area_never_raises_any_temperature(net, a1, a2) -> None:  # type: ignore[no-untyped-def]
    n, links, _areas, q, rad_node, ts = net
    lo, hi = sorted((a1, a2))
    g = chain(n, links)
    r_small, r_big = np.zeros(n), np.zeros(n)
    r_small[rad_node], r_big[rad_node] = 0.8 * S * lo, 0.8 * S * hi
    small = solve_steady_state(g, r_small, np.array(q), ts)
    big = solve_steady_state(g, r_big, np.array(q), ts)
    assert (big <= small + 1e-6).all()


@settings(max_examples=60, deadline=None)
@given(networks, st.floats(1.0, 4.0))
def test_better_conduction_never_widens_the_temperature_spread(net, factor) -> None:  # type: ignore[no-untyped-def]
    n, links, areas, q, rad_node, ts = net
    r = np.zeros(n)
    r[rad_node] = 0.8 * S * areas[rad_node]
    t1 = solve_steady_state(chain(n, links), r, np.array(q), ts)
    t2 = solve_steady_state(chain(n, [x * factor for x in links]), r, np.array(q), ts)
    assert (t2.max() - t2.min()) <= (t1.max() - t1.min()) + 1e-6
