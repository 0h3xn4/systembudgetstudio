"""Steady-state nodal heat balance (equation TH-BAL), a pure function over NumPy arrays.

For every node i:  sum_j G_ij (T_j - T_i) + R_i (T_space^4 - T_i^4) + Q_i = 0
with G the conduction between nodes (W/K), R_i = sum over its surfaces of emissivity * sigma *
area (W/K^4) and Q_i the heat put into the node (W). Solved by damped Newton iteration; every
group of connected nodes needs a path to space (some R > 0), otherwise there is no equilibrium.
"""

from __future__ import annotations

from typing import Any

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]

# Stefan-Boltzmann constant, exact in the 2019 SI (defined from h, k and c). A definitional
# constant shipped with its source like the geodesy constants (decision D-054, D-072).
STEFAN_BOLTZMANN_WM2K4 = 5.670374419e-8
STEFAN_BOLTZMANN_SOURCE = "CODATA 2018 / SI 2019 (exact from the defining constants h, k, c)"


class ThermalSolveError(Exception):
    """No equilibrium: `nodes` are the indices of nodes without a path to space (or empty when
    the iteration did not converge)."""

    def __init__(self, message: str, nodes: tuple[int, ...] = ()) -> None:
        super().__init__(message)
        self.nodes = nodes


def components(conductance_wk: NDArray) -> list[list[int]]:
    """Groups of nodes connected by a positive conductance."""
    n = len(conductance_wk)
    seen = [False] * n
    groups: list[list[int]] = []
    for start in range(n):
        if seen[start]:
            continue
        stack, group = [start], []
        seen[start] = True
        while stack:
            i = stack.pop()
            group.append(i)
            for j in np.nonzero(conductance_wk[i] > 0.0)[0]:
                if not seen[int(j)]:
                    seen[int(j)] = True
                    stack.append(int(j))
        groups.append(sorted(group))
    return groups


def solve_steady_state(
    conductance_wk: NDArray,
    radiation_wk4: NDArray,
    heat_w: NDArray,
    space_k: float,
    tolerance_k: float = 1e-10,
    max_iterations: int = 200,
) -> NDArray:
    """Equilibrium temperatures (K) of the nodes."""
    g = np.asarray(conductance_wk, dtype=np.float64)
    r = np.asarray(radiation_wk4, dtype=np.float64)
    q = np.asarray(heat_w, dtype=np.float64)
    n = len(q)
    if g.shape != (n, n) or r.shape != (n,):
        raise ValueError("the arrays must describe the same number of nodes")
    if not np.allclose(g, g.T) or (g < 0).any() or (r < 0).any() or (q < 0).any():
        raise ValueError("conductances must be symmetric and nothing may be negative")
    if space_k <= 0.0:
        raise ValueError("the space temperature must be positive")
    stranded = [i for group in components(g) if r[group].sum() <= 0.0 for i in group]
    if stranded:
        raise ThermalSolveError("some nodes have no path to space", tuple(stranded))

    laplacian = np.diag(g.sum(axis=1)) - g
    coupling = np.abs(laplacian)
    # Start from the equilibrium of the whole body treated as one node, a good first guess.
    t = np.full(n, (q.sum() / r.sum() + space_k**4) ** 0.25)
    for _ in range(max_iterations):
        flow = -laplacian @ t + r * (space_k**4 - t**4) + q
        if _balanced(flow, coupling, t, q, r):
            return _checked(laplacian, coupling, r, t)
        jacobian = laplacian + np.diag(4.0 * r * t**3)
        step = np.linalg.solve(jacobian, flow)
        biggest = float(np.max(np.abs(step) / t))
        scale = 1.0 if biggest <= 0.5 else 0.5 / biggest  # keep every temperature positive
        t = t + scale * step
        if float(np.max(np.abs(step))) * scale < tolerance_k:
            flow = -laplacian @ t + r * (space_k**4 - t**4) + q
            if _balanced(flow, coupling, t, q, r):
                return _checked(laplacian, coupling, r, t)
    raise ThermalSolveError("the iteration did not converge")


ACCURACY_K = 1e-4


def _checked(laplacian: NDArray, coupling: NDArray, r: NDArray, t: NDArray) -> NDArray:
    """The temperatures, if double precision can resolve them. The rounding of the conduction
    terms is an uncertainty in the heat balance; mapped through the Jacobian it bounds the error of
    each temperature. Conductances many orders above the radiation leave that error large, and a
    wrong temperature must not be reported as a result."""
    floor = 64.0 * np.finfo(np.float64).eps * (coupling @ t)
    jacobian = laplacian + np.diag(4.0 * r * t**3)
    uncertainty = float(np.max(np.abs(np.linalg.inv(jacobian)) @ floor))
    if uncertainty > ACCURACY_K:
        raise ThermalSolveError(
            "the conductances are so large compared with the radiation that the temperatures "
            "cannot be resolved in double precision (check the units of the conductances)"
        )
    return t


def _balanced(flow: NDArray, coupling: NDArray, t: NDArray, q: NDArray, r: NDArray) -> bool:
    """The heat balance holds at every node: the imbalance is a negligible share of the heat
    flowing through the body, or no larger than the rounding of the conduction terms. A small
    step alone is not enough: with very stiff conductances a tiny step can leave a large
    imbalance."""
    total = float(q.sum() + np.sum(r * t**4)) + 1e-300
    floor = 64.0 * np.finfo(np.float64).eps * (coupling @ t)
    return bool(np.all(np.abs(flow) <= 1e-9 * total + floor))


def node_balance_w(
    conductance_wk: NDArray,
    radiation_wk4: NDArray,
    heat_w: NDArray,
    space_k: float,
    temperature_k: NDArray,
) -> NDArray:
    """Residual of the heat balance per node (W); zero at equilibrium."""
    laplacian = np.diag(conductance_wk.sum(axis=1)) - conductance_wk
    t = np.asarray(temperature_k, dtype=np.float64)
    return np.asarray(
        -laplacian @ t + radiation_wk4 * (space_k**4 - t**4) + heat_w, dtype=np.float64
    )
