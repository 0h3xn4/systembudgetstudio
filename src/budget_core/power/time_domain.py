"""Time-domain power budget over a scenario: generation, demand, battery state, violations.

Pipeline (decisions D-061 to D-066): the mode timeline gives the demand of each step (exact
overlap with the mode segments), the environment gives sunlight and the Sun direction, the array
model gives generation, the battery integrates the surplus or deficit. Two cases are solved from
the same inputs: beginning of life (BOL) and end of life (EOL). A number that is a placeholder or
missing makes the results that need it `None` (n/a); it is never replaced by zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from budget_core.assumptions import Assumption, incomplete
from budget_core.model import Project, Sourced
from budget_core.model.power_system import PowerSystem
from budget_core.power import array as arr
from budget_core.power.attitude import sun_in_orbital_frame
from budget_core.power.battery import integrate_battery, pack_capacity_wh
from budget_core.power.orbits import orbit_windows
from budget_core.power.signals import integral_of_steps, step_edges, step_means
from budget_core.power.static_budget import ModePowerResult, static_power_budget
from budget_core.problems import Problem, Severity
from budget_core.scenario.run import ScenarioRun
from budget_core.scenario.timeline import mode_index_on_grid

NDArray = np.ndarray[Any, np.dtype[np.float64]]
BoolArray = np.ndarray[Any, np.dtype[np.bool_]]
LoadBasis = Literal["nominal", "margined"]
CASES = ("bol", "eol")
FILE = "config/power_system.yaml"

# Violation codes
DOD_EXCEEDED = "BATTERY_DOD_EXCEEDED"
BATTERY_DEPLETED = "BATTERY_DEPLETED"
ORBIT_BALANCE_NEGATIVE = "ORBIT_BALANCE_NEGATIVE"
PEAK_POWER_EXCEEDED = "PEAK_POWER_EXCEEDED"

CODES_TEXT = {
    DOD_EXCEEDED: "Depth of discharge above the allowed limit",
    BATTERY_DEPLETED: "Battery empty, demand not supplied",
    ORBIT_BALANCE_NEGATIVE: "Negative energy balance over an orbit",
    PEAK_POWER_EXCEEDED: "Peak power above the limit",
}

_MESSAGES = {
    DOD_EXCEEDED: "The battery depth of discharge exceeds the limit of the mission phase.",
    BATTERY_DEPLETED: "The battery is empty and the demand is not fully supplied.",
    ORBIT_BALANCE_NEGATIVE: "The energy generated over an orbit is less than the energy demanded.",
    PEAK_POWER_EXCEEDED: "The peak power demand at the source exceeds the power limit.",
}


@dataclass(frozen=True)
class Violation:
    case: str | None  # None when the finding does not depend on the case
    code: str
    start_s: float
    end_s: float
    extreme: float | None  # worst value inside the interval
    limit: float | None
    unit: str
    file: str  # input to change, for the jump link
    path: str


@dataclass(frozen=True)
class OrbitBalance:
    index: int  # 1-based
    start_s: float
    end_s: float
    eclipse_s: float
    generation_wh: float | None
    demand_wh: float | None
    balance_wh: float | None
    battery_change_wh: float | None


@dataclass(frozen=True)
class CaseSummary:
    average_generation_w: float | None
    average_demand_w: float | None
    generated_wh: float | None
    demanded_wh: float | None
    minimum_margin_w: float | None
    minimum_soc_ratio: float | None
    maximum_dod_ratio: float | None
    unmet_wh: float | None
    curtailed_wh: float | None
    energy_change_wh: float | None


@dataclass(frozen=True, eq=False)
class CaseResult:
    case: str
    age_years: float | None
    capacity_wh: float | None
    generation_w: NDArray | None  # per step
    margin_w: NDArray | None  # generation minus demand, per step
    energy_wh: NDArray | None  # stored energy at the step edges (N + 1)
    soc_ratio: NDArray | None  # (N + 1)
    dod_ratio: NDArray | None  # (N + 1)
    battery_power_w: NDArray | None
    unmet_w: NDArray | None
    curtailed_w: NDArray | None
    summary: CaseSummary
    balances: tuple[OrbitBalance, ...]
    violations: tuple[Violation, ...]


@dataclass(frozen=True)
class ModeRow:
    mode_id: str
    mode_name: str
    duration_s: float
    load_w: float | None
    demand_w: float | None
    peak_demand_w: float | None


@dataclass(frozen=True, eq=False)
class TimeDomainResult:
    run: ScenarioRun
    load_basis: str
    mission_phase: str | None
    edges_s: NDArray
    mode_ids: tuple[str, ...]  # index space of `step_mode`
    step_mode: NDArray  # mode at the start of each step (index into mode_ids)
    lit_ratio: NDArray  # share of each step in sunlight
    load_w: NDArray | None  # sum of unit loads, per step
    demand_w: NDArray | None  # demand at the source (after converter and distribution losses)
    cases: tuple[CaseResult, ...]
    modes: tuple[ModeRow, ...]
    windows: tuple[tuple[float, float], ...]
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]
    violations: tuple[Violation, ...] = field(default_factory=tuple)
    peak_limit_w: float | None = None
    dod_limit_ratio: float | None = None

    @property
    def steps(self) -> int:
        return len(self.edges_s) - 1

    def case(self, name: str) -> CaseResult:
        return next(c for c in self.cases if c.case == name)


# ---- inputs ---------------------------------------------------------------------------------


def _value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


@dataclass
class _Collector:
    assumptions: list[Assumption] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    def get(self, name: str, item: Sourced | None, unit: str, path: str, what: str) -> float | None:
        if item is None:
            self.assumptions.append(Assumption(name, None, unit, "missing", FILE, path, True))
            self.problems.append(
                incomplete(f"{what} is missing ({FILE} not provided).", FILE, path)
            )
            return None
        self.assumptions.append(
            Assumption(name, item.value, unit, item.source, FILE, path, item.is_placeholder)
        )
        if item.is_placeholder:
            self.problems.append(incomplete(f"{what} is a placeholder.", FILE, path))
            return None
        return item.value


def _mode_flow(mode: ModePowerResult, basis: LoadBasis) -> tuple[float | None, ...]:
    """(load_w, demand_w, peak_demand_w) of a mode on the chosen basis."""
    if basis == "margined":
        return (
            mode.average.system_margined_w,
            mode.average.source_margined_w,
            (mode.peak.source_margined_w),
        )
    return mode.average.load_w, mode.average.source_w, mode.peak.source_w


def _lit_ratio(run: ScenarioRun, edges: NDArray) -> NDArray:
    """Share of each step in sunlight: exact for a sharp shadow, trapezoid for a soft one."""
    env = run.env
    ratio = np.asarray(env.sunlight_ratio, dtype=np.float64)
    steps = len(edges) - 1
    soft = bool(np.any((ratio > 1e-9) & (ratio < 1.0 - 1e-9)))
    if not soft:
        starts = [e.start_s for e in env.eclipses]
        ends = [e.end_s for e in env.eclipses]
        shadow = step_means(starts, ends, [1.0] * len(starts), edges)
        return np.asarray(1.0 - shadow, dtype=np.float64)
    first = ratio[:steps]
    second = np.append(ratio[1 : steps + 1], ratio[steps - 1 : steps])[:steps]
    if len(second) < steps:  # a non-divisible duration: the last step has only its first sample
        second = np.append(second, first[len(second) :])
    return np.asarray(0.5 * (first + second), dtype=np.float64)


# ---- violations -----------------------------------------------------------------------------


def _runs(mask: BoolArray) -> list[tuple[int, int]]:
    """Inclusive index ranges where `mask` is True."""
    if not mask.any():
        return []
    padded = np.concatenate(([False], mask, [False]))
    change = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(a), int(b) - 1) for a, b in zip(change[::2], change[1::2], strict=True)]


def _crossing(t0: float, v0: float, t1: float, v1: float, level: float) -> float:
    if v1 == v0:
        return t1
    return t0 + (level - v0) / (v1 - v0) * (t1 - t0)


def _exceeding(edges: NDArray, values: NDArray, limit: float) -> list[tuple[float, float, float]]:
    """Intervals where the state `values` (at the edges) is above `limit`, as (start, end, worst);
    the ends are interpolated linearly between the edges."""
    out: list[tuple[float, float, float]] = []
    last = len(values) - 1
    for a, b in _runs(values > limit):
        start = (
            float(edges[0])
            if a == 0
            else _crossing(edges[a - 1], values[a - 1], edges[a], values[a], limit)
        )
        end = (
            float(edges[last])
            if b == last
            else _crossing(edges[b], values[b], edges[b + 1], values[b + 1], limit)
        )
        out.append((start, end, float(values[a : b + 1].max())))
    return out


# ---- main entry -----------------------------------------------------------------------------


def time_domain_budget(
    project: Project,
    run: ScenarioRun,
    *,
    load_basis: LoadBasis = "nominal",
    cases: tuple[str, ...] = CASES,
    mission_phase: str | None = None,
) -> TimeDomainResult:
    """Solve the scenario. The project must be valid; `run` is its computed scenario."""
    scenario = run.scenario
    env = run.env
    system: PowerSystem | None = project.config.power_system
    static = static_power_budget(project)
    col = _Collector()
    for assumption in static.assumptions:
        col.assumptions.append(assumption)
    col.problems.extend(static.problems)

    edges = step_edges(env.grid.duration_s, env.grid.step_s)
    dt = np.diff(edges)

    # --- modes, demand ------------------------------------------------------------------
    timeline = run.timeline
    mode_ids = tuple(sorted({s.mode for s in timeline}))
    by_mode = {m.mode_id: m for m in static.modes}
    flows = {m: _mode_flow(by_mode[m], load_basis) for m in mode_ids}
    seg_starts = [s.start_s for s in timeline]
    seg_ends = [s.end_s for s in timeline]

    def per_step(index: int) -> NDArray | None:
        if any(flows[s.mode][index] is None for s in timeline):
            return None
        values = [float(flows[s.mode][index] or 0.0) for s in timeline]
        return step_means(seg_starts, seg_ends, values, edges)

    load_w = per_step(0)
    demand_w = per_step(1)
    step_mode = mode_index_on_grid(timeline, edges[:-1], list(mode_ids))
    durations = {m: sum(s.duration_s for s in timeline if s.mode == m) for m in mode_ids}
    mode_rows = tuple(
        ModeRow(
            m,
            by_mode[m].mode_name,
            durations[m],
            flows[m][0],
            flows[m][1],
            flows[m][2],
        )
        for m in mode_ids
    )
    lit = _lit_ratio(run, edges)
    windows = tuple(orbit_windows(env.grid.times_s, env.position_m))

    phase = mission_phase or scenario.mission_phase
    if phase is None and len(project.phases) == 1:
        phase = project.phases[0]

    # --- array ----------------------------------------------------------------------------
    base_generation = _base_generation(project, system, run, edges, step_mode, mode_ids, lit, col)
    life = col.get(
        "Design life",
        system.design_life_yr if system else None,
        "yr",
        "design_life_yr",
        "The design life",
    )

    # --- battery limits -------------------------------------------------------------------
    battery_inputs = _battery_inputs(system, phase, col, f"scenarios/{run.scenario_id}.yaml")
    annual = col.get(
        "Array annual degradation",
        system.solar_array.annual_degradation_ratio if system else None,
        "ratio",
        "solar_array.annual_degradation_ratio",
        "The array annual degradation",
    )
    peak_limit = col.get(
        "Peak power limit",
        system.limits.peak_power_w if system else None,
        "W",
        "limits.peak_power_w",
        "The peak power limit",
    )

    peak_violations = _peak_violations(run, mode_rows, peak_limit)
    case_results = tuple(
        _solve_case(
            name,
            edges,
            dt,
            base_generation,
            demand_w,
            battery_inputs,
            life,
            annual,
            phase,
            windows,
            run,
        )
        for name in cases
    )
    violations = tuple(
        sorted(
            peak_violations + [v for c in case_results for v in c.violations],
            key=lambda v: (v.start_s, v.code, v.case or ""),
        )
    )
    return TimeDomainResult(
        run=run,
        load_basis=load_basis,
        mission_phase=phase,
        edges_s=edges,
        mode_ids=mode_ids,
        step_mode=step_mode,
        lit_ratio=lit,
        load_w=load_w,
        demand_w=demand_w,
        cases=case_results,
        modes=mode_rows,
        windows=windows,
        assumptions=tuple(_unique(col.assumptions)),
        problems=tuple(_unique_problems(col.problems)),
        violations=violations,
        peak_limit_w=peak_limit,
        dod_limit_ratio=None if battery_inputs is None else battery_inputs.dod_limit,
    )


def _unique(items: list[Assumption]) -> list[Assumption]:
    seen: set[tuple[str, str]] = set()
    out: list[Assumption] = []
    for a in items:
        key = (a.file, a.path or a.name)
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


def _unique_problems(items: list[Problem]) -> list[Problem]:
    seen: set[tuple[str, str | None, str, str]] = set()
    out: list[Problem] = []
    for p in items:
        key = (p.code, p.file, p.path, p.message)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


@dataclass(frozen=True)
class _BatteryInputs:
    cell_capacity_ah: float
    cell_voltage_v: float
    series: int
    parallel: int
    fade: float
    eta_c: float
    eta_d: float
    initial_soc: float
    dod_limit: float | None


def _battery_inputs(
    system: PowerSystem | None, phase: str | None, col: _Collector, scenario_file: str
) -> _BatteryInputs | None:
    b = system.battery if system else None
    cap = col.get(
        "Battery cell capacity",
        b.cell_capacity_ah if b else None,
        "Ah",
        "battery.cell_capacity_ah",
        "The battery cell capacity",
    )
    volt = col.get(
        "Battery cell voltage",
        b.cell_nominal_voltage_v if b else None,
        "V",
        "battery.cell_nominal_voltage_v",
        "The battery cell voltage",
    )
    eta_c = col.get(
        "Battery charge efficiency",
        b.charge_efficiency_ratio if b else None,
        "ratio",
        "battery.charge_efficiency_ratio",
        "The battery charge efficiency",
    )
    eta_d = col.get(
        "Battery discharge efficiency",
        b.discharge_efficiency_ratio if b else None,
        "ratio",
        "battery.discharge_efficiency_ratio",
        "The battery discharge efficiency",
    )
    fade = col.get(
        "Battery annual capacity fade",
        b.annual_capacity_fade_ratio if b else None,
        "ratio",
        "battery.annual_capacity_fade_ratio",
        "The battery capacity fade",
    )
    soc0 = col.get(
        "Battery initial state of charge",
        b.initial_soc_ratio if b else None,
        "ratio",
        "battery.initial_soc_ratio",
        "The initial state of charge",
    )
    dod: float | None = None
    if phase is None:
        col.problems.append(
            incomplete(
                "The scenario has no mission phase, so the allowed depth of discharge is unknown.",
                scenario_file,
                "mission_phase",
            )
        )
    elif b is not None:
        item = b.max_dod_ratio.get(phase)
        dod = col.get(
            f"Allowed depth of discharge, phase {phase}",
            item,
            "ratio",
            f"battery.max_dod_ratio.{phase}",
            f"The allowed depth of discharge of phase '{phase}'",
        )
    if b is None or None in (cap, volt, eta_c, eta_d, fade, soc0):
        return None
    assert cap is not None and volt is not None and eta_c is not None
    assert eta_d is not None and fade is not None and soc0 is not None
    return _BatteryInputs(
        cap, volt, b.cells_in_series, b.cells_in_parallel, fade, eta_c, eta_d, soc0, dod
    )


def _base_generation(
    project: Project,
    system: PowerSystem | None,
    run: ScenarioRun,
    edges: NDArray,
    step_mode: NDArray,
    mode_ids: tuple[str, ...],
    lit: NDArray,
    col: _Collector,
) -> NDArray | None:
    """Generation per step at beginning of life, or None when an input is missing."""
    a = system.solar_array if system else None
    base = "solar_array."
    irradiance = col.get(
        "Solar irradiance",
        a.solar_irradiance_wm2 if a else None,
        "W/m2",
        base + "solar_irradiance_wm2",
        "The solar irradiance",
    )
    area = col.get(
        "Cell area", a.cell_area_m2 if a else None, "m2", base + "cell_area_m2", "The cell area"
    )
    eff = col.get(
        "Cell efficiency",
        a.cell_efficiency_ratio if a else None,
        "ratio",
        base + "cell_efficiency_ratio",
        "The cell efficiency",
    )
    tref = col.get(
        "Reference temperature",
        a.reference_temperature_k if a else None,
        "K",
        base + "reference_temperature_k",
        "The reference temperature",
    )
    tcell = col.get(
        "Cell temperature",
        a.cell_temperature_k if a else None,
        "K",
        base + "cell_temperature_k",
        "The cell temperature",
    )
    coeff = col.get(
        "Efficiency temperature coefficient",
        a.efficiency_temp_coeff_perk if a else None,
        "1/K",
        base + "efficiency_temp_coeff_perk",
        "The temperature coefficient",
    )
    packing = col.get(
        "Packing loss",
        a.packing_loss_ratio if a else None,
        "ratio",
        base + "packing_loss_ratio",
        "The packing loss",
    )
    harness = col.get(
        "Harness loss",
        a.harness_loss_ratio if a else None,
        "ratio",
        base + "harness_loss_ratio",
        "The harness loss",
    )
    # annual degradation is used by the end-of-life case; it is reported there
    if a is None or not a.faces:
        if a is not None:
            col.problems.append(
                incomplete("The solar array has no faces.", FILE, "solar_array.faces")
            )
        return None
    if None in (irradiance, area, eff, tref, tcell, coeff, packing, harness):
        return None
    assert irradiance is not None and area is not None and eff is not None
    assert tref is not None and tcell is not None and coeff is not None
    assert packing is not None and harness is not None

    # attitude: which direction does the Sun have in the body frame, per step
    att = system.attitude if system else None
    assert att is not None
    pointing = [att.by_mode.get(m, att.default) for m in mode_ids]
    missing = [m for m, p in zip(mode_ids, pointing, strict=True) if p is None]
    if missing:
        col.problems.append(
            incomplete(
                "Some spacecraft modes of the scenario have no pointing and there is no default.",
                FILE,
                "attitude.default",
            )
        )
        return None
    if "sun" in pointing and att.sun_direction_body is None:
        col.problems.append(
            incomplete(
                "A sun-pointing mode is used but the Sun direction in the body frame is missing.",
                FILE,
                "attitude.sun_direction_body",
            )
        )
        return None

    env = run.env
    steps = len(edges) - 1
    kinds = np.array([p == "sun" for p in pointing])[step_mode]
    sun_body = np.empty((steps, 3), dtype=np.float64)
    if kinds.any():
        assert att.sun_direction_body is not None
        sun_body[kinds] = np.asarray(att.sun_direction_body, dtype=np.float64)
    if (~kinds).any():
        orbital = sun_in_orbital_frame(env.sun_direction, env.position_m, env.grid.times_s)
        sun_body[~kinds] = orbital[:steps][~kinds]
    normals = np.array([f.normal_body for f in a.faces], dtype=np.float64)
    counts = np.array([f.cell_count for f in a.faces], dtype=np.float64)
    cosines = arr.face_cosines(normals, sun_body)
    return arr.array_power_w(
        irradiance_wm2=irradiance,
        cell_counts=counts,
        cell_area_m2=area,
        efficiency_ratio=eff,
        temperature_factor_ratio=arr.temperature_factor(tcell, tref, coeff),
        packing_loss_ratio=packing,
        harness_loss_ratio=harness,
        age_factor_ratio=1.0,
        cosines=cosines,
        lit_ratio=lit,
    )


def _peak_violations(
    run: ScenarioRun, modes: tuple[ModeRow, ...], limit: float | None
) -> list[Violation]:
    if limit is None:
        return []
    over = {m.mode_id: m.peak_demand_w for m in modes if m.peak_demand_w is not None}
    out: list[Violation] = []
    for seg in run.timeline:
        peak = over.get(seg.mode)
        if peak is None or peak <= limit:
            continue
        if out and out[-1].end_s >= seg.start_s - 1e-9:
            previous = out[-1]
            out[-1] = Violation(
                None,
                PEAK_POWER_EXCEEDED,
                previous.start_s,
                seg.end_s,
                max(previous.extreme or 0.0, peak),
                limit,
                "W",
                previous.file,
                previous.path,
            )
        else:
            out.append(
                Violation(
                    None,
                    PEAK_POWER_EXCEEDED,
                    seg.start_s,
                    seg.end_s,
                    peak,
                    limit,
                    "W",
                    FILE,
                    "limits.peak_power_w",
                )
            )
    return out


def _solve_case(
    name: str,
    edges: NDArray,
    dt: NDArray,
    base_generation: NDArray | None,
    demand_w: NDArray | None,
    battery: _BatteryInputs | None,
    life_yr: float | None,
    annual: float | None,
    phase: str | None,
    windows: tuple[tuple[float, float], ...],
    run: ScenarioRun,
) -> CaseResult:
    years = life_yr if name == "eol" else 0.0
    age = None
    if years is not None and annual is not None:
        age = arr.degradation_factor(annual, years)
    generation = None if base_generation is None or age is None else base_generation * age

    capacity = None
    if battery is not None and years is not None:
        capacity = pack_capacity_wh(
            battery.cell_capacity_ah,
            battery.cell_voltage_v,
            battery.series,
            battery.parallel,
            battery.fade,
            years,
        )

    margin = None if generation is None or demand_w is None else generation - demand_w
    energy = soc = dod = bat_power = unmet = curtailed = None
    if generation is not None and demand_w is not None and battery is not None and capacity:
        trace = integrate_battery(
            dt,
            generation,
            demand_w,
            capacity,
            battery.eta_c,
            battery.eta_d,
            battery.initial_soc * capacity,
        )
        energy = trace.energy_wh
        soc = energy / capacity
        dod = 1.0 - soc
        bat_power, unmet, curtailed = trace.battery_power_w, trace.unmet_w, trace.curtailed_w

    violations: list[Violation] = []
    if dod is not None and battery is not None and battery.dod_limit is not None:
        for start, end, worst in _exceeding(edges, dod, battery.dod_limit):
            violations.append(
                Violation(
                    name,
                    DOD_EXCEEDED,
                    start,
                    end,
                    worst,
                    battery.dod_limit,
                    "ratio",
                    FILE,
                    f"battery.max_dod_ratio.{phase}",
                )
            )
    if unmet is not None:
        for a, b in _runs(unmet > 1e-9):
            violations.append(
                Violation(
                    name,
                    BATTERY_DEPLETED,
                    float(edges[a]),
                    float(edges[b + 1]),
                    float(unmet[a : b + 1].max()),
                    0.0,
                    "W",
                    FILE,
                    "battery",
                )
            )

    balances = _balances(edges, dt, generation, demand_w, energy, windows, run)
    for balance in balances:
        if balance.balance_wh is not None and balance.balance_wh < 0.0:
            violations.append(
                Violation(
                    name,
                    ORBIT_BALANCE_NEGATIVE,
                    balance.start_s,
                    balance.end_s,
                    balance.balance_wh,
                    0.0,
                    "Wh",
                    FILE,
                    "solar_array",
                )
            )
    summary = _summary(dt, generation, demand_w, margin, soc, dod, unmet, curtailed, energy)
    return CaseResult(
        name,
        years,
        capacity,
        generation,
        margin,
        energy,
        soc,
        dod,
        bat_power,
        unmet,
        curtailed,
        summary,
        tuple(balances),
        tuple(violations),
    )


def _wh(power_w: NDArray | None, dt: NDArray) -> float | None:
    return None if power_w is None else float(np.sum(power_w * dt) / 3600.0)


def _summary(
    dt: NDArray,
    generation: NDArray | None,
    demand: NDArray | None,
    margin: NDArray | None,
    soc: NDArray | None,
    dod: NDArray | None,
    unmet: NDArray | None,
    curtailed: NDArray | None,
    energy: NDArray | None,
) -> CaseSummary:
    total = float(np.sum(dt))
    gen_wh, dem_wh = _wh(generation, dt), _wh(demand, dt)
    return CaseSummary(
        average_generation_w=None if gen_wh is None else gen_wh * 3600.0 / total,
        average_demand_w=None if dem_wh is None else dem_wh * 3600.0 / total,
        generated_wh=gen_wh,
        demanded_wh=dem_wh,
        minimum_margin_w=None if margin is None else float(margin.min()),
        minimum_soc_ratio=None if soc is None else float(soc.min()),
        maximum_dod_ratio=None if dod is None else float(dod.max()),
        unmet_wh=_wh(unmet, dt),
        curtailed_wh=_wh(curtailed, dt),
        energy_change_wh=None if energy is None else float(energy[-1] - energy[0]),
    )


def _balances(
    edges: NDArray,
    dt: NDArray,
    generation: NDArray | None,
    demand: NDArray | None,
    energy: NDArray | None,
    windows: tuple[tuple[float, float], ...],
    run: ScenarioRun,
) -> list[OrbitBalance]:
    if not windows:
        return []
    bounds = np.array([w for pair in windows for w in pair], dtype=np.float64)
    ecl_s = [e.start_s for e in run.env.eclipses]
    ecl_e = [e.end_s for e in run.env.eclipses]
    shadow = integral_of_steps(ecl_s, ecl_e, [1.0] * len(ecl_s), bounds)

    def at(power: NDArray | None) -> NDArray | None:
        if power is None:
            return None
        cumulative = np.concatenate(([0.0], np.cumsum(power * dt))) / 3600.0
        return np.asarray(np.interp(bounds, edges, cumulative), dtype=np.float64)

    gen, dem = at(generation), at(demand)
    stored = None if energy is None else np.interp(bounds, edges, energy)
    out: list[OrbitBalance] = []
    for k, (start, end) in enumerate(windows):
        i0, i1 = 2 * k, 2 * k + 1
        g = None if gen is None else float(gen[i1] - gen[i0])
        d = None if dem is None else float(dem[i1] - dem[i0])
        out.append(
            OrbitBalance(
                k + 1,
                start,
                end,
                float(shadow[i1] - shadow[i0]),
                g,
                d,
                None if g is None or d is None else g - d,
                None if stored is None else float(stored[i1] - stored[i0]),
            )
        )
    return out


def violation_problems(result: TimeDomainResult) -> list[Problem]:
    """One Problem per finding kind and case, with the count, the first time and a jump link.
    The full list of intervals stays in the result."""
    groups: dict[tuple[str, str | None], list[Violation]] = {}
    for v in result.violations:
        groups.setdefault((v.code, v.case), []).append(v)
    out: list[Problem] = []
    for (code, case), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        first = min(items, key=lambda v: v.start_s)
        where = f" Case {case.upper()}." if case else ""
        out.append(
            Problem(
                Severity.ERROR,
                code,
                f"{_MESSAGES[code]}{where} {len(items)} interval(s), the first at "
                f"{format_offset(first.start_s)}.",
                file=first.file,
                path=first.path,
                hint="Open the violations table for every interval; change the input named "
                "here or the scenario.",
            )
        )
    return out


def format_offset(seconds: float) -> str:
    """T+hh:mm:ss from the scenario start (days are folded into the hours)."""
    total = int(math.floor(seconds + 1e-9))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"T+{hours:02d}:{minutes:02d}:{secs:02d}"
