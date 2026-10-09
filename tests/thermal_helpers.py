"""A two-node thermal project with round numbers (source: test fixture).

Nodes A and B joined by 2 W/K; only A radiates (surface of 1 m2, emissivity 0.8, absorptivity 0.3).
Hot case: unit u1 (node A) dissipates 10 W, unit u2 (node B) 20 W * duty 0.5 * ratio 0.6 = 6 W;
the surface sees the Sun by 0.5 and the Earth by 0.5 (flux 1000 W/m2, albedo 0.3, Earth infrared
200 W/m2). Cold case: everything off, no environment. Space is 4 K, the margin 5 K.
"""

from __future__ import annotations

from pathlib import Path

from budget_core.model import (
    Bus,
    Conductance,
    Exposure,
    Project,
    ProjectConfig,
    ProjectMeta,
    Spacecraft,
    SpacecraftMode,
    Surface,
    TemperatureLimits,
    ThermalCase,
    ThermalEnvironment,
    ThermalModel,
    ThermalNode,
    Unit,
)
from budget_core.model.equipment import PowerMode
from tests.power_helpers import sv

SIGMA = 5.670374419e-8


def unit(
    name: str, subsystem: str, on_w: float, duty: float, ratio: float | None, **extra: object
) -> Unit:
    return Unit(
        name=name,
        subsystem=subsystem,
        mass_kg=1.0,
        bus="main",
        maturity="m1",
        modes=[
            PowerMode(
                name="on",
                avg_power_w=on_w,
                peak_power_w=on_w * 1.5,
                duty_cycle_ratio=duty,
                heat_dissipation_ratio=ratio,
            ),
            PowerMode(name="off", avg_power_w=0.0, peak_power_w=0.0, heat_dissipation_ratio=1.0),
        ],
        **extra,  # type: ignore[arg-type]
    )


def exposure(sun: float | None, earth: float | None) -> Exposure:
    return Exposure(solar_view_ratio=sv(sun), earth_view_ratio=sv(earth))


def thermal_project(
    root: Path = Path("."),
    *,
    ratio_u2: float | None = 0.6,
    limits_u2: TemperatureLimits | None = None,
    limits_u1: TemperatureLimits | None = None,
    hot_flux: float | None = 1000.0,
    conductance: float | None = 2.0,
    margin: float | None = 5.0,
    with_model: bool = True,
) -> Project:
    model = ThermalModel(
        nodes={"A": ThermalNode(name="Node A"), "B": ThermalNode(name="Node B")},
        conductances=[Conductance(first_node="A", second_node="B", conductance_wk=sv(conductance))],
        surfaces=[
            Surface(
                name="radiator",
                node="A",
                area_m2=1.0,
                emissivity_ratio=sv(0.8),
                absorptivity_ratio=sv(0.3),
                exposure={"hot": exposure(0.5, 0.5), "cold": exposure(0.0, 0.0)},
            )
        ],
    )
    env = ThermalEnvironment(
        space_temperature_k=sv(4.0),
        temperature_margin_k=sv(margin),
        cases={
            "hot": ThermalCase(
                spacecraft_mode="hot",
                solar_flux_wm2=sv(hot_flux),
                albedo_ratio=sv(0.3),
                earth_ir_wm2=sv(200.0),
            ),
            "cold": ThermalCase(
                spacecraft_mode="cold",
                solar_flux_wm2=sv(0.0),
                albedo_ratio=sv(0.0),
                earth_ir_wm2=sv(0.0),
            ),
        },
    )
    return Project(
        root=root,
        meta=ProjectMeta(name="Thermal test", revision="r1"),
        spacecraft=Spacecraft(
            name="SAT", buses=[Bus(name="main", nominal_voltage_v=28.0)], body_frame="test"
        ),
        units={
            "u1": unit("U1", "A", 10.0, 1.0, 1.0, temperature_limits=limits_u1),
            "u2": unit("U2", "B", 20.0, 0.5, ratio_u2, temperature_limits=limits_u2),
        },
        modes={
            "hot": SpacecraftMode(name="Hot", assignments={"u1": "on", "u2": "on"}),
            "cold": SpacecraftMode(name="Cold", assignments={"u1": "off", "u2": "off"}),
        },
        config=ProjectConfig(
            thermal_model=model if with_model else None,
            thermal_environment=env if with_model else None,
        ),
    )
