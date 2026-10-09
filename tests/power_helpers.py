"""Builders for time-domain power tests: a synthetic environment and a project with round numbers.

Everything is invented (source: test fixture). With these inputs every expected value in the
regression tests can be worked out by hand:

* array: 1000 W/m2 * 400 cells * 0.0005 m2 * 0.5 efficiency = 100 W per unit cosine, BOL
* battery: 5 Ah * 4 V * 5 cells in series = 100 Wh, efficiencies 1 unless a test says otherwise
* loads: mode "a" 40 W, mode "b" 100 W (peak 120 W); converter efficiency 1, no distribution loss
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from budget_core.environment.data import EnvironmentData, TimeGrid
from budget_core.environment.intervals import Interval
from budget_core.model import (
    ArrayFace,
    Attitude,
    Battery,
    Bus,
    MarginPolicy,
    MaturityClass,
    PowerConfig,
    PowerLimits,
    PowerMode,
    PowerSystem,
    Project,
    ProjectConfig,
    ProjectMeta,
    Scenario,
    ScenarioRule,
    SolarArray,
    Sourced,
    Spacecraft,
    SpacecraftMode,
    Unit,
)
from budget_core.scenario.run import ScenarioRun
from budget_core.scenario.timeline import build_timeline

FIXTURE = "test fixture"
START = datetime(2026, 1, 1, tzinfo=UTC)


def sv(value: float | None) -> Sourced:
    return Sourced(value=value, source=FIXTURE if value is not None else "TBD")


def power_system(**changes: object) -> PowerSystem:
    array = SolarArray(
        faces=[ArrayFace(name="top", normal_body=[0.0, 0.0, 1.0], strings=20, cells_per_string=20)],
        solar_irradiance_wm2=sv(1000.0),
        cell_area_m2=sv(0.0005),
        cell_efficiency_ratio=sv(0.5),
        reference_temperature_k=sv(300.0),
        cell_temperature_k=sv(300.0),
        efficiency_temp_coeff_perk=sv(-0.002),
        packing_loss_ratio=sv(0.0),
        harness_loss_ratio=sv(0.0),
        annual_degradation_ratio=sv(0.02),
    )
    battery = Battery(
        cell_capacity_ah=sv(5.0),
        cell_nominal_voltage_v=sv(4.0),
        cells_in_series=5,
        cells_in_parallel=1,
        charge_efficiency_ratio=sv(1.0),
        discharge_efficiency_ratio=sv(1.0),
        annual_capacity_fade_ratio=sv(0.01),
        initial_soc_ratio=sv(1.0),
        max_dod_ratio={"launch": sv(0.5), "eol": sv(0.3)},
    )
    system = PowerSystem(
        design_life_yr=sv(5.0),
        solar_array=array,
        battery=battery,
        attitude=Attitude(default="sun", sun_direction_body=[0.0, 0.0, 1.0]),
        limits=PowerLimits(peak_power_w=sv(110.0)),
    )
    return system.model_copy(update=changes)


def td_project(
    root: Path = Path("."),
    *,
    system: PowerSystem | None = None,
    eta: float | None = 1.0,
    loss: float | None = 0.0,
) -> Project:
    def unit(modes: list[tuple[str, float, float]]) -> Unit:
        return Unit(
            name="Load",
            subsystem="TEST",
            mass_kg=1.0,
            bus="main",
            maturity="m1",
            modes=[PowerMode(name=n, avg_power_w=a, peak_power_w=p) for n, a, p in modes],
        )

    return Project(
        root=root,
        meta=ProjectMeta(name="Time-domain test", revision="r1"),
        spacecraft=Spacecraft(
            name="SAT",
            buses=[Bus(name="main", nominal_voltage_v=28.0)],
            mission_phases=["launch", "eol"],
            body_frame="test frame",
        ),
        units={"load": unit([("a", 40.0, 50.0), ("b", 100.0, 120.0)])},
        modes={
            "a": SpacecraftMode(name="Mode A", assignments={"load": "a"}),
            "b": SpacecraftMode(name="Mode B", assignments={"load": "b"}),
        },
        config=ProjectConfig(
            margin_policy=MarginPolicy(
                classes={
                    "m1": MaturityClass(power_margin_ratio=sv(0.1), mass_margin_ratio=sv(0.1))
                },
                system_power_margin_ratio=sv(0.05),
                system_mass_margin_ratio=sv(0.05),
            ),
            power_config=PowerConfig(
                distribution_loss_ratio=sv(loss), converter_efficiency_ratio={"main": sv(eta)}
            ),
            power_system=system if system is not None else power_system(),
        ),
    )


def synthetic_env(
    duration_s: float,
    step_s: float,
    eclipses: list[tuple[float, float]] | None = None,
    period_s: float = 6000.0,
    radius_m: float = 7.0e6,
) -> EnvironmentData:
    """Circular orbit in the x-y plane (counter-clockwise), the Sun fixed along +x, sharp shadow
    on the given intervals. Position r(t) = R (cos wt, sin wt, 0)."""
    grid = TimeGrid(START, duration_s, step_s)
    t = grid.times_s
    w = 2.0 * np.pi / period_s
    position = radius_m * np.stack([np.cos(w * t), np.sin(w * t), np.zeros_like(t)], axis=1)
    sun = np.tile(np.array([1.0, 0.0, 0.0]), (len(t), 1))
    intervals = tuple(Interval(a, b) for a, b in (eclipses or []))
    ratio = np.ones_like(t)
    for a, b in eclipses or []:
        ratio[(t >= a) & (t < b)] = 0.0
    return EnvironmentData(
        grid=grid,
        source="synthetic",
        shadow_model="cylindrical",
        position_m=position,
        sun_direction=sun,
        sunlight_ratio=ratio,
        eclipses=intervals,
        umbras=intervals,
        sites={},
    )


def synthetic_run(
    env: EnvironmentData,
    *,
    default_mode: str = "a",
    rules: list[ScenarioRule] | None = None,
    phase: str | None = "eol",
) -> ScenarioRun:
    scenario = Scenario(
        name="Synthetic",
        orbit="leo",
        start_utc="2026-01-01T00:00:00Z",
        duration_s=env.grid.duration_s,
        step_s=env.grid.step_s,
        default_mode=default_mode,
        rules=rules or [],
        mission_phase=phase,
    )
    return ScenarioRun("synthetic", scenario, env, build_timeline(scenario, env), ())
