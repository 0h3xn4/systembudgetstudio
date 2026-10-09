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
    MarginPolicy,
    MaturityClass,
    PowerConfig,
    PowerMode,
    Project,
    ProjectConfig,
    ProjectMeta,
    Sourced,
    Spacecraft,
    SpacecraftMode,
    Unit,
)

SYNTHETIC = "Synthetic example data; not a real spacecraft."
CLASSES = ("class_a", "class_b", "class_c")


def _tbd() -> Sourced:
    return Sourced(value=None, source="TBD", note="Placeholder: supply the project's value.")


def _config(buses: list[str]) -> ProjectConfig:
    return ProjectConfig(
        margin_policy=MarginPolicy(
            classes={c: MaturityClass(margin_ratio=_tbd()) for c in CLASSES},
            system_margin_ratio=_tbd(),
        ),
        power_config=PowerConfig(
            distribution_loss_ratio=_tbd(),
            converter_efficiency_ratio={b: _tbd() for b in buses},
        ),
        ebn0_table=Ebn0Table(),
        attenuation_table=AttenuationTable(),
    )


# (id, name, subsystem, mass_kg, bus, maturity, {mode: (avg_w, peak_w, duty)})
UnitRow = tuple[str, str, str, float, str, str, dict[str, tuple[float, float, float]]]


def _unit(row: UnitRow) -> tuple[str, Unit]:
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


def _cubesat() -> Project:
    units = dict(_unit(r) for r in CUBESAT_UNITS)
    return Project(
        root=Path("."),
        meta=ProjectMeta(name="Example 3U CubeSat", revision="1", description=SYNTHETIC),
        spacecraft=Spacecraft(name="CubeSat 3U", buses=[Bus(name="main", nominal_voltage_v=5.0)]),
        units=units,
        modes=_mode_map(units, CUBESAT_MODES),
        config=_config(["main"]),
    )


def _microsat() -> Project:
    units = dict(_unit(r) for r in MICROSAT_UNITS)
    return Project(
        root=Path("."),
        meta=ProjectMeta(name="Example 150 kg microsatellite", revision="1", description=SYNTHETIC),
        spacecraft=Spacecraft(
            name="Microsat 150",
            buses=[
                Bus(name="main_28v", nominal_voltage_v=28.0),
                Bus(name="payload_12v", nominal_voltage_v=12.0),
            ],
        ),
        units=units,
        modes=_mode_map(units, MICROSAT_MODES),
        config=_config(["main_28v", "payload_12v"]),
    )


def _stress() -> Project:
    """200 units with deterministic, invented power values (formulas of the index only)."""
    rows: list[UnitRow] = []
    for i in range(200):
        base = 0.2 + (i % 17) * 0.15
        modes = {"off": (0.0, 0.0, 1.0)}
        for j, m in enumerate(STRESS_MODES):
            avg = round(base * (1.0 + 0.1 * ((i + j) % 5)), 3)
            modes[m] = (avg, round(avg * 1.5, 3), 1.0 if (i + j) % 3 else 0.5)
        rows.append(
            (
                f"unit_{i:03d}",
                f"Stress unit {i:03d}",
                STRESS_SUBSYSTEMS[i % len(STRESS_SUBSYSTEMS)],
                round(0.05 + (i % 11) * 0.07, 3),
                "main" if i % 4 else "aux",
                CLASSES[i % 3],
                modes,
            )
        )
    units = dict(_unit(r) for r in rows)
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
        ),
        units=units,
        modes=_mode_map(units, plan),
        config=_config(["main", "aux"]),
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
