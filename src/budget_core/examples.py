"""The three reference projects. All data is invented; nothing here is a real spacecraft.

Every configuration number is a placeholder (`source: TBD`) so the examples exercise the
Problems list instead of suggesting plausible-looking standards values (spec constraint 15).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from budget_core.io.project_loader import write_project
from budget_core.model import (
    AttenuationTable,
    Bus,
    Ebn0Table,
    Elements,
    Expendable,
    GroundStation,
    Inertia,
    MarginPolicy,
    MassLimit,
    MassLimits,
    MassProperties,
    MaturityClass,
    Orbit,
    PowerConfig,
    PowerMode,
    Project,
    ProjectConfig,
    ProjectMeta,
    Scenario,
    ScenarioRule,
    ScenarioSegment,
    Sourced,
    Spacecraft,
    SpacecraftMode,
    Target,
    Unit,
)

SYNTHETIC = "Synthetic example data; not a real spacecraft."
CLASSES = ("class_a", "class_b", "class_c")


def _tbd() -> Sourced:
    return Sourced(value=None, source="TBD", note="Placeholder: supply the project's value.")


def _config(buses: list[str]) -> ProjectConfig:
    return ProjectConfig(
        margin_policy=MarginPolicy(
            classes={
                c: MaturityClass(power_margin_ratio=_tbd(), mass_margin_ratio=_tbd())
                for c in CLASSES
            },
            system_power_margin_ratio=_tbd(),
            system_mass_margin_ratio=_tbd(),
        ),
        power_config=PowerConfig(
            distribution_loss_ratio=_tbd(),
            converter_efficiency_ratio={b: _tbd() for b in buses},
        ),
        ebn0_table=Ebn0Table(),
        attenuation_table=AttenuationTable(),
        mass_limits=MassLimits(
            limits=[MassLimit(name="Launch mass", phase="launch", limit_kg=_tbd())]
        ),
    )


# (id, name, subsystem, mass_kg, bus, maturity, {mode: (avg_w, peak_w, duty)})
UnitRow = tuple[str, str, str, float, str, str, dict[str, tuple[float, float, float]]]


Geometry = tuple[tuple[float, float, float], tuple[float, float, float] | None]
BODY_FRAME = (
    "Right-handed body frame. Origin: centre of the launch-vehicle interface plane. +Z: along the "
    "launch axis, away from the interface. X and Y: in the interface plane. Positions are item "
    "centres of mass in metres. Synthetic example."
)


def _box_inertia(mass: float, dims: tuple[float, float, float]) -> Inertia:
    """Uniform box about its centre: I_xx = m (dy^2 + dz^2) / 12, and so on (textbook formula)."""
    dx, dy, dz = dims
    return Inertia(
        ixx_kgm2=round(mass * (dy * dy + dz * dz) / 12.0, 6),
        iyy_kgm2=round(mass * (dx * dx + dz * dz) / 12.0, 6),
        izz_kgm2=round(mass * (dx * dx + dy * dy) / 12.0, 6),
    )


def _props(mass: float, geometry: Geometry | None) -> MassProperties | None:
    if geometry is None:
        return None
    position, dims = geometry
    return MassProperties(
        position_m=list(position), inertia=_box_inertia(mass, dims) if dims else None
    )


def _unit(
    row: UnitRow, geometry: Geometry | None = None, phases: list[str] | None = None
) -> tuple[str, Unit]:
    uid, name, subsystem, mass, bus, maturity, modes = row
    return uid, Unit(
        name=name,
        subsystem=subsystem,
        mass_kg=mass,
        bus=bus,
        maturity=maturity,
        modes=[
            PowerMode(name=m, avg_power_w=a, peak_power_w=p, duty_cycle_ratio=d)
            for m, (a, p, d) in modes.items()
        ],
        mass_properties=_props(mass, geometry),
        phases=phases,
    )


def _mode_map(
    units: dict[str, Unit], plan: dict[str, tuple[str, str]]
) -> dict[str, SpacecraftMode]:
    """plan: mode id -> (name, description); each unit gets its mode named like the spacecraft
    mode when it has one, otherwise its 'off' mode (or first mode)."""
    out: dict[str, SpacecraftMode] = {}
    for mid, (name, description) in plan.items():
        assignments = {}
        for uid, unit in units.items():
            names = [m.name for m in unit.modes]
            assignments[uid] = mid if mid in names else ("off" if "off" in names else names[0])
        out[mid] = SpacecraftMode(name=name, description=description, assignments=assignments)
    return out


CUBESAT_UNITS: list[UnitRow] = [
    (
        "obc",
        "On-board computer",
        "DH",
        0.12,
        "main",
        "class_a",
        {
            "safe": (0.3, 0.5, 1.0),
            "nominal": (0.5, 0.8, 1.0),
            "imaging": (0.7, 1.0, 1.0),
            "downlink": (0.6, 0.9, 1.0),
            "charging": (0.3, 0.5, 1.0),
        },
    ),
    (
        "eps",
        "Power board",
        "EPS",
        0.25,
        "main",
        "class_a",
        {
            "safe": (0.1, 0.2, 1.0),
            "nominal": (0.15, 0.25, 1.0),
            "imaging": (0.15, 0.25, 1.0),
            "downlink": (0.15, 0.25, 1.0),
            "charging": (0.15, 0.25, 1.0),
        },
    ),
    (
        "radio",
        "UHF/VHF radio",
        "TTC",
        0.09,
        "main",
        "class_b",
        {
            "off": (0.0, 0.0, 1.0),
            "safe": (0.2, 0.3, 1.0),
            "nominal": (0.2, 0.3, 1.0),
            "imaging": (0.2, 0.3, 1.0),
            "downlink": (1.8, 4.0, 0.5),
            "charging": (0.2, 0.3, 1.0),
        },
    ),
    (
        "adcs",
        "ADCS module",
        "ADCS",
        0.15,
        "main",
        "class_b",
        {
            "off": (0.0, 0.0, 1.0),
            "safe": (0.4, 0.6, 1.0),
            "nominal": (0.9, 1.4, 1.0),
            "imaging": (1.1, 1.8, 1.0),
            "downlink": (0.9, 1.4, 1.0),
            "charging": (0.6, 1.0, 1.0),
        },
    ),
    (
        "camera",
        "Camera payload",
        "PL",
        0.2,
        "main",
        "class_c",
        {"off": (0.0, 0.0, 1.0), "imaging": (2.4, 3.2, 0.6)},
    ),
    (
        "gnss",
        "GNSS receiver",
        "ADCS",
        0.03,
        "main",
        "class_b",
        {
            "off": (0.0, 0.0, 1.0),
            "nominal": (0.25, 0.4, 1.0),
            "imaging": (0.25, 0.4, 1.0),
            "downlink": (0.25, 0.4, 1.0),
            "charging": (0.25, 0.4, 1.0),
        },
    ),
]

MICROSAT_UNITS: list[UnitRow] = [
    (
        "obc_a",
        "OBC A",
        "DH",
        1.2,
        "main_28v",
        "class_a",
        {
            "safe": (4.0, 6.0, 1.0),
            "nominal": (6.0, 9.0, 1.0),
            "imaging": (7.5, 10.0, 1.0),
            "downlink": (7.0, 10.0, 1.0),
            "survival": (3.0, 4.0, 1.0),
        },
    ),
    (
        "obc_b",
        "OBC B (cold redundant)",
        "DH",
        1.2,
        "main_28v",
        "class_a",
        {"off": (0.0, 0.0, 1.0), "safe": (0.0, 0.0, 1.0)},
    ),
    (
        "pcdu",
        "Power conditioning unit",
        "EPS",
        4.5,
        "main_28v",
        "class_a",
        {
            "safe": (6.0, 8.0, 1.0),
            "nominal": (9.0, 12.0, 1.0),
            "imaging": (9.0, 12.0, 1.0),
            "downlink": (9.0, 12.0, 1.0),
            "survival": (5.0, 6.0, 1.0),
        },
    ),
    (
        "star_tracker",
        "Star tracker",
        "AOCS",
        0.9,
        "main_28v",
        "class_b",
        {
            "off": (0.0, 0.0, 1.0),
            "nominal": (3.5, 5.0, 1.0),
            "imaging": (3.5, 5.0, 1.0),
            "downlink": (3.5, 5.0, 1.0),
        },
    ),
    (
        "reaction_wheels",
        "Reaction wheels",
        "AOCS",
        6.0,
        "main_28v",
        "class_b",
        {
            "off": (0.0, 0.0, 1.0),
            "safe": (2.0, 12.0, 0.5),
            "nominal": (12.0, 30.0, 0.6),
            "imaging": (18.0, 40.0, 0.7),
            "downlink": (12.0, 30.0, 0.6),
        },
    ),
    (
        "magnetorquers",
        "Magnetorquers",
        "AOCS",
        1.5,
        "main_28v",
        "class_b",
        {
            "off": (0.0, 0.0, 1.0),
            "safe": (1.5, 3.0, 0.3),
            "nominal": (1.0, 3.0, 0.2),
            "survival": (1.5, 3.0, 0.3),
        },
    ),
    (
        "gnss",
        "GNSS receiver",
        "AOCS",
        0.4,
        "main_28v",
        "class_b",
        {
            "off": (0.0, 0.0, 1.0),
            "nominal": (1.2, 1.8, 1.0),
            "imaging": (1.2, 1.8, 1.0),
            "downlink": (1.2, 1.8, 1.0),
        },
    ),
    (
        "sband_trx",
        "S-band transceiver",
        "TTC",
        1.1,
        "main_28v",
        "class_b",
        {
            "off": (0.0, 0.0, 1.0),
            "safe": (2.5, 3.0, 1.0),
            "nominal": (2.5, 3.0, 1.0),
            "imaging": (2.5, 3.0, 1.0),
            "downlink": (12.0, 20.0, 0.8),
            "survival": (2.5, 3.0, 1.0),
        },
    ),
    (
        "xband_tx",
        "X-band transmitter",
        "PL-DATA",
        1.8,
        "payload_12v",
        "class_c",
        {"off": (0.0, 0.0, 1.0), "downlink": (28.0, 40.0, 0.9)},
    ),
    (
        "camera",
        "Imager",
        "PL",
        7.5,
        "payload_12v",
        "class_c",
        {"off": (0.0, 0.0, 1.0), "imaging": (22.0, 30.0, 0.8)},
    ),
    (
        "pdu_data",
        "Payload data unit",
        "PL-DATA",
        2.2,
        "payload_12v",
        "class_c",
        {
            "off": (0.0, 0.0, 1.0),
            "nominal": (4.0, 6.0, 1.0),
            "imaging": (14.0, 18.0, 1.0),
            "downlink": (10.0, 14.0, 1.0),
        },
    ),
    (
        "heaters",
        "Thermal heaters",
        "THERM",
        0.6,
        "main_28v",
        "class_a",
        {
            "off": (0.0, 0.0, 1.0),
            "safe": (8.0, 16.0, 0.4),
            "nominal": (6.0, 16.0, 0.3),
            "imaging": (6.0, 16.0, 0.3),
            "downlink": (6.0, 16.0, 0.3),
            "survival": (14.0, 16.0, 0.6),
        },
    ),
    (
        "sun_sensors",
        "Coarse sun sensors",
        "AOCS",
        0.2,
        "main_28v",
        "class_a",
        {
            "safe": (0.4, 0.5, 1.0),
            "nominal": (0.4, 0.5, 1.0),
            "imaging": (0.4, 0.5, 1.0),
            "downlink": (0.4, 0.5, 1.0),
            "survival": (0.4, 0.5, 1.0),
        },
    ),
]

MICROSAT_MODES = {
    "safe": ("Safe", "Sun-pointing, minimum loads."),
    "nominal": ("Nominal", "Earth-pointing housekeeping."),
    "imaging": ("Imaging", "Payload imaging over a target."),
    "downlink": ("Downlink", "Payload data downlink over a ground-station pass."),
    "survival": ("Survival", "Battery survival, heaters only."),
}

CUBESAT_MODES = {
    "safe": ("Safe", "Detumbled, minimum loads."),
    "nominal": ("Nominal", "Housekeeping."),
    "imaging": ("Imaging", "Camera on."),
    "downlink": ("Downlink", "Radio transmitting."),
    "charging": ("Charging", "Sun-pointing to charge the battery."),
}

STRESS_SUBSYSTEMS = ("DH", "EPS", "AOCS", "TTC", "PL", "THERM", "PL-DATA", "HARNESS")
STRESS_MODES = ("safe", "nominal", "imaging", "downlink", "charging")


# Invented geometry: unit id -> (centre-of-mass position in m, box dimensions in m or None for a
# point mass). The box formula gives each unit a consistent, physically valid inertia tensor.
CUBESAT_GEOMETRY: dict[str, Geometry] = {
    "obc": ((0.0, 0.0, 0.050), (0.09, 0.09, 0.015)),
    "eps": ((0.0, 0.0, 0.080), (0.09, 0.09, 0.030)),
    "radio": ((0.0, 0.0, 0.120), (0.09, 0.09, 0.020)),
    "adcs": ((0.0, 0.0, 0.160), (0.09, 0.09, 0.040)),
    "camera": ((0.0, 0.0, 0.260), (0.08, 0.08, 0.140)),
    "gnss": ((0.03, 0.0, 0.330), None),
}

MICROSAT_GEOMETRY: dict[str, Geometry] = {
    "obc_a": ((0.20, 0.10, 0.40), (0.20, 0.15, 0.08)),
    "obc_b": ((0.20, -0.10, 0.40), (0.20, 0.15, 0.08)),
    "pcdu": ((-0.20, 0.00, 0.35), (0.30, 0.25, 0.12)),
    "star_tracker": ((0.30, 0.25, 0.90), (0.10, 0.10, 0.15)),
    "reaction_wheels": ((0.00, 0.00, 0.30), (0.40, 0.40, 0.15)),
    "magnetorquers": ((0.00, 0.00, 0.60), (0.50, 0.50, 0.05)),
    "gnss": ((-0.30, -0.25, 0.95), None),
    "sband_trx": ((0.20, 0.00, 0.55), (0.18, 0.12, 0.06)),
    "xband_tx": ((-0.25, 0.20, 0.55), (0.20, 0.15, 0.08)),
    "camera": ((0.00, 0.00, 0.85), (0.30, 0.30, 0.50)),
    "pdu_data": ((-0.20, -0.15, 0.50), (0.25, 0.20, 0.10)),
    "heaters": ((0.00, 0.00, 0.50), None),
    "sun_sensors": ((0.25, -0.25, 0.98), None),
    "structure": ((0.00, 0.00, 0.50), (0.80, 0.80, 1.00)),
    "solar_array": ((0.00, 0.00, 0.50), (1.60, 0.80, 0.05)),
    "battery": ((-0.15, 0.10, 0.20), (0.30, 0.20, 0.15)),
    "adapter": ((0.00, 0.00, -0.03), (0.90, 0.90, 0.06)),
}

# Extra unprojected-power structure units for the microsat (zero electrical power).
MICROSAT_UNITS += [
    (
        "structure",
        "Primary structure",
        "STRUCT",
        80.0,
        "main_28v",
        "class_a",
        {"off": (0.0, 0.0, 1.0)},
    ),
    (
        "solar_array",
        "Solar array panels",
        "EPS",
        14.0,
        "main_28v",
        "class_b",
        {"off": (0.0, 0.0, 1.0)},
    ),
    ("battery", "Battery pack", "EPS", 18.0, "main_28v", "class_b", {"off": (0.0, 0.0, 1.0)}),
    (
        "adapter",
        "Separation adapter",
        "STRUCT",
        2.5,
        "main_28v",
        "class_a",
        {"off": (0.0, 0.0, 1.0)},
    ),
]

PHASES = ["launch", "bol", "eol"]

# Invented orbit and sites (round numbers; no real stations or customer targets).
EXAMPLE_ORBIT = Orbit(
    name="Example sun-synchronous-like orbit, about 550 km",
    elements=Elements(
        epoch_utc="2026-06-01T00:00:00Z",
        semi_major_axis_m=6928137.0,
        eccentricity_ratio=0.001,
        inclination_deg=97.6,
        raan_deg=100.0,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=0.0,
    ),
)
EXAMPLE_STATIONS = {
    "gs_north": GroundStation(
        name="Example station north",
        latitude_deg=67.0,
        longitude_deg=20.0,
        altitude_m=100.0,
        min_elevation_deg=5.0,
    ),
    "gs_south": GroundStation(
        name="Example station south",
        latitude_deg=-45.0,
        longitude_deg=170.0,
        altitude_m=50.0,
        min_elevation_deg=10.0,
    ),
}
EXAMPLE_TARGETS = {
    "tgt_plains": Target(
        name="Example imaging target",
        latitude_deg=40.0,
        longitude_deg=-100.0,
        altitude_m=300.0,
        min_elevation_deg=45.0,
    ),
}


def _cubesat() -> Project:
    units = dict(_unit(r, CUBESAT_GEOMETRY.get(r[0])) for r in CUBESAT_UNITS)
    return Project(
        root=Path("."),
        meta=ProjectMeta(name="Example 3U CubeSat", revision="1", description=SYNTHETIC),
        spacecraft=Spacecraft(
            name="CubeSat 3U",
            buses=[Bus(name="main", nominal_voltage_v=5.0)],
            mission_phases=["launch", "eol"],
            body_frame=BODY_FRAME,
        ),
        units=units,
        modes=_mode_map(units, CUBESAT_MODES),
        config=_config(["main"]),
        orbits={"leo": EXAMPLE_ORBIT},
        ground_stations=EXAMPLE_STATIONS,
        targets=EXAMPLE_TARGETS,
        scenarios={
            "one_day": Scenario(
                name="One day: charging by default, imaging and downlink over passes",
                orbit="leo",
                start_utc="2026-06-01T00:00:00Z",
                duration_s=86400.0,
                step_s=10.0,
                sites=["gs_north", "tgt_plains"],
                default_mode="charging",
                rules=[
                    ScenarioRule(kind="in_eclipse", mode="nominal"),
                    ScenarioRule(
                        kind="during_pass", site="tgt_plains", mode="imaging", lead_s=30.0
                    ),
                    ScenarioRule(kind="during_pass", site="gs_north", mode="downlink"),
                ],
            )
        },
    )


def _microsat() -> Project:
    units = dict(
        _unit(r, MICROSAT_GEOMETRY.get(r[0]), ["launch"] if r[0] == "adapter" else None)
        for r in MICROSAT_UNITS
    )
    propellant = Expendable(
        name="Propellant",
        subsystem="PROP",
        maturity="class_c",
        masses_kg={"launch": 9.0, "bol": 8.5, "eol": 0.8},
        mass_properties=MassProperties(position_m=[0.0, 0.0, 0.35]),
    )
    return Project(
        root=Path("."),
        meta=ProjectMeta(name="Example 150 kg microsatellite", revision="1", description=SYNTHETIC),
        spacecraft=Spacecraft(
            name="Microsat 150",
            buses=[
                Bus(name="main_28v", nominal_voltage_v=28.0),
                Bus(name="payload_12v", nominal_voltage_v=12.0),
            ],
            mission_phases=PHASES,
            body_frame=BODY_FRAME,
        ),
        units=units,
        modes=_mode_map(units, MICROSAT_MODES),
        config=_config(["main_28v", "payload_12v"]),
        expendables={"propellant": propellant},
        orbits={"leo": EXAMPLE_ORBIT},
        ground_stations=EXAMPLE_STATIONS,
        targets=EXAMPLE_TARGETS,
        scenarios={
            "commissioning_day": Scenario(
                name="One day with a safe-mode commissioning start",
                orbit="leo",
                start_utc="2026-06-01T00:00:00Z",
                duration_s=86400.0,
                step_s=10.0,
                shadow_model="conical",
                sites=["gs_north", "gs_south", "tgt_plains"],
                default_mode="nominal",
                rules=[
                    ScenarioRule(
                        kind="during_pass", site="tgt_plains", mode="imaging", lead_s=20.0
                    ),
                    ScenarioRule(kind="during_pass", site="gs_north", mode="downlink"),
                    ScenarioRule(kind="during_pass", site="gs_south", mode="downlink"),
                ],
                segments=[ScenarioSegment(start_s=0.0, duration_s=1800.0, mode="safe")],
            )
        },
    )


def _stress() -> Project:
    """200 units with deterministic, invented values (formulas of the index only)."""
    rows: list[UnitRow] = []
    geometry: dict[str, Geometry] = {}
    for i in range(200):
        base = 0.2 + (i % 17) * 0.15
        modes = {"off": (0.0, 0.0, 1.0)}
        for j, m in enumerate(STRESS_MODES):
            avg = round(base * (1.0 + 0.1 * ((i + j) % 5)), 3)
            modes[m] = (avg, round(avg * 1.5, 3), 1.0 if (i + j) % 3 else 0.5)
        uid = f"unit_{i:03d}"
        rows.append(
            (
                uid,
                f"Stress unit {i:03d}",
                STRESS_SUBSYSTEMS[i % len(STRESS_SUBSYSTEMS)],
                round(0.05 + (i % 11) * 0.07, 3),
                "main" if i % 4 else "aux",
                CLASSES[i % 3],
                modes,
            )
        )
        position = (
            round(((i % 7) - 3) * 0.05, 3),
            round((((i // 7) % 7) - 3) * 0.05, 3),
            round(0.1 + (i % 13) * 0.04, 3),
        )
        geometry[uid] = (position, (0.04, 0.04, 0.04) if i % 5 else None)
    units = dict(_unit(r, geometry[r[0]]) for r in rows)
    plan = {m: (m.capitalize(), "Stress-test mode.") for m in STRESS_MODES}
    return Project(
        root=Path("."),
        meta=ProjectMeta(
            name="Example stress case (200 units)", revision="1", description=SYNTHETIC
        ),
        spacecraft=Spacecraft(
            name="Stress SAT",
            buses=[
                Bus(name="main", nominal_voltage_v=28.0),
                Bus(name="aux", nominal_voltage_v=12.0),
            ],
            mission_phases=["launch", "eol"],
            body_frame=BODY_FRAME,
        ),
        units=units,
        modes=_mode_map(units, plan),
        config=_config(["main", "aux"]),
        orbits={"leo": EXAMPLE_ORBIT},
        ground_stations=EXAMPLE_STATIONS,
        targets=EXAMPLE_TARGETS,
        scenarios={
            "stress_week": Scenario(
                name="One week at 1 s resolution",
                orbit="leo",
                start_utc="2026-06-01T00:00:00Z",
                duration_s=604800.0,
                step_s=1.0,
                shadow_model="conical",
                sites=["gs_north", "gs_south", "tgt_plains"],
                default_mode="nominal",
                rules=[
                    ScenarioRule(kind="in_eclipse", mode="safe"),
                    ScenarioRule(kind="during_pass", site="tgt_plains", mode="imaging"),
                    ScenarioRule(kind="during_pass", site="gs_north", mode="downlink"),
                    ScenarioRule(kind="during_pass", site="gs_south", mode="downlink"),
                    ScenarioRule(kind="in_sunlight", mode="charging"),
                ],
            )
        },
    )


EXAMPLES: dict[str, Callable[[], Project]] = {
    "cubesat_3u": _cubesat,
    "microsat_150kg": _microsat,
    "stress_200_units": _stress,
}


def export_examples(out_dir: Path) -> list[str]:
    """Write all example projects below `out_dir`; returns their folder names."""
    for name, build in EXAMPLES.items():
        write_project(build(), out_dir / name)
    return sorted(EXAMPLES)
