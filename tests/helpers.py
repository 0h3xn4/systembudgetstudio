"""Builders for small valid projects used across tests (invented values, source: test fixture)."""

from __future__ import annotations

from pathlib import Path

from budget_core.io.project_loader import write_project
from budget_core.model import (
    AttenuationEntry,
    AttenuationTable,
    Bus,
    Ebn0Entry,
    Ebn0Table,
    Expendable,
    MarginPolicy,
    MassLimit,
    MassLimits,
    MassProperties,
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

FIXTURE = "test fixture"


def sourced(value: float | None = 0.1, source: str = FIXTURE) -> Sourced:
    return Sourced(value=value, source=source)


def build_project(root: Path) -> Project:
    def unit(name: str, modes: list[tuple[str, float, float]]) -> Unit:
        return Unit(
            name=name,
            subsystem="TEST",
            mass_kg=0.2,
            bus="main",
            maturity="m1",
            mass_properties=MassProperties(position_m=[0.1, 0.0, 0.2]),
            modes=[PowerMode(name=n, avg_power_w=a, peak_power_w=p) for n, a, p in modes],
        )

    return Project(
        root=root,
        meta=ProjectMeta(name="Test project", revision="r1"),
        spacecraft=Spacecraft(
            name="SAT",
            buses=[Bus(name="main", nominal_voltage_v=28.0)],
            mission_phases=["launch", "eol"],
            body_frame="test frame",
        ),
        units={
            "obc": unit("OBC", [("on", 1.0, 2.0), ("off", 0.0, 0.0)]),
            "radio": unit("Radio", [("rx", 1.0, 1.5), ("tx", 5.0, 8.0)]),
        },
        modes={
            "nominal": SpacecraftMode(name="Nominal", assignments={"obc": "on", "radio": "rx"}),
            "downlink": SpacecraftMode(name="Downlink", assignments={"obc": "on", "radio": "tx"}),
        },
        expendables={
            "fuel": Expendable(
                name="Fuel",
                subsystem="PROP",
                maturity="m1",
                masses_kg={"launch": 2.0, "eol": 0.5},
                mass_properties=MassProperties(position_m=[0.0, 0.0, 0.1]),
            )
        },
        config=ProjectConfig(
            mass_limits=MassLimits(
                limits=[MassLimit(name="launch mass", phase="launch", limit_kg=sourced(100.0))]
            ),
            margin_policy=MarginPolicy(
                classes={
                    "m1": MaturityClass(
                        power_margin_ratio=sourced(0.1), mass_margin_ratio=sourced(0.1)
                    ),
                    "m2": MaturityClass(
                        power_margin_ratio=sourced(0.2), mass_margin_ratio=sourced(0.2)
                    ),
                },
                system_power_margin_ratio=sourced(0.05),
                system_mass_margin_ratio=sourced(0.05),
            ),
            power_config=PowerConfig(
                distribution_loss_ratio=sourced(0.02),
                converter_efficiency_ratio={"main": sourced(0.9)},
            ),
            ebn0_table=Ebn0Table(
                entries=[
                    Ebn0Entry(modulation="TEST-MOD", coding="none", required_ebn0_db=sourced(10.0))
                ]
            ),
            attenuation_table=AttenuationTable(
                entries=[
                    AttenuationEntry(
                        name="test", attenuation_kind="rain", freq_hz=2.2e9, loss_db=sourced(0.5)
                    )
                ]
            ),
        ),
    )


def write_valid_project(root: Path) -> Project:
    project = build_project(root)
    write_project(project, root)
    return project


def edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {rel}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def line_of(root: Path, rel: str, needle: str) -> int:
    for number, line in enumerate((root / rel).read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not found in {rel}")
