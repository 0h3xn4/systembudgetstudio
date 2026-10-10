"""The reference projects. All data is invented; nothing here is a real spacecraft.

Three examples keep every configuration number a placeholder (`source: TBD`) so they exercise the
Problems list instead of suggesting plausible-looking standards values (spec constraint 15). The
fourth, `cubesat_3u_eps`, has invented round values for the power inputs (margins, converters,
array, battery) so the time-domain budget shows results; its mass inputs are still placeholders.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from budget_core.io.project_loader import write_project
from budget_core.model import (
    Antenna,
    AntennaPattern,
    ArrayFace,
    AttenuationEntry,
    AttenuationTable,
    Attitude,
    Battery,
    Bus,
    Conductance,
    Ebn0Entry,
    Ebn0Table,
    Elements,
    Expendable,
    Exposure,
    GroundStation,
    Inertia,
    Link,
    MarginPolicy,
    MassLimit,
    MassLimits,
    MassProperties,
    MaturityClass,
    Orbit,
    PowerConfig,
    PowerLimits,
    PowerMode,
    PowerSystem,
    Project,
    ProjectConfig,
    ProjectMeta,
    Receiver,
    Scenario,
    ScenarioRule,
    ScenarioSegment,
    SolarArray,
    Sourced,
    Spacecraft,
    SpacecraftMode,
    StaticPoint,
    Surface,
    Target,
    TemperatureLimits,
    ThermalCase,
    ThermalEnvironment,
    ThermalModel,
    ThermalNode,
    Transmitter,
    Unit,
)
from budget_core.model.power_system import Pointing

SYNTHETIC = "Synthetic example data; not a real spacecraft."
CLASSES = ("class_a", "class_b", "class_c")


def _tbd() -> Sourced:
    return Sourced(value=None, source="TBD", note="Placeholder: supply the project's value.")


SYNTH_VALUE = "Synthetic example value; not from a data sheet or a standard."


def _val(value: float) -> Sourced:
    return Sourced(value=value, source=SYNTH_VALUE)


def _power_system(
    filled: bool, phases: list[str], by_mode: dict[str, Pointing] | None = None
) -> PowerSystem:
    """Array and battery of the 3U CubeSat example. The design (faces, cell counts, pointing) is
    always given; the electrical numbers are placeholders unless `filled`, in which case they are
    invented round values (the project data of an example, not standards values)."""

    def n(value: float) -> Sourced:
        return _val(value) if filled else _tbd()

    faces = [
        ArrayFace(name="plus_x", normal_body=[1.0, 0.0, 0.0], strings=2, cells_per_string=3),
        ArrayFace(name="minus_x", normal_body=[-1.0, 0.0, 0.0], strings=2, cells_per_string=3),
        ArrayFace(name="plus_y", normal_body=[0.0, 1.0, 0.0], strings=2, cells_per_string=3),
        ArrayFace(name="minus_y", normal_body=[0.0, -1.0, 0.0], strings=2, cells_per_string=3),
        ArrayFace(name="minus_z", normal_body=[0.0, 0.0, -1.0], strings=1, cells_per_string=2),
    ]
    return PowerSystem(
        design_life_yr=n(2.0),
        solar_array=SolarArray(
            faces=faces,
            solar_irradiance_wm2=n(1360.0),
            cell_area_m2=n(0.003),
            cell_efficiency_ratio=n(0.28),
            reference_temperature_k=n(301.0),
            cell_temperature_k=n(318.0),
            efficiency_temp_coeff_perk=n(-0.0020),
            packing_loss_ratio=n(0.03),
            harness_loss_ratio=n(0.02),
            annual_degradation_ratio=n(0.03),
        ),
        battery=Battery(
            cell_capacity_ah=n(2.6),
            cell_nominal_voltage_v=n(3.6),
            cells_in_series=2,
            cells_in_parallel=2,
            charge_efficiency_ratio=n(0.95),
            discharge_efficiency_ratio=n(0.95),
            annual_capacity_fade_ratio=n(0.04),
            initial_soc_ratio=n(0.9),
            max_dod_ratio={p: n(0.3) for p in phases},
        ),
        attitude=Attitude(
            default="sun",
            by_mode=by_mode or {},
            sun_direction_body=[1.0, 0.0, 0.0],
        ),
        limits=PowerLimits(peak_power_w=n(7.5)),
    )


def _config(
    buses: list[str],
    power_system: PowerSystem | None = None,
    filled_power: bool = False,
    thermal: tuple[ThermalModel, ThermalEnvironment] | None = None,
    link_tables: tuple[Ebn0Table, AttenuationTable] | None = None,
) -> ProjectConfig:
    """Margin policy and power configuration: placeholders, or (for the complete power example)
    invented round values. Mass numbers and tables stay placeholders in every example."""

    def p(value: float) -> Sourced:
        return _val(value) if filled_power else _tbd()

    margins = {"class_a": 0.05, "class_b": 0.10, "class_c": 0.20}
    return ProjectConfig(
        power_system=power_system,
        thermal_model=thermal[0] if thermal else None,
        thermal_environment=thermal[1] if thermal else None,
        margin_policy=MarginPolicy(
            classes={
                c: MaturityClass(power_margin_ratio=p(margins[c]), mass_margin_ratio=_tbd())
                for c in CLASSES
            },
            system_power_margin_ratio=p(0.10),
            system_mass_margin_ratio=_tbd(),
        ),
        power_config=PowerConfig(
            distribution_loss_ratio=p(0.03),
            converter_efficiency_ratio={b: p(0.90) for b in buses},
        ),
        ebn0_table=link_tables[0] if link_tables else Ebn0Table(),
        attenuation_table=link_tables[1] if link_tables else AttenuationTable(),
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


# Heat dissipation ratio per (unit id, power mode): every power mode dissipates all of its
# electrical power except these (invented values; a transmitter radiates part of it as RF).
RF_RADIATING = {
    ("radio", "downlink"): 0.7,
    ("sband_trx", "downlink"): 0.7,
    ("xband_tx", "downlink"): 0.5,
}
# Invented operating and survival limits of the complete-inputs example, in kelvin.
EXAMPLE_LIMITS = TemperatureLimits(
    operating_min_k=233.15, operating_max_k=343.15, survival_min_k=218.15, survival_max_k=358.15
)
# The radio is the one unit with a tighter upper limit, so the example shows a margin finding.
RADIO_LIMITS = TemperatureLimits(
    operating_min_k=233.15, operating_max_k=335.15, survival_min_k=218.15, survival_max_k=358.15
)


def _unit(
    row: UnitRow,
    geometry: Geometry | None = None,
    phases: list[str] | None = None,
    limits: TemperatureLimits | None = None,
) -> tuple[str, Unit]:
    uid, name, subsystem, mass, bus, maturity, modes = row
    return uid, Unit(
        name=name,
        subsystem=subsystem,
        mass_kg=mass,
        bus=bus,
        maturity=maturity,
        modes=[
            PowerMode(
                name=m,
                avg_power_w=a,
                peak_power_w=p,
                duty_cycle_ratio=d,
                heat_dissipation_ratio=RF_RADIATING.get((uid, m), 1.0),
            )
            for m, (a, p, d) in modes.items()
        ],
        mass_properties=_props(mass, geometry),
        phases=phases,
        temperature_limits=limits,
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
        config=_config(
            ["main"],
            _power_system(False, ["launch", "eol"], CUBESAT_POINTING),
            thermal=_thermal(units, "imaging", "safe", 0.02, False),
            link_tables=_cubesat_link_tables(False),
        ),
        links=_cubesat_links(False),
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


def _thermal(
    units: dict[str, Unit], hot_mode: str, cold_mode: str, area_m2: float, filled: bool
) -> tuple[ThermalModel, ThermalEnvironment]:
    """One node per subsystem in a chain, one radiating surface per node, a hot and a cold case.
    The design (nodes, links, areas, which mode is hot or cold) is always given; the numbers are
    placeholders unless `filled` (then invented round values, labelled as such)."""

    def n(value: float) -> Sourced:
        return _val(value) if filled else _tbd()

    names = sorted({u.subsystem for u in units.values()})
    sun = {"hot": (0.5, 0.3), "cold": (0.0, 0.8)}
    model = ThermalModel(
        nodes={name: ThermalNode(name=name) for name in names},
        conductances=[
            Conductance(first_node=a, second_node=b, conductance_wk=n(0.5))
            for a, b in zip(names[:-1], names[1:], strict=True)
        ],
        surfaces=[
            Surface(
                name=f"{name} panel",
                node=name,
                area_m2=area_m2,
                emissivity_ratio=n(0.85),
                absorptivity_ratio=n(0.6),
                exposure={
                    case: Exposure(solar_view_ratio=n(s_), earth_view_ratio=n(e_))
                    for case, (s_, e_) in sun.items()
                },
            )
            for name in names
        ],
    )
    environment = ThermalEnvironment(
        space_temperature_k=n(3.0),
        temperature_margin_k=n(5.0),
        cases={
            "cold": ThermalCase(
                description="Eclipse with the lowest-power mode.",
                spacecraft_mode=cold_mode,
                solar_flux_wm2=n(0.0),
                albedo_ratio=n(0.0),
                earth_ir_wm2=n(240.0),
            ),
            "hot": ThermalCase(
                description="Sunlight with the highest-power mode.",
                spacecraft_mode=hot_mode,
                solar_flux_wm2=n(1400.0),
                albedo_ratio=n(0.3),
                earth_ir_wm2=n(240.0),
            ),
        },
    )
    return model, environment


def _link(
    name: str,
    direction: str,
    peer: str,
    frequency_hz: float,
    rates: list[float],
    modulation: str,
    coding: str,
    points: list[StaticPoint],
    filled: bool,
    *,
    tx_w: float,
    tx_gain_dbi: float | AntennaPattern,
    g_over_t_dbk: float,
    attenuation: list[str] | None = None,
    active_modes: list[str] | None = None,
) -> Link:
    """A downlink (or uplink) of the examples. The design (band, rates, modulation, antenna type,
    static points) is always given; the numbers are placeholders unless `filled`."""

    def n(value: float) -> Sourced:
        return _val(value) if filled else _tbd()

    if isinstance(tx_gain_dbi, AntennaPattern):
        antenna = Antenna(
            pattern=tx_gain_dbi if filled else tx_gain_dbi.model_copy(update={"source": "TBD"})
        )
    else:
        antenna = Antenna(gain_dbi=n(tx_gain_dbi))
    return Link(
        name=name,
        direction=direction,  # type: ignore[arg-type]
        peer=peer,
        frequency_hz=frequency_hz,
        transmitter=Transmitter(
            power_w=n(tx_w), line_loss_db=n(0.5), antenna=antenna, polarisation="RHCP"
        ),
        receiver=Receiver(g_over_t_dbk=n(g_over_t_dbk), polarisation="RHCP"),
        modulation=modulation,
        coding=coding,
        data_rates_bps=rates,
        required_margin_db=n(3.0),
        pointing_loss_db=n(1.0),
        polarisation_loss_db=n(0.5),
        implementation_loss_db=n(1.0),
        attenuation=attenuation or [],
        active_modes=active_modes or [],
        static_points=points,
    )


UHF_POINTS = [
    StaticPoint(name="5 deg elevation", elevation_deg=5.0, range_m=2.2e6),
    StaticPoint(name="zenith", elevation_deg=90.0, range_m=5.5e5),
]


def _cubesat_links(filled: bool) -> dict[str, Link]:
    return {
        "uhf_down": _link(
            "UHF telemetry downlink",
            "downlink",
            "gs_north",
            4.35e8,
            [1200.0, 9600.0, 19200.0, 76800.0],
            "BPSK",
            "none",
            UHF_POINTS,
            filled,
            tx_w=1.0,
            tx_gain_dbi=0.0,
            g_over_t_dbk=-15.0,
            active_modes=["downlink"],
        )
    }


def _cubesat_link_tables(filled: bool) -> tuple[Ebn0Table, AttenuationTable]:
    value = _val(10.0) if filled else _tbd()
    return (
        Ebn0Table(entries=[Ebn0Entry(modulation="BPSK", coding="none", required_ebn0_db=value)]),
        AttenuationTable(),
    )


def _microsat_links() -> dict[str, Link]:
    xband_pattern = AntennaPattern(
        source=SYNTH_VALUE, angles_deg=[0.0, 30.0, 60.0], gains_dbi=[10.0, 7.0, 0.0]
    )
    return {
        "sband_down": _link(
            "S-band telemetry downlink",
            "downlink",
            "gs_north",
            2.2e9,
            [32e3, 128e3, 512e3, 2.048e6, 8.192e6],
            "QPSK",
            "rate 1/2",
            [
                StaticPoint(name="5 deg elevation", elevation_deg=5.0, range_m=2.2e6),
                StaticPoint(name="zenith", elevation_deg=90.0, range_m=5.5e5),
            ],
            True,
            tx_w=5.0,
            tx_gain_dbi=3.0,
            g_over_t_dbk=10.0,
            attenuation=["gas_s"],
            active_modes=["downlink"],
        ),
        "xband_down": _link(
            "X-band payload downlink",
            "downlink",
            "gs_south",
            8.2e9,
            [1e6, 10e6, 50e6],
            "QPSK",
            "rate 1/2",
            [
                StaticPoint(name="10 deg elevation", elevation_deg=10.0, range_m=1.6e6),
                StaticPoint(name="zenith", elevation_deg=90.0, range_m=5.5e5),
            ],
            True,
            tx_w=10.0,
            tx_gain_dbi=xband_pattern,
            g_over_t_dbk=20.0,
            attenuation=["rain_x", "gas_x"],
            active_modes=["downlink"],
        ),
    }


def _microsat_link_tables() -> tuple[Ebn0Table, AttenuationTable]:
    ebn0 = Ebn0Table(
        entries=[
            Ebn0Entry(modulation="QPSK", coding="rate 1/2", required_ebn0_db=_val(4.0)),
            Ebn0Entry(modulation="QPSK", coding="none", required_ebn0_db=_val(10.0)),
        ]
    )

    def entry(name: str, kind: str, freq: float, el: float | None, loss: float) -> AttenuationEntry:
        return AttenuationEntry(
            name=name,
            attenuation_kind=kind,  # type: ignore[arg-type]
            freq_hz=freq,
            elevation_deg=el,
            loss_db=_val(loss),
        )

    attenuation = AttenuationTable(
        entries=[
            entry("gas_s", "gas", 2.2e9, None, 0.2),
            entry("gas_x", "gas", 8.2e9, None, 0.5),
            entry("rain_x", "rain", 8.2e9, 5.0, 3.0),
            entry("rain_x", "rain", 8.2e9, 20.0, 1.0),
            entry("rain_x", "rain", 8.2e9, 90.0, 0.4),
        ]
    )
    return ebn0, attenuation


CUBESAT_POINTING: dict[str, Pointing] = {
    "downlink": "nadir",
    "imaging": "nadir",
    "nominal": "nadir",
}


def _cubesat_eps() -> Project:
    """The 3U CubeSat with complete power and thermal inputs (invented values), to show the
    time-domain and thermal budgets with results instead of n/a."""
    base = _cubesat()
    units = dict(
        _unit(
            r, CUBESAT_GEOMETRY.get(r[0]), None, RADIO_LIMITS if r[0] == "radio" else EXAMPLE_LIMITS
        )
        for r in CUBESAT_UNITS
    )
    scenario = base.scenarios["one_day"].model_copy(
        update={"name": "One day with complete power inputs", "mission_phase": "eol"}
    )
    return Project(
        root=base.root,
        meta=ProjectMeta(
            name="Example 3U CubeSat, complete power and thermal inputs",
            revision="1",
            description=SYNTHETIC
            + " Array, battery, power and thermal configuration have invented values.",
        ),
        spacecraft=base.spacecraft,
        units=units,
        modes=base.modes,
        config=_config(
            ["main"],
            _power_system(True, ["launch", "eol"], CUBESAT_POINTING),
            filled_power=True,
            thermal=_thermal(units, "imaging", "safe", 0.02, True),
            link_tables=_cubesat_link_tables(True),
        ),
        links=_cubesat_links(True),
        orbits=base.orbits,
        ground_stations=base.ground_stations,
        targets=base.targets,
        scenarios={"one_day": scenario},
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
        config=_config(
            ["main_28v", "payload_12v"],
            _power_system(False, PHASES),
            thermal=_thermal(units, "imaging", "survival", 0.3, False),
            link_tables=_microsat_link_tables(),
        ),
        links=_microsat_links(),
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
        config=_config(
            ["main", "aux"],
            _power_system(False, ["launch", "eol"]),
            thermal=_thermal(units, "imaging", "safe", 0.2, False),
        ),
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
    "cubesat_3u_eps": _cubesat_eps,
    "microsat_150kg": _microsat,
    "stress_200_units": _stress,
}


def export_examples(out_dir: Path) -> list[str]:
    """Write all example projects below `out_dir`; returns their folder names."""
    for name, build in EXAMPLES.items():
        write_project(build(), out_dir / name)
    return sorted(EXAMPLES)
