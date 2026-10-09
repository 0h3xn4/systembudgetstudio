"""Static thermal budget: dissipation by unit, subsystem, node and spacecraft mode, and the
steady-state node temperatures of the hot, cold (and any other) cases with unit limit checks.

Conventions are in docs/DECISIONS.md D-071 to D-075. A number that is a placeholder or missing
makes every result that needs it `None`; it is never replaced by zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from budget_core.assumptions import Assumption, incomplete
from budget_core.model import Project, Sourced, ThermalCase
from budget_core.power.static_budget import static_power_budget
from budget_core.problems import Problem, Severity
from budget_core.thermal.steady_state import (
    STEFAN_BOLTZMANN_WM2K4,
    ThermalSolveError,
    node_balance_w,
    solve_steady_state,
)

NDArray = np.ndarray[Any, np.dtype[np.float64]]

# ---- results --------------------------------------------------------------------------------


@dataclass(frozen=True)
class UnitHeat:
    unit_id: str
    unit_name: str
    subsystem: str
    node: str
    power_mode: str
    effective_power_w: float
    peak_power_w: float
    heat_dissipation_ratio: float | None
    dissipation_w: float | None
    peak_dissipation_w: float | None


@dataclass(frozen=True)
class GroupHeat:
    name: str  # subsystem or node
    dissipation_w: float | None
    peak_dissipation_w: float | None


@dataclass(frozen=True)
class ModeHeat:
    mode_id: str
    mode_name: str
    rows: tuple[UnitHeat, ...]
    subsystems: tuple[GroupHeat, ...]
    nodes: tuple[GroupHeat, ...]
    total_w: float | None
    peak_total_w: float | None


@dataclass(frozen=True)
class NodeTemperature:
    node: str
    temperature_k: float
    dissipation_w: float
    absorbed_w: float  # sunlight, albedo and Earth infrared absorbed by its surfaces
    radiated_w: float  # to space
    conducted_out_w: float  # net to the other nodes


@dataclass(frozen=True)
class UnitLimitCheck:
    unit_id: str
    node: str
    temperature_k: float | None
    lower_limit_k: float | None
    upper_limit_k: float | None
    lower_headroom_k: float | None  # temperature - lower limit
    upper_headroom_k: float | None  # upper limit - temperature
    required_margin_k: float | None
    status: str  # ok, exceeded, margin, no limits, n/a


@dataclass(frozen=True)
class CaseThermal:
    case: str
    description: str
    mode_id: str
    limit_set: str
    complete: bool  # False when an input is missing: no temperatures were computed
    nodes: tuple[NodeTemperature, ...]
    checks: tuple[UnitLimitCheck, ...]
    balance_residual_w: float | None  # largest node imbalance after solving


@dataclass(frozen=True)
class StaticThermalResult:
    modes: tuple[ModeHeat, ...]
    cases: tuple[CaseThermal, ...]
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]


# ---- helpers --------------------------------------------------------------------------------

STATUS_OK, STATUS_EXCEEDED, STATUS_MARGIN = "ok", "exceeded", "margin"
STATUS_NO_LIMITS, STATUS_NA = "no limits", "n/a"


def dissipation_w(power_w: float, ratio: float | None) -> float | None:
    """TH-DISS: heat dissipated in the unit; None when the ratio is not given."""
    return None if ratio is None else power_w * ratio


def absorbed_w(
    area_m2: float,
    absorptivity: float,
    emissivity: float,
    solar_view: float,
    earth_view: float,
    solar_flux_wm2: float,
    albedo: float,
    earth_ir_wm2: float,
) -> float:
    """TH-ABS: sunlight, albedo and Earth infrared absorbed by a surface (W)."""
    sun = absorptivity * solar_view * solar_flux_wm2
    reflected = absorptivity * earth_view * albedo * solar_flux_wm2
    infrared = emissivity * earth_view * earth_ir_wm2
    return area_m2 * (sun + reflected + infrared)


def _clean(watts: float) -> float:
    """Flow values below a nano-watt are rounding noise (and -0.0): show them as zero."""
    return 0.0 if abs(watts) < 1e-9 else watts


def _sum_opt(values: list[float | None]) -> float | None:
    return None if any(v is None for v in values) else math.fsum(v for v in values if v is not None)


def _val(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


class _Notes:
    def __init__(self) -> None:
        self.assumptions: list[Assumption] = []
        self.problems: list[Problem] = []
        self._seen: set[tuple[str, str]] = set()

    def get(
        self, name: str, item: Sourced | None, unit: str, file: str, path: str, what: str
    ) -> float | None:
        key = (file, path)
        first = key not in self._seen
        self._seen.add(key)
        if item is None:
            if first:
                self.assumptions.append(Assumption(name, None, unit, "missing", file, path, True))
                self.problems.append(incomplete(f"{what} is missing.", file, path))
            return None
        if first:
            self.assumptions.append(
                Assumption(name, item.value, unit, item.source, file, path, item.is_placeholder)
            )
            if item.is_placeholder:
                self.problems.append(incomplete(f"{what} is a placeholder.", file, path))
        return None if item.is_placeholder else item.value


# ---- dissipation ----------------------------------------------------------------------------


def unit_node(project: Project, unit_id: str) -> str:
    unit = project.units[unit_id]
    return unit.thermal_node or unit.subsystem


def _group(rows: list[UnitHeat], key: str) -> tuple[GroupHeat, ...]:
    """Dissipation summed by `subsystem` or `node`; None when a member has no ratio."""
    names = sorted({getattr(r, key) for r in rows})
    return tuple(
        GroupHeat(
            n,
            _sum_opt([r.dissipation_w for r in rows if getattr(r, key) == n]),
            _sum_opt([r.peak_dissipation_w for r in rows if getattr(r, key) == n]),
        )
        for n in names
    )


def dissipation_by_mode(project: Project) -> tuple[ModeHeat, ...]:
    power = static_power_budget(project)
    out: list[ModeHeat] = []
    for mode in power.modes:
        rows: list[UnitHeat] = []
        for r in mode.rows:
            unit = project.units[r.unit_id]
            pm = next(m for m in unit.modes if m.name == r.power_mode)
            ratio = pm.heat_dissipation_ratio
            rows.append(
                UnitHeat(
                    r.unit_id,
                    r.unit_name,
                    r.subsystem,
                    unit_node(project, r.unit_id),
                    r.power_mode,
                    r.effective_power_w,
                    r.peak_power_w,
                    ratio,
                    dissipation_w(r.effective_power_w, ratio),
                    dissipation_w(r.peak_power_w, ratio),
                )
            )

        out.append(
            ModeHeat(
                mode.mode_id,
                mode.mode_name,
                tuple(rows),
                _group(rows, "subsystem"),
                _group(rows, "node"),
                _sum_opt([r.dissipation_w for r in rows]),
                _sum_opt([r.peak_dissipation_w for r in rows]),
            )
        )
    return tuple(out)


# ---- steady state ---------------------------------------------------------------------------


def static_thermal_budget(project: Project) -> StaticThermalResult:
    """Dissipation of every spacecraft mode and the node temperatures of every case. The project
    must be valid."""
    modes = dissipation_by_mode(project)
    notes = _Notes()
    heat_by_mode = {m.mode_id: m for m in modes}
    model, env = project.config.thermal_model, project.config.thermal_environment
    mfile, efile = "config/thermal_model.yaml", "config/thermal_environment.yaml"
    _dissipation_gaps(project, notes)

    cases: list[CaseThermal] = []
    if model is None or env is None:
        for file, item in ((mfile, model), (efile, env)):
            if item is None:
                notes.problems.append(
                    incomplete(
                        f"{file} is not provided, so no node temperatures are computed.", file, ""
                    )
                )
    else:
        names = list(model.nodes)
        index = {n: i for i, n in enumerate(names)}
        space = notes.get(
            "Space temperature",
            env.space_temperature_k,
            "K",
            efile,
            "space_temperature_k",
            "The space temperature",
        )
        margin = notes.get(
            "Temperature margin",
            env.temperature_margin_k,
            "K",
            efile,
            "temperature_margin_k",
            "The temperature margin",
        )
        g = np.zeros((len(names), len(names)))
        links_ok = True
        for i, link in enumerate(model.conductances):
            value = notes.get(
                f"Conductance {link.first_node} - {link.second_node}",
                link.conductance_wk,
                "W/K",
                mfile,
                f"conductances[{i}].conductance_wk",
                "A conductance",
            )
            if value is None:
                links_ok = False
                continue
            a, b = index[link.first_node], index[link.second_node]
            g[a, b] += value
            g[b, a] += value
        if not model.conductances:
            links_ok = True
        for case_name, case in env.cases.items():
            cases.append(
                _solve_case(
                    project,
                    case_name,
                    case,
                    heat_by_mode,
                    names,
                    index,
                    g if links_ok else None,
                    space,
                    margin,
                    notes,
                )
            )
    return StaticThermalResult(
        modes, tuple(cases), tuple(notes.assumptions), tuple(_unique(notes.problems))
    )


def _unique(items: list[Problem]) -> list[Problem]:
    seen: set[tuple[str, str | None, str, str]] = set()
    out: list[Problem] = []
    for p in items:
        key = (p.code, p.file, p.path, p.message)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _dissipation_gaps(project: Project, notes: _Notes) -> None:
    """One warning per unit with a used power mode that has no heat dissipation ratio."""
    used: dict[str, set[str]] = {}
    for mode in project.modes.values():
        for uid, power_mode in mode.assignments.items():
            used.setdefault(uid, set()).add(power_mode)
    for uid in sorted(used):
        unit = project.units[uid]
        missing = [
            i
            for i, m in enumerate(unit.modes)
            if m.name in used[uid] and m.heat_dissipation_ratio is None
        ]
        if missing:
            notes.problems.append(
                incomplete(
                    f"Unit '{uid}' has power modes without a heat dissipation ratio.",
                    f"units/{uid}.yaml",
                    f"modes[{missing[0]}].heat_dissipation_ratio",
                )
            )


def _solve_case(
    project: Project,
    name: str,
    case: ThermalCase,
    heat_by_mode: dict[str, ModeHeat],
    node_names: list[str],
    index: dict[str, int],
    conductance: NDArray | None,
    space: float | None,
    margin: float | None,
    notes: _Notes,
) -> CaseThermal:
    model = project.config.thermal_model
    assert model is not None
    mfile, efile = "config/thermal_model.yaml", "config/thermal_environment.yaml"
    base = f"cases.{name}"
    flux = notes.get(
        f"Solar flux, case {name}",
        case.solar_flux_wm2,
        "W/m2",
        efile,
        f"{base}.solar_flux_wm2",
        f"The solar flux of case '{name}'",
    )
    albedo = notes.get(
        f"Albedo, case {name}",
        case.albedo_ratio,
        "ratio",
        efile,
        f"{base}.albedo_ratio",
        f"The albedo of case '{name}'",
    )
    earth_ir = notes.get(
        f"Earth infrared, case {name}",
        case.earth_ir_wm2,
        "W/m2",
        efile,
        f"{base}.earth_ir_wm2",
        f"The Earth infrared flux of case '{name}'",
    )
    heat = heat_by_mode.get(case.spacecraft_mode)
    dissipation = np.zeros(len(node_names))
    complete = conductance is not None and None not in (space, flux, albedo, earth_ir)
    if heat is None or any(r.dissipation_w is None for r in heat.rows):
        complete = False
    else:
        for r in heat.rows:
            assert r.dissipation_w is not None
            dissipation[index[r.node]] += r.dissipation_w

    absorbed = np.zeros(len(node_names))
    radiation = np.zeros(len(node_names))
    for i, s in enumerate(model.surfaces):
        path = f"surfaces[{i}]"
        eps = notes.get(
            f"Emissivity, {s.name}",
            s.emissivity_ratio,
            "ratio",
            mfile,
            f"{path}.emissivity_ratio",
            f"The emissivity of surface '{s.name}'",
        )
        alpha = notes.get(
            f"Absorptivity, {s.name}",
            s.absorptivity_ratio,
            "ratio",
            mfile,
            f"{path}.absorptivity_ratio",
            f"The absorptivity of surface '{s.name}'",
        )
        exposure = s.exposure.get(name)
        if exposure is None:
            notes.problems.append(
                incomplete(
                    f"Surface '{s.name}' has no exposure for case '{name}'.",
                    mfile,
                    f"{path}.exposure",
                )
            )
            complete = False
            continue
        sun_view = notes.get(
            f"Solar view, {s.name}, case {name}",
            exposure.solar_view_ratio,
            "ratio",
            mfile,
            f"{path}.exposure.{name}.solar_view_ratio",
            f"The solar view ratio of surface '{s.name}'",
        )
        earth_view = notes.get(
            f"Earth view, {s.name}, case {name}",
            exposure.earth_view_ratio,
            "ratio",
            mfile,
            f"{path}.exposure.{name}.earth_view_ratio",
            f"The Earth view ratio of surface '{s.name}'",
        )
        if None in (eps, alpha, sun_view, earth_view, flux, albedo, earth_ir):
            complete = False
            continue
        assert eps is not None and alpha is not None and sun_view is not None
        assert earth_view is not None and flux is not None and albedo is not None
        assert earth_ir is not None
        node = index[s.node]
        absorbed[node] += absorbed_w(
            s.area_m2, alpha, eps, sun_view, earth_view, flux, albedo, earth_ir
        )
        radiation[node] += eps * STEFAN_BOLTZMANN_WM2K4 * s.area_m2

    limit_set = case.limit_set
    if not complete or conductance is None or space is None:
        return CaseThermal(
            name,
            case.description,
            case.spacecraft_mode,
            limit_set,
            False,
            (),
            _checks(project, limit_set, None, node_names, margin, notes),
            None,
        )
    heat_in = dissipation + absorbed
    try:
        temps = solve_steady_state(conductance, radiation, heat_in, space)
    except ThermalSolveError as exc:
        stranded = ", ".join(node_names[i] for i in exc.nodes)
        message = (
            f"No equilibrium temperature for case '{name}': nodes without a path to space "
            f"({stranded})."
            if exc.nodes
            else f"The temperature solution for case '{name}' did not converge."
        )
        notes.problems.append(
            Problem(
                Severity.ERROR,
                "THERMAL_SOLVE_FAILED",
                message,
                file=mfile,
                hint="Give every group of connected nodes a surface that radiates to space.",
            )
        )
        return CaseThermal(
            name,
            case.description,
            case.spacecraft_mode,
            limit_set,
            False,
            (),
            _checks(project, limit_set, None, node_names, margin, notes),
            None,
        )
    residual = node_balance_w(conductance, radiation, heat_in, space, temps)
    laplacian = np.diag(conductance.sum(axis=1)) - conductance
    conducted = -laplacian @ temps
    nodes = tuple(
        NodeTemperature(
            n,
            float(temps[i]),
            float(dissipation[i]),
            float(absorbed[i]),
            _clean(float(radiation[i] * (temps[i] ** 4 - space**4))),
            _clean(float(-conducted[i])),
        )
        for i, n in enumerate(node_names)
    )
    by_node = {n.node: n.temperature_k for n in nodes}
    return CaseThermal(
        name,
        case.description,
        case.spacecraft_mode,
        limit_set,
        True,
        nodes,
        _checks(project, limit_set, by_node, node_names, margin, notes),
        _clean(float(np.max(np.abs(residual)))),
    )


def _checks(
    project: Project,
    limit_set: str,
    temperatures: dict[str, float] | None,
    node_names: list[str],
    margin: float | None,
    notes: _Notes,
) -> tuple[UnitLimitCheck, ...]:
    out: list[UnitLimitCheck] = []
    for uid in sorted(project.units):
        unit = project.units[uid]
        node = unit_node(project, uid)
        limits = unit.temperature_limits
        lo = hi = None
        if limits is not None:
            lo = limits.operating_min_k if limit_set == "operating" else limits.survival_min_k
            hi = limits.operating_max_k if limit_set == "operating" else limits.survival_max_k
        if lo is None and hi is None:
            notes.problems.append(
                Problem(
                    Severity.WARNING,
                    "THERMAL_NO_LIMITS",
                    f"Unit '{uid}' has no {limit_set} temperature limits; it is not checked.",
                    file=f"units/{uid}.yaml",
                    path="temperature_limits",
                    hint="Add temperature_limits from the unit's data sheet.",
                )
            )
            out.append(
                UnitLimitCheck(uid, node, None, None, None, None, None, margin, STATUS_NO_LIMITS)
            )
            continue
        t = None if temperatures is None else temperatures.get(node)
        if t is None:
            out.append(UnitLimitCheck(uid, node, None, lo, hi, None, None, margin, STATUS_NA))
            continue
        up = None if hi is None else hi - t
        down = None if lo is None else t - lo
        status = STATUS_OK
        if (up is not None and up < 0.0) or (down is not None and down < 0.0):
            status = STATUS_EXCEEDED
            notes.problems.append(
                Problem(
                    Severity.ERROR,
                    "THERMAL_LIMIT_EXCEEDED",
                    f"Unit '{uid}' is outside its {limit_set} temperature limits.",
                    file=f"units/{uid}.yaml",
                    path="temperature_limits",
                    hint="Change the design (conduction, radiator area, dissipation) or the limit.",
                )
            )
        elif margin is not None and (
            (up is not None and up < margin) or (down is not None and down < margin)
        ):
            status = STATUS_MARGIN
            notes.problems.append(
                Problem(
                    Severity.ERROR,
                    "THERMAL_MARGIN_INSUFFICIENT",
                    f"Unit '{uid}' is within its {limit_set} limits but closer than the "
                    "required temperature margin.",
                    file=f"units/{uid}.yaml",
                    path="temperature_limits",
                    hint="The margin is set in config/thermal_environment.yaml.",
                )
            )
        out.append(UnitLimitCheck(uid, node, t, lo, hi, down, up, margin, status))
    return tuple(out)
